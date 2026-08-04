"""GraphQL mutations for the Training module.

CRUD mutations follow the openIMIS pattern (``BaseHistoryModel*MutationMixin +
BaseMutation`` with custom ``_validate_mutation`` / ``_mutate``), journaling through
the per-entity ``*Mutation`` link tables.  Training create/update additionally run
hard-conflict enforcement (see docs/05-conflict-detection.md), and status-workflow
mutations delegate to ``TrainingService.transition``.
"""
import graphene
from django.core.exceptions import PermissionDenied
from django.utils.translation import gettext as _

from core.gql.gql_mutations.base_mutation import (
    BaseHistoryModelCreateMutationMixin, BaseHistoryModelUpdateMutationMixin,
    BaseHistoryModelDeleteMutationMixin, BaseMutation,
)
from core.schema import OpenIMISMutation

from training.apps import TrainingConfig
from training.models import (
    Training, TrainingCategory, TrainerProfile,
    TrainingAssignment, TrainingParticipant, TrainingMaterial, TrainingEvidence,
    TrainingSession,
    ParticipantCategory, ParticipantCategoryMutation,
    JobTitle, JobTitleMutation,
    TrainingMutation, TrainingCategoryMutation, TrainerProfileMutation,
    TrainingAssignmentMutation, TrainingParticipantMutation, TrainingSessionMutation,
    TrainingStatus, TrainerType, AssignmentRole, AssignmentStatus,
    AttendanceStatus, Gender,
)
from training.services import (
    TrainingService, TrainingCategoryService, TrainerProfileService,
    TrainingAssignmentService, TrainingParticipantService, TrainingSessionService,
    TrainingMaterialService, TrainingEvidenceService, ConflictService,
    ParticipantCategoryService, JobTitleService,
)


def _gql_enum(name, choices_cls):
    return graphene.Enum(name, [(c.value, c.value) for c in choices_cls])


TrainingStatusEnum = _gql_enum('TrainingStatusInput', TrainingStatus)
TrainerTypeEnum = _gql_enum('TrainerTypeInput', TrainerType)
AssignmentRoleEnum = _gql_enum('AssignmentRoleInput', AssignmentRole)
AssignmentStatusEnum = _gql_enum('AssignmentStatusInput', AssignmentStatus)
AttendanceStatusEnum = _gql_enum('AttendanceStatusInput', AttendanceStatus)
GenderEnum = _gql_enum('GenderInput', Gender)


def _strip_client(data):
    data.pop('client_mutation_id', None)
    data.pop('client_mutation_label', None)


def _journal(mutation_model, fk_name, user, client_mutation_id, obj):
    if client_mutation_id and obj is not None:
        mutation_model.object_mutated(user, client_mutation_id=client_mutation_id, **{fk_name: obj})


# ===========================================================================
# Training
# ===========================================================================
class CreateTrainingInput(OpenIMISMutation.Input):
    code = graphene.String(required=False)
    title = graphene.String(required=True)
    description = graphene.String(required=False)
    category_id = graphene.UUID(required=False)
    start_datetime = graphene.DateTime(required=True)
    end_datetime = graphene.DateTime(required=True)
    venue = graphene.String(required=False)
    location_id = graphene.Int(required=False)
    paa_reference = graphene.String(required=False)
    status = graphene.Field(TrainingStatusEnum, required=False)
    expected_participants = graphene.Int(required=False)
    learning_outcomes = graphene.List(graphene.String, required=False)
    intended_for = graphene.List(graphene.String, required=False)
    # conflict pre-check helpers (not persisted)
    ignore_conflicts = graphene.Boolean(required=False)
    conflict_trainer_ids = graphene.List(graphene.UUID, required=False)
    conflict_staff_user_ids = graphene.List(graphene.UUID, required=False)


class UpdateTrainingInput(CreateTrainingInput):
    id = graphene.UUID(required=True)


