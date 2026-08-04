"""Participant gender must be reachable through the GraphQL API.

The column has always existed on the model but was only ever written by the public
QR check-in endpoint, so manually registered participants were silently stuck at
NULL and every gender-disaggregated report under-counted.  These tests pin the
three surfaces that were missing: the mutation input, the query filter, and the
service round-trip.
"""
from datetime import timedelta

import graphene
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.utils import timezone
from graphql_relay import to_global_id

from core.test_helpers import LogInHelper
from location.models import Location

from training.gql_mutations import (
    CreateTrainingParticipantMutation, UpdateTrainingParticipantMutation, GenderEnum,
)
from training.gql_queries import TrainingParticipantGQLType
from training.models import Gender, TrainingParticipant
from training.schema import Query
from training.services import TrainingService, TrainingParticipantService


class ParticipantGenderApiSurfaceTests(TestCase):
    """Guards against the field silently disappearing from the API again."""

    def test_gender_is_a_create_input_argument(self):
        self.assertIn('gender', CreateTrainingParticipantMutation.Input._meta.fields)

    def test_gender_is_an_update_input_argument(self):
        self.assertIn('gender', UpdateTrainingParticipantMutation.Input._meta.fields)

    def test_gender_enum_matches_the_model_choices(self):
        self.assertEqual(
            sorted(GenderEnum._meta.enum.__members__.keys()),
            sorted(c.value for c in Gender),
        )

    def test_gender_is_filterable(self):
        self.assertIn('gender', TrainingParticipantGQLType._meta.filter_fields)

    def test_update_accepts_a_partial_row(self):
        # The panel edits one cell at a time; requiring full_name here rejected every
        # such mutation, which is what silently broke the attendance dropdown too.
        # graphene marks a required input by wrapping its type in NonNull.
        for field in ('full_name', 'training_id'):
            with self.subTest(field=field):
                self.assertNotIsInstance(
                    UpdateTrainingParticipantMutation.Input._meta.fields[field].type,
                    graphene.NonNull,
                    f'{field} must be optional on update for partial edits to validate',
                )


