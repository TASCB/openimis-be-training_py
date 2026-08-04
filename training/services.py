"""Service layer for the Training module.

Per-entity CRUD services extend ``core.services.BaseService`` (uniform
``{success, data, error}`` contract, service signals).  ``ConflictService`` and
``TrainingSummaryService`` are standalone read services.  Status transitions live in
``TrainingService.transition`` — the single chokepoint that a Phase-2 maker-checker
flow can later wrap (see docs/06-workflow-status.md).
"""
import logging
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

from django.db import transaction
from django.db.models import Count
from django.utils import timezone
from django.utils.translation import gettext as _

from core.services import BaseService
from core.services.utils import output_exception, model_representation, check_authentication
from core.signals import register_service_signal
from location.models import Location

from training.apps import TrainingConfig
from training.models import (
    Training, TrainingCategory, TrainerProfile,
    TrainingAssignment, TrainingParticipant, TrainingMaterial, TrainingEvidence,
    TrainingSession, TrainingStatus, TERMINAL_STATUSES, AssignmentStatus,
    ActivityCodeSequence, ParticipantCategory, JobTitle,
)
from training.validations import (
    TrainingValidation, TrainingCategoryValidation, TrainerProfileValidation,
    TrainingAssignmentValidation, TrainingParticipantValidation,
    TrainingMaterialValidation, TrainingEvidenceValidation, TrainingSessionValidation,
    ParticipantCategoryValidation, JobTitleValidation,
)

logger = logging.getLogger(__name__)
TRAINING_CODE_PREFIX = 'TRN'

TRAINER_CODE_SEQUENCE = 'TRAINER'


# ---------------------------------------------------------------------------
# CRUD services
# ---------------------------------------------------------------------------
class _FalsyDefaultFixMixin:
    """Work around core's pre_save validator dropping falsy values.

    ``core.validation.base.validator`` runs on every HistoryModel save and resets any
    field that declares a model default back to that default when the incoming value is
    FALSY — it tests ``not attr`` rather than ``attr is None``. So ``is_active=False``
    never survives a save on any model whose field is ``BooleanField(default=True)``:
    deactivating a category, a programme area or a trainer silently did nothing.

    Core is an installed dependency, so the fix is applied here: let the normal save run
    (it writes the history row and bumps the version), then re-apply the falsy flags with
    a queryset update, which does not fire pre_save. The historical row therefore records
    the pre-reset value; the live row is correct, which is what reads and reports use.
    """

    FALSY_DEFAULT_FIELDS = ('is_active',)

    def _reapply_falsy_defaults(self, obj_data, result):
        overrides = {name: False for name in self.FALSY_DEFAULT_FIELDS
                     if obj_data.get(name) is False}
        if not overrides or not result.get('success') or not obj_data.get('id'):
            return result
        self.OBJECT_TYPE.objects.filter(id=obj_data['id']).update(**overrides)
        if isinstance(result.get('data'), dict):
            result['data'].update(overrides)
        return result


class TrainingCategoryService(_FalsyDefaultFixMixin, BaseService):
    OBJECT_TYPE = TrainingCategory

    def __init__(self, user, validation_class=TrainingCategoryValidation):
        super().__init__(user, validation_class)

    @register_service_signal('training_category_service.create')
    def create(self, obj_data):
        return super().create(obj_data)

    @register_service_signal('training_category_service.update')
    def update(self, obj_data):
        return self._reapply_falsy_defaults(obj_data, super().update(obj_data))

    @register_service_signal('training_category_service.delete')
    def delete(self, obj_data):
        return super().delete(obj_data)


class ParticipantCategoryService(_FalsyDefaultFixMixin, BaseService):
    OBJECT_TYPE = ParticipantCategory

    def __init__(self, user, validation_class=ParticipantCategoryValidation):
        super().__init__(user, validation_class)

    @register_service_signal('participant_category_service.create')
    def create(self, obj_data):
        return super().create(obj_data)

    @register_service_signal('participant_category_service.update')
    def update(self, obj_data):
        return self._reapply_falsy_defaults(obj_data, super().update(obj_data))

    @register_service_signal('participant_category_service.delete')
    def delete(self, obj_data):
        return super().delete(obj_data)


