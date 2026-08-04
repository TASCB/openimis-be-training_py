"""Seed demo trainings/participants with gender for local testing.

Every row is stamped ``json_ext['_seed'] = 'demo'`` so ``--clear`` can take them all
back out again; nothing else in the module writes that marker.  Locations are picked
at deliberately different depths (district / ward / village, mainland and Zanzibar)
so the PAA roll-up is actually exercised rather than assumed.

    manage.py seed_training_demo
    manage.py seed_training_demo --clear
"""
import random
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from core.models import User
from location.models import Location

from training.models import (
    Training, TrainingParticipant, TrainingCategory, TrainingStatus,
    Gender, ParticipantCategory, AttendanceStatus,
)
from training.services import TrainingService, TrainingParticipantService, resolve_paa_reference

SEED_MARKER = {'_seed': 'demo'}

FIRST_NAMES_F = ['Asha', 'Neema', 'Zainabu', 'Halima', 'Rehema', 'Mwajuma', 'Amina', 'Subira',
                 'Tatu', 'Fatuma', 'Grace', 'Upendo', 'Salma', 'Riziki', 'Zuhura']
FIRST_NAMES_M = ['Juma', 'Hamisi', 'Baraka', 'Emmanuel', 'Said', 'Rashid', 'Mussa', 'Daudi',
                 'Elias', 'Frank', 'Godfrey', 'Ibrahim', 'Nassoro', 'Shabani', 'Yusuph']
SURNAMES = ['Mwakasege', 'Kimaro', 'Mtenga', 'Shirima', 'Msangi', 'Ngowi', 'Kessy', 'Mwakalinga',
            'Lyimo', 'Massawe', 'Mrema', 'Chuwa', 'Mbwambo', 'Nkya', 'Swai']

# (ParticipantCategory.code, how many, share female) — an uneven split so a gender report
# has something to actually show, spread down the governance ladder so the statistics
# table exercises more than one level.
PARTICIPANT_MIX = [
    ('TMU_HQ_STAFF', 8, 0.5),
    ('PAAF', 6, 0.33),
    ('CMC', 10, 0.6),
    ('CMT', 5, 0.4),
    ('WEO', 7, 0.57),
    ('VEO', 4, 0.25),
    ('COMMUNITY_MEMBER', 6, 0.83),
]


class Command(BaseCommand):
    help = 'Seed demo training participants with gender for local testing.'

    def add_arguments(self, parser):
        parser.add_argument('--clear', action='store_true',
                            help='Remove previously seeded demo rows and exit.')
        parser.add_argument('--seed', type=int, default=20260731,
                            help='RNG seed, so re-runs produce the same people.')

    def handle(self, *args, **options):
        if options['clear']:
            return self._clear()
        random.seed(options['seed'])
        self._seed()

    # -- clear ---------------------------------------------------------------
    def _clear(self):
        participants = TrainingParticipant.objects.filter(json_ext___seed='demo')
        trainings = Training.objects.filter(json_ext___seed='demo')
        counts = (participants.count(), trainings.count())
        participants.delete()
        trainings.delete()
        self.stdout.write(self.style.WARNING(
            f'Removed {counts[0]} demo participant(s) and {counts[1]} demo training(s).'))

    # -- seed ----------------------------------------------------------------
    def _seed(self):
        user = User.objects.order_by('id').first()
        if not user:
            self.stderr.write('No user in the database to attribute the seed to.')
            return

        venues = self._pick_locations()
        if not venues:
            self.stderr.write('No locations found — cannot seed.')
            return

        with transaction.atomic():
            trainings = [self._make_training(user, label, location)
                         for label, location in venues]
            total = sum(self._make_participants(user, training, location)
                        for training, location in zip(trainings, [v[1] for v in venues]))

        self.stdout.write(self.style.SUCCESS(
            f'Seeded {len(trainings)} training(s) and {total} participant(s).'))
        for training, (label, location) in zip(trainings, venues):
            self.stdout.write(
                f'  {training.code}  {label:<22} location={location.name} ({location.type})'
                f'  -> PAA {resolve_paa_reference(location)}')

    # Zanzibar regions are coded 51-55; api_etl rolls those up to UNGUJA / PEMBA
    # instead of the district. Everything else is mainland, where the PAA is the district.
    ZANZIBAR_REGION = r'^5[1-5]$'

    def _pick_locations(self):
        """One mainland district, one mainland village, one Zanzibar village and one
        Zanzibar district — the four cases the roll-up has to get right."""
        districts = Location.objects.filter(type='D', validity_to__isnull=True)
        villages = Location.objects.filter(type='V', validity_to__isnull=True)
        candidates = [
            ('mainland district',
             districts.exclude(parent__code__regex=self.ZANZIBAR_REGION).first()),
            ('mainland village',
             villages.exclude(parent__parent__parent__code__regex=self.ZANZIBAR_REGION).first()),
            ('zanzibar village',
             villages.filter(parent__parent__parent__code__regex=self.ZANZIBAR_REGION).first()),
            ('zanzibar district',
             districts.filter(parent__code__regex=self.ZANZIBAR_REGION).first()),
        ]
        return [(label, location) for label, location in candidates if location]

    def _make_training(self, user, label, location):
        category = TrainingCategory.objects.filter(is_deleted=False).order_by('code').first()
        start = timezone.now() + timedelta(days=random.randint(-30, 30))
        result = TrainingService(user).create({
            'title': f'[DEMO] Gender reporting test — {label}',
            'description': 'Seeded by seed_training_demo for local testing.',
            'category_id': category.id if category else None,
            'start_datetime': start,
            'end_datetime': start + timedelta(days=1),
            'venue': f'Demo venue {label}',
            'location_id': location.id,
            'expected_participants': sum(n for _t, n, _s in PARTICIPANT_MIX),
            'status': TrainingStatus.COMPLETED,
            'json_ext': dict(SEED_MARKER),
        })
        if not result.get('success'):
            raise RuntimeError(f'training create failed: {result.get("detail")}')
        return Training.objects.get(id=result['data']['id'])

    def _make_participants(self, user, training, location):
        service = TrainingParticipantService(user)
        categories = dict(ParticipantCategory.objects.values_list('code', 'id'))
        made = 0
        for category_code, count, female_share in PARTICIPANT_MIX:
            category_id = categories.get(category_code)
            if category_id is None:
                raise RuntimeError(
                    f'category {category_code} is not seeded — run migrate first')
            for _i in range(count):
                female = random.random() < female_share
                gender = Gender.FEMALE if female else Gender.MALE
                given = random.choice(FIRST_NAMES_F if female else FIRST_NAMES_M)
                result = service.create({
                    'training_id': training.id,
                    'full_name': f'{given} {random.choice(SURNAMES)}',
                    'gender': gender,
                    'phone': f'07{random.randint(10000000, 99999999)}',
                    'category_id': category_id,
                    'location_id': location.id,
                    'attendance_status': random.choice([
                        AttendanceStatus.ATTENDED, AttendanceStatus.ATTENDED,
                        AttendanceStatus.ATTENDED, AttendanceStatus.ABSENT,
                    ]),
                    'json_ext': dict(SEED_MARKER),
                })
                if not result.get('success'):
                    raise RuntimeError(f'participant create failed: {result.get("detail")}')
                made += 1
        return made