def _enforce_training_conflicts(user, data):
    """Return an error dict if a HARD conflict blocks the save, else None.
    Pops the non-persisted conflict helper keys from ``data`` in all cases."""
    data.pop('ignore_conflicts', False)  # accepted but never honoured — hard conflicts always block
    trainer_ids = data.pop('conflict_trainer_ids', None)
    staff_ids = data.pop('conflict_staff_user_ids', None)
    if not TrainingConfig.conflict_check_enabled:
        return None
    conflicts = ConflictService(user).check(
        start=data.get('start_datetime'), end=data.get('end_datetime'),
        training_id=data.get('id'), venue=data.get('venue'),
        location_id=data.get('location_id'),
        trainer_ids=trainer_ids, staff_user_ids=staff_ids,
    )
    hard = [c for c in conflicts if c['hard']]
    if hard:  # hard conflicts always block, regardless of ignore_conflicts
        return {"success": False, "message": _("training.mutation.hard_conflict"),
                "detail": " | ".join(c['message'] for c in hard)}
    return None


class CreateTrainingMutation(BaseHistoryModelCreateMutationMixin, BaseMutation):
    _mutation_module = "training"
    _mutation_class = "CreateTrainingMutation"

    @classmethod
    def _validate_mutation(cls, user, **data):
        super()._validate_mutation(user, **data)
        if not user.has_perms(TrainingConfig.gql_training_create_perms):
            raise PermissionDenied(_("unauthorized"))

    @classmethod
    def _mutate(cls, user, **data):
        client_mutation_id = data.get('client_mutation_id')
        _strip_client(data)
        conflict_error = _enforce_training_conflicts(user, data)
        if conflict_error:
            return conflict_error
        res = TrainingService(user).create(data)
        if res['success']:
            obj = Training.objects.get(id=res['data']['id'])
            _journal(TrainingMutation, 'training', user, client_mutation_id, obj)
        return res if not res['success'] else None

    class Input(CreateTrainingInput):
        pass


class UpdateTrainingMutation(BaseHistoryModelUpdateMutationMixin, BaseMutation):
    _mutation_module = "training"
    _mutation_class = "UpdateTrainingMutation"
    _model = Training

    @classmethod
    def _validate_mutation(cls, user, **data):
        super()._validate_mutation(user, **data)
        if not user.has_perms(TrainingConfig.gql_training_update_perms):
            raise PermissionDenied(_("unauthorized"))

    @classmethod
    def _mutate(cls, user, **data):
        client_mutation_id = data.get('client_mutation_id')
        _strip_client(data)
        conflict_error = _enforce_training_conflicts(user, data)
        if conflict_error:
            return conflict_error
        res = TrainingService(user).update(data)
        if res['success']:
            obj = Training.objects.get(id=data['id'])
            _journal(TrainingMutation, 'training', user, client_mutation_id, obj)
        return res if not res['success'] else None

    class Input(UpdateTrainingInput):
        pass


class DeleteTrainingMutation(BaseHistoryModelDeleteMutationMixin, BaseMutation):
    _mutation_module = "training"
    _mutation_class = "DeleteTrainingMutation"
    _model = Training

    @classmethod
    def _validate_mutation(cls, user, **data):
        super()._validate_mutation(user, **data)
        if not user.has_perms(TrainingConfig.gql_training_delete_perms):
            raise PermissionDenied(_("unauthorized"))

    @classmethod
    def _mutate(cls, user, **data):
        _strip_client(data)
        service = TrainingService(user)
        for identifier in data.get('ids', []):
            res = service.delete({'id': identifier})
            if not res['success']:
                return res
        return None

    class Input(OpenIMISMutation.Input):
        ids = graphene.List(graphene.UUID)


# --- status workflow -------------------------------------------------------
class TransitionInput(OpenIMISMutation.Input):
    id = graphene.UUID(required=True)
    reason = graphene.String(required=False)


class _TransitionLogic:
    """Plain (non-graphene) mixin shared by the status-workflow mutations.

    Must NOT be a graphene mutation itself — subclassing a processed graphene
    mutation that already carries an ``Input`` triggers an InputObjectType MRO error.
    """
    _action = None

    @classmethod
    def _validate_mutation(cls, user, **data):
        perms = (TrainingConfig.gql_training_approve_perms
                 if cls._action in ('approve', 'reject')
                 else TrainingConfig.gql_training_update_perms)
        if not user.has_perms(perms):
            raise PermissionDenied(_("unauthorized"))

    @classmethod
    def _mutate(cls, user, **data):
        _strip_client(data)
        res = TrainingService(user).transition(
            data.get('id'), cls._action, reason=data.get('reason'))
        return res if not res['success'] else None


