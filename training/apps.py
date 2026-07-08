"""AppConfig for the Training module.

Loads module configuration (rights + conflict + seed data) from
``core.ModuleConfiguration`` and performs idempotent seeding of rights and the
default TASAF programme areas via the ``post_migrate`` signal.  Seeding on
``post_migrate`` (rather than a hand-shipped data migration) keeps the standard
``makemigrations training && migrate`` workflow friction-free while remaining
idempotent.  See ``docs/04-permissions.md`` and ``docs/09-runbook.md``.
"""
import logging
import uuid

from django.apps import AppConfig
from django.db.models.signals import post_migrate

logger = logging.getLogger(__name__)

MODULE_NAME = 'training'

# IMIS Administrator system role (same constant used by payment_cycle seeding).
IMIS_ADMINISTRATOR_SYSTEM = 64

# Default TASAF programme / business areas seeded as TrainingCategory rows.
DEFAULT_PROGRAMME_AREAS = [
    ('TARGETING', 'Targeting / Registry'),
    ('ENROLLMENT', 'Enrollment'),
    ('PAYMENT', 'Payment'),
    ('GRIEVANCE', 'Grievance'),
    ('PUBLIC_WORKS', 'Public Works'),
    ('LIVELIHOODS', 'Livelihoods'),
    ('CASE_MGMT', 'Case Management'),
    ('MONITORING', 'Monitoring and Evaluation'),
    ('SAFEGUARDS', 'Environmental and Social Safeguards'),
    ('DATA_QUALITY', 'Data Quality / MIS'),
    ('COMMUNITY', 'Community Sessions / Behaviour Change'),
    ('GENERAL_ADMIN', 'General Administration'),
]

DEFAULT_CONFIG = {
    # --- Training ---
    'gql_training_search_perms': ['210101'],
    'gql_training_create_perms': ['210102'],
    'gql_training_update_perms': ['210103'],
    'gql_training_delete_perms': ['210104'],
    'gql_training_approve_perms': ['210110'],
    # --- Training category / programme area ---
    'gql_training_category_search_perms': ['210201'],
    'gql_training_category_create_perms': ['210202'],
    'gql_training_category_update_perms': ['210203'],
    'gql_training_category_delete_perms': ['210204'],
    # --- Trainer profile ---
    'gql_trainer_search_perms': ['210301'],
    'gql_trainer_create_perms': ['210302'],
    'gql_trainer_update_perms': ['210303'],
    'gql_trainer_delete_perms': ['210304'],
    # --- Assignment ---
    'gql_assignment_search_perms': ['210401'],
    'gql_assignment_create_perms': ['210402'],
    'gql_assignment_update_perms': ['210403'],
    'gql_assignment_delete_perms': ['210404'],
    # --- Material ---
    'gql_material_search_perms': ['210501'],
    'gql_material_upload_perms': ['210502'],
    'gql_material_delete_perms': ['210504'],
    # --- Dashboard / calendar ---
    'gql_dashboard_view_perms': ['210601'],
    # --- Participant / attendance ---
    'gql_participant_search_perms': ['210701'],
    'gql_participant_create_perms': ['210702'],
    'gql_participant_update_perms': ['210703'],
    'gql_participant_delete_perms': ['210704'],
    # --- Evidence ---
    'gql_evidence_search_perms': ['210801'],
    'gql_evidence_upload_perms': ['210802'],
    'gql_evidence_delete_perms': ['210804'],
    # --- Session / QR self check-in ---
    'gql_session_search_perms': ['210901'],
    'gql_session_create_perms': ['210902'],
    'gql_session_update_perms': ['210903'],
    'gql_session_delete_perms': ['210904'],
    # --- Conflict detection (configurable) ---
    'conflict_check_enabled': True,
    'conflict_hard_types': ['TRAINER', 'VENUE', 'STAFF'],
    'conflict_soft_types': ['LOCATION'],
    # --- Seeding ---
    'seed_programme_areas': True,
}

