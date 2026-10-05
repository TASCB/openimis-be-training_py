"""GraphQL schema (Query + Mutation) for the Training module.

Concatenated into the global openIMIS schema by the assembly (same mechanism as
``payment_cycle``).
"""
import graphene
import graphene_django_optimizer as gql_optimizer
from django.contrib.auth.models import AnonymousUser
from django.core.exceptions import PermissionDenied
from django.db.models import Q
from django.utils.translation import gettext as _

from core.schema import OrderedDjangoFilterConnectionField
from core.services import wait_for_mutation
from location.models import Location

from training.apps import TrainingConfig
from training.models import (
    Training, TrainingCategory, TrainerProfile,
    TrainingAssignment, TrainingParticipant, TrainingMaterial, TrainingEvidence,
    TrainingSession, ParticipantCategory, JobTitle, StaffUserGroup, TrainingLevel,
)
from training.gql_queries import (
    JobTitleGQLType, StaffUserGroupGQLType, TrainingLevelGQLType,
    TrainingGQLType, TrainingCategoryGQLType, TrainerProfileGQLType,
    ParticipantCategoryGQLType,
    TrainingAssignmentGQLType, TrainingParticipantGQLType, TrainingSessionGQLType,
    TrainingMaterialGQLType, TrainingEvidenceGQLType,
    TrainingConflictGQLType, TrainingSummaryGQLType,
    StatusCountGQLType, CategoryCountGQLType,
)
from training.services import ConflictService, TrainingSummaryService, resolve_paa_reference
from training.gql_mutations import (
    CreateTrainingMutation, UpdateTrainingMutation, DeleteTrainingMutation,
    SubmitTrainingMutation, ApproveTrainingMutation, RejectTrainingMutation,
    ScheduleTrainingMutation, StartTrainingMutation, CompleteTrainingMutation,
    CancelTrainingMutation, CloseTrainingMutation, RescheduleTrainingMutation,
    CreateTrainingCategoryMutation, UpdateTrainingCategoryMutation, DeleteTrainingCategoryMutation,
    CreateParticipantCategoryMutation, UpdateParticipantCategoryMutation, DeleteParticipantCategoryMutation,
    CreateJobTitleMutation, UpdateJobTitleMutation, DeleteJobTitleMutation,
    CreateTrainingLevelMutation, UpdateTrainingLevelMutation, DeleteTrainingLevelMutation,
    CreateTrainerProfileMutation, UpdateTrainerProfileMutation, DeleteTrainerProfileMutation,
    CreateTrainingAssignmentMutation, UpdateTrainingAssignmentMutation, DeleteTrainingAssignmentMutation,
    CreateTrainingParticipantMutation, UpdateTrainingParticipantMutation, DeleteTrainingParticipantMutation,
    CreateTrainingSessionMutation, UpdateTrainingSessionMutation, DeleteTrainingSessionMutation,
    DeleteTrainingMaterialMutation, DeleteTrainingEvidenceMutation,
)


def _check(user, perms):
    if type(user) is AnonymousUser or not user.id or not user.has_perms(perms):
        raise PermissionDenied(_("unauthorized"))


def _location_filter(parent_location, parent_location_level):
    from location.apps import LocationConfig
    q, key = Q(), "location__uuid"
    for _i in range(len(LocationConfig.location_types)):
        q |= Q(**{key: parent_location})
        key = key.replace("location__", "location__parent__", 1)
    return q