class JobTitleService(_FalsyDefaultFixMixin, BaseService):
    OBJECT_TYPE = JobTitle

    def __init__(self, user, validation_class=JobTitleValidation):
        super().__init__(user, validation_class)

    @register_service_signal('job_title_service.create')
    def create(self, obj_data):
        return super().create(obj_data)

    @register_service_signal('job_title_service.update')
    def update(self, obj_data):
        return self._reapply_falsy_defaults(obj_data, super().update(obj_data))

    @register_service_signal('job_title_service.delete')
    def delete(self, obj_data):
        return super().delete(obj_data)


class TrainerProfileService(_FalsyDefaultFixMixin, BaseService):
    OBJECT_TYPE = TrainerProfile

    def __init__(self, user, validation_class=TrainerProfileValidation):
        super().__init__(user, validation_class)

    @register_service_signal('trainer_profile_service.create')
    @transaction.atomic
    def create(self, obj_data):
        self._assign_code(obj_data)
        return super().create(obj_data)

    @register_service_signal('trainer_profile_service.update')
    def update(self, obj_data):
        return self._reapply_falsy_defaults(obj_data, super().update(obj_data))

    @register_service_signal('trainer_profile_service.delete')
    def delete(self, obj_data):
        return super().delete(obj_data)

    @staticmethod
    def _assign_code(obj_data):
        sequence = ActivityCodeSequence.objects.select_for_update().get(prefix=TRAINER_CODE_SEQUENCE)
        sequence.last_number += 1
        sequence.save()
        obj_data['code'] = f'{sequence.last_number:04}'


class TrainingAssignmentService(BaseService):
    OBJECT_TYPE = TrainingAssignment

    def __init__(self, user, validation_class=TrainingAssignmentValidation):
        super().__init__(user, validation_class)

    @register_service_signal('training_assignment_service.create')
    def create(self, obj_data):
        return super().create(obj_data)

    @register_service_signal('training_assignment_service.update')
    def update(self, obj_data):
        return super().update(obj_data)

    @register_service_signal('training_assignment_service.delete')
    def delete(self, obj_data):
        return super().delete(obj_data)


class TrainingParticipantService(BaseService):
    OBJECT_TYPE = TrainingParticipant

    def __init__(self, user, validation_class=TrainingParticipantValidation):
        super().__init__(user, validation_class)

    @register_service_signal('training_participant_service.create')
    def create(self, obj_data):
        return super().create(obj_data)

    @register_service_signal('training_participant_service.update')
    def update(self, obj_data):
        return super().update(obj_data)

    @register_service_signal('training_participant_service.delete')
    def delete(self, obj_data):
        return super().delete(obj_data)


class TrainingSessionService(BaseService):
    OBJECT_TYPE = TrainingSession

    def __init__(self, user, validation_class=TrainingSessionValidation):
        super().__init__(user, validation_class)

    @register_service_signal('training_session_service.create')
    def create(self, obj_data):
        return super().create(obj_data)

    @register_service_signal('training_session_service.update')
    def update(self, obj_data):
        return super().update(obj_data)

    @register_service_signal('training_session_service.delete')
    def delete(self, obj_data):
        return super().delete(obj_data)


def _local_now():
    # Session times are wall-clock; the server clock is UTC (USE_TZ=False). See docs/QR_SESSION_ATTENDANCE.md §4.1.
    try:
        return datetime.now(ZoneInfo(TrainingConfig.checkin_timezone)).replace(tzinfo=None)
    except Exception:
        return timezone.now()


def _auto_open_today(session):
    if not TrainingConfig.checkin_auto_open_on_session_date or not session.session_date:
        return False
    if session.registration_opens_at or session.registration_closes_at:
        return False  # explicit window = the officer drives this session by hand
    starts = datetime.combine(session.session_date, session.start_time or time.min) \
        - timedelta(minutes=TrainingConfig.checkin_open_minutes_before)
    ends = datetime.combine(session.session_date, session.end_time or time.max) \
        + timedelta(minutes=TrainingConfig.checkin_open_minutes_after)
    return starts <= _local_now() <= ends