# All right codes managed by this module (granted to the admin role on migrate).
ALL_RIGHTS = [
    210101, 210102, 210103, 210104, 210110,
    210201, 210202, 210203, 210204,
    210301, 210302, 210303, 210304,
    210401, 210402, 210403, 210404,
    210501, 210502, 210504,
    210601,
    210701, 210702, 210703, 210704,
    210801, 210802, 210804,
    210901, 210902, 210903, 210904,
]


class TrainingConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = MODULE_NAME

    # rights
    gql_training_search_perms = []
    gql_training_create_perms = []
    gql_training_update_perms = []
    gql_training_delete_perms = []
    gql_training_approve_perms = []
    gql_training_category_search_perms = []
    gql_training_category_create_perms = []
    gql_training_category_update_perms = []
    gql_training_category_delete_perms = []
    gql_trainer_search_perms = []
    gql_trainer_create_perms = []
    gql_trainer_update_perms = []
    gql_trainer_delete_perms = []
    gql_assignment_search_perms = []
    gql_assignment_create_perms = []
    gql_assignment_update_perms = []
    gql_assignment_delete_perms = []
    gql_material_search_perms = []
    gql_material_upload_perms = []
    gql_material_delete_perms = []
    gql_dashboard_view_perms = []
    gql_participant_search_perms = []
    gql_participant_create_perms = []
    gql_participant_update_perms = []
    gql_participant_delete_perms = []
    gql_evidence_search_perms = []
    gql_evidence_upload_perms = []
    gql_evidence_delete_perms = []
    gql_session_search_perms = []
    gql_session_create_perms = []
    gql_session_update_perms = []
    gql_session_delete_perms = []
    # behaviour
    conflict_check_enabled = True
    conflict_hard_types = []
    conflict_soft_types = []
    seed_programme_areas = True

    def ready(self):
        from core.models import ModuleConfiguration
        cfg = ModuleConfiguration.get_or_default(MODULE_NAME, DEFAULT_CONFIG)
        self.__load_config(cfg)
        post_migrate.connect(on_post_migrate, sender=self)

    @classmethod
    def __load_config(cls, cfg):
        for field in cfg:
            if hasattr(TrainingConfig, field):
                setattr(TrainingConfig, field, cfg[field])


def on_post_migrate(sender, **kwargs):
    """Idempotent seeding run after this app's tables exist."""
    apps = kwargs.get('apps')
    try:
        _seed_admin_rights(apps)
    except Exception as exc:  # never break the migrate of other apps
        logger.warning("training: rights seeding skipped (%s)", exc)
    try:
        if TrainingConfig.seed_programme_areas:
            _seed_programme_areas(apps)
    except Exception as exc:
        logger.warning("training: programme-area seeding skipped (%s)", exc)


def _seed_admin_rights(apps):
    Role = apps.get_model('core', 'Role')
    RoleRight = apps.get_model('core', 'RoleRight')
    role = Role.objects.filter(is_system=IMIS_ADMINISTRATOR_SYSTEM, validity_to__isnull=True).first()
    if not role:
        return
    for right_id in ALL_RIGHTS:
        if not RoleRight.objects.filter(role=role, right_id=right_id, validity_to__isnull=True).exists():
            RoleRight.objects.create(role=role, right_id=right_id, audit_user_id=1)


def _seed_programme_areas(apps):
    # Seed via the migration-state model, which lacks HistoryModel.save(); so the UUID
    # PK and the (NOT NULL) audit FKs must be supplied explicitly.
    TrainingCategory = apps.get_model('training', 'TrainingCategory')
    User = apps.get_model('core', 'User')
    admin = User.objects.order_by('id').first()
    if not admin:
        return  # no user yet (fresh bootstrap) — categories can be created later
    for code, name in DEFAULT_PROGRAMME_AREAS:
        if not TrainingCategory.objects.filter(code=code).exists():
            TrainingCategory.objects.create(
                id=uuid.uuid4(), code=code, name=name, is_active=True, version=1,
                user_created_id=admin.id, user_updated_id=admin.id,
            )
