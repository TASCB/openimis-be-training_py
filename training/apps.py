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

# Participant categories (requirement 6). Reconciled from three disagreeing lists in the
# brief; `code` is structural and `sequence` orders the governance ladder.
DEFAULT_PARTICIPANT_CATEGORIES = [
    # (code, name, sequence)
    ('TMU_HQ_STAFF', 'TMU Headquarters Staff', 10),
    ('TMO', 'TASAF Monitoring Officer', 15),
    ('MP', 'Member of Parliament', 20),
    ('RC', 'Regional Commissioner', 30),
    ('RS', 'Regional Secretary', 40),
    ('REGIONAL_SECURITY_COMMITTEE', 'Regional Security Committee', 50),
    ('DC', 'District Commissioner', 60),
    ('DAS', 'District Assistant Secretary', 70),
    ('DED', 'District Executive Director', 80),
    ('CMT', 'Council Management Team', 90),
    ('WARD_COUNCILLOR', 'Ward Councillor', 100),
    ('PSSNC', 'Project Area Authority Coordinator', 110),
    ('PSSNA', 'Project Area Authority Accountant', 120),
    ('PAAF', 'Project Area Authority Facilitator', 130),
    ('WEO', 'Ward Executive Officer', 140),
    ('VEO', 'Village Executive Officer', 150),
    ('VC', 'Village Chairperson', 160),
    ('VILLAGE_COUNCIL_MEMBER', 'Village Council Member', 170),
    ('MEO', 'Mtaa Executive Officer', 180),
    ('MITAA_COMMITTEE_LEADER', 'Mitaa Committee Leader', 190),
    ('SHEHA', 'Sheha', 200),
    ('CMC', 'Community Management Committee', 210),
    ('COMMUNITY_MEMBER', 'Community Member', 220),
    ('OTHER', 'Other', 999),
]

DEFAULT_TRAINING_LEVELS = [
    # (code, name, sequence, implementation_location, reporting_application,
    #  primary category codes, facilitator category codes)
    ('L1', 'TMU Headquarters', 10, 'TASAF Headquarters', 'Headquarters training reports',
     ['TMU_HQ_STAFF'], ['TMU_HQ_STAFF']),
    ('L2', 'Training of Trainers (TOT)', 20, 'Designated TOT venue', 'TOT reports',
     ['TMO', 'PSSNC', 'PSSNA'], ['TMU_HQ_STAFF']),
    ('L3', 'Local Government Authorities', 30, 'PAA / Local Government Authority',
     'PAA facilitator training reports',
     ['PAAF'], ['PSSNC']),
    ('L4', 'Community Level', 40, 'Village / Mtaa / Shehia and community',
     'Community training and targeting reports',
     ['VC', 'VILLAGE_COUNCIL_MEMBER', 'VEO', 'SHEHA', 'MEO', 'MITAA_COMMITTEE_LEADER', 'CMC'],
     ['PAAF', 'COMMUNITY_MEMBER']),
]

# User groups and job titles, generated from the TASAF RBAC catalogue. A job title is not
# an openIMIS role: roles are permission bundles shared across titles, so a title cannot
# be derived from a user's roles.
DEFAULT_STAFF_USER_GROUPS = [
    # (code, name)
    ('UG01', 'Executive Office and Corporate Governance'),
    ('UG02', 'Internal Audit and Assurance'),
    ('UG03', 'Finance, Disbursement and E Payment'),
    ('UG04', 'Administration, Human Resources, Registry and Logistics'),
    ('UG05', 'ICT, Systems and Digital Delivery'),
    ('UG06', 'Programs, Productive Cash Transfer and Economic Inclusion'),
    ('UG07', 'Climate Smart Public Works, Targeted Infrastructure, Safeguards and GRM'),
    ('UG08', 'Monitoring, Evaluation and Data'),
]