class SubmitTrainingMutation(_TransitionLogic, BaseMutation):
    _mutation_module = "training"
    _mutation_class = "SubmitTrainingMutation"
    _action = 'submit'

    class Input(TransitionInput):
        pass


class ApproveTrainingMutation(_TransitionLogic, BaseMutation):
    _mutation_module = "training"
    _mutation_class = "ApproveTrainingMutation"
    _action = 'approve'

    class Input(TransitionInput):
        pass


class RejectTrainingMutation(_TransitionLogic, BaseMutation):
    _mutation_module = "training"
    _mutation_class = "RejectTrainingMutation"
    _action = 'reject'

    class Input(TransitionInput):
        pass


class ScheduleTrainingMutation(_TransitionLogic, BaseMutation):
    _mutation_module = "training"
    _mutation_class = "ScheduleTrainingMutation"
    _action = 'schedule'

    class Input(TransitionInput):
        pass


class StartTrainingMutation(_TransitionLogic, BaseMutation):
    _mutation_module = "training"
    _mutation_class = "StartTrainingMutation"
    _action = 'start'

    class Input(TransitionInput):
        pass


class CompleteTrainingMutation(_TransitionLogic, BaseMutation):
    _mutation_module = "training"
    _mutation_class = "CompleteTrainingMutation"
    _action = 'complete'

    class Input(TransitionInput):
        pass


class CancelTrainingMutation(_TransitionLogic, BaseMutation):
    _mutation_module = "training"
    _mutation_class = "CancelTrainingMutation"
    _action = 'cancel'

    class Input(TransitionInput):
        pass


class CloseTrainingMutation(_TransitionLogic, BaseMutation):
    _mutation_module = "training"
    _mutation_class = "CloseTrainingMutation"
    _action = 'close'

    class Input(TransitionInput):
        pass


class RescheduleTrainingInput(OpenIMISMutation.Input):
    id = graphene.UUID(required=True)
    start_datetime = graphene.DateTime(required=True)
    end_datetime = graphene.DateTime(required=True)
    reason = graphene.String(required=False)


class RescheduleTrainingMutation(BaseMutation):
    """Move a scheduled training to a new date window (status unchanged)."""
    _mutation_module = "training"
    _mutation_class = "RescheduleTrainingMutation"

    @classmethod
    def _validate_mutation(cls, user, **data):
        if not user.has_perms(TrainingConfig.gql_training_update_perms):
            raise PermissionDenied(_("unauthorized"))

    @classmethod
    def _mutate(cls, user, **data):
        client_mutation_id = data.get('client_mutation_id')
        _strip_client(data)
        res = TrainingService(user).reschedule(
            data.get('id'), data.get('start_datetime'), data.get('end_datetime'),
            reason=data.get('reason'))
        if res['success']:
            _journal(TrainingMutation, 'training', user, client_mutation_id,
                     Training.objects.filter(id=data['id']).first())
        return res if not res['success'] else None

    class Input(RescheduleTrainingInput):
        pass


# ===========================================================================
# CRUD for the simpler entities — explicit  Helper keeps the bodies short.
# ===========================================================================
def _crud_create(user, data, service_cls, model, mutation_model, fk_name):
    client_mutation_id = data.get('client_mutation_id')
    _strip_client(data)
    res = service_cls(user).create(data)
    if res['success']:
        obj = model.objects.get(id=res['data']['id'])
        _journal(mutation_model, fk_name, user, client_mutation_id, obj)
    return res if not res['success'] else None


def _crud_update(user, data, service_cls, model, mutation_model, fk_name):
    client_mutation_id = data.get('client_mutation_id')
    _strip_client(data)
    res = service_cls(user).update(data)
    if res['success']:
        obj = model.objects.get(id=data['id'])
        _journal(mutation_model, fk_name, user, client_mutation_id, obj)
    return res if not res['success'] else None


def _crud_delete(user, data, service_cls):
    _strip_client(data)
    service = service_cls(user)
    for identifier in data.get('ids', []):
        res = service.delete({'id': identifier})
        if not res['success']:
            return res
    return None


