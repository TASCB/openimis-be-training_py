"""URL patterns for the Training module (DRF upload/download endpoints).

Every openIMIS module must expose ``urlpatterns`` (even if empty).
"""
from django.urls import path

from training.views import (
    TrainingMaterialUploadView, TrainingMaterialDownloadView,
    TrainingEvidenceUploadView, TrainingEvidenceDownloadView,
    TrainingCheckinView,
)

urlpatterns = [
    path('materials/upload/', TrainingMaterialUploadView.as_view()),
    path('materials/<uuid:uuid>/download/', TrainingMaterialDownloadView.as_view()),
    path('evidence/upload/', TrainingEvidenceUploadView.as_view()),
    path('evidence/<uuid:uuid>/download/', TrainingEvidenceDownloadView.as_view()),
    path('checkin/<str:token>/', TrainingCheckinView.as_view()),
]
