"""Validation classes for Training entities (openIMIS core validation mixins)."""
from django.core.exceptions import ValidationError
from django.utils.translation import gettext as _

from core.validation import BaseModelValidation, UniqueCodeValidationMixin, ObjectExistsValidationMixin
from core.validation.stringFieldValidationMixin import StringFieldValidationMixin

from training.models import (
    Training, TrainingCategory, TrainerProfile,
    TrainingAssignment, TrainingParticipant, TrainingMaterial, TrainingEvidence,
    TrainingSession, ParticipantCategory, JobTitle, StaffUserGroup,
)


class _CodedValidation(BaseModelValidation, UniqueCodeValidationMixin,
                       ObjectExistsValidationMixin, StringFieldValidationMixin):
    """Shared create/update validation for entities carrying a unique ``code``."""

    @classmethod
    def validate_create(cls, user, **data):
        code = data.get('code', None)
        cls.validate_empty_string(code)
        cls.validate_unique_code_name(code)

    @classmethod
    def validate_update(cls, user, **data):
        id_ = data.get('id', None)
        cls.validate_object_exists(id_)
        code = data.get('code', None)
        if code:
            cls.validate_unique_code_name(code, id_)


class TrainingValidation(_CodedValidation):
    OBJECT_TYPE = Training

    @classmethod
    def validate_create(cls, user, **data):
        code = data.get('code', None)
        if code:
            cls.validate_empty_string(code)
            cls.validate_unique_code_name(code)
        cls._validate_dates(data)

    @classmethod
    def validate_update(cls, user, **data):
        id_ = data.get('id', None)
        cls.validate_object_exists(id_)
        if 'code' in data:
            existing = Training.objects.filter(id=id_).only('code').first()
            if existing and data.get('code') != existing.code:
                raise ValidationError(_("training.validation.code_immutable"))
            if data.get('code'):
                cls.validate_unique_code_name(data.get('code'), id_)
        cls._validate_dates(data)

    @staticmethod
    def _validate_dates(data):
        start = data.get('start_datetime')
        end = data.get('end_datetime')
        if start and end and end < start:
            raise ValidationError(_("training.validation.end_before_start"))


class TrainingCategoryValidation(_CodedValidation):
    OBJECT_TYPE = TrainingCategory


class ParticipantCategoryValidation(_CodedValidation):
    OBJECT_TYPE = ParticipantCategory


class JobTitleValidation(_CodedValidation):
    OBJECT_TYPE = JobTitle


class StaffUserGroupValidation(_CodedValidation):
    OBJECT_TYPE = StaffUserGroup


class TrainerProfileValidation(_CodedValidation):
    OBJECT_TYPE = TrainerProfile


class TrainingAssignmentValidation(BaseModelValidation, ObjectExistsValidationMixin):
    OBJECT_TYPE = TrainingAssignment

    @classmethod
    def validate_create(cls, user, **data):
        if not data.get('trainer_id') and not data.get('staff_user_id') \
                and not data.get('trainer') and not data.get('staff_user'):
            raise ValidationError(_("training.validation.assignment_requires_trainer_or_staff"))

    @classmethod
    def validate_update(cls, user, **data):
        cls.validate_object_exists(data.get('id', None))


class TrainingParticipantValidation(BaseModelValidation, ObjectExistsValidationMixin):
    OBJECT_TYPE = TrainingParticipant


class TrainingSessionValidation(BaseModelValidation, ObjectExistsValidationMixin):
    OBJECT_TYPE = TrainingSession


class TrainingMaterialValidation(BaseModelValidation, ObjectExistsValidationMixin):
    OBJECT_TYPE = TrainingMaterial


class TrainingEvidenceValidation(BaseModelValidation, ObjectExistsValidationMixin):
    OBJECT_TYPE = TrainingEvidence


def validate_training_unique_code(code, uuid=None):
    """Helper for the ``trainingCodeValidity`` GraphQL query."""
    try:
        TrainingValidation().validate_unique_code_name(code, uuid)
        return []
    except ValidationError:
        return [{"message": _("training.validation.code_exists")}]