class ParticipantGenderServiceTests(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.user = LogInHelper().get_or_create_user_api()
        start = timezone.now() + timedelta(days=1)
        cls.training_id = TrainingService(cls.user).create({
            'title': 'Gender round-trip', 'start_datetime': start,
            'end_datetime': start + timedelta(hours=2), 'venue': 'Venue GENDER',
        })['data']['id']
        cls.service = TrainingParticipantService(cls.user)

    def _create(self, full_name, **over):
        data = {'training_id': self.training_id, 'full_name': full_name}
        data.update(over)
        res = self.service.create(data)
        self.assertTrue(res.get('success'), res.get('detail'))
        return res['data']['id']

    def test_gender_persists_on_create(self):
        pid = self._create('Asha Female', gender=Gender.FEMALE)
        self.assertEqual(TrainingParticipant.objects.get(id=pid).gender, 'F')

    def test_gender_is_optional(self):
        pid = self._create('No Gender Given')
        self.assertIsNone(TrainingParticipant.objects.get(id=pid).gender)

    def test_gender_can_be_set_by_update(self):
        pid = self._create('Later Filled In')
        res = self.service.update({'id': pid, 'gender': Gender.MALE})
        self.assertTrue(res.get('success'), res.get('detail'))
        self.assertEqual(TrainingParticipant.objects.get(id=pid).gender, 'M')

    def test_partial_update_leaves_the_rest_of_the_row_alone(self):
        # Backfilling gender on a historical row must not wipe the fields it omits.
        pid = self._create('Keep My Details', phone='0700000001', organization='TASAF HQ')
        self.assertTrue(self.service.update({'id': pid, 'gender': Gender.FEMALE}).get('success'))
        participant = TrainingParticipant.objects.get(id=pid)
        self.assertEqual(participant.gender, 'F')
        self.assertEqual(participant.full_name, 'Keep My Details')
        self.assertEqual(participant.phone, '0700000001')
        self.assertEqual(participant.organization, 'TASAF HQ')


class _Ctx:
    """Minimal request context: a permitted user, plus the headers the
    connection field reads while resolving."""

    def __init__(self, user):
        self.user = user
        self.headers = {}


class ParticipantGenderQueryTests(TestCase):
    """The filter has to actually narrow the result set, not just exist."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.user = LogInHelper().get_or_create_user_api()
        cls.schema = graphene.Schema(query=Query)
        start = timezone.now() + timedelta(days=2)
        cls.training_id = TrainingService(cls.user).create({
            'title': 'Gender filter', 'start_datetime': start,
            'end_datetime': start + timedelta(hours=2), 'venue': 'Venue FILTER',
        })['data']['id']
        service = TrainingParticipantService(cls.user)
        for name, gender in (('Female One', Gender.FEMALE), ('Female Two', Gender.FEMALE),
                             ('Male One', Gender.MALE), ('Unrecorded', None)):
            service.create({'training_id': cls.training_id,
                            'full_name': name, 'gender': gender})

    def _names(self, gender_arg):
        # FK filters take a relay global id, matching what the frontend sends via encId().
        training_gid = to_global_id('TrainingGQLType', self.training_id)
        res = self.schema.execute(
            'query { trainingParticipant(trainingId: "%s", %s) { edges { node { fullName gender } } } }'
            % (training_gid, gender_arg),
            context_value=_Ctx(self.user),
        )
        self.assertIsNone(res.errors, msg=res.errors)
        return {e['node']['fullName'] for e in res.data['trainingParticipant']['edges']}

    # graphene_django types the filter from the model choices, so the argument is a
    # TrainingParticipantGender enum literal (unquoted M/F/O) — not a string.
    def test_gender_is_returned_on_the_node(self):
        self.assertEqual(self._names('gender: F'), {'Female One', 'Female Two'})

    def test_filter_by_single_gender(self):
        self.assertEqual(self._names('gender: M'), {'Male One'})

    def test_filter_by_gender_list(self):
        self.assertEqual(self._names('gender_In: [M, F]'),
                         {'Female One', 'Female Two', 'Male One'})

    def test_filter_isolates_participants_with_no_gender_recorded(self):
        # Historical rows cannot be backfilled, so reports need this bucket explicitly.
        self.assertEqual(self._names('gender_Isnull: true'), {'Unrecorded'})


class ParticipantPaaReferenceTests(TestCase):
    """A participant reports at district level, or island scope in Zanzibar, however
    deep the stored location happens to be."""

    ZANZIBAR_REGION = r'^5[1-5]$'

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.user = LogInHelper().get_or_create_user_api()
        cls.schema = graphene.Schema(query=Query)
        start = timezone.now() + timedelta(days=3)
        cls.training_id = TrainingService(cls.user).create({
            'title': 'PAA roll-up', 'start_datetime': start,
            'end_datetime': start + timedelta(hours=2), 'venue': 'Venue PAA',
        })['data']['id']

    def _participant_at(self, location):
        res = TrainingParticipantService(self.user).create({
            'training_id': self.training_id, 'full_name': f'At {location.name}',
            'gender': Gender.FEMALE, 'location_id': location.id,
        })
        self.assertTrue(res.get('success'), res.get('detail'))
        return TrainingParticipant.objects.get(id=res['data']['id'])

    def _query_paa(self):
        res = self.schema.execute(
            'query { trainingParticipant(trainingId: "%s") { edges { node { fullName paaReference } } } }'
            % to_global_id('TrainingGQLType', self.training_id),
            context_value=_Ctx(self.user),
        )
        self.assertIsNone(res.errors, msg=res.errors)
        return {e['node']['fullName']: e['node']['paaReference']
                for e in res.data['trainingParticipant']['edges']}

    def test_mainland_village_reports_at_its_district(self):
        village = Location.objects.filter(type='V', validity_to__isnull=True).exclude(
            parent__parent__parent__code__regex=self.ZANZIBAR_REGION).first()
        if not village:
            self.skipTest('no mainland village in the location tree')
        participant = self._participant_at(village)
        self.assertEqual(self._query_paa()[participant.full_name],
                         village.parent.parent.name)

    def test_zanzibar_village_reports_at_island_scope(self):
        village = Location.objects.filter(
            type='V', validity_to__isnull=True,
            parent__parent__parent__code__regex=self.ZANZIBAR_REGION).first()
        if not village:
            self.skipTest('no Zanzibar village in the location tree')
        participant = self._participant_at(village)
        self.assertIn(self._query_paa()[participant.full_name], ('UNGUJA', 'PEMBA'))

    def test_participant_without_a_location_has_no_paa(self):
        res = TrainingParticipantService(self.user).create({
            'training_id': self.training_id, 'full_name': 'Nowhere In Particular'})
        self.assertTrue(res.get('success'), res.get('detail'))
        self.assertIsNone(self._query_paa()['Nowhere In Particular'])

    def test_paa_resolution_does_not_scale_queries_with_rows(self):
        # The roll-up walks up to 4 parent levels; without the select_related hint that
        # is a per-row cascade, which is what would make the attendance list slow.
        village = Location.objects.filter(type='V', validity_to__isnull=True).first()
        if not village:
            self.skipTest('no village in the location tree')

        def query_count(rows):
            for _i in range(rows):
                self._participant_at(village)
            with CaptureQueriesContext(connection) as captured:
                self._query_paa()
            return len(captured)

        # Doubling the rows must not change the number of queries.
        self.assertEqual(query_count(5), query_count(5))