# --- TrainingCategory ------------------------------------------------------
class CreateTrainingCategoryInput(OpenIMISMutation.Input):
    code = graphene.String(required=True)
    name = graphene.String(required=True)
    description = graphene.String(required=False)
    is_active = graphene.Boolean(required=False)


class CreateTrainingCategoryMutation(BaseHistoryModelCreateMutationMixin, BaseMutation):
    _mutation_module = "training"
    _mutation_class = "CreateTrainingCategoryMutation"

    @classmethod
    def _validate_mutation(cls, user, **data):
        super()._validate_mutation(user, **data)
        if not user.has_perms(TrainingConfig.gql_training_category_create_perms):
            raise PermissionDenied(_("unauthorized"))

    @classmethod
    def _mutate(cls, user, **data):
        return _crud_create(user, data, TrainingCategoryService, TrainingCategory,
                            TrainingCategoryMutation, 'training_category')

    class Input(CreateTrainingCategoryInput):
        pass


class UpdateTrainingCategoryMutation(BaseHistoryModelUpdateMutationMixin, BaseMutation):
    _mutation_module = "training"
    _mutation_class = "UpdateTrainingCategoryMutation"
    _model = TrainingCategory

    @classmethod
    def _validate_mutation(cls, user, **data):
        super()._validate_mutation(user, **data)
        if not user.has_perms(TrainingConfig.gql_training_category_update_perms):
            raise PermissionDenied(_("unauthorized"))

    @classmethod
    def _mutate(cls, user, **data):
        return _crud_update(user, data, TrainingCategoryService, TrainingCategory,
                            TrainingCategoryMutation, 'training_category')

    class Input(CreateTrainingCategoryInput):
        id = graphene.UUID(required=True)


class DeleteTrainingCategoryMutation(BaseHistoryModelDeleteMutationMixin, BaseMutation):
    _mutation_module = "training"
    _mutation_class = "DeleteTrainingCategoryMutation"
    _model = TrainingCategory

    @classmethod
    def _validate_mutation(cls, user, **data):
        super()._validate_mutation(user, **data)
        if not user.has_perms(TrainingConfig.gql_training_category_delete_perms):
            raise PermissionDenied(_("unauthorized"))

    @classmethod
    def _mutate(cls, user, **data):
        return _crud_delete(user, data, TrainingCategoryService)

    class Input(OpenIMISMutation.Input):
        ids = graphene.List(graphene.UUID)


# --- JobTitle (the RBAC catalogue's 63 substantive titles) -------------------
class CreateJobTitleInput(OpenIMISMutation.Input):
    code = graphene.String(required=True)
    name = graphene.String(required=True)
    sn = graphene.Int(required=False)
    user_group_id = graphene.UUID(required=False)
    is_active = graphene.Boolean(required=False)


class CreateJobTitleMutation(BaseHistoryModelCreateMutationMixin, BaseMutation):
    _mutation_module = "training"
    _mutation_class = "CreateJobTitleMutation"

    @classmethod
    def _validate_mutation(cls, user, **data):
        super()._validate_mutation(user, **data)
        if not user.has_perms(TrainingConfig.gql_job_title_create_perms):
            raise PermissionDenied(_("unauthorized"))

    @classmethod
    def _mutate(cls, user, **data):
        return _crud_create(user, data, JobTitleService, JobTitle,
                            JobTitleMutation, 'job_title')

    class Input(CreateJobTitleInput):
        pass


class UpdateJobTitleMutation(BaseHistoryModelUpdateMutationMixin, BaseMutation):
    _mutation_module = "training"
    _mutation_class = "UpdateJobTitleMutation"
    _model = JobTitle

    @classmethod
    def _validate_mutation(cls, user, **data):
        super()._validate_mutation(user, **data)
        if not user.has_perms(TrainingConfig.gql_job_title_update_perms):
            raise PermissionDenied(_("unauthorized"))

    @classmethod
    def _mutate(cls, user, **data):
        return _crud_update(user, data, JobTitleService, JobTitle,
                            JobTitleMutation, 'job_title')

    class Input(CreateJobTitleInput):
        id = graphene.UUID(required=True)
        # Optional on update so a rename does not have to resend the structural code.
        code = graphene.String(required=False)
        name = graphene.String(required=False)


