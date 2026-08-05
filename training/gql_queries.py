"""GraphQL object types for the Training module."""
import graphene
from graphene_django import DjangoObjectType

from core import ExtendedConnection
from location.models import Location
from training.models import (
    Training, TrainingCategory, TrainerProfile,
    TrainingAssignment, TrainingParticipant, TrainingMaterial, TrainingEvidence,
    TrainingSession, ParticipantCategory, JobTitle, StaffUserGroup, TrainingLevel,
)
from training.services import checkin_open, resolve_paa_reference


class TrainingCategoryGQLType(DjangoObjectType):
    uuid = graphene.String(source='uuid')

    class Meta:
        model = TrainingCategory
        interfaces = (graphene.relay.Node,)
        filter_fields = {
            "id": ["exact"],
            "code": ["exact", "istartswith", "icontains", "iexact"],
            "name": ["exact", "istartswith", "icontains", "iexact"],
            "is_active": ["exact"],
            "is_deleted": ["exact"],
            "date_created": ["exact", "lt", "lte", "gt", "gte"],
            "version": ["exact"],
        }
        connection_class = ExtendedConnection


class ParticipantCategoryGQLType(DjangoObjectType):
    uuid = graphene.String(source='uuid')

    class Meta:
        model = ParticipantCategory
        interfaces = (graphene.relay.Node,)
        filter_fields = {
            "id": ["exact"],
            "code": ["exact", "istartswith", "icontains", "iexact"],
            "name": ["exact", "istartswith", "icontains", "iexact"],
            "sequence": ["exact", "lt", "lte", "gt", "gte"],
            "primary_for_levels__code": ["exact", "in"],
            "facilitator_for_levels__code": ["exact", "in"],
            "is_active": ["exact"],
            "is_deleted": ["exact"],
            "date_created": ["exact", "lt", "lte", "gt", "gte"],
            "version": ["exact"],
        }
        connection_class = ExtendedConnection


class TrainingLevelGQLType(DjangoObjectType):
    uuid = graphene.String(source='uuid')

    class Meta:
        model = TrainingLevel
        interfaces = (graphene.relay.Node,)
        filter_fields = {
            "id": ["exact"],
            "code": ["exact", "istartswith", "icontains", "iexact"],
            "name": ["exact", "istartswith", "icontains", "iexact"],
            "sequence": ["exact", "lt", "lte", "gt", "gte"],
            "is_active": ["exact"],
            "is_deleted": ["exact"],
            "version": ["exact"],
        }
        connection_class = ExtendedConnection


class StaffUserGroupGQLType(DjangoObjectType):
    uuid = graphene.String(source='uuid')

    class Meta:
        model = StaffUserGroup
        interfaces = (graphene.relay.Node,)
        filter_fields = {
            "id": ["exact"],
            "code": ["exact", "istartswith", "icontains", "iexact"],
            "name": ["exact", "istartswith", "icontains", "iexact"],
            "is_active": ["exact"],
            "is_deleted": ["exact"],
            "version": ["exact"],
        }
        connection_class = ExtendedConnection


class JobTitleGQLType(DjangoObjectType):
    uuid = graphene.String(source='uuid')

    class Meta:
        model = JobTitle
        interfaces = (graphene.relay.Node,)
        filter_fields = {
            "id": ["exact"],
            "sn": ["exact", "lt", "lte", "gt", "gte"],
            "code": ["exact", "istartswith", "icontains", "iexact"],
            "name": ["exact", "istartswith", "icontains", "iexact"],
            "user_group_id": ["exact"],
            "user_group__code": ["exact", "in"],
            "is_active": ["exact"],
            "is_deleted": ["exact"],
            "version": ["exact"],
        }
        connection_class = ExtendedConnection


class TrainerProfileGQLType(DjangoObjectType):
    uuid = graphene.String(source='uuid')

    class Meta:
        model = TrainerProfile
        interfaces = (graphene.relay.Node,)
        filter_fields = {
            "id": ["exact"],
            "code": ["exact", "istartswith", "icontains", "iexact"],
            "full_name": ["exact", "istartswith", "icontains", "iexact"],
            "gender": ["exact", "in", "isnull"],
            "position_id": ["exact", "isnull"],
            "position__code": ["exact", "in"],
            "position__user_group__code": ["exact", "in"],
            "email": ["exact", "icontains"],
            "phone": ["exact", "icontains"],
            "organization": ["exact", "icontains"],
            "trainer_type": ["exact"],
            "specialization": ["exact", "icontains"],
            "is_active": ["exact"],
            "is_deleted": ["exact"],
            "version": ["exact"],
        }
        connection_class = ExtendedConnection


class TrainingGQLType(DjangoObjectType):
    uuid = graphene.String(source='uuid')

    class Meta:
        model = Training
        interfaces = (graphene.relay.Node,)
        filter_fields = {
            "id": ["exact"],
            "code": ["exact", "istartswith", "icontains", "iexact"],
            "title": ["exact", "istartswith", "icontains", "iexact"],
            "status": ["exact", "in"],
            "venue": ["exact", "icontains"],
            "paa_reference": ["exact", "icontains"],
            "category_id": ["exact"],
            "level_id": ["exact"],
            "level__code": ["exact", "in"],
            "location_id": ["exact"],
            # reverse relation → GraphQL arg "assignments_Trainer_Id" (searcher trainer filter)
            "assignments__trainer__id": ["exact"],
            "start_datetime": ["exact", "lt", "lte", "gt", "gte"],
            "end_datetime": ["exact", "lt", "lte", "gt", "gte"],
            "expected_participants": ["exact", "lt", "lte", "gt", "gte"],
            "is_deleted": ["exact"],
            "date_created": ["exact", "lt", "lte", "gt", "gte"],
            "version": ["exact"],
        }
        connection_class = ExtendedConnection


