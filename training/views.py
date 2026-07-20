"""DRF endpoints for binary uploads/downloads (materials & evidence).

GraphQL is JSON-only, so file uploads use multipart DRF endpoints — mirroring how
``payment_cycle`` exposes CSV via ``APIView`` + ``check_user_rights``.  Files are
stored through Django's default storage (``FileField``); metadata is created via the
service layer so audit fields are populated.
"""
import logging

from django.core.cache import cache
from django.http import FileResponse, Http404
from django.utils import timezone
from rest_framework import views
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from core.views import check_user_rights

from training.apps import TrainingConfig
from training.models import (
    Training, TrainingMaterial, TrainingEvidence,
    TrainingSession, TrainingParticipant, AttendanceStatus, CheckInMethod, Gender,
)
from training.services import TrainingMaterialService, TrainingEvidenceService

logger = logging.getLogger(__name__)

CHECKIN_RATE_MAX = 20        # submissions per IP
CHECKIN_RATE_WINDOW = 60     # seconds


class _BaseUploadView(views.APIView):
    parser_classes = [MultiPartParser, FormParser]
    service_class = None
    extra_fields = ()  # additional form fields copied into the payload

    def post(self, request):
        try:
            training_id = request.data.get('training_id')
            upload = request.FILES.get('file')
            if not training_id or not upload:
                return Response({'success': False, 'error': 'training_id and file are required'}, status=400)
            if not Training.objects.filter(id=training_id, is_deleted=False).exists():
                return Response({'success': False, 'error': 'training not found'}, status=404)
            payload = {
                'training_id': training_id,
                'file': upload,
                'file_name': request.data.get('file_name') or upload.name,
                'file_type': request.data.get('file_type') or getattr(upload, 'content_type', None),
                'description': request.data.get('description'),
            }
            for f in self.extra_fields:
                if request.data.get(f) is not None:
                    payload[f] = request.data.get(f)
            res = self.service_class(request.user).create(payload)
            if not res['success']:
                return Response(res, status=400)
            return Response({'success': True, 'id': res['data']['id']}, status=201)
        except Exception as exc:
            logger.error("training upload failed", exc_info=exc)
            return Response({'success': False, 'error': str(exc)}, status=500)


class TrainingMaterialUploadView(_BaseUploadView):
    permission_classes = [check_user_rights(TrainingConfig.gql_material_upload_perms)]
    service_class = TrainingMaterialService


class TrainingEvidenceUploadView(_BaseUploadView):
    permission_classes = [check_user_rights(TrainingConfig.gql_evidence_upload_perms)]
    service_class = TrainingEvidenceService
    extra_fields = ('evidence_type',)


class _BaseDownloadView(views.APIView):
    model = None

    def get(self, request, uuid):
        obj = self.model.objects.filter(id=uuid, is_deleted=False).first()
        if not obj or not obj.file:
            raise Http404
        try:
            return FileResponse(obj.file.open('rb'), as_attachment=True, filename=obj.file_name)
        except Exception as exc:
            logger.error("training download failed", exc_info=exc)
            raise Http404


class TrainingMaterialDownloadView(_BaseDownloadView):
    permission_classes = [check_user_rights(TrainingConfig.gql_material_search_perms)]
    model = TrainingMaterial


class TrainingEvidenceDownloadView(_BaseDownloadView):
    permission_classes = [check_user_rights(TrainingConfig.gql_evidence_search_perms)]
    model = TrainingEvidence


# ── Public QR self check-in ──────────────────────────────────────────────────
# The ONLY unauthenticated endpoint. Scoped by an opaque per-session token; closed
# by default; anti-abuse = open/close window + (phone, session) de-dupe + per-IP
# rate limit + honeypot. (A real captcha can be slotted into ``_passes_captcha``.)
def _session_for_token(token):
    return TrainingSession.objects.filter(
        registration_token=token, is_deleted=False).select_related('training').first()


def _checkin_open(session):
    if not session.registration_open:
        return False
    now = timezone.now()
    if session.registration_opens_at and now < session.registration_opens_at:
        return False
    if session.registration_closes_at and now > session.registration_closes_at:
        return False
    return True


def _passes_captcha(data):
    # Placeholder — to be wired (Turnstile/hCaptcha) here if required. For now
    # anti-bot relies on the honeypot + per-IP rate limit.
    return True


class TrainingCheckinView(views.APIView):
    """Public self check-in for a session (token = session.registration_token)."""
    authentication_classes = []
    permission_classes = [AllowAny]

    def get(self, request, token):
        session = _session_for_token(token)
        if not session:
            return Response({'error': 'not_found'}, status=404)
        t = session.training
        return Response({
            'training': {'code': t.code, 'title': t.title, 'venue': t.venue, 'description': t.description},
            'session': {
                'title': session.title,
                'date': session.session_date.isoformat() if session.session_date else None,
                'startTime': session.start_time.strftime('%H:%M') if session.start_time else None,
                'endTime': session.end_time.strftime('%H:%M') if session.end_time else None,
                'venue': session.venue,
            },
            'ref': (session.registration_token or '')[:4] + '·' + (session.registration_token or '')[-4:],
            'isOpen': _checkin_open(session),
        })

    def post(self, request, token):
        session = _session_for_token(token)
        if not session:
            return Response({'error': 'not_found'}, status=404)
        if not _checkin_open(session):
            return Response({'error': 'closed'}, status=403)

        ip = request.META.get('REMOTE_ADDR', 'anon')
        key = f'training:checkin:rl:{ip}'
        count = cache.get(key, 0)
        if count >= CHECKIN_RATE_MAX:
            return Response({'error': 'rate_limited'}, status=429)
        cache.set(key, count + 1, CHECKIN_RATE_WINDOW)

        data = request.data
        if (data.get('hp') or '').strip():        # honeypot — silently accept bots
            return Response({'ok': True})
        if not _passes_captcha(data):
            return Response({'error': 'captcha'}, status=400)

        full_name = (data.get('full_name') or '').strip()
        phone = (data.get('phone') or '').strip().replace(' ', '')
        if not full_name or not phone:
            return Response({'error': 'missing_fields', 'fields': ['full_name', 'phone']}, status=400)

        if TrainingParticipant.objects.filter(session=session, phone=phone, is_deleted=False).exists():
            return Response({'ok': True, 'already': True})

        gender = data.get('gender')
        if gender not in dict(Gender.choices):
            gender = None

        audit_user = session.user_created  # attribute to the officer who opened the session
        try:
            participant = TrainingParticipant(
                training=session.training, session=session,
                full_name=full_name[:255], gender=gender, phone=phone[:50],
                email=((data.get('email') or '').strip()[:255] or None),
                organization=((data.get('organization') or '').strip()[:255] or None),
                title=((data.get('title') or '').strip()[:255] or None),
                attendance_status=AttendanceStatus.ATTENDED,
                self_registered=True, check_in_method=CheckInMethod.QR,
                registered_at=timezone.now(),
            )
            # HistoryModel.save sets user_created/user_updated from `user`.
            participant.save(user=audit_user)
        except Exception as exc:
            logger.error('training self check-in failed', exc_info=exc)
            return Response({'error': 'server_error'}, status=500)
        return Response({'ok': True}, status=201)
