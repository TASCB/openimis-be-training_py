"""Training management models."""
import secrets

from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _

from core.models import HistoryModel, UUIDModel, ObjectMutation, MutationLog
from core.fields import DateTimeField
from location.models import Location


def generate_registration_token():
    """Opaque, URL-safe token embedded in a session's QR code (never the UUID)."""
    return secrets.token_urlsafe(24)


class TrainingStatus(models.TextChoices):
    DRAFT = 'DRAFT', _('Draft')
    SUBMITTED = 'SUBMITTED', _('Submitted')
    APPROVED = 'APPROVED', _('Approved')
    REJECTED = 'REJECTED', _('Rejected')
    SCHEDULED = 'SCHEDULED', _('Scheduled')
    ONGOING = 'ONGOING', _('Ongoing')
    COMPLETED = 'COMPLETED', _('Completed')
    CANCELLED = 'CANCELLED', _('Cancelled')
    CLOSED = 'CLOSED', _('Closed')


TERMINAL_STATUSES = (TrainingStatus.CANCELLED, TrainingStatus.REJECTED, TrainingStatus.CLOSED)


class TrainerType(models.TextChoices):
    INTERNAL = 'INTERNAL', _('Internal')
    EXTERNAL = 'EXTERNAL', _('External')


class AssignmentRole(models.TextChoices):
    LEAD_TRAINER = 'LEAD_TRAINER', _('Lead Trainer')
    ASSISTANT_TRAINER = 'ASSISTANT_TRAINER', _('Assistant Trainer')
    FACILITATOR = 'FACILITATOR', _('Facilitator')
    COORDINATOR = 'COORDINATOR', _('Coordinator')
    OBSERVER = 'OBSERVER', _('Observer')
    SUPPORT_STAFF = 'SUPPORT_STAFF', _('Support Staff')


class AssignmentStatus(models.TextChoices):
    ASSIGNED = 'ASSIGNED', _('Assigned')
    CONFIRMED = 'CONFIRMED', _('Confirmed')
    DECLINED = 'DECLINED', _('Declined')
    REPLACED = 'REPLACED', _('Replaced')
    CANCELLED = 'CANCELLED', _('Cancelled')


class ParticipantType(models.TextChoices):
    TASAF_STAFF = 'TASAF_STAFF', _('TASAF Staff')
    PAA_REP = 'PAA_REP', _('PAA Representative')
    CMC_MEMBER = 'CMC_MEMBER', _('CMC Member')
    LGA_OFFICER = 'LGA_OFFICER', _('LGA Officer')
    ENUMERATOR = 'ENUMERATOR', _('Enumerator')
    SUPERVISOR = 'SUPERVISOR', _('Supervisor')
    COMMUNITY_FACILITATOR = 'COMMUNITY_FACILITATOR', _('Community Facilitator')
    TRAINER = 'TRAINER', _('Trainer')
    OTHER = 'OTHER', _('Other')


class AttendanceStatus(models.TextChoices):
    INVITED = 'INVITED', _('Invited')
    CONFIRMED = 'CONFIRMED', _('Confirmed')
    ATTENDED = 'ATTENDED', _('Attended')
    ABSENT = 'ABSENT', _('Absent')
    REPLACED = 'REPLACED', _('Replaced')


class EvidenceType(models.TextChoices):
    REPORT = 'REPORT', _('Training Report')
    ATTENDANCE_SHEET = 'ATTENDANCE_SHEET', _('Attendance Sheet')
    PHOTO = 'PHOTO', _('Photo')
    SIGNED_FORM = 'SIGNED_FORM', _('Signed Form')
    EVALUATION_SUMMARY = 'EVALUATION_SUMMARY', _('Evaluation Summary')
    TRAINER_REPORT = 'TRAINER_REPORT', _('Trainer Report')
    OTHER = 'OTHER', _('Other')


class Gender(models.TextChoices):
    MALE = 'M', _('Male')
    FEMALE = 'F', _('Female')
    OTHER = 'O', _('Other')


class CheckInMethod(models.TextChoices):
    MANUAL = 'MANUAL', _('Manual entry')
    QR = 'QR', _('QR self check-in')


class TrainingCategory(HistoryModel):
    """TASAF programme / business area a training belongs to (configurable)."""
    code = models.CharField(max_length=255, blank=False, null=False)
    name = models.CharField(max_length=255, blank=False, null=False)
    description = models.TextField(blank=True, null=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        indexes = [models.Index(fields=['code']), models.Index(fields=['is_active'])]

    def __str__(self):
        return f'{self.code} - {self.name}'


class TrainerProfile(HistoryModel):
    """Reusable trainer profile (internal staff or external)."""
    code = models.CharField(max_length=255, blank=False, null=False)
    full_name = models.CharField(max_length=255, blank=False, null=False)
    email = models.CharField(max_length=255, blank=True, null=True)
    phone = models.CharField(max_length=50, blank=True, null=True)
    organization = models.CharField(max_length=255, blank=True, null=True)
    trainer_type = models.CharField(
        max_length=20, choices=TrainerType.choices, default=TrainerType.INTERNAL)
    specialization = models.CharField(max_length=255, blank=True, null=True)
    bio = models.TextField(blank=True, null=True)
    staff_user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.DO_NOTHING, blank=True, null=True,
        related_name='trainer_profiles')
    is_active = models.BooleanField(default=True)

    class Meta:
        indexes = [
            models.Index(fields=['code']),
            models.Index(fields=['trainer_type']),
            models.Index(fields=['is_active']),
        ]

    def __str__(self):
        return f'{self.full_name} ({self.code})'


