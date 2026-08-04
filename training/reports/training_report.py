"""Training Report — the record of a single training event.

Covers requirement 7's "Training Report": the event's details, who delivered it, who
attended, and the gender-disaggregated participant breakdown requirement 11 asks for.

Run via the core report app: ``/api/report/training_report/pdf/?training_id=<uuid>``
(``xlsx`` also works). Registered in ``training/report.py``.
"""
from django.db.models import Count, F, Q

from training.models import Training, TrainingAssignment, TrainingParticipant, Gender
from training.services import resolve_paa_reference

from . import brand
from .reportbro import document, page_parameters, parameter, table, text

# Unrecorded values are reported as such, never folded into a catch-all.
NOT_RECORDED = 'Not recorded'


def heading(label, y):
    """Section heading: brand teal over a hairline rule, matching the docs/ PDFs."""
    return text(label, y=y, height=16, fontSize=10.5, bold=True,
                textColor=brand.TEAL, borderBottom=True,
                borderColor=brand.LINE, borderWidth='0.5')


def field(label, value, *, x, y, label_width=88, value_width=190):
    return [
        text(label, x=x, y=y, width=label_width, height=13, bold=True,
             fontSize=8.5, textColor=brand.MUTED),
        text(value, x=x + label_width, y=y, width=value_width, height=13,
             textColor=brand.INK),
    ]


def data_table(source, columns, y):
    return table(source, columns, y=y,
                 header_background=brand.TEAL, header_color=brand.WHITE,
                 text_color=brand.INK, border_color=brand.LINE)


# --- template ---------------------------------------------------------------
HEADER = [
    # Teal masthead band, echoing the cover treatment of the branded reportlab documents.
    # The band itself is one full-width element; the right-hand label sits on top of it
    # with no background of its own, otherwise it would repaint over the organisation name.
    text(brand.ORGANISATION, y=0, height=16, width=575, fontSize=7.5, bold=True,
         textColor=brand.WHITE, backgroundColor=brand.TEAL,
         paddingLeft=6, paddingTop=4, container='0_header'),
    text('Training Report', y=0, height=16, width=575, fontSize=7.5,
         horizontalAlignment='right', textColor=brand.WHITE,
         paddingRight=6, paddingTop=4, container='0_header'),
    text('${training_title}', y=24, height=20, fontSize=15, bold=True,
         textColor=brand.TEAL_DEEP, container='0_header'),
    text('${training_code}  ·  ${category}  ·  ${status}', y=45, height=13,
         fontSize=8.5, textColor=brand.MUTED, container='0_header'),
    text('Generated ${current_date}', y=45, height=13, width=575, fontSize=7.5,
         horizontalAlignment='right', textColor=brand.FAINT, container='0_header'),
]

FOOTER = [
    text('Page ${page_number} of ${page_count}', y=6, height=12, fontSize=7.5,
         horizontalAlignment='center', textColor=brand.FAINT,
         borderTop=True, borderColor=brand.LINE, borderWidth='0.5',
         paddingTop=4, container='0_footer'),
]

DETAILS = [
    heading('Training details', 0),
    *field('Starts', '${start}', x=0, y=22),
    *field('Ends', '${end}', x=292, y=22),
    *field('Venue', '${venue}', x=0, y=37),
    *field('PAA', '${paa}', x=292, y=37),
    *field('Expected', '${expected}', x=0, y=52),
    *field('Attended', '${attended}', x=292, y=52),
]

BODY = [
    heading('Trainers and facilitators', 82),
    data_table('assignments', [
        ('Name', '${name}', 240),
        ('Role', '${role}', 180),
        ('Status', '${status}', 155),
    ], 104),

    heading('Participants by category and gender', 152),
    data_table('stats', [
        ('SN', '${sn}', 40),
        ('Category', '${category}', 275),
        ('Male', '${male}', 80, 'right'),
        ('Female', '${female}', 80, 'right'),
        ('Total', '${total}', 100, 'right'),
    ], 174),

    heading('Attendance register', 224),
    data_table('participants', [
        ('SN', '${sn}', 35, 'right'),
        ('Name', '${full_name}', 165),
        ('Gender', '${gender}', 55),
        ('Category', '${participant_category}', 130),
        ('Organization', '${organization}', 110),
        ('Attendance', '${attendance}', 80),
    ], 246),
]

# ReportBro type-checks every value it is handed, so the declared type has to match what
# the query actually produces. Anything that can come back blank stays a string —
# `sn` is blank on the trailing Total row, `expected` is blank when unset.
ROW_PARAMS = {
    'assignments': [('name', 'string'), ('role', 'string'), ('status', 'string')],
    'stats': [('sn', 'string'), ('category', 'string'),
              ('male', 'number'), ('female', 'number'), ('total', 'number')],
    'participants': [('sn', 'number'), ('full_name', 'string'), ('gender', 'string'),
                     ('participant_category', 'string'), ('organization', 'string'),
                     ('attendance', 'string')],
}

