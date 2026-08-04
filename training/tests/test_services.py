"""Unit tests for Training services: CRUD, conflict detection, status workflow."""
from datetime import datetime, time, timedelta
from types import SimpleNamespace

from django.test import SimpleTestCase, TestCase
from django.utils import timezone

from core.test_helpers import LogInHelper

from training.models import (
    Training, TrainingSession, TrainingStatus, AssignmentStatus, AssignmentRole,
)
from training.services import (
    TrainingService, TrainerProfileService, TrainingAssignmentService, ConflictService,
    TrainingSessionService, checkin_open, _local_now, resolve_paa_reference,
)


class TrainingServiceTests(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.user = LogInHelper().get_or_create_user_api()
        cls.service = TrainingService(cls.user)
        cls.start = timezone.now() + timedelta(days=1)
        cls.end = cls.start + timedelta(hours=3)

    def _payload(self, code, **over):
        data = {
            'code': code, 'title': f'Training {code}',
            'start_datetime': self.start, 'end_datetime': self.end,
            'venue': 'TASAF HQ Room 2', 'status': TrainingStatus.DRAFT,
        }
        data.update(over)
        return data

    def test_create_training(self):
        res = self.service.create(self._payload('T-CREATE'))
        self.assertTrue(res.get('success'), res.get('detail'))
        training = Training.objects.get(id=res['data']['id'])
        self.assertEqual(training.title, 'Training T-CREATE')
        # codes are server-assigned from the sequence, the payload code is ignored
        self.assertTrue(training.code.startswith('TRN'))

    def test_soft_delete(self):
        res = self.service.create(self._payload('T-DEL'))
        tid = res['data']['id']
        self.service.delete({'id': tid})
        self.assertEqual(Training.objects.filter(id=tid, is_deleted=False).count(), 0)
        self.assertEqual(Training.objects.filter(id=tid, is_deleted=True).count(), 1)

    def test_invalid_transition_is_rejected(self):
        res = self.service.create(self._payload('T-FSM'))
        tid = res['data']['id']
        # DRAFT -> approve is illegal (must submit first)
        out = self.service.transition(tid, 'approve')
        self.assertFalse(out.get('success'))

    def test_valid_transition_chain(self):
        res = self.service.create(self._payload('T-FSM2'))
        tid = res['data']['id']
        self.assertTrue(self.service.transition(tid, 'submit')['success'])
        self.assertTrue(self.service.transition(tid, 'approve')['success'])
        self.assertTrue(self.service.transition(tid, 'schedule')['success'])
        self.assertEqual(Training.objects.get(id=tid).status, TrainingStatus.SCHEDULED)

    def _scheduled(self, code, **over):
        tid = self.service.create(self._payload(code, **over))['data']['id']
        for action in ('submit', 'approve', 'schedule'):
            self.service.transition(tid, action)
        return tid

    def test_reschedule_moves_window_and_logs(self):
        tid = self._scheduled('T-RSC', venue='Room RSC')
        new_start = self.start + timedelta(days=7)
        new_end = new_start + timedelta(hours=3)
        out = self.service.reschedule(tid, new_start, new_end, reason='Trainer unavailable')
        self.assertTrue(out.get('success'), out.get('detail'))

        training = Training.objects.get(id=tid)
        self.assertEqual(training.status, TrainingStatus.SCHEDULED)
        self.assertEqual(training.start_datetime, new_start)
        self.assertEqual(training.end_datetime, new_end)
        log = training.json_ext['reschedule_log']
        self.assertEqual(len(log), 1)
        self.assertEqual(log[0]['reason'], 'Trainer unavailable')
        self.assertEqual(log[0]['by'], self.user.username)
        self.assertEqual(log[0]['to_start'], new_start.isoformat())

    def test_reschedule_rejected_from_draft(self):
        tid = self.service.create(self._payload('T-RSC-DRAFT'))['data']['id']
        out = self.service.reschedule(tid, self.start + timedelta(days=3),
                                      self.start + timedelta(days=3, hours=2))
        self.assertFalse(out.get('success'))
        self.assertEqual(Training.objects.get(id=tid).start_datetime, self.start)

    def test_reschedule_rejects_inverted_window(self):
        tid = self._scheduled('T-RSC-BAD', venue='Room BAD')
        out = self.service.reschedule(tid, self.end, self.start)
        self.assertFalse(out.get('success'))

    def test_reschedule_shifts_sessions_and_keeps_gaps(self):
        tid = self._scheduled('T-RSC-SESS', venue='Room SESS',
                              end_datetime=self.start + timedelta(days=4))
        session_service = TrainingSessionService(self.user)
        # Day 1 and Day 3 — a deliberate one-day gap that must survive the move.
        for seq, offset in ((1, 0), (2, 2)):
            session_service.create({
                'training_id': tid, 'title': f'Day {seq}', 'sequence': seq,
                'session_date': (self.start + timedelta(days=offset)).date(),
                'registration_opens_at': self.start + timedelta(days=offset),
            })
        undated = session_service.create({
            'training_id': tid, 'title': 'Unscheduled', 'sequence': 3})['data']['id']

        new_start = self.start + timedelta(days=10)
        out = self.service.reschedule(tid, new_start, new_start + timedelta(days=4))
        self.assertTrue(out.get('success'), out.get('detail'))

        dates = list(TrainingSession.objects
                     .filter(training_id=tid, is_deleted=False, session_date__isnull=False)
                     .order_by('sequence').values_list('session_date', flat=True))
        self.assertEqual(dates, [new_start.date(), (new_start + timedelta(days=2)).date()])
        # QR registration window travels with its session
        opens = TrainingSession.objects.get(training_id=tid, sequence=1).registration_opens_at
        self.assertEqual(opens.date(), new_start.date())
        # undated session untouched
        self.assertIsNone(TrainingSession.objects.get(id=undated).session_date)

        entry = Training.objects.get(id=tid).json_ext['reschedule_log'][-1]
        self.assertEqual(entry['sessions_shifted'], 2)
        self.assertEqual(entry['sessions_outside_window'], 0)

    def test_reschedule_flags_sessions_left_outside_shorter_window(self):
        tid = self._scheduled('T-RSC-SHRINK', venue='Room SHRINK',
                              end_datetime=self.start + timedelta(days=3))
        session_service = TrainingSessionService(self.user)
        for seq, offset in ((1, 0), (2, 3)):
            session_service.create({
                'training_id': tid, 'title': f'Day {seq}', 'sequence': seq,
                'session_date': (self.start + timedelta(days=offset)).date(),
            })

        # same start, window shortened from 3 days to 1 — Day 2 no longer fits
        out = self.service.reschedule(tid, self.start, self.start + timedelta(hours=4))
        self.assertTrue(out.get('success'), out.get('detail'))
        entry = Training.objects.get(id=tid).json_ext['reschedule_log'][-1]
        self.assertEqual(entry['sessions_shifted'], 0)
        self.assertEqual(entry['sessions_outside_window'], 1)

    def test_reschedule_blocked_by_hard_conflict(self):
        # an existing training occupies the venue in the target window
        blocker_start = self.start + timedelta(days=14)
        self.service.create(self._payload(
            'T-RSC-BLOCKER', venue='Shared Hall',
            start_datetime=blocker_start, end_datetime=blocker_start + timedelta(hours=3)))
        tid = self._scheduled('T-RSC-MOVER', venue='Shared Hall')

        out = self.service.reschedule(tid, blocker_start, blocker_start + timedelta(hours=2))
        self.assertFalse(out.get('success'))
        # window must be untouched after a blocked reschedule
        self.assertEqual(Training.objects.get(id=tid).start_datetime, self.start)

    def test_trainer_conflict_detected(self):
        # trainer assigned to first training, overlapping second
        t1 = self.service.create(self._payload('T-CONF1'))['data']['id']
        trainer = TrainerProfileService(self.user).create(
            {'code': 'TR-1', 'full_name': 'John Doe'})['data']['id']
        TrainingAssignmentService(self.user).create({
            'training_id': t1, 'trainer_id': trainer,
            'role': AssignmentRole.LEAD_TRAINER, 'status': AssignmentStatus.ASSIGNED,
        })
        conflicts = ConflictService(self.user).check(
            start=self.start, end=self.end, venue='Other venue',
            trainer_ids=[trainer])
        trainer_conflicts = [c for c in conflicts if c['type'] == 'TRAINER']
        self.assertTrue(trainer_conflicts)
        self.assertTrue(trainer_conflicts[0]['hard'])

    def test_venue_conflict_detected(self):
        self.service.create(self._payload('T-VEN1'))
        conflicts = ConflictService(self.user).check(
            start=self.start, end=self.end, venue='TASAF HQ Room 2')
        venue_conflicts = [c for c in conflicts if c['type'] == 'VENUE']
        self.assertTrue(venue_conflicts)
        self.assertTrue(venue_conflicts[0]['hard'])


class CheckinOpenTests(SimpleTestCase):
    """``checkin_open`` is pure attribute logic — no DB needed."""

    def _session(self, **over):
        data = {
            'registration_open': False, 'registration_opens_at': None,
            'registration_closes_at': None, 'session_date': None,
            'start_time': None, 'end_time': None,
        }
        data.update(over)
        return SimpleNamespace(**data)

    def test_switch_opens_regardless_of_date(self):
        self.assertTrue(checkin_open(self._session(registration_open=True)))

    def test_undated_session_stays_closed(self):
        self.assertFalse(checkin_open(self._session()))

    def test_auto_opens_on_the_session_day(self):
        today = _local_now().date()
        self.assertTrue(checkin_open(self._session(session_date=today)))
        self.assertFalse(checkin_open(self._session(session_date=today - timedelta(days=1))))
        self.assertFalse(checkin_open(self._session(session_date=today + timedelta(days=1))))

    def test_auto_open_respects_session_times_and_grace(self):
        now = _local_now()
        long_over = self._session(session_date=now.date(), start_time=time(0, 1),
                                  end_time=(now - timedelta(hours=5)).time())
        just_over = self._session(session_date=now.date(), start_time=time(0, 1),
                                  end_time=(now - timedelta(minutes=30)).time())
        self.assertFalse(checkin_open(long_over))
        self.assertTrue(checkin_open(just_over))  # within checkin_open_minutes_after

    def test_explicit_window_disables_the_fallback_and_force_closes(self):
        past = datetime.now() - timedelta(days=1)
        today = _local_now().date()
        self.assertFalse(checkin_open(self._session(session_date=today, registration_closes_at=past)))
        self.assertFalse(checkin_open(self._session(
            session_date=today, registration_open=True, registration_closes_at=past)))


class ResolvePaaReferenceTests(SimpleTestCase):
    """PAA = the district, except Zanzibar (api_etl's UNGUJA/PEMBA scopes)."""

    def _loc(self, type_, code, name, parent=None):
        return SimpleNamespace(type=type_, code=code, name=name, parent=parent)

    def test_mainland_district_is_its_own_paa(self):
        district = self._loc('D', '2205', 'Ludewa', self._loc('R', '22', 'Njombe'))
        self.assertEqual(resolve_paa_reference(district), 'Ludewa')

    def test_zanzibar_districts_roll_up_to_island_scope(self):
        pemba = self._loc('D', '5402', 'Micheweni', self._loc('R', '54', 'Kaskazini Pemba'))
        unguja = self._loc('D', '5101', 'Kaskazini A', self._loc('R', '51', 'Kaskazini Unguja'))
        self.assertEqual(resolve_paa_reference(pemba), 'PEMBA')
        self.assertEqual(resolve_paa_reference(unguja), 'UNGUJA')

    def test_ward_and_village_resolve_through_their_district(self):
        district = self._loc('D', '5402', 'Micheweni', self._loc('R', '54', 'Kaskazini Pemba'))
        ward = self._loc('W', '540201', 'Konde', district)
        village = self._loc('V', '54020101', 'Kinyasini', ward)
        self.assertEqual(resolve_paa_reference(ward), 'PEMBA')
        self.assertEqual(resolve_paa_reference(village), 'PEMBA')

    def test_region_only_has_no_paa(self):
        self.assertIsNone(resolve_paa_reference(self._loc('R', '22', 'Njombe')))
        self.assertIsNone(resolve_paa_reference(None))

    def test_zanzibar_region_alone_already_names_the_paa(self):
        # A Zanzibar region determines the island scope before a district is picked, which is what
        # lets the form show "PEMBA" as soon as the region is chosen.
        self.assertEqual(resolve_paa_reference(self._loc('R', '54', 'Kaskazini Pemba')), 'PEMBA')
        self.assertEqual(resolve_paa_reference(self._loc('R', '51', 'Kaskazini Unguja')), 'UNGUJA')