class Training(HistoryModel):
    """A training event with a status workflow (see docs/06-workflow-status.md)."""
    code = models.CharField(max_length=255, blank=False, null=False)
    title = models.CharField(max_length=255, blank=False, null=False)
    description = models.TextField(blank=True, null=True)
    category = models.ForeignKey(
        TrainingCategory, on_delete=models.DO_NOTHING, blank=True, null=True,
        related_name='trainings')
    start_datetime = DateTimeField(blank=False, null=False)
    end_datetime = DateTimeField(blank=False, null=False)
    venue = models.CharField(max_length=255, blank=True, null=True)
    location = models.ForeignKey(
        Location, on_delete=models.DO_NOTHING, blank=True, null=True,
        related_name='trainings')
    paa_reference = models.CharField(max_length=255, blank=True, null=True)
    status = models.CharField(
        max_length=20, choices=TrainingStatus.choices, default=TrainingStatus.DRAFT)
    expected_participants = models.IntegerField(blank=True, null=True)
    learning_outcomes = models.JSONField(default=list, blank=True, null=True)
    intended_for = models.JSONField(default=list, blank=True, null=True)

    class Meta:
        indexes = [
            models.Index(fields=['code']),
            models.Index(fields=['status']),
            models.Index(fields=['start_datetime']),
            models.Index(fields=['end_datetime']),
            models.Index(fields=['category']),
            models.Index(fields=['location']),
        ]

    def __str__(self):
        return f'{self.code} - {self.title}'


class TrainingSession(HistoryModel):
    """A session/day of a training. Owns its own QR self check-in token so
    attendance can be recorded per session (Day 1, Day 2, ...)."""
    training = models.ForeignKey(
        Training, on_delete=models.DO_NOTHING, related_name='sessions')
    title = models.CharField(max_length=255, blank=False, null=False)
    session_date = models.DateField(blank=True, null=True)
    start_time = models.TimeField(blank=True, null=True)
    end_time = models.TimeField(blank=True, null=True)
    sequence = models.IntegerField(default=1)
    venue = models.CharField(max_length=255, blank=True, null=True)
    registration_token = models.CharField(
        max_length=64, unique=True, default=generate_registration_token)
    registration_open = models.BooleanField(default=False)
    registration_opens_at = DateTimeField(blank=True, null=True)
    registration_closes_at = DateTimeField(blank=True, null=True)

    class Meta:
        indexes = [
            models.Index(fields=['training']),
            models.Index(fields=['registration_open']),
            models.Index(fields=['session_date']),
        ]

    def __str__(self):
        return f'{self.title} ({self.training_id})'


class TrainingAssignment(HistoryModel):
    """Trainer/staff assigned to a training in a given role."""
    training = models.ForeignKey(
        Training, on_delete=models.DO_NOTHING, related_name='assignments')
    trainer = models.ForeignKey(
        TrainerProfile, on_delete=models.DO_NOTHING, blank=True, null=True,
        related_name='assignments')
    staff_user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.DO_NOTHING, blank=True, null=True,
        related_name='training_assignments')
    role = models.CharField(
        max_length=30, choices=AssignmentRole.choices, default=AssignmentRole.LEAD_TRAINER)
    status = models.CharField(
        max_length=20, choices=AssignmentStatus.choices, default=AssignmentStatus.ASSIGNED)
    notes = models.TextField(blank=True, null=True)

    class Meta:
        indexes = [
            models.Index(fields=['training']),
            models.Index(fields=['trainer']),
            models.Index(fields=['staff_user']),
            models.Index(fields=['role']),
            models.Index(fields=['status']),
        ]

    def __str__(self):
        who = self.trainer or self.staff_user
        return f'{who} @ {self.training_id} ({self.role})'