class TrainingAssignmentGQLType(DjangoObjectType):
    uuid = graphene.String(source='uuid')

    class Meta:
        model = TrainingAssignment
        interfaces = (graphene.relay.Node,)
        filter_fields = {
            "id": ["exact"],
            "training_id": ["exact"],
            "trainer_id": ["exact"],
            "staff_user_id": ["exact"],
            "role": ["exact", "in"],
            "status": ["exact", "in"],
            "is_deleted": ["exact"],
            "version": ["exact"],
        }
        connection_class = ExtendedConnection


class TrainingParticipantGQLType(DjangoObjectType):
    uuid = graphene.String(source='uuid')
    # Reporting unit for a participant: the district on the mainland, the island scope
    # (UNGUJA/PEMBA) in Zanzibar — regardless of how deep the stored location is.
    paa_reference = graphene.String()

    def resolve_paa_reference(self, info):
        """Resolved from location_id rather than self.location: the optimizer defers the
        relation when the query asks only for this field, and a select_related hint then
        collides with that deferral. Memoised per request, so a list of participants costs
        one query per distinct location instead of four per row."""
        if not self.location_id:
            return None
        cache = getattr(info.context, '_training_paa_cache', None)
        if cache is None:
            cache = {}
            setattr(info.context, '_training_paa_cache', cache)
        if self.location_id not in cache:
            location = (Location.objects.filter(id=self.location_id)
                        .select_related('parent__parent__parent').first())
            cache[self.location_id] = resolve_paa_reference(location) if location else None
        return cache[self.location_id]

    class Meta:
        model = TrainingParticipant
        interfaces = (graphene.relay.Node,)
        filter_fields = {
            "id": ["exact"],
            "training_id": ["exact"],
            "training__title": ["icontains"],
            "training__code": ["icontains"],
            "session_id": ["exact"],
            "full_name": ["exact", "istartswith", "icontains", "iexact"],
            "gender": ["exact", "in", "isnull"],
            "category_id": ["exact", "in", "isnull"],
            "category__code": ["exact", "in"],
            "attendance_status": ["exact", "in"],
            "self_registered": ["exact"],
            "internal_user_id": ["exact"],
            "location_id": ["exact"],
            "is_deleted": ["exact"],
            "version": ["exact"],
        }
        connection_class = ExtendedConnection


class TrainingSessionGQLType(DjangoObjectType):
    uuid = graphene.String(source='uuid')
    # Effective public state, not the raw switch.
    checkin_open = graphene.Boolean()

    def resolve_checkin_open(self, info):
        return checkin_open(self)

    class Meta:
        model = TrainingSession
        interfaces = (graphene.relay.Node,)
        filter_fields = {
            "id": ["exact"],
            "training_id": ["exact"],
            "title": ["exact", "icontains"],
            "registration_open": ["exact"],
            "registration_token": ["exact"],
            "is_deleted": ["exact"],
            "version": ["exact"],
        }
        connection_class = ExtendedConnection


class TrainingMaterialGQLType(DjangoObjectType):
    uuid = graphene.String(source='uuid')
    file_url = graphene.String()

    class Meta:
        model = TrainingMaterial
        interfaces = (graphene.relay.Node,)
        filter_fields = {
            "id": ["exact"],
            "training_id": ["exact"],
            "file_name": ["exact", "icontains"],
            "file_type": ["exact", "icontains"],
            "is_deleted": ["exact"],
            "version": ["exact"],
        }
        connection_class = ExtendedConnection

    def resolve_file_url(self, info):
        try:
            return self.file.url if self.file else None
        except Exception:
            return None


class TrainingEvidenceGQLType(DjangoObjectType):
    uuid = graphene.String(source='uuid')
    file_url = graphene.String()

    class Meta:
        model = TrainingEvidence
        interfaces = (graphene.relay.Node,)
        filter_fields = {
            "id": ["exact"],
            "training_id": ["exact"],
            "evidence_type": ["exact", "in"],
            "file_name": ["exact", "icontains"],
            "file_type": ["exact", "icontains"],
            "is_deleted": ["exact"],
            "version": ["exact"],
        }
        connection_class = ExtendedConnection

    def resolve_file_url(self, info):
        try:
            return self.file.url if self.file else None
        except Exception:
            return None


# --- Non-model types -------------------------------------------------------
class TrainingConflictGQLType(graphene.ObjectType):
    type = graphene.String()
    hard = graphene.Boolean()
    message = graphene.String()
    conflicting_training_id = graphene.String()
    conflicting_training_code = graphene.String()
    subject_id = graphene.String()
    subject_label = graphene.String()


class StatusCountGQLType(graphene.ObjectType):
    status = graphene.String()
    count = graphene.Int()


class CategoryCountGQLType(graphene.ObjectType):
    category_id = graphene.String()
    category_name = graphene.String()
    count = graphene.Int()


class TrainingSummaryGQLType(graphene.ObjectType):
    total_trainings = graphene.Int()
    trainings_this_week = graphene.Int()
    upcoming_trainings = graphene.Int()
    ongoing_trainings = graphene.Int()
    completed_trainings = graphene.Int()
    cancelled_trainings = graphene.Int()
    active_trainers = graphene.Int()
    by_status = graphene.List(StatusCountGQLType)
    by_category = graphene.List(CategoryCountGQLType)
