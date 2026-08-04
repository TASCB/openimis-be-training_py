"""ParticipantCategory — the configurable replacement for the ParticipantType enum.

The 24 categories were reconciled from three inconsistent lists in the client brief
(requirement 6's 19, requirement 10's level hierarchy, requirement 11's statistics table).
These tests pin the reconciliation itself, because the seeded ``code`` is the stable key
participant rows and reports join on: changing one later means a data migration.
"""
from importlib import import_module

import graphene
from django.test import TestCase

from core.test_helpers import LogInHelper

from training.apps import DEFAULT_PARTICIPANT_CATEGORIES
from training.gql_mutations import (
    CreateParticipantCategoryMutation, UpdateParticipantCategoryMutation,
)
from training.gql_queries import ParticipantCategoryGQLType
from training.models import ParticipantCategory
from training.schema import Query
from training.services import ParticipantCategoryService


class _Ctx:
    def __init__(self, user):
        self.user = user
        self.headers = {}


class ParticipantCategorySeedTests(TestCase):
    """post_migrate seeds these, so they are present without the test creating them."""

    def test_all_24_categories_are_seeded(self):
        self.assertEqual(ParticipantCategory.objects.filter(is_deleted=False).count(), 24)

    def test_seed_matches_the_reconciled_list(self):
        seeded = dict(ParticipantCategory.objects.filter(is_deleted=False)
                      .values_list('code', 'name'))
        for code, name, _sequence in DEFAULT_PARTICIPANT_CATEGORIES:
            self.assertIn(code, seeded)
            self.assertEqual(seeded[code], name)

    def test_requirement_6_categories_are_all_present(self):
        # The 19 from the brief, by the code each was assigned.
        required = [
            'TMU_HQ_STAFF', 'MP', 'RC', 'RS', 'DC', 'DAS', 'DED', 'WARD_COUNCILLOR', 'CMT',
            'PSSNC', 'PSSNA', 'PAAF', 'WEO', 'VC', 'SHEHA', 'VEO',
            'VILLAGE_COUNCIL_MEMBER', 'CMC', 'COMMUNITY_MEMBER',
        ]
        self.assertEqual(len(required), 19)
        seeded = set(ParticipantCategory.objects.values_list('code', flat=True))
        self.assertEqual([c for c in required if c not in seeded], [])

    def test_additions_from_requirements_10_and_11_are_present(self):
        # Requirement 10 contributed the Regional Security Committee; requirement 11's
        # statistics table contributed the urban counterparts of VEO / Village Council Member.
        for code in ('REGIONAL_SECURITY_COMMITTEE', 'MEO', 'MITAA_COMMITTEE_LEADER'):
            self.assertTrue(ParticipantCategory.objects.filter(code=code).exists(), code)

    def test_councillors_was_merged_not_duplicated(self):
        # Requirement 11 says "Councillors", requirement 6 says "Ward Councillors" — one role.
        self.assertEqual(ParticipantCategory.objects.filter(
            name__icontains='councillor', is_deleted=False).count(), 1)

    def test_other_catch_all_exists_and_sorts_last(self):
        # Without it an unlisted attendee gets forced into a wrong category, which would
        # quietly corrupt the gender statistics.
        other = ParticipantCategory.objects.get(code='OTHER')
        self.assertEqual(
            other.sequence,
            max(ParticipantCategory.objects.values_list('sequence', flat=True)))

    def test_codes_are_unique(self):
        codes = list(ParticipantCategory.objects.values_list('code', flat=True))
        self.assertEqual(len(codes), len(set(codes)))

    def test_sequence_orders_the_governance_ladder(self):
        ordered = list(ParticipantCategory.objects.filter(is_deleted=False)
                       .order_by('sequence').values_list('code', flat=True))
        self.assertEqual(ordered[0], 'TMU_HQ_STAFF')          # national
        self.assertLess(ordered.index('RC'), ordered.index('DC'))       # region before district
        self.assertLess(ordered.index('DC'), ordered.index('WEO'))      # district before ward
        self.assertLess(ordered.index('WEO'), ordered.index('VEO'))     # ward before village
        self.assertLess(ordered.index('VEO'), ordered.index('COMMUNITY_MEMBER'))
        self.assertEqual(ordered[-1], 'OTHER')

    def test_seeding_is_idempotent_and_does_not_reset_local_edits(self):
        from training.apps import _seed_participant_categories
        from django.apps import apps as django_apps

        category = ParticipantCategory.objects.get(code='OTHER')
        ParticipantCategory.objects.filter(pk=category.pk).update(
            name='Other (renamed locally)', is_active=False)

        _seed_participant_categories(django_apps)

        self.assertEqual(ParticipantCategory.objects.filter(is_deleted=False).count(), 24)
        category.refresh_from_db()
        self.assertEqual(category.name, 'Other (renamed locally)')
        self.assertFalse(category.is_active)