class TrainingParticipant(HistoryModel):
    """A participant of a training plus their attendance status.

    When ``session`` is set the row is the attendance register for that one session
    (a person attending N sessions has N rows). ``session = null`` is a legacy /
    manual whole-training entry."""
    training = models.ForeignKey(
        Training, on_delete=models.DO_NOTHING, related_name='participants')
    session = models.ForeignKey(
        'TrainingSession', on_delete=models.DO_NOTHING, blank=True, null=True,
        related_name='participants')
    full_name = models.CharField(max_length=255, blank=False, null=False)
    gender = models.CharField(max_length=10, choices=Gender.choices, blank=True, null=True)
    phone = models.CharField(max_length=50, blank=True, null=True)
    email = models.CharField(max_length=255, blank=True, null=True)
    organization = models.CharField(max_length=255, blank=True, null=True)
    title = models.CharField(max_length=255, blank=True, null=True)
    participant_type = models.CharField(
        max_length=30, choices=ParticipantType.choices, default=ParticipantType.OTHER)
    internal_user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.DO_NOTHING, blank=True, null=True,
        related_name='training_participations')
    location = models.ForeignKey(
        Location, on_delete=models.DO_NOTHING, blank=True, null=True,
        related_name='training_participants')
    attendance_status = models.CharField(
        max_length=20, choices=AttendanceStatus.choices, default=AttendanceStatus.INVITED)
    attendance_remarks = models.TextField(blank=True, null=True)
    self_registered = models.BooleanField(default=False)
    check_in_method = models.CharField(
        max_length=10, choices=CheckInMethod.choices, default=CheckInMethod.MANUAL)
    registered_at = DateTimeField(blank=True, null=True)

    class Meta:
        indexes = [
            models.Index(fields=['training']),
            models.Index(fields=['session']),
            models.Index(fields=['participant_type']),
            models.Index(fields=['attendance_status']),
            models.Index(fields=['self_registered']),
        ]

    def __str__(self):
        return f'{self.full_name} @ {self.training_id}'


class TrainingMaterial(HistoryModel):
    """A file attached to a training before/while it runs (agenda, slides, ...)."""
    training = models.ForeignKey(
        Training, on_delete=models.DO_NOTHING, related_name='materials')
    file_name = models.CharField(max_length=255, blank=False, null=False)
    file_type = models.CharField(max_length=100, blank=True, null=True)
    file = models.FileField(upload_to='training/materials/%Y/%m/', blank=True, null=True)
    description = models.TextField(blank=True, null=True)

    class Meta:
        indexes = [models.Index(fields=['training']), models.Index(fields=['file_type'])]

    def __str__(self):
        return self.file_name


class TrainingEvidence(HistoryModel):
    """Post-training evidence/report (report, attendance sheet, photos, ...)."""
    training = models.ForeignKey(
        Training, on_delete=models.DO_NOTHING, related_name='evidence')
    evidence_type = models.CharField(
        max_length=30, choices=EvidenceType.choices, default=EvidenceType.REPORT)
    file_name = models.CharField(max_length=255, blank=False, null=False)
    file_type = models.CharField(max_length=100, blank=True, null=True)
    file = models.FileField(upload_to='training/evidence/%Y/%m/', blank=True, null=True)
    description = models.TextField(blank=True, null=True)

    class Meta:
        indexes = [models.Index(fields=['training']), models.Index(fields=['evidence_type'])]

    def __str__(self):
        return f'{self.evidence_type}: {self.file_name}'


class TrainingMutation(UUIDModel, ObjectMutation):
    training = models.ForeignKey(Training, models.DO_NOTHING, related_name='mutations')
    mutation = models.ForeignKey(MutationLog, models.DO_NOTHING, related_name='trainings')


class TrainingCategoryMutation(UUIDModel, ObjectMutation):
    training_category = models.ForeignKey(TrainingCategory, models.DO_NOTHING, related_name='mutations')
    mutation = models.ForeignKey(MutationLog, models.DO_NOTHING, related_name='training_categories')


class TrainerProfileMutation(UUIDModel, ObjectMutation):
    trainer_profile = models.ForeignKey(TrainerProfile, models.DO_NOTHING, related_name='mutations')
    mutation = models.ForeignKey(MutationLog, models.DO_NOTHING, related_name='trainer_profiles')


class TrainingAssignmentMutation(UUIDModel, ObjectMutation):
    training_assignment = models.ForeignKey(TrainingAssignment, models.DO_NOTHING, related_name='mutations')
    mutation = models.ForeignKey(MutationLog, models.DO_NOTHING, related_name='training_assignments')


class TrainingSessionMutation(UUIDModel, ObjectMutation):
    training_session = models.ForeignKey(TrainingSession, models.DO_NOTHING, related_name='mutations')
    mutation = models.ForeignKey(MutationLog, models.DO_NOTHING, related_name='training_sessions')


class TrainingParticipantMutation(UUIDModel, ObjectMutation):
    training_participant = models.ForeignKey(TrainingParticipant, models.DO_NOTHING, related_name='mutations')
    mutation = models.ForeignKey(MutationLog, models.DO_NOTHING, related_name='training_participants')


class TrainingMaterialMutation(UUIDModel, ObjectMutation):
    training_material = models.ForeignKey(TrainingMaterial, models.DO_NOTHING, related_name='mutations')
    mutation = models.ForeignKey(MutationLog, models.DO_NOTHING, related_name='training_materials')


class TrainingEvidenceMutation(UUIDModel, ObjectMutation):
    training_evidence = models.ForeignKey(TrainingEvidence, models.DO_NOTHING, related_name='mutations')
    mutation = models.ForeignKey(MutationLog, models.DO_NOTHING, related_name='training_evidences')
