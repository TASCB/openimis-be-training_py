"""Service layer for the Training module.

Per-entity CRUD services extend ``core.services.BaseService`` (uniform
``{success, data, error}`` contract, service signals).  ``ConflictService`` and
``TrainingSummaryService`` are standalone read services.  Status transitions live in
``TrainingService.transition`` — the single chokepoint that a Phase-2 maker-checker
flow can later wrap (see docs/06-workflow-status.md).
"""
import logging
from datetime import timedelta

from django.db import transaction
from django.db.models import Count
from django.utils import timezone
from django.utils.translation import gettext as _

from core.services import BaseService
from core.services.utils import output_exception, model_representation, check_authentication
from core.signals import register_service_signal

from training.apps import TrainingConfig
from training.models import (
    Training, TrainingCategory, TrainerProfile,
    TrainingAssignment, TrainingParticipant, TrainingMaterial, TrainingEvidence,
    TrainingSession, TrainingStatus, TERMINAL_STATUSES, AssignmentStatus,
    ActivityCodeSequence,
)
from training.validations import (
    TrainingValidation, TrainingCategoryValidation, TrainerProfileValidation,
    TrainingAssignmentValidation, TrainingParticipantValidation,
    TrainingMaterialValidation, TrainingEvidenceValidation, TrainingSessionValidation,
)

logger = logging.getLogger(__name__)
TRAINING_CODE_PREFIX = 'TRN'

TRAINER_CODE_SEQUENCE = 'TRAINER'


# ---------------------------------------------------------------------------
# CRUD services
# ---------------------------------------------------------------------------
class TrainingCategoryService(BaseService):
    OBJECT_TYPE = TrainingCategory

    def __init__(self, user, validation_class=TrainingCategoryValidation):
        super().__init__(user, validation_class)

    @register_service_signal('training_category_service.create')
    def create(self, obj_data):
        return super().create(obj_data)

    @register_service_signal('training_category_service.update')
    def update(self, obj_data):
        return super().update(obj_data)

    @register_service_signal('training_category_service.delete')
    def delete(self, obj_data):
        return super().delete(obj_data)


class TrainerProfileService(BaseService):
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
        return super().update(obj_data)

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


class TrainingService(BaseService):
    OBJECT_TYPE = Training

    def __init__(self, user, validation_class=TrainingValidation):
        super().__init__(user, validation_class)

    @register_service_signal('training_service.create')
    @transaction.atomic
    def create(self, obj_data):
        self._assign_code(obj_data)
        return super().create(obj_data)

    @register_service_signal('training_service.update')
    def update(self, obj_data):
        return super().update(obj_data)

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
        try:
            s = timezone.localtime(training.start_datetime)
            e = timezone.localtime(training.end_datetime)
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