class DeleteJobTitleMutation(BaseHistoryModelDeleteMutationMixin, BaseMutation):
    _mutation_module = "training"
    _mutation_class = "DeleteJobTitleMutation"
    _model = JobTitle

    @classmethod
    def _validate_mutation(cls, user, **data):
        super()._validate_mutation(user, **data)
        if not user.has_perms(TrainingConfig.gql_job_title_delete_perms):
            raise PermissionDenied(_("unauthorized"))

    @classmethod
    def _mutate(cls, user, **data):
        return _crud_delete(user, data, JobTitleService)

    class Input(OpenIMISMutation.Input):
        ids = graphene.List(graphene.UUID)


# --- ParticipantCategory (who attends; replaces the ParticipantType enum) ----
class CreateParticipantCategoryInput(OpenIMISMutation.Input):
    code = graphene.String(required=True)
    name = graphene.String(required=True)
    description = graphene.String(required=False)
    sequence = graphene.Int(required=False)
    is_active = graphene.Boolean(required=False)


class CreateParticipantCategoryMutation(BaseHistoryModelCreateMutationMixin, BaseMutation):
    _mutation_module = "training"
    _mutation_class = "CreateParticipantCategoryMutation"

    @classmethod
    def _validate_mutation(cls, user, **data):
        super()._validate_mutation(user, **data)
        if not user.has_perms(TrainingConfig.gql_participant_category_create_perms):
            raise PermissionDenied(_("unauthorized"))

    @classmethod
    def _mutate(cls, user, **data):
        return _crud_create(user, data, ParticipantCategoryService, ParticipantCategory,
                            ParticipantCategoryMutation, 'participant_category')

    class Input(CreateParticipantCategoryInput):
        pass


class UpdateParticipantCategoryMutation(BaseHistoryModelUpdateMutationMixin, BaseMutation):
    _mutation_module = "training"
    _mutation_class = "UpdateParticipantCategoryMutation"
    _model = ParticipantCategory

    @classmethod
    def _validate_mutation(cls, user, **data):
        super()._validate_mutation(user, **data)
        if not user.has_perms(TrainingConfig.gql_participant_category_update_perms):
            raise PermissionDenied(_("unauthorized"))

    @classmethod
    def _mutate(cls, user, **data):
        return _crud_update(user, data, ParticipantCategoryService, ParticipantCategory,
                            ParticipantCategoryMutation, 'participant_category')

    class Input(CreateParticipantCategoryInput):
        id = graphene.UUID(required=True)
        # A rename is fine, but code/name stay required on create — the code is the stable
        # key participant rows and reports join on.
        code = graphene.String(required=False)
        name = graphene.String(required=False)


class DeleteParticipantCategoryMutation(BaseHistoryModelDeleteMutationMixin, BaseMutation):
    _mutation_module = "training"
    _mutation_class = "DeleteParticipantCategoryMutation"
    _model = ParticipantCategory

    @classmethod
    def _validate_mutation(cls, user, **data):
        super()._validate_mutation(user, **data)
        if not user.has_perms(TrainingConfig.gql_participant_category_delete_perms):
            raise PermissionDenied(_("unauthorized"))

    @classmethod
    def _mutate(cls, user, **data):
        return _crud_delete(user, data, ParticipantCategoryService)

    class Input(OpenIMISMutation.Input):
        ids = graphene.List(graphene.UUID)


# --- TrainerProfile --------------------------------------------------------
class CreateTrainerProfileInput(OpenIMISMutation.Input):
    code = graphene.String(required=False)  # auto-generated by TrainerProfileService on create
    full_name = graphene.String(required=True)
    gender = graphene.Field(GenderEnum, required=False)
    position_id = graphene.UUID(required=False)
    email = graphene.String(required=False)
    phone = graphene.String(required=False)
    organization = graphene.String(required=False)
    trainer_type = graphene.Field(TrainerTypeEnum, required=False)
    specialization = graphene.String(required=False)
    bio = graphene.String(required=False)
    staff_user_id = graphene.UUID(required=False)
    is_active = graphene.Boolean(required=False)