def checkin_open(session):
    """Whether public QR self check-in accepts submissions — docs/QR_SESSION_ATTENDANCE.md §4.1."""
    now = timezone.now()
    if session.registration_opens_at and now < session.registration_opens_at:
        return False
    if session.registration_closes_at and now > session.registration_closes_at:
        return False
    return bool(session.registration_open) or _auto_open_today(session)


class TrainingMaterialService(BaseService):
    OBJECT_TYPE = TrainingMaterial

    def __init__(self, user, validation_class=TrainingMaterialValidation):
        super().__init__(user, validation_class)

    @register_service_signal('training_material_service.create')
    def create(self, obj_data):
        return super().create(obj_data)

    @register_service_signal('training_material_service.update')
    def update(self, obj_data):
        return super().update(obj_data)

    @register_service_signal('training_material_service.delete')
    def delete(self, obj_data):
        return super().delete(obj_data)


class TrainingEvidenceService(BaseService):
    OBJECT_TYPE = TrainingEvidence

    def __init__(self, user, validation_class=TrainingEvidenceValidation):
        super().__init__(user, validation_class)

    @register_service_signal('training_evidence_service.create')
    def create(self, obj_data):
        return super().create(obj_data)

    @register_service_signal('training_evidence_service.update')
    def update(self, obj_data):
        return super().update(obj_data)

    @register_service_signal('training_evidence_service.delete')
    def delete(self, obj_data):
        return super().delete(obj_data)


# ---------------------------------------------------------------------------
# Training CRUD + status workflow
# ---------------------------------------------------------------------------
# Allowed status transitions: action -> (from-states, to-state)
STATUS_TRANSITIONS = {
    'submit': ((TrainingStatus.DRAFT, TrainingStatus.REJECTED), TrainingStatus.SUBMITTED),
    'approve': ((TrainingStatus.SUBMITTED,), TrainingStatus.APPROVED),
    'reject': ((TrainingStatus.SUBMITTED,), TrainingStatus.REJECTED),
    'revise': ((TrainingStatus.REJECTED,), TrainingStatus.DRAFT),
    'schedule': ((TrainingStatus.APPROVED,), TrainingStatus.SCHEDULED),
    'start': ((TrainingStatus.SCHEDULED,), TrainingStatus.ONGOING),
    'complete': ((TrainingStatus.ONGOING,), TrainingStatus.COMPLETED),
    'cancel': ((TrainingStatus.DRAFT, TrainingStatus.APPROVED,
                TrainingStatus.SCHEDULED, TrainingStatus.ONGOING), TrainingStatus.CANCELLED),
    'close': ((TrainingStatus.COMPLETED,), TrainingStatus.CLOSED),
}

# Rescheduling moves the date window without changing status — not a STATUS_TRANSITIONS entry.
RESCHEDULE_FROM_STATUSES = (TrainingStatus.SCHEDULED,)


def _paa_scope(location):
    # Owned by api_etl so a training and an ETL import cannot disagree; absent = mainland behaviour.
    try:
        from api_etl.paa_aliases import get_paa_scope
    except Exception:
        return None
    return get_paa_scope(name=location.name, code=location.code)


def resolve_paa_reference(location):
    """The PAA a location belongs to — docs/PAA_LOCATION.md."""
    district = None
    node = location
    while node is not None:
        scope = _paa_scope(node)
        if scope:
            return scope
        if district is None and node.type == 'D':
            district = node
        node = node.parent
    return district.name if district else None


