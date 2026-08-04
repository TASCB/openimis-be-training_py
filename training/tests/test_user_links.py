"""Existing system users can stand in for trainers and trainees.

The FKs and mutation arguments were always there; what was missing was any way to set
them from the UI. These tests pin the backend contract the pickers now rely on —
above all that an assignment is valid with a staff user and no trainer profile.
"""
from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from core.test_helpers import LogInHelper

from training.models import (
    AssignmentRole, AssignmentStatus, Gender, TrainerProfile,
    TrainingAssignment, TrainingParticipant,
)
from training.services import (
    TrainingService, TrainerProfileService, TrainingAssignmentService,
    TrainingParticipantService,
)


class UserLinkTests(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.user = LogInHelper().get_or_create_user_api()
        start = timezone.now() + timedelta(days=4)
        cls.training_id = TrainingService(cls.user).create({
            'title': 'User links', 'start_datetime': start,
            'end_datetime': start + timedelta(hours=2), 'venue': 'Venue USERS',
        })['data']['id']

    # -- assignments ---------------------------------------------------------
    def _assign(self, **over):
        data = {'training_id': self.training_id, 'role': AssignmentRole.FACILITATOR,
                'status': AssignmentStatus.ASSIGNED}
        data.update(over)
        return TrainingAssignmentService(self.user).create(data)

    def test_assignment_accepts_a_staff_user_without_a_trainer_profile(self):
        res = self._assign(staff_user_id=self.user.id)
        self.assertTrue(res.get('success'), res.get('detail'))
        assignment = TrainingAssignment.objects.get(id=res['data']['id'])
        self.assertEqual(assignment.staff_user_id, self.user.id)
        self.assertIsNone(assignment.trainer_id)

    def test_assignment_accepts_a_trainer_profile_without_a_staff_user(self):
        trainer_id = TrainerProfileService(self.user).create(
            {'full_name': 'Standalone Trainer'})['data']['id']
        res = self._assign(trainer_id=trainer_id)
        self.assertTrue(res.get('success'), res.get('detail'))
        assignment = TrainingAssignment.objects.get(id=res['data']['id'])
        self.assertEqual(str(assignment.trainer_id), str(trainer_id))
        self.assertIsNone(assignment.staff_user_id)

    def test_assignment_with_neither_is_rejected(self):
        # The panel's add button mirrors this rule by staying disabled.
        self.assertFalse(self._assign().get('success'))

    # -- trainer profile -----------------------------------------------------
    def test_trainer_profile_links_to_a_system_account(self):
        res = TrainerProfileService(self.user).create(
            {'full_name': 'Internal Trainer', 'staff_user_id': self.user.id})
        self.assertTrue(res.get('success'), res.get('detail'))
        self.assertEqual(TrainerProfile.objects.get(id=res['data']['id']).staff_user_id,
                         self.user.id)

    # -- session register ----------------------------------------------------
    def test_participant_can_be_added_straight_to_a_session_register(self):
        """Only QR check-in could attach a participant to a session; manual entries were
        always whole-training rows, which left the per-session report with nothing."""
        from training.gql_mutations import CreateTrainingParticipantMutation
        from training.models import TrainingSession
        from training.services import TrainingSessionService

        self.assertIn('session_id', CreateTrainingParticipantMutation.Input._meta.fields)

        session_id = TrainingSessionService(self.user).create({
            'training_id': self.training_id, 'title': 'Day 1', 'sequence': 1,
        })['data']['id']
        res = TrainingParticipantService(self.user).create({
            'training_id': self.training_id, 'session_id': session_id,
            'full_name': 'Day One Attendee', 'gender': Gender.MALE,
        })
        self.assertTrue(res.get('success'), res.get('detail'))
        participant = TrainingParticipant.objects.get(id=res['data']['id'])
        self.assertEqual(str(participant.session_id), str(session_id))
        self.assertEqual(TrainingSession.objects.get(id=session_id).participants.count(), 1)

    def test_participant_without_a_session_is_a_whole_training_entry(self):
        res = TrainingParticipantService(self.user).create({
            'training_id': self.training_id, 'full_name': 'Whole Training Attendee'})
        self.assertTrue(res.get('success'), res.get('detail'))
        self.assertIsNone(TrainingParticipant.objects.get(id=res['data']['id']).session_id)

    # -- participant ---------------------------------------------------------
    def test_participant_links_to_a_system_account(self):
        res = TrainingParticipantService(self.user).create({
            'training_id': self.training_id, 'full_name': 'Staff Attendee',
            'gender': Gender.FEMALE, 'internal_user_id': self.user.id,
        })
        self.assertTrue(res.get('success'), res.get('detail'))
        self.assertEqual(TrainingParticipant.objects.get(id=res['data']['id']).internal_user_id,
                         self.user.id)