class CreateTrainerProfileMutation(BaseHistoryModelCreateMutationMixin, BaseMutation):
    _mutation_module = "training"
    _mutation_class = "CreateTrainerProfileMutation"

    @classmethod
    def _validate_mutation(cls, user, **data):
        super()._validate_mutation(user, **data)
        if not user.has_perms(TrainingConfig.gql_trainer_create_perms):
            raise PermissionDenied(_("unauthorized"))

    @classmethod
    def _mutate(cls, user, **data):
        return _crud_create(user, data, TrainerProfileService, TrainerProfile,
                            TrainerProfileMutation, 'trainer_profile')

    class Input(CreateTrainerProfileInput):
        pass


class UpdateTrainerProfileMutation(BaseHistoryModelUpdateMutationMixin, BaseMutation):
    _mutation_module = "training"
    _mutation_class = "UpdateTrainerProfileMutation"
    _model = TrainerProfile

    @classmethod
    def _validate_mutation(cls, user, **data):
        super()._validate_mutation(user, **data)
        if not user.has_perms(TrainingConfig.gql_trainer_update_perms):
            raise PermissionDenied(_("unauthorized"))

    @classmethod
    def _mutate(cls, user, **data):
        return _crud_update(user, data, TrainerProfileService, TrainerProfile,
                            TrainerProfileMutation, 'trainer_profile')

    class Input(CreateTrainerProfileInput):
        id = graphene.UUID(required=True)


class DeleteTrainerProfileMutation(BaseHistoryModelDeleteMutationMixin, BaseMutation):
    _mutation_module = "training"
    _mutation_class = "DeleteTrainerProfileMutation"
    _model = TrainerProfile

    @classmethod
    def _validate_mutation(cls, user, **data):
        super()._validate_mutation(user, **data)
        if not user.has_perms(TrainingConfig.gql_trainer_delete_perms):
            raise PermissionDenied(_("unauthorized"))

    @classmethod
    def _mutate(cls, user, **data):
        return _crud_delete(user, data, TrainerProfileService)

    class Input(OpenIMISMutation.Input):
        ids = graphene.List(graphene.UUID)


# --- TrainingAssignment ----------------------------------------------------
class CreateTrainingAssignmentInput(OpenIMISMutation.Input):
    training_id = graphene.UUID(required=True)
    trainer_id = graphene.UUID(required=False)
    staff_user_id = graphene.UUID(required=False)
    role = graphene.Field(AssignmentRoleEnum, required=False)
    status = graphene.Field(AssignmentStatusEnum, required=False)
    notes = graphene.String(required=False)


class CreateTrainingAssignmentMutation(BaseHistoryModelCreateMutationMixin, BaseMutation):
    _mutation_module = "training"
    _mutation_class = "CreateTrainingAssignmentMutation"

    @classmethod
    def _validate_mutation(cls, user, **data):
        super()._validate_mutation(user, **data)
        if not user.has_perms(TrainingConfig.gql_assignment_create_perms):
            raise PermissionDenied(_("unauthorized"))

    @classmethod
    def _mutate(cls, user, **data):
        return _crud_create(user, data, TrainingAssignmentService, TrainingAssignment,
                            TrainingAssignmentMutation, 'training_assignment')

    class Input(CreateTrainingAssignmentInput):
        pass


class UpdateTrainingAssignmentMutation(BaseHistoryModelUpdateMutationMixin, BaseMutation):
    _mutation_module = "training"
    _mutation_class = "UpdateTrainingAssignmentMutation"
    _model = TrainingAssignment

    @classmethod
    def _validate_mutation(cls, user, **data):
        super()._validate_mutation(user, **data)
        if not user.has_perms(TrainingConfig.gql_assignment_update_perms):
            raise PermissionDenied(_("unauthorized"))

    @classmethod
    def _mutate(cls, user, **data):
        return _crud_update(user, data, TrainingAssignmentService, TrainingAssignment,
                            TrainingAssignmentMutation, 'training_assignment')

    class Input(CreateTrainingAssignmentInput):
        id = graphene.UUID(required=True)