class Query(graphene.ObjectType):
    training = OrderedDjangoFilterConnectionField(
        TrainingGQLType,
        orderBy=graphene.List(of_type=graphene.String),
        client_mutation_id=graphene.String(),
        show_deleted=graphene.Boolean(),
        parent_location=graphene.String(),
        parent_location_level=graphene.Int(),
    )
    training_category = OrderedDjangoFilterConnectionField(
        TrainingCategoryGQLType, orderBy=graphene.List(of_type=graphene.String),
        show_deleted=graphene.Boolean())
    participant_category = OrderedDjangoFilterConnectionField(
        ParticipantCategoryGQLType, orderBy=graphene.List(of_type=graphene.String),
        show_deleted=graphene.Boolean())
    training_level = OrderedDjangoFilterConnectionField(
        TrainingLevelGQLType, orderBy=graphene.List(of_type=graphene.String),
        show_deleted=graphene.Boolean())
    job_title = OrderedDjangoFilterConnectionField(
        JobTitleGQLType, orderBy=graphene.List(of_type=graphene.String),
        show_deleted=graphene.Boolean())
    staff_user_group = OrderedDjangoFilterConnectionField(
        StaffUserGroupGQLType, orderBy=graphene.List(of_type=graphene.String),
        show_deleted=graphene.Boolean())
    trainer_profile = OrderedDjangoFilterConnectionField(
        TrainerProfileGQLType, orderBy=graphene.List(of_type=graphene.String),
        client_mutation_id=graphene.String(), show_deleted=graphene.Boolean())
    training_assignment = OrderedDjangoFilterConnectionField(
        TrainingAssignmentGQLType, orderBy=graphene.List(of_type=graphene.String))
    training_participant = OrderedDjangoFilterConnectionField(
        TrainingParticipantGQLType, orderBy=graphene.List(of_type=graphene.String),
        show_deleted=graphene.Boolean(),
        parent_location=graphene.String(), parent_location_level=graphene.Int())
    training_session = OrderedDjangoFilterConnectionField(
        TrainingSessionGQLType, orderBy=graphene.List(of_type=graphene.String))
    training_material = OrderedDjangoFilterConnectionField(
        TrainingMaterialGQLType, orderBy=graphene.List(of_type=graphene.String))
    training_evidence = OrderedDjangoFilterConnectionField(
        TrainingEvidenceGQLType, orderBy=graphene.List(of_type=graphene.String))

    training_calendar = graphene.List(
        TrainingGQLType,
        date_from=graphene.DateTime(required=True),
        date_to=graphene.DateTime(required=True),
        status=graphene.String(),
        category_id=graphene.UUID(),
        location_id=graphene.Int(),
        trainer_id=graphene.UUID(),
    )

    training_conflicts = graphene.List(
        TrainingConflictGQLType,
        start_datetime=graphene.DateTime(required=True),
        end_datetime=graphene.DateTime(required=True),
        training_id=graphene.UUID(),
        venue=graphene.String(),
        location_id=graphene.Int(),
        trainer_ids=graphene.List(graphene.UUID),
        staff_user_ids=graphene.List(graphene.UUID),
    )

    training_summary = graphene.Field(
        TrainingSummaryGQLType,
        date_from=graphene.DateTime(),
        date_to=graphene.DateTime(),
        location_id=graphene.Int(),
    )

    # Lets the form show the PAA live without shipping the Zanzibar mapping to the browser.
    paa_for_location = graphene.String(location_id=graphene.Int(required=True))

    # -- resolvers ----------------------------------------------------------
    def resolve_training(self, info, **kwargs):
        _check(info.context.user, TrainingConfig.gql_training_search_perms)
        filters = [] if kwargs.get('show_deleted') else [Q(is_deleted=False)]
        client_mutation_id = kwargs.get("client_mutation_id")
        if client_mutation_id:
            wait_for_mutation(client_mutation_id)
            filters.append(Q(mutations__mutation__client_mutation_id=client_mutation_id))
        if kwargs.get('parent_location') is not None:
            filters.append(_location_filter(kwargs['parent_location'], kwargs.get('parent_location_level')))
        # .distinct() guards against duplicate rows when filtering across the
        # reverse `assignments` relation (e.g. assignments_Trainer_Id).
        return gql_optimizer.query(Training.objects.filter(*filters).distinct(), info)

    def resolve_training_category(self, info, **kwargs):
        _check(info.context.user, TrainingConfig.gql_training_category_search_perms)
        filters = [] if kwargs.get('show_deleted') else [Q(is_deleted=False)]
        return gql_optimizer.query(TrainingCategory.objects.filter(*filters), info)

    def resolve_participant_category(self, info, **kwargs):
        _check(info.context.user, TrainingConfig.gql_participant_category_search_perms)
        filters = [] if kwargs.get('show_deleted') else [Q(is_deleted=False)]
        return gql_optimizer.query(ParticipantCategory.objects.filter(*filters), info)

    def resolve_training_level(self, info, **kwargs):
        _check(info.context.user, TrainingConfig.gql_training_level_search_perms)
        filters = [] if kwargs.get('show_deleted') else [Q(is_deleted=False)]
        return gql_optimizer.query(TrainingLevel.objects.filter(*filters), info)

    def resolve_job_title(self, info, **kwargs):
        _check(info.context.user, TrainingConfig.gql_job_title_search_perms)
        filters = [] if kwargs.get('show_deleted') else [Q(is_deleted=False)]
        return gql_optimizer.query(JobTitle.objects.filter(*filters), info)

    def resolve_staff_user_group(self, info, **kwargs):
        _check(info.context.user, TrainingConfig.gql_staff_user_group_search_perms)
        filters = [] if kwargs.get('show_deleted') else [Q(is_deleted=False)]
        return gql_optimizer.query(StaffUserGroup.objects.filter(*filters), info)

    def resolve_trainer_profile(self, info, **kwargs):
        _check(info.context.user, TrainingConfig.gql_trainer_search_perms)
        filters = [] if kwargs.get('show_deleted') else [Q(is_deleted=False)]
        client_mutation_id = kwargs.get("client_mutation_id")
        if client_mutation_id:
            wait_for_mutation(client_mutation_id)
            filters.append(Q(mutations__mutation__client_mutation_id=client_mutation_id))
        return gql_optimizer.query(TrainerProfile.objects.filter(*filters), info)

    def resolve_training_assignment(self, info, **kwargs):
        _check(info.context.user, TrainingConfig.gql_assignment_search_perms)
        return gql_optimizer.query(TrainingAssignment.objects.filter(is_deleted=False), info)

    def resolve_training_participant(self, info, **kwargs):
        _check(info.context.user, TrainingConfig.gql_participant_search_perms)
        filters = [] if kwargs.get('show_deleted') else [Q(is_deleted=False)]
        parent_location = kwargs.get('parent_location')
        parent_location_level = kwargs.get('parent_location_level')
        if parent_location is not None and parent_location_level is not None:
            filters.append(_location_filter(parent_location, parent_location_level))
        return gql_optimizer.query(TrainingParticipant.objects.filter(*filters).distinct(), info)

    def resolve_training_session(self, info, **kwargs):
        _check(info.context.user, TrainingConfig.gql_session_search_perms)
        return gql_optimizer.query(TrainingSession.objects.filter(is_deleted=False), info)

    def resolve_training_material(self, info, **kwargs):
        _check(info.context.user, TrainingConfig.gql_material_search_perms)
        return gql_optimizer.query(TrainingMaterial.objects.filter(is_deleted=False), info)

    def resolve_training_evidence(self, info, **kwargs):
        _check(info.context.user, TrainingConfig.gql_evidence_search_perms)
        return gql_optimizer.query(TrainingEvidence.objects.filter(is_deleted=False), info)

    def resolve_training_calendar(self, info, date_from, date_to, **kwargs):
        _check(info.context.user, TrainingConfig.gql_dashboard_view_perms)
        qs = (Training.objects.filter(is_deleted=False)
              .filter(start_datetime__lt=date_to, end_datetime__gt=date_from))
        if kwargs.get('status'):
            qs = qs.filter(status=kwargs['status'])
        if kwargs.get('category_id'):
            qs = qs.filter(category_id=kwargs['category_id'])
        if kwargs.get('location_id'):
            qs = qs.filter(location_id=kwargs['location_id'])
        if kwargs.get('trainer_id'):
            qs = qs.filter(assignments__trainer_id=kwargs['trainer_id'], assignments__is_deleted=False)
        return gql_optimizer.query(qs.distinct().order_by('start_datetime'), info)

    def resolve_training_conflicts(self, info, start_datetime, end_datetime, **kwargs):
        _check(info.context.user, TrainingConfig.gql_training_search_perms)
        conflicts = ConflictService(info.context.user).check(
            start=start_datetime, end=end_datetime,
            training_id=kwargs.get('training_id'), venue=kwargs.get('venue'),
            location_id=kwargs.get('location_id'),
            trainer_ids=kwargs.get('trainer_ids'), staff_user_ids=kwargs.get('staff_user_ids'),
        )
        return [TrainingConflictGQLType(**c) for c in conflicts]

    def resolve_paa_for_location(self, info, location_id, **kwargs):
        _check(info.context.user, TrainingConfig.gql_training_search_perms)
        return resolve_paa_reference(Location.objects.filter(id=location_id).first())

    def resolve_training_summary(self, info, **kwargs):
        _check(info.context.user, TrainingConfig.gql_dashboard_view_perms)
        data = TrainingSummaryService(info.context.user).get_summary(
            date_from=kwargs.get('date_from'), date_to=kwargs.get('date_to'),
            location_id=kwargs.get('location_id'))
        return TrainingSummaryGQLType(
            total_trainings=data['total_trainings'],
            trainings_this_week=data['trainings_this_week'],
            upcoming_trainings=data['upcoming_trainings'],
            ongoing_trainings=data['ongoing_trainings'],
            completed_trainings=data['completed_trainings'],
            cancelled_trainings=data['cancelled_trainings'],
            active_trainers=data['active_trainers'],
            by_status=[StatusCountGQLType(**r) for r in data['by_status']],
            by_category=[CategoryCountGQLType(**r) for r in data['by_category']],
        )