class TrainingService(BaseService):
    OBJECT_TYPE = Training

    def __init__(self, user, validation_class=TrainingValidation):
        super().__init__(user, validation_class)

    @register_service_signal('training_service.create')
    @transaction.atomic
    def create(self, obj_data):
        self._assign_code(obj_data)
        self._assign_paa_reference(obj_data)
        return super().create(obj_data)

    @register_service_signal('training_service.update')
    def update(self, obj_data):
        self._assign_paa_reference(obj_data)
        return super().update(obj_data)

    @staticmethod
    def _assign_paa_reference(obj_data):
        """PAA is derived from the chosen location, never typed."""
        if 'location_id' not in obj_data:
            return  # partial update leaving the location alone
        location = Location.objects.filter(id=obj_data.get('location_id')).first()
        obj_data['paa_reference'] = resolve_paa_reference(location)

    @staticmethod
    def _assign_code(obj_data):
        sequence = ActivityCodeSequence.objects.select_for_update().get(prefix=TRAINING_CODE_PREFIX)
        sequence.last_number += 1
        sequence.save()
        obj_data['code'] = f'{TRAINING_CODE_PREFIX}{sequence.last_number:06}'  # e.g. TRN000001 (max 999,999)

    @register_service_signal('training_service.delete')
    def delete(self, obj_data):
        return super().delete(obj_data)

    @register_service_signal('training_service.transition')
    def transition(self, training_id, action, **ctx):
        """Guarded status transition. Returns the BaseService ``{success,...}`` shape."""
        try:
            if action not in STATUS_TRANSITIONS:
                return {"success": False, "message": _("training.validation.unknown_action"),
                        "detail": action}
            training = Training.objects.filter(id=training_id, is_deleted=False).first()
            if not training:
                return {"success": False, "message": _("training.validation.not_found"),
                        "detail": str(training_id)}
            from_states, to_state = STATUS_TRANSITIONS[action]
            if training.status not in from_states:
                return {"success": False,
                        "message": _("training.validation.invalid_status_transition"),
                        "detail": f"{training.status} -> {to_state} ({action})"}
            # Re-check hard conflicts when (re)scheduling.
            if action == 'schedule':
                conflicts = ConflictService(self.user).check_for_training(training)
                hard = [c for c in conflicts if c['hard']]
                if hard:
                    return {"success": False,
                            "message": _("training.validation.hard_conflict"),
                            "detail": " | ".join(c['message'] for c in hard)}
            if action == 'reject' and ctx.get('reason'):
                training.json_ext = {**(training.json_ext or {}), 'reject_reason': ctx['reason']}
            training.status = to_state
            training.save(username=self.user.username)
            return {"success": True, "message": _("training.transition.success"),
                    "data": model_representation(training)}
        except Exception as exc:
            return output_exception(model_name=self.OBJECT_TYPE.__name__, method="transition", exception=exc)

    @register_service_signal('training_service.reschedule')
    @transaction.atomic
    def reschedule(self, training_id, start, end, reason=None):
        """Move a scheduled training to a new window, keeping its status."""
        try:
            training = Training.objects.filter(id=training_id, is_deleted=False).first()
            if not training:
                return {"success": False, "message": _("training.validation.not_found"),
                        "detail": str(training_id)}
            if training.status not in RESCHEDULE_FROM_STATUSES:
                return {"success": False,
                        "message": _("training.validation.invalid_reschedule_status"),
                        "detail": training.status}
            if not start or not end or start >= end:
                return {"success": False, "message": _("training.validation.invalid_window"),
                        "detail": f"{start} -> {end}"}

            was_start, was_end = training.start_datetime, training.end_datetime
            training.start_datetime = start
            training.end_datetime = end

            hard = [c for c in ConflictService(self.user).check_for_training(training) if c['hard']]
            if hard:
                return {"success": False, "message": _("training.validation.hard_conflict"),
                        "detail": " | ".join(c['message'] for c in hard)}

            shifted, outside = self._shift_sessions(training, was_start)

            log = list((training.json_ext or {}).get('reschedule_log') or [])
            log.append({
                'from_start': was_start.isoformat() if was_start else None,
                'from_end': was_end.isoformat() if was_end else None,
                'to_start': start.isoformat(),
                'to_end': end.isoformat(),
                'reason': reason or '',
                'by': self.user.username,
                'at': timezone.now().isoformat(),
                'sessions_shifted': shifted,
                'sessions_outside_window': outside,
            })
            training.json_ext = {**(training.json_ext or {}), 'reschedule_log': log}
            training.save(username=self.user.username)
            return {"success": True, "message": _("training.reschedule.success"),
                    "data": model_representation(training)}
        except Exception as exc:
            return output_exception(model_name=self.OBJECT_TYPE.__name__, method="reschedule", exception=exc)

    def _shift_sessions(self, training, was_start):
        """Move dated sessions by the whole-day delta; sessions left outside the
        new window are counted, not blocked. Returns ``(shifted, outside)``."""
        days = (training.start_datetime.date() - was_start.date()).days if was_start else 0
        delta = timedelta(days=days)
        window = (training.start_datetime.date(), training.end_datetime.date())
        shifted = outside = 0
        for session in TrainingSession.objects.filter(training=training, is_deleted=False):
            if not session.session_date:
                continue
            if days:
                session.session_date += delta
                if session.registration_opens_at:
                    session.registration_opens_at += delta
                if session.registration_closes_at:
                    session.registration_closes_at += delta
                session.save(username=self.user.username)
                shifted += 1
            if not window[0] <= session.session_date <= window[1]:
                outside += 1
        return shifted, outside


