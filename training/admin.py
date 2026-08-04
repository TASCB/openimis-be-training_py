from django.contrib import admin

from training.models import (
    Training, TrainingCategory, TrainerProfile,
    TrainingAssignment, TrainingParticipant, TrainingMaterial, TrainingEvidence,
)


@admin.register(TrainingCategory)
class TrainingCategoryAdmin(admin.ModelAdmin):
    list_display = ('code', 'name', 'is_active', 'is_deleted')
    search_fields = ('code', 'name')


@admin.register(TrainerProfile)
class TrainerProfileAdmin(admin.ModelAdmin):
    list_display = ('code', 'full_name', 'trainer_type', 'is_active', 'is_deleted')
    search_fields = ('code', 'full_name', 'email')


@admin.register(Training)
class TrainingAdmin(admin.ModelAdmin):
    list_display = ('code', 'title', 'status', 'start_datetime', 'end_datetime', 'is_deleted')
    list_filter = ('status',)
    search_fields = ('code', 'title')


@admin.register(TrainingAssignment)
class TrainingAssignmentAdmin(admin.ModelAdmin):
    list_display = ('training', 'trainer', 'staff_user', 'role', 'status')


@admin.register(TrainingParticipant)
class TrainingParticipantAdmin(admin.ModelAdmin):
    list_display = ('training', 'full_name', 'category', 'attendance_status')
    search_fields = ('full_name',)


@admin.register(TrainingMaterial)
class TrainingMaterialAdmin(admin.ModelAdmin):
    list_display = ('training', 'file_name', 'file_type')


@admin.register(TrainingEvidence)
class TrainingEvidenceAdmin(admin.ModelAdmin):
    list_display = ('training', 'evidence_type', 'file_name')