DEFAULT_JOB_TITLES = [
    # (sn, code, name, user_group_code)
    (1, 'ASSISTANT_ADMINISTRATIVE_OFFICER', 'Assistant Administrative Officer', 'UG04'),
    (2, 'ACCOUNTANT_DISBURSEMENTS', 'Accountant - Disbursements', 'UG03'),
    (3, 'ACCOUNTANT_FINAL_ACCOUNTS', 'Accountant - Final Accounts', 'UG03'),
    (4, 'ACCOUNTS_MANAGER', 'Accounts Manager', 'UG03'),
    (5, 'ADMINISTRATIVE_OFFICER', 'Administrative Officer', 'UG04'),
    (6, 'ASSISTANT_OFFICE_MANAGEMENT_SECRETARY', 'Assistant Office Management Secretary', 'UG01'),
    (7, 'ASSISTANT_PROCUREMENT_OFFICER', 'Assistant Procurement Officer', 'UG01'),
    (8, 'ASSISTANT_SUPPLIES_AND_INVENTORY_OFFICER', 'Assistant Supplies & Inventory Officer', 'UG01'),
    (9, 'APPLICATION_SUPPORT_ASSISTANTS', 'Application Support Assistants', 'UG05'),
    (10, 'APPLICATION_SUPPORT_OFFICER', 'Application Support Officer', 'UG05'),
    (11, 'COORDINATION_AND_LOGISTICS_MANAGER', 'Coordination and Logistics Manager', 'UG01'),
    (12, 'COORDINATION_LOGISTICS_OFFICER', 'Coordination Logistics Officer', 'UG01'),
    (13, 'COMMUNICATION_MANAGER', 'Communication Manager', 'UG01'),
    (14, 'COMMUNICATION_OFFICER', 'Communication Officer', 'UG01'),
    (15, 'CLIMATE_SMART_PUBLIC_WORKS_MANAGER', 'Climate Smart Public Works Manager', 'UG07'),
    (16, 'CLIMATE_SMART_PUBLIC_WORKS_OFFICER', 'Climate Smart Public Works Officer', 'UG07'),
    (17, 'DATA_ANALYST_AND_ADMIN_OFFICER', 'Data Analyst and Admin Officer', 'UG05'),
    (18, 'DIRECTOR_OF_FINANCE_AND_ADMINISTRATION', 'Director of Finance and Administration', 'UG03'),
    (19, 'DIRECTOR_OF_INTERNAL_AUDIT', 'Director of Internal Audit', 'UG02'),
    (20, 'DIRECTOR_OF_IT_AND_DELIVERY_SYSTEMS', 'Director of IT and Delivery Systems', 'UG05'),
    (21, 'DISBURSEMENT_MANAGER', 'Disbursement Manager', 'UG03'),
    (22, 'DIRECTOR_OF_PROGRAMS', 'Director of Programs', 'UG06'),
    (23, 'EXECUTIVE_DIRECTOR', 'Executive Director', 'UG01'),
    (24, 'ECONOMIC_INCLUSION_MANAGER', 'Economic Inclusion Manager', 'UG06'),
    (25, 'ECONOMIC_INCLUSION_OFFICER', 'Economic Inclusion Officer', 'UG06'),
    (26, 'E_PAYMENT_COORDINATOR', 'E-Payment Coordinator', 'UG03'),
    (27, 'E_PAYMENT_OFFICER', 'E-Payment Officer', 'UG03'),
    (28, 'ASSISTANT_GRIEVANCE_REDRESSAL', 'Assistant Grievance Redressal', 'UG07'),
    (29, 'GRIEVANCE_REDRESSAL_OFFICER', 'Grievance Redressal Officer', 'UG07'),
    (30, 'HUMAN_RESOURCE_MANAGER', 'Human Resource Manager', 'UG04'),
    (31, 'INTERNAL_AUDITOR', 'Internal Auditor', 'UG02'),
    (32, 'INTERNAL_AUDIT_MANAGER', 'Internal Audit Manager', 'UG02'),
    (33, 'INFRASTRUCTURE_AND_SYSTEMS_ADMINISTRATION_OFFICER', 'Infrastructure and Systems Administration Officer', 'UG05'),
    (34, 'ICT_TECHNICIAN', 'ICT Technician', 'UG05'),
    (35, 'IT_MANAGER', 'IT - Manager', 'UG05'),
    (36, 'LEGAL_OFFICER', 'Legal Officer', 'UG01'),
    (37, 'MONITORING_AND_EVALUATION_MANAGER', 'Monitoring and Evaluation Manager', 'UG08'),
    (38, 'MONITORING_AND_EVALUATION_OFFICER', 'Monitoring and Evaluation Officer', 'UG08'),
    (39, 'MOTOR_VEHICLE_MECHANICS', 'Motor Vehicle Mechanics', 'UG04'),
    (40, 'NETWORK_ADMINISTRATOR', 'Network Administrator', 'UG05'),
    (41, 'OFFICE_ATTENDANT', 'Office Attendant', 'UG04'),
    (42, 'OFFICE_MANAGEMENT_SECRETARY', 'Office Management Secretary', 'UG01'),
    (43, 'PRODUCTIVE_CASH_TRANSFER_OFFICER', 'Productive Cash Transfer Officer', 'UG06'),
    (44, 'PRODUCTIVE_CASH_TRANSFER_MANAGER', 'Productive Cash Transfer Manager', 'UG06'),
    (45, 'PO_COMMUNITY_DEVELOPMENT', 'PO - Community Development', 'UG07'),
    (46, 'PROJECT_OFFICER_CLIMATE_GENDER_AND_CROSS_CUTTING', 'Project Officer Climate, Gender and Cross Cutting', 'UG07'),
    (47, 'PO_ENVIRONMENT', 'PO - Environment', 'UG07'),
    (48, 'PROCUREMENT_MANAGER', 'Procurement Manager', 'UG01'),
    (49, 'PROCUREMENT_OFFICER', 'Procurement Officer', 'UG01'),
    (50, 'REGISTRY_ASSISTANT', 'Registry Assistant', 'UG04'),
    (51, 'REGISTRY_ASSISTANT_CUM_SECRETARY', 'Registry Assistant CUM Secretary', 'UG01'),
    (52, 'REGISTRY_OFFICER', 'Registry Officer', 'UG04'),
    (53, 'SUPPLIES_AND_INVENTORY_OFFICER', 'Supplies & Inventory Officer', 'UG01'),
    (54, 'SUPPORT_ASSISTANT', 'Support Assistant', 'UG05'),
    (55, 'SENIOR_APPLICATION_SUPPORT_OFFICER', 'Senior Application Support Officer', 'UG05'),
    (56, 'SYSTEM_DEVELOPMENT_OFFICER', 'System Development Officer', 'UG05'),
    (57, 'SENIOR_LEGAL_OFFICER', 'Senior Legal Officer', 'UG01'),
    (58, 'SAFEGUARD_MANAGER', 'Safeguard Manager', 'UG07'),
    (59, 'SENIOR_SYSTEM_DEVELOPMENT_OFFICER', 'Senior System Development Officer', 'UG05'),
    (60, 'TARGETED_INFRASTRUCTURE_OFFICER', 'Targeted Infrastructure Officer', 'UG07'),
    (61, 'TARGETED_INFRASTRUCTURE_SECRETARY', 'Targeted Infrastructure Secretary', 'UG07'),
    (62, 'TASAF_MONITORING_OFFICER', 'TASAF Monitoring Officer', 'UG08'),
    (63, 'TRANSPORT_OFFICER', 'Transport Officer', 'UG04'),
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
    # --- Participant category (2110xx) ---
    'gql_participant_category_search_perms': ['211001'],
    'gql_participant_category_create_perms': ['211002'],
    'gql_participant_category_update_perms': ['211003'],
    'gql_participant_category_delete_perms': ['211004'],
    # --- Training level (2114xx) ---
    'gql_training_level_search_perms': ['211401'],
    'gql_training_level_create_perms': ['211402'],
    'gql_training_level_update_perms': ['211403'],
    'gql_training_level_delete_perms': ['211404'],
    # --- Job title / user group (2111xx, 2112xx) ---
    'gql_job_title_search_perms': ['211101'],
    'gql_job_title_create_perms': ['211102'],
    'gql_job_title_update_perms': ['211103'],
    'gql_job_title_delete_perms': ['211104'],
    'gql_staff_user_group_search_perms': ['211201'],
    # --- Reports (2113xx) ---
    'gql_training_report_perms': ['211301'],
    # --- QR self check-in window (docs/QR_SESSION_ATTENDANCE.md §4.1) ---
    'checkin_auto_open_on_session_date': True,
    'checkin_timezone': 'Africa/Dar_es_Salaam',  # session_date/start_time are wall-clock here
    'checkin_open_minutes_before': 60,
    'checkin_open_minutes_after': 120,
    # --- Conflict detection (configurable) ---
    'conflict_check_enabled': True,
    'conflict_hard_types': ['TRAINER', 'VENUE', 'STAFF'],
    'conflict_soft_types': ['LOCATION'],
    # --- Seeding ---
    'seed_programme_areas': True,
    'seed_participant_categories': True,
    'seed_job_titles': True,
    'seed_training_levels': True,
}

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
    211001, 211002, 211003, 211004,
    211101, 211102, 211103, 211104,
    211401, 211402, 211403, 211404,
    211201,
    211301,
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
    gql_participant_category_search_perms = []
    gql_participant_category_create_perms = []
    gql_participant_category_update_perms = []
    gql_participant_category_delete_perms = []
    gql_training_level_search_perms = []
    gql_training_level_create_perms = []
    gql_training_level_update_perms = []
    gql_training_level_delete_perms = []
    gql_job_title_search_perms = []
    gql_job_title_create_perms = []
    gql_job_title_update_perms = []
    gql_job_title_delete_perms = []
    gql_staff_user_group_search_perms = []
    gql_training_report_perms = []
    # behaviour
    checkin_auto_open_on_session_date = True
    checkin_timezone = 'Africa/Dar_es_Salaam'
    checkin_open_minutes_before = 60
    checkin_open_minutes_after = 120
    conflict_check_enabled = True
    conflict_hard_types = []
    conflict_soft_types = []
    seed_programme_areas = True
    seed_participant_categories = True
    seed_job_titles = True
    seed_training_levels = True

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
    try:
        if TrainingConfig.seed_participant_categories:
            _seed_participant_categories(apps)
    except Exception as exc:
        logger.warning("training: participant-category seeding skipped (%s)", exc)
    try:
        if TrainingConfig.seed_job_titles:
            _seed_job_titles(apps)
    except Exception as exc:
        logger.warning("training: job-title seeding skipped (%s)", exc)
    try:
        if TrainingConfig.seed_training_levels:
            _seed_training_levels(apps)
    except Exception as exc:
        logger.warning("training: training-level seeding skipped (%s)", exc)


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
    TrainingCategory = apps.get_model('training', 'TrainingCategory')
    User = apps.get_model('core', 'User')
    admin = User.objects.order_by('id').first()
    if not admin:
        return 
    for code, name in DEFAULT_PROGRAMME_AREAS:
        if not TrainingCategory.objects.filter(code=code).exists():
            TrainingCategory.objects.create(
                id=uuid.uuid4(), code=code, name=name, is_active=True, version=1,
                user_created_id=admin.id, user_updated_id=admin.id,
            )