class DeleteTrainingAssignmentMutation(BaseHistoryModelDeleteMutationMixin, BaseMutation):
    _mutation_module = "training"
    _mutation_class = "DeleteTrainingAssignmentMutation"
    _model = TrainingAssignment

    @classmethod
    def _validate_mutation(cls, user, **data):
        super()._validate_mutation(user, **data)
        if not user.has_perms(TrainingConfig.gql_assignment_delete_perms):
            raise PermissionDenied(_("unauthorized"))

    @classmethod
    def _mutate(cls, user, **data):
        return _crud_delete(user, data, TrainingAssignmentService)

    class Input(OpenIMISMutation.Input):
        ids = graphene.List(graphene.UUID)


# --- TrainingParticipant ---------------------------------------------------
class CreateTrainingParticipantInput(OpenIMISMutation.Input):
    training_id = graphene.UUID(required=True)
    # Null = a whole-training entry. Set = the attendance register for that one session,
    # which is what the per-session Community Session Report reads.
    session_id = graphene.UUID(required=False)
    full_name = graphene.String(required=True)
    gender = graphene.Field(GenderEnum, required=False)
    phone = graphene.String(required=False)
    email = graphene.String(required=False)
    organization = graphene.String(required=False)
    title = graphene.String(required=False)
    category_id = graphene.UUID(required=False)
    internal_user_id = graphene.UUID(required=False)
    location_id = graphene.Int(required=False)
    attendance_status = graphene.Field(AttendanceStatusEnum, required=False)
    attendance_remarks = graphene.String(required=False)


class CreateTrainingParticipantMutation(BaseHistoryModelCreateMutationMixin, BaseMutation):
    _mutation_module = "training"
    _mutation_class = "CreateTrainingParticipantMutation"

    @classmethod
    def _validate_mutation(cls, user, **data):
        super()._validate_mutation(user, **data)
        if not user.has_perms(TrainingConfig.gql_participant_create_perms):
            raise PermissionDenied(_("unauthorized"))

    @classmethod
    def _mutate(cls, user, **data):
        return _crud_create(user, data, TrainingParticipantService, TrainingParticipant,
                            TrainingParticipantMutation, 'training_participant')

    class Input(CreateTrainingParticipantInput):
        pass


class UpdateTrainingParticipantMutation(BaseHistoryModelUpdateMutationMixin, BaseMutation):
    _mutation_module = "training"
    _mutation_class = "UpdateTrainingParticipantMutation"
    _model = TrainingParticipant

    @classmethod
    def _validate_mutation(cls, user, **data):
        super()._validate_mutation(user, **data)
        if not user.has_perms(TrainingConfig.gql_participant_update_perms):
            raise PermissionDenied(_("unauthorized"))

    @classmethod
    def _mutate(cls, user, **data):
        return _crud_update(user, data, TrainingParticipantService, TrainingParticipant,
                            TrainingParticipantMutation, 'training_participant')

    class Input(CreateTrainingParticipantInput):
        id = graphene.UUID(required=True)
        # The participants panel edits one cell at a time (gender, attendance), so a
        # partial update must not have to resend the whole row.
        training_id = graphene.UUID(required=False)
        full_name = graphene.String(required=False)


class DeleteTrainingParticipantMutation(BaseHistoryModelDeleteMutationMixin, BaseMutation):
    _mutation_module = "training"
    _mutation_class = "DeleteTrainingParticipantMutation"
    _model = TrainingParticipant

    @classmethod
    def _validate_mutation(cls, user, **data):
        super()._validate_mutation(user, **data)
        if not user.has_perms(TrainingConfig.gql_participant_delete_perms):
            raise PermissionDenied(_("unauthorized"))

    @classmethod
    def _mutate(cls, user, **data):
        return _crud_delete(user, data, TrainingParticipantService)

    class Input(OpenIMISMutation.Input):
        ids = graphene.List(graphene.UUID)


# --- TrainingSession (sessions/days + QR self check-in) -----------------------
class CreateTrainingSessionInput(OpenIMISMutation.Input):
    training_id = graphene.UUID(required=True)
    title = graphene.String(required=True)
    session_date = graphene.Date(required=False)
    start_time = graphene.Time(required=False)
    end_time = graphene.Time(required=False)
    sequence = graphene.Int(required=False)
    venue = graphene.String(required=False)
    registration_open = graphene.Boolean(required=False)
    registration_opens_at = graphene.DateTime(required=False)
    registration_closes_at = graphene.DateTime(required=False)


