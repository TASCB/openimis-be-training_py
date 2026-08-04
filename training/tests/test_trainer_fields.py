"""TrainerProfile.gender and .position — requirement 1.

Both were missing entirely from the model, so a gender-disaggregated trainer report was
impossible in the same way the participant one was. Gender reuses the module-wide M/F
vocabulary rather than introducing a second one.
"""
import graphene
from django.test import TestCase

from core.test_helpers import LogInHelper

from training.gql_mutations import (
    CreateTrainerProfileMutation, UpdateTrainerProfileMutation,
)
from training.apps import DEFAULT_JOB_TITLES, DEFAULT_STAFF_USER_GROUPS
from training.gql_queries import TrainerProfileGQLType
from training.models import Gender, JobTitle, StaffUserGroup, TrainerProfile
from training.services import TrainerProfileService


class TrainerFieldApiTests(TestCase):
    def test_gender_and_position_are_create_input_arguments(self):
        fields = CreateTrainerProfileMutation.Input._meta.fields
        self.assertIn('gender', fields)
        self.assertIn('position_id', fields)

    def test_gender_and_position_are_update_input_arguments(self):
        fields = UpdateTrainerProfileMutation.Input._meta.fields
        self.assertIn('gender', fields)
        self.assertIn('position_id', fields)

    def test_gender_enum_matches_the_model_choices(self):
        enum = CreateTrainerProfileMutation.Input._meta.fields['gender'].type
        values = {v.value for v in enum._meta.enum}
        self.assertEqual(values, {g.value for g in Gender})

    def test_both_fields_are_filterable(self):
        filters = TrainerProfileGQLType._meta.filter_fields
        self.assertEqual(filters['gender'], ['exact', 'in', 'isnull'])
        self.assertIn('position_id', filters)
        # Grouping trainers by directorate is the point of linking title -> group.
        self.assertIn('position__user_group__code', filters)

    def test_neither_field_is_required(self):
        for name in ('gender', 'position_id'):
            self.assertNotIsInstance(
                CreateTrainerProfileMutation.Input._meta.fields[name].type,
                graphene.NonNull)


class TrainerFieldPersistenceTests(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.user = LogInHelper().get_or_create_user_api()
        cls.service = TrainerProfileService(cls.user)

    def _create(self, **extra):
        result = self.service.create({'full_name': 'Trainer Under Test', **extra})
        self.assertTrue(result.get('success'), result.get('detail'))
        return TrainerProfile.objects.get(id=result['data']['id'])

    def test_gender_and_position_persist_on_create(self):
        title = JobTitle.objects.get(code='TASAF_MONITORING_OFFICER')
        trainer = self._create(gender=Gender.FEMALE, position_id=title.id)
        self.assertEqual(trainer.gender, Gender.FEMALE)
        self.assertEqual(trainer.position_id, title.id)

    def test_both_are_optional(self):
        trainer = self._create()
        self.assertIsNone(trainer.gender)
        self.assertIsNone(trainer.position)

    def test_they_can_be_set_by_update(self):
        trainer = self._create()
        title = JobTitle.objects.get(code='INTERNAL_AUDITOR')
        result = self.service.update(
            {'id': trainer.id, 'gender': Gender.MALE, 'position_id': title.id})
        self.assertTrue(result.get('success'), result.get('detail'))
        trainer.refresh_from_db()
        self.assertEqual(trainer.gender, Gender.MALE)
        self.assertEqual(trainer.position_id, title.id)

    def test_trainers_with_no_gender_recorded_stay_queryable_as_a_bucket(self):
        # The explicit not-recorded bucket, so a report can say so instead of guessing.
        self._create(gender=Gender.MALE)
        self._create()
        self.assertTrue(TrainerProfile.objects.filter(gender__isnull=True).exists())


class JobTitleCatalogueTests(TestCase):
    """The seed is generated from the canonical RBAC catalogue, so these pin it to the
    document (``docs/pssn/Roles/USER_GROUPS_AND_ROLES_GUIDELINE.md``, Parts 2 and 5).
    A drift here means the seed and the approved catalogue disagree.
    """

    def test_all_eight_user_groups_are_seeded(self):
        self.assertEqual(StaffUserGroup.objects.filter(is_deleted=False).count(), 8)

    def test_all_63_job_titles_are_seeded(self):
        self.assertEqual(JobTitle.objects.filter(is_deleted=False).count(), 63)

    def test_group_codes_are_ug01_to_ug08(self):
        codes = sorted(StaffUserGroup.objects.values_list('code', flat=True))
        self.assertEqual(codes, [f'UG{n:02}' for n in range(1, 9)])

    def test_serial_numbers_are_1_to_63_and_unique(self):
        sns = sorted(JobTitle.objects.values_list('sn', flat=True))
        self.assertEqual(sns, list(range(1, 64)))

    def test_every_title_belongs_to_a_group(self):
        self.assertFalse(JobTitle.objects.filter(user_group__isnull=True).exists())

    def test_per_group_title_counts_match_the_catalogue(self):
        # Part 2 declares the count each group covers; Part 5 lists them individually.
        expected = {'UG01': 15, 'UG02': 3, 'UG03': 7, 'UG04': 8,
                    'UG05': 12, 'UG06': 5, 'UG07': 10, 'UG08': 3}
        actual = {g.code: g.job_titles.count() for g in StaffUserGroup.objects.all()}
        self.assertEqual(actual, expected)

    def test_tmo_resolves_to_its_full_title(self):
        # The acronym the client's level spec used, expanded via the catalogue at SN 62.
        title = JobTitle.objects.get(sn=62)
        self.assertEqual(title.name, 'TASAF Monitoring Officer')
        self.assertEqual(title.user_group.code, 'UG08')

    def test_codes_are_unique(self):
        codes = list(JobTitle.objects.values_list('code', flat=True))
        self.assertEqual(len(codes), len(set(codes)))

    def test_seed_constants_match_what_was_stored(self):
        self.assertEqual(len(DEFAULT_STAFF_USER_GROUPS), 8)
        self.assertEqual(len(DEFAULT_JOB_TITLES), 63)
        stored = dict(JobTitle.objects.values_list('code', 'name'))
        for _sn, code, name, _group in DEFAULT_JOB_TITLES:
            self.assertEqual(stored.get(code), name)