# ---------------------------------------------------------------------------
# Conflict detection
# ---------------------------------------------------------------------------
ACTIVE_ASSIGNMENT_STATUSES = (AssignmentStatus.ASSIGNED, AssignmentStatus.CONFIRMED)


class ConflictService:
    def __init__(self, user):
        self.user = user

    @check_authentication
    def check(self, *, start, end, training_id=None, venue=None, location_id=None,
              trainer_ids=None, staff_user_ids=None):
        """Return a list of conflict dicts. Hard conflicts block saving."""
        if not TrainingConfig.conflict_check_enabled or not start or not end:
            return []
        hard_types = set(TrainingConfig.conflict_hard_types or [])
        conflicts = []

        overlap = (Training.objects
                   .filter(is_deleted=False, start_datetime__lt=end, end_datetime__gt=start)
                   .exclude(status__in=TERMINAL_STATUSES))
        if training_id:
            overlap = overlap.exclude(id=training_id)

        # VENUE (hard)
        if venue:
            for t in overlap.filter(venue__iexact=venue.strip()):
                conflicts.append(self._mk('VENUE', 'VENUE' in hard_types, t,
                                          subject_label=venue,
                                          subject=_("Venue %(v)s") % {'v': venue}))
        # TRAINER (hard)
        if trainer_ids:
            qs = (TrainingAssignment.objects
                  .filter(is_deleted=False, trainer_id__in=trainer_ids,
                          status__in=ACTIVE_ASSIGNMENT_STATUSES, training__in=overlap)
                  .select_related('trainer', 'training'))
            for a in qs:
                conflicts.append(self._mk('TRAINER', 'TRAINER' in hard_types, a.training,
                                          subject_id=str(a.trainer_id),
                                          subject_label=a.trainer.full_name if a.trainer else None,
                                          subject=_("Trainer %(n)s") % {
                                              'n': a.trainer.full_name if a.trainer else a.trainer_id}))
        # STAFF (hard)
        if staff_user_ids:
            qs = (TrainingAssignment.objects
                  .filter(is_deleted=False, staff_user_id__in=staff_user_ids,
                          status__in=ACTIVE_ASSIGNMENT_STATUSES, training__in=overlap)
                  .select_related('staff_user', 'training'))
            for a in qs:
                label = getattr(a.staff_user, 'username', None)
                conflicts.append(self._mk('STAFF', 'STAFF' in hard_types, a.training,
                                          subject_id=str(a.staff_user_id), subject_label=label,
                                          subject=_("Staff member %(n)s") % {'n': label or a.staff_user_id}))
        # LOCATION / PAA (soft by default)
        if location_id:
            for t in overlap.filter(location_id=location_id):
                conflicts.append(self._mk('LOCATION', 'LOCATION' in hard_types, t,
                                          subject_id=str(location_id),
                                          subject=_("Location")))
        return conflicts

    def check_for_training(self, training):
        """Convenience: conflict-check an existing (saved) Training using its assignments."""
        active = (TrainingAssignment.objects
                  .filter(training=training, is_deleted=False, status__in=ACTIVE_ASSIGNMENT_STATUSES))
        trainer_ids = [a.trainer_id for a in active if a.trainer_id]
        staff_ids = [a.staff_user_id for a in active if a.staff_user_id]
        return self.check(start=training.start_datetime, end=training.end_datetime,
                          training_id=training.id, venue=training.venue,
                          location_id=training.location_id,
                          trainer_ids=trainer_ids or None, staff_user_ids=staff_ids or None)

    @staticmethod
    def _mk(ctype, hard, training, subject=None, subject_id=None, subject_label=None):
        when = ConflictService._fmt_window(training)
        message = _("Conflict detected: %(subject)s is already assigned to Training "
                    "%(code)s %(when)s.") % {
                        'subject': subject or ctype, 'code': training.code, 'when': when}
        return {
            'type': ctype, 'hard': bool(hard), 'message': message,
            'conflicting_training_id': str(training.id),
            'conflicting_training_code': training.code,
            'subject_id': subject_id, 'subject_label': subject_label,
        }

    @staticmethod
    def _fmt_window(training):
        # localtime() raises on naive datetimes, and USE_TZ=False makes every one of these naive.
        def local(value):
            return timezone.localtime(value) if timezone.is_aware(value) else value

        try:
            s = local(training.start_datetime)
            e = local(training.end_datetime)
            if s.date() == e.date():
                return _("from %(s)s to %(e)s on %(d)s") % {
                    's': s.strftime('%H:%M'), 'e': e.strftime('%H:%M'), 'd': s.strftime('%Y-%m-%d')}
            return _("from %(s)s to %(e)s") % {
                's': s.strftime('%Y-%m-%d %H:%M'), 'e': e.strftime('%Y-%m-%d %H:%M')}
        except Exception:
            return ""