class CreateTrainingSessionMutation(BaseHistoryModelCreateMutationMixin, BaseMutation):
    _mutation_module = "training"
    _mutation_class = "CreateTrainingSessionMutation"

    @classmethod
    def _validate_mutation(cls, user, **data):
        super()._validate_mutation(user, **data)
        if not user.has_perms(TrainingConfig.gql_session_create_perms):
            raise PermissionDenied(_("unauthorized"))

    @classmethod
    def _mutate(cls, user, **data):
        return _crud_create(user, data, TrainingSessionService, TrainingSession,
                            TrainingSessionMutation, 'training_session')

    class Input(CreateTrainingSessionInput):
        pass


class UpdateTrainingSessionMutation(BaseHistoryModelUpdateMutationMixin, BaseMutation):
    _mutation_module = "training"
    _mutation_class = "UpdateTrainingSessionMutation"
    _model = TrainingSession

    @classmethod
    def _validate_mutation(cls, user, **data):
        super()._validate_mutation(user, **data)
        if not user.has_perms(TrainingConfig.gql_session_update_perms):
            raise PermissionDenied(_("unauthorized"))

    @classmethod
    def _mutate(cls, user, **data):
        return _crud_update(user, data, TrainingSessionService, TrainingSession,
                            TrainingSessionMutation, 'training_session')

    class Input(CreateTrainingSessionInput):
        id = graphene.UUID(required=True)
        # partial updates (e.g. toggling registration) must not require title
        title = graphene.String(required=False)


class DeleteTrainingSessionMutation(BaseHistoryModelDeleteMutationMixin, BaseMutation):
    _mutation_module = "training"
    _mutation_class = "DeleteTrainingSessionMutation"
    _model = TrainingSession

    @classmethod
    def _validate_mutation(cls, user, **data):
        super()._validate_mutation(user, **data)
        if not user.has_perms(TrainingConfig.gql_session_delete_perms):
            raise PermissionDenied(_("unauthorized"))

    @classmethod
    def _mutate(cls, user, **data):
        return _crud_delete(user, data, TrainingSessionService)

    class Input(OpenIMISMutation.Input):
        ids = graphene.List(graphene.UUID)


# --- TrainingMaterial / TrainingEvidence: delete via GraphQL (create = DRF upload)
class DeleteTrainingMaterialMutation(BaseHistoryModelDeleteMutationMixin, BaseMutation):
    _mutation_module = "training"
    _mutation_class = "DeleteTrainingMaterialMutation"
    _model = TrainingMaterial

    @classmethod
    def _validate_mutation(cls, user, **data):
        super()._validate_mutation(user, **data)
        if not user.has_perms(TrainingConfig.gql_material_delete_perms):
            raise PermissionDenied(_("unauthorized"))

    @classmethod
    def _mutate(cls, user, **data):
        _strip_client(data)
        service = TrainingMaterialService(user)
        for identifier in data.get('ids', []):
            res = service.delete({'id': identifier})
            if not res['success']:
                return res
        return None

    class Input(OpenIMISMutation.Input):
        ids = graphene.List(graphene.UUID)


class DeleteTrainingEvidenceMutation(BaseHistoryModelDeleteMutationMixin, BaseMutation):
    _mutation_module = "training"
    _mutation_class = "DeleteTrainingEvidenceMutation"
    _model = TrainingEvidence

    @classmethod
    def _validate_mutation(cls, user, **data):
        super()._validate_mutation(user, **data)
        if not user.has_perms(TrainingConfig.gql_evidence_delete_perms):
            raise PermissionDenied(_("unauthorized"))

    @classmethod
    def _mutate(cls, user, **data):
        _strip_client(data)
        service = TrainingEvidenceService(user)
        for identifier in data.get('ids', []):
            res = service.delete({'id': identifier})
            if not res['success']:
                return res
        return None

    class Input(OpenIMISMutation.Input):
        ids = graphene.List(graphene.UUID)