class ParticipantCategoryCrudTests(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.user = LogInHelper().get_or_create_user_api()
        cls.service = ParticipantCategoryService(cls.user)

    def test_create_update_delete(self):
        created = self.service.create(
            {'code': 'TEST_CAT', 'name': 'Test Category', 'sequence': 500})
        self.assertTrue(created.get('success'), created.get('detail'))
        category_id = created['data']['id']

        updated = self.service.update({'id': category_id, 'name': 'Renamed'})
        self.assertTrue(updated.get('success'), updated.get('detail'))
        self.assertEqual(ParticipantCategory.objects.get(id=category_id).name, 'Renamed')

        self.service.delete({'id': category_id})
        self.assertFalse(ParticipantCategory.objects.filter(
            id=category_id, is_deleted=False).exists())

    def test_duplicate_code_is_rejected(self):
        self.assertFalse(self.service.create(
            {'code': 'WEO', 'name': 'Duplicate ward officer'}).get('success'))

    def test_a_category_can_be_retired_without_deleting_it(self):
        # is_active is how a category leaves the picker while its historical rows survive.
        created = self.service.create({'code': 'RETIRE_ME', 'name': 'Retire me'})
        category_id = created['data']['id']
        self.assertTrue(self.service.update(
            {'id': category_id, 'is_active': False}).get('success'))
        category = ParticipantCategory.objects.get(id=category_id)
        self.assertFalse(category.is_active)
        self.assertFalse(category.is_deleted)

    def test_a_retired_category_can_be_reactivated(self):
        created = self.service.create({'code': 'REACTIVATE_ME', 'name': 'Reactivate me'})
        category_id = created['data']['id']
        self.service.update({'id': category_id, 'is_active': False})
        self.service.update({'id': category_id, 'is_active': True})
        self.assertTrue(ParticipantCategory.objects.get(id=category_id).is_active)


class FalsyDefaultFixTests(TestCase):
    """Regression guard for a core openIMIS bug, not a training-module one.

    ``core.validation.base.validator`` is a global pre_save receiver that resets any field
    declaring a model default back to that default whenever the incoming value is FALSY —
    it tests ``not attr`` instead of ``attr is None``. Every
    ``BooleanField(default=True)`` is therefore impossible to turn off through a normal
    save, which silently broke deactivating trainers and programme areas long before
    ParticipantCategory existed. services._FalsyDefaultFixMixin re-applies the value after
    the save; these tests fail if that mixin is dropped or if core is ever fixed upstream
    in a way that changes the behaviour.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.user = LogInHelper().get_or_create_user_api()

    def test_trainer_profile_can_be_deactivated(self):
        from training.models import TrainerProfile
        from training.services import TrainerProfileService

        service = TrainerProfileService(self.user)
        trainer_id = service.create({'full_name': 'Retiring Trainer'})['data']['id']
        self.assertTrue(service.update({'id': trainer_id, 'is_active': False}).get('success'))
        self.assertFalse(TrainerProfile.objects.get(id=trainer_id).is_active)

    def test_training_category_can_be_deactivated(self):
        from training.models import TrainingCategory
        from training.services import TrainingCategoryService

        service = TrainingCategoryService(self.user)
        category_id = service.create(
            {'code': 'RETIRE_AREA', 'name': 'Retiring area'})['data']['id']
        self.assertTrue(service.update({'id': category_id, 'is_active': False}).get('success'))
        self.assertFalse(TrainingCategory.objects.get(id=category_id).is_active)

    def test_the_service_result_reports_the_value_that_was_actually_stored(self):
        service = ParticipantCategoryService(self.user)
        category_id = service.create({'code': 'RESULT_CHECK', 'name': 'Result check'})['data']['id']
        result = service.update({'id': category_id, 'is_active': False})
        self.assertFalse(result['data']['is_active'])
        self.assertEqual(result['data']['is_active'],
                         ParticipantCategory.objects.get(id=category_id).is_active)


class ParticipantCategoryApiTests(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.user = LogInHelper().get_or_create_user_api()
        cls.schema = graphene.Schema(query=Query)

    def test_mutation_inputs_exist(self):
        self.assertIn('code', CreateParticipantCategoryMutation.Input._meta.fields)
        self.assertIn('sequence', CreateParticipantCategoryMutation.Input._meta.fields)
        self.assertIn('id', UpdateParticipantCategoryMutation.Input._meta.fields)

    def test_code_is_optional_on_update_so_a_rename_does_not_resend_it(self):
        self.assertNotIsInstance(
            UpdateParticipantCategoryMutation.Input._meta.fields['code'].type,
            graphene.NonNull)

    def test_is_filterable_by_active_and_code(self):
        for field in ('is_active', 'code', 'sequence'):
            self.assertIn(field, ParticipantCategoryGQLType._meta.filter_fields)

    def test_query_returns_the_seeded_categories_in_sequence(self):
        res = self.schema.execute(
            'query { participantCategory(orderBy: "sequence", first: 30) '
            '{ edges { node { code name sequence } } } }',
            context_value=_Ctx(self.user))
        self.assertIsNone(res.errors, msg=res.errors)
        codes = [e['node']['code'] for e in res.data['participantCategory']['edges']]
        self.assertEqual(len(codes), 24)
        self.assertEqual(codes[0], 'TMU_HQ_STAFF')
        self.assertEqual(codes[-1], 'OTHER')


class ParticipantTypeMigrationTests(TestCase):
    """The 0009 mapping off the retired ParticipantType enum.

    The mapping is deliberately partial — the old enum mixed governance positions with
    operational roles, and only two values have an honest counterpart on the ladder. What
    must not happen is a typo'd target code, which would silently drop rows onto NULL and
    look identical to a deliberate non-mapping.
    """

    OLD_ENUM_VALUES = {
        'TASAF_STAFF', 'PAA_REP', 'CMC_MEMBER', 'LGA_OFFICER', 'ENUMERATOR',
        'SUPERVISOR', 'COMMUNITY_FACILITATOR', 'TRAINER', 'OTHER',
    }

    def setUp(self):
        # The module name starts with a digit, so it cannot be imported by name.
        migration = import_module('training.migrations.0009_participant_category_fk')
        self.mapping = migration.PARTICIPANT_TYPE_TO_CATEGORY

    def test_every_old_enum_value_is_accounted_for(self):
        self.assertEqual(set(self.mapping), self.OLD_ENUM_VALUES)

    def test_mapped_targets_all_exist_in_the_seeded_vocabulary(self):
        targets = {code for code in self.mapping.values() if code}
        seeded = set(ParticipantCategory.objects.values_list('code', flat=True))
        self.assertTrue(targets <= seeded, msg=f'unknown codes: {targets - seeded}')

    def test_the_two_clean_maps_are_the_ones_documented(self):
        mapped = {old: new for old, new in self.mapping.items() if new}
        self.assertEqual(mapped, {'TASAF_STAFF': 'TMU_HQ_STAFF', 'CMC_MEMBER': 'CMC'})

    def test_operational_roles_are_left_uncategorised_not_swept_into_other(self):
        for value in ('ENUMERATOR', 'SUPERVISOR', 'COMMUNITY_FACILITATOR', 'TRAINER'):
            self.assertIsNone(self.mapping[value])