# ---------------------------------------------------------------------------
# Dashboard summary 
# ---------------------------------------------------------------------------
class TrainingSummaryService:
    def __init__(self, user):
        self.user = user

    @check_authentication
    def get_summary(self, *, date_from=None, date_to=None, location_id=None):
        now = timezone.now()
        week_start = (now - timedelta(days=now.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)
        week_end = week_start + timedelta(days=7)

        qs = Training.objects.filter(is_deleted=False)
        if location_id:
            qs = qs.filter(location_id=location_id)
        if date_from:
            qs = qs.filter(start_datetime__gte=date_from)
        if date_to:
            qs = qs.filter(start_datetime__lte=date_to)

        def count(**f):
            return qs.filter(**f).count()

        by_status = list(qs.values('status').order_by('status').annotate(count=Count('id')))
        by_category = list(qs.values('category_id', 'category__name')
                           .order_by('category__name')
                           .annotate(count=Count('id')))

        return {
            'total_trainings': qs.count(),
            'trainings_this_week': count(start_datetime__gte=week_start, start_datetime__lt=week_end),
            'upcoming_trainings': count(start_datetime__gte=now,
                                        status__in=[TrainingStatus.SCHEDULED, TrainingStatus.APPROVED]),
            'ongoing_trainings': count(status=TrainingStatus.ONGOING),
            'completed_trainings': count(status=TrainingStatus.COMPLETED),
            'cancelled_trainings': count(status=TrainingStatus.CANCELLED),
            'active_trainers': TrainerProfile.objects.filter(is_deleted=False, is_active=True).count(),
            'by_status': [{'status': r['status'], 'count': r['count']} for r in by_status],
            'by_category': [{'category_id': str(r['category_id']) if r['category_id'] else None,
                             'category_name': r['category__name'], 'count': r['count']} for r in by_category],
        }