def _seed_participant_categories(apps):
    """Idempotent by code; existing rows are never overwritten."""
    ParticipantCategory = apps.get_model('training', 'ParticipantCategory')
    User = apps.get_model('core', 'User')
    admin = User.objects.order_by('id').first()
    if not admin:
        return
    for code, name, sequence in DEFAULT_PARTICIPANT_CATEGORIES:
        if not ParticipantCategory.objects.filter(code=code).exists():
            ParticipantCategory.objects.create(
                id=uuid.uuid4(), code=code, name=name, sequence=sequence,
                is_active=True, version=1,
                user_created_id=admin.id, user_updated_id=admin.id,
            )


def _seed_job_titles(apps):
    """Seed the eight user groups and the 63 job titles, idempotent by code."""
    StaffUserGroup = apps.get_model('training', 'StaffUserGroup')
    JobTitle = apps.get_model('training', 'JobTitle')
    User = apps.get_model('core', 'User')
    admin = User.objects.order_by('id').first()
    if not admin:
        return

    audit = {'version': 1, 'user_created_id': admin.id, 'user_updated_id': admin.id}
    for code, name in DEFAULT_STAFF_USER_GROUPS:
        if not StaffUserGroup.objects.filter(code=code).exists():
            StaffUserGroup.objects.create(
                id=uuid.uuid4(), code=code, name=name, is_active=True, **audit)

    groups = dict(StaffUserGroup.objects.values_list('code', 'id'))
    for sn, code, name, group_code in DEFAULT_JOB_TITLES:
        if not JobTitle.objects.filter(code=code).exists():
            JobTitle.objects.create(
                id=uuid.uuid4(), sn=sn, code=code, name=name,
                user_group_id=groups.get(group_code), is_active=True, **audit)


def _seed_training_levels(apps):
    """Seed L1-L4 and their permitted participant categories, idempotent by code."""
    TrainingLevel = apps.get_model('training', 'TrainingLevel')
    ParticipantCategory = apps.get_model('training', 'ParticipantCategory')
    User = apps.get_model('core', 'User')
    admin = User.objects.order_by('id').first()
    if not admin:
        return

    categories = dict(ParticipantCategory.objects.values_list('code', 'id'))
    audit = {'version': 1, 'user_created_id': admin.id, 'user_updated_id': admin.id}
    for code, name, sequence, location, reporting, primary, facilitators in DEFAULT_TRAINING_LEVELS:
        if TrainingLevel.objects.filter(code=code).exists():
            continue
        level = TrainingLevel.objects.create(
            id=uuid.uuid4(), code=code, name=name, sequence=sequence,
            implementation_location=location, reporting_application=reporting,
            is_active=True, **audit)
        level.primary_categories.set([categories[c] for c in primary if c in categories])
        level.facilitator_categories.set([categories[c] for c in facilitators if c in categories])