class Mutation(graphene.ObjectType):
    # Training CRUD
    create_training = CreateTrainingMutation.Field()
    update_training = UpdateTrainingMutation.Field()
    delete_training = DeleteTrainingMutation.Field()
    # Training status workflow
    submit_training = SubmitTrainingMutation.Field()
    approve_training = ApproveTrainingMutation.Field()
    reject_training = RejectTrainingMutation.Field()
    schedule_training = ScheduleTrainingMutation.Field()
    start_training = StartTrainingMutation.Field()
    complete_training = CompleteTrainingMutation.Field()
    cancel_training = CancelTrainingMutation.Field()
    close_training = CloseTrainingMutation.Field()
    reschedule_training = RescheduleTrainingMutation.Field()
    # Category
    create_training_category = CreateTrainingCategoryMutation.Field()
    update_training_category = UpdateTrainingCategoryMutation.Field()
    delete_training_category = DeleteTrainingCategoryMutation.Field()
    create_training_level = CreateTrainingLevelMutation.Field()
    update_training_level = UpdateTrainingLevelMutation.Field()
    delete_training_level = DeleteTrainingLevelMutation.Field()
    create_job_title = CreateJobTitleMutation.Field()
    update_job_title = UpdateJobTitleMutation.Field()
    delete_job_title = DeleteJobTitleMutation.Field()
    create_participant_category = CreateParticipantCategoryMutation.Field()
    update_participant_category = UpdateParticipantCategoryMutation.Field()
    delete_participant_category = DeleteParticipantCategoryMutation.Field()
    # Trainer profile
    create_trainer_profile = CreateTrainerProfileMutation.Field()
    update_trainer_profile = UpdateTrainerProfileMutation.Field()
    delete_trainer_profile = DeleteTrainerProfileMutation.Field()
    # Assignment
    create_training_assignment = CreateTrainingAssignmentMutation.Field()
    update_training_assignment = UpdateTrainingAssignmentMutation.Field()
    delete_training_assignment = DeleteTrainingAssignmentMutation.Field()
    # Participant
    create_training_participant = CreateTrainingParticipantMutation.Field()
    update_training_participant = UpdateTrainingParticipantMutation.Field()
    delete_training_participant = DeleteTrainingParticipantMutation.Field()
    create_training_session = CreateTrainingSessionMutation.Field()
    update_training_session = UpdateTrainingSessionMutation.Field()
    delete_training_session = DeleteTrainingSessionMutation.Field()
    # Material / Evidence (create via DRF upload endpoints)
    delete_training_material = DeleteTrainingMaterialMutation.Field()
    delete_training_evidence = DeleteTrainingEvidenceMutation.Field()