SCALAR_PARAMS = [
    ('training_code', 'string'), ('training_title', 'string'), ('category', 'string'),
    ('status', 'string'), ('start', 'string'), ('end', 'string'), ('venue', 'string'),
    ('paa', 'string'), ('expected', 'string'), ('attended', 'number'),
]

template = document(
    doc_elements=HEADER + FOOTER + DETAILS + BODY,
    header_size=66, footer_size=24,
    parameters=[
        *page_parameters(),
        parameter('current_date', 'date', pattern='d/M/yyyy H:mm'),
        *[parameter(name, type_) for name, type_ in SCALAR_PARAMS],
        *[parameter(source, 'array',
                    children=[parameter(field, type_) for field, type_ in fields])
          for source, fields in ROW_PARAMS.items()],
    ],
)


# --- data -------------------------------------------------------------------
def _label(instance, field):
    """Human label for a choices field.

    get_FOO_display() returns a lazy gettext proxy, and ReportBro rejects anything that
    is not a real str — so every label is resolved here, at the boundary.
    """
    getter = getattr(instance, f'get_{field}_display', None)
    value = getter() if getter else getattr(instance, field, None)
    return str(value) if value is not None else None


def _fmt(value, fmt='%d/%m/%Y %H:%M'):
    return value.strftime(fmt) if value else ''


def _assignment_rows(training):
    rows = []
    for assignment in (TrainingAssignment.objects
                       .filter(training=training, is_deleted=False)
                       .select_related('trainer', 'staff_user')
                       .order_by('role')):
        who = assignment.trainer.full_name if assignment.trainer_id else None
        if not who and assignment.staff_user_id:
            who = assignment.staff_user.username
        rows.append({
            'name': who or '',
            'role': _label(assignment, 'role') or '',
            'status': _label(assignment, 'status') or '',
        })
    return rows


def _participant_rows(participants):
    rows = []
    for index, participant in enumerate(participants, start=1):
        rows.append({
            'sn': index,
            'full_name': participant.full_name,
            'gender': _label(participant, 'gender') or NOT_RECORDED,
            'participant_category': participant.category.name if participant.category else NOT_RECORDED,
            'organization': participant.organization or '',
            'attendance': _label(participant, 'attendance_status') or '',
        })
    return rows


def _stat_rows(training):
    """Category x gender with auto totals and a trailing Total row.

    Unrecorded gender/category count toward the total but get their own bucket.
    """
    grouped = (TrainingParticipant.objects
               .filter(training=training, is_deleted=False)
               .values('category__name', 'category__sequence')
               .annotate(male=Count('id', filter=Q(gender=Gender.MALE)),
                         female=Count('id', filter=Q(gender=Gender.FEMALE)),
                         total=Count('id'))
               .order_by(F('category__sequence').asc(nulls_last=True)))

    rows, totals = [], {'male': 0, 'female': 0, 'total': 0}
    for index, group in enumerate(grouped, start=1):
        rows.append({
            'sn': str(index),
            'category': group['category__name'] or NOT_RECORDED,
            'male': group['male'], 'female': group['female'], 'total': group['total'],
        })
        for key in totals:
            totals[key] += group[key]
    rows.append({'sn': '', 'category': 'Total', **totals})
    return rows


def training_report_query(user, training_id=None, **kwargs):
    """Data for one training. ``training_id`` comes straight off the query string."""
    from core import datetime

    training = (Training.objects.filter(id=training_id, is_deleted=False)
                .select_related('category', 'location').first()) if training_id else None
    if not training:
        # A missing/unknown id yields an empty but well-formed report rather than a 500.
        # `attended` stays numeric here — ReportBro validates the declared type even
        # when nothing is rendered.
        return {'current_date': datetime.datetime.now(), 'training_title': 'Training not found',
                'training_code': '', 'category': '', 'status': '', 'start': '', 'end': '',
                'venue': '', 'paa': '', 'expected': '', 'attended': 0,
                'assignments': [], 'stats': [], 'participants': []}

    participants = list(TrainingParticipant.objects
                        .filter(training=training, is_deleted=False)
                        .select_related('category')
                        .order_by(F('category__sequence').asc(nulls_last=True), 'full_name'))
    attended = sum(1 for p in participants if p.attendance_status == 'ATTENDED')

    return {
        'current_date': datetime.datetime.now(),
        'training_code': training.code,
        'training_title': training.title,
        'category': training.category.name if training.category_id else '',
        'status': _label(training, 'status') or '',
        'start': _fmt(training.start_datetime),
        'end': _fmt(training.end_datetime),
        'venue': training.venue or '',
        'paa': (training.paa_reference
                or (resolve_paa_reference(training.location) if training.location_id else '')
                or ''),
        'expected': str(training.expected_participants)
                    if training.expected_participants is not None else '',
        'attended': attended,
        'assignments': _assignment_rows(training),
        'stats': _stat_rows(training),
        'participants': _participant_rows(participants),
    }
