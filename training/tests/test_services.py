"""Unit tests for Training services: CRUD, conflict detection, status workflow."""
from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from core.test_helpers import LogInHelper

from training.models import Training, TrainerProfile, TrainingStatus, AssignmentStatus, AssignmentRole
from training.services import (
    TrainingService, TrainerProfileService, TrainingAssignmentService, ConflictService,
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
        self.assertEqual(Training.objects.filter(code='T-CREATE', is_deleted=False).count(), 1)

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
