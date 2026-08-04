"""Training Report — registration, permissions, data shape and actual rendering.

Rendering is exercised for real (ReportBro produces the bytes) because the template is
type-checked at render time: a mismatch between a declared parameter type and what the
query returns fails there and nowhere earlier.
"""
from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from core.test_helpers import LogInHelper
from report.apps import ReportConfig
from report.services import generate_report, get_report_definition

from training.apps import DEFAULT_CONFIG
from training.models import AssignmentRole, AttendanceStatus, Gender, ParticipantCategory
from training.reports import brand
from training.services import (
    TrainingService, TrainerProfileService, TrainingAssignmentService,
    TrainingParticipantService,
)

REPORT_NAME = 'training_report'


class TrainingReportRegistrationTests(TestCase):
    def test_report_is_discovered_by_the_core_report_app(self):
        self.assertIsNotNone(ReportConfig.get_report(REPORT_NAME))

    def test_report_is_permission_gated(self):
        # An empty permission list would make has_perms() return True for everyone, so
        # the definition must never be registered with one.
        permission = ReportConfig.get_report(REPORT_NAME)['permission']
        self.assertTrue(permission, 'training_report must not be registered ungated')
        self.assertEqual(permission, DEFAULT_CONFIG['gql_training_report_perms'])

    def test_report_declares_the_reportbro_engine_and_a_query(self):
        report = ReportConfig.get_report(REPORT_NAME)
        self.assertEqual(report['engine'], 0)
        self.assertTrue(callable(report['python_query']))
        self.assertEqual(report['module'], 'training')


class TrainingReportDataTests(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.user = LogInHelper().get_or_create_user_api()
        start = timezone.now() + timedelta(days=5)
        cls.training_id = TrainingService(cls.user).create({
            'title': 'Reported training', 'start_datetime': start,
            'end_datetime': start + timedelta(hours=6), 'venue': 'Venue REPORT',
            'expected_participants': 4,
        })['data']['id']

        trainer_id = TrainerProfileService(cls.user).create(
            {'full_name': 'Lead Trainer'})['data']['id']
        TrainingAssignmentService(cls.user).create({
            'training_id': cls.training_id, 'trainer_id': trainer_id,
            'role': AssignmentRole.LEAD_TRAINER,
        })

        service = TrainingParticipantService(cls.user)
        categories = dict(ParticipantCategory.objects.values_list('code', 'id'))
        people = [
            ('Female Staff', Gender.FEMALE, 'TMU_HQ_STAFF', AttendanceStatus.ATTENDED),
            ('Male Staff', Gender.MALE, 'TMU_HQ_STAFF', AttendanceStatus.ATTENDED),
            ('Female CMC', Gender.FEMALE, 'CMC', AttendanceStatus.ABSENT),
            ('Unknown Gender', None, 'CMC', AttendanceStatus.ATTENDED),
            # No category — the report must show it rather than silently drop the row.
            ('Uncategorised', Gender.MALE, None, AttendanceStatus.ATTENDED),
        ]
        for name, gender, code, attendance in people:
            service.create({'training_id': cls.training_id, 'full_name': name,
                            'gender': gender, 'category_id': categories.get(code),
                            'attendance_status': attendance})

    def _data(self, **kwargs):
        return ReportConfig.get_report(REPORT_NAME)['python_query'](self.user, **kwargs)

    def test_header_fields(self):
        data = self._data(training_id=self.training_id)
        self.assertEqual(data['training_title'], 'Reported training')
        self.assertEqual(data['venue'], 'Venue REPORT')
        self.assertEqual(data['expected'], '4')
        self.assertEqual(data['attended'], 4)

    def test_assignments_are_listed(self):
        data = self._data(training_id=self.training_id)
        self.assertEqual([a['name'] for a in data['assignments']], ['Lead Trainer'])

    def test_register_lists_every_participant(self):
        data = self._data(training_id=self.training_id)
        self.assertEqual(len(data['participants']), 5)
        self.assertEqual(data['participants'][0]['sn'], 1)

    def test_participant_with_no_gender_is_labelled_not_recorded(self):
        data = self._data(training_id=self.training_id)
        unknown = next(p for p in data['participants'] if p['full_name'] == 'Unknown Gender')
        self.assertEqual(unknown['gender'], 'Not recorded')

    def test_statistics_are_disaggregated_by_gender_with_totals(self):
        stats = {row['category']: row for row in self._data(training_id=self.training_id)['stats']}
        self.assertEqual((stats['TMU Headquarters Staff']['male'], stats['TMU Headquarters Staff']['female'],
                          stats['TMU Headquarters Staff']['total']), (1, 1, 2))
        # The ungendered CMC member counts toward the total but neither column.
        cmc = stats['Community Management Committee']
        self.assertEqual((cmc['male'], cmc['female'], cmc['total']), (0, 1, 2))

    def test_participant_with_no_category_gets_its_own_row(self):
        stats = {row['category']: row for row in self._data(training_id=self.training_id)['stats']}
        self.assertEqual(stats['Not recorded']['total'], 1)

    def test_uncategorised_rows_sort_after_the_governance_ladder(self):
        rows = [row['category'] for row in self._data(training_id=self.training_id)['stats']]
        self.assertEqual(rows[-2:], ['Not recorded', 'Total'])

    def test_total_row_sums_every_category(self):
        total = next(row for row in self._data(training_id=self.training_id)['stats']
                     if row['category'] == 'Total')
        self.assertEqual((total['male'], total['female'], total['total']), (2, 2, 5))
        self.assertEqual(total['sn'], '')

    def test_unknown_training_returns_a_well_formed_empty_payload(self):
        data = self._data()
        self.assertEqual(data['participants'], [])
        self.assertEqual(data['attended'], 0)


class TrainingReportRenderTests(TestCase):
    """The template is only type-checked when it renders, so render it."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.user = LogInHelper().get_or_create_user_api()
        start = timezone.now() + timedelta(days=6)
        cls.training_id = TrainingService(cls.user).create({
            'title': 'Rendered training', 'start_datetime': start,
            'end_datetime': start + timedelta(hours=2), 'venue': 'Venue RENDER',
        })['data']['id']
        TrainingParticipantService(cls.user).create({
            'training_id': cls.training_id, 'full_name': 'Someone',
            'gender': Gender.FEMALE, 'attendance_status': AttendanceStatus.ATTENDED,
        })

    def _render(self, fmt, **kwargs):
        report = ReportConfig.get_report(REPORT_NAME)
        data = report['python_query'](self.user, **kwargs)
        definition = get_report_definition(REPORT_NAME, report['default_report'])
        return generate_report(REPORT_NAME, definition, data, fmt)

    def test_renders_a_pdf(self):
        output = self._render('pdf', training_id=self.training_id)
        self.assertTrue(output.startswith(b'%PDF'), 'expected a PDF payload')

    def test_renders_an_xlsx(self):
        output = self._render('xlsx', training_id=self.training_id)
        self.assertTrue(output.startswith(b'PK'), 'expected an xlsx (zip) payload')

    def test_renders_even_when_the_training_is_unknown(self):
        # The empty payload still has to satisfy the declared parameter types.
        self.assertTrue(self._render('pdf').startswith(b'%PDF'))

    def test_uses_a_unicode_font_so_names_are_not_mangled(self):
        """Guards against silently falling back to a core latin-1 font.

        helvetica/courier/times cannot encode an em dash or an accented name — those
        come out as mojibake rather than failing, so the only reliable check is which
        font the PDF actually embeds. Note the report app also offers 'dejavusans',
        whose .ttf files ship as 0 bytes in this build and crash fpdf's TTF parser.
        """
        output = self._render('pdf', training_id=self.training_id)
        self.assertIn(b'NotoSans', output,
                      'report fell back to a core font; non-latin1 text would be mangled')


class TrainingReportBrandingTests(TestCase):
    """The report has to look like it came from the same system as the docs/ PDFs."""

    def setUp(self):
        from training.reports.training_report import template
        self.template = template

    def _elements(self):
        return self.template['docElements']

    def test_masthead_carries_the_organisation_name(self):
        header = [e for e in self._elements() if e.get('containerId') == '0_header']
        self.assertIn(brand.ORGANISATION, [e['content'] for e in header])

    def test_only_one_masthead_element_paints_the_band(self):
        # Two overlapping elements both painting the teal background hid the
        # organisation name behind the right-hand label.
        band = [e for e in self._elements()
                if e.get('containerId') == '0_header'
                and e.get('backgroundColor') == brand.TEAL]
        self.assertEqual(len(band), 1)

    def test_tables_use_the_brand_header(self):
        tables = [e for e in self._elements() if e['elementType'] == 'table']
        self.assertTrue(tables)
        for element in tables:
            self.assertEqual(element['headerData']['backgroundColor'], brand.TEAL)
            self.assertEqual(element['borderColor'], brand.LINE)
            for cell in element['headerData']['columnData']:
                self.assertEqual(cell['textColor'], brand.WHITE)

    def test_section_headings_use_the_brand_colour(self):
        headings = [e for e in self._elements()
                    if e['elementType'] == 'text' and e.get('textColor') == brand.TEAL]
        self.assertGreaterEqual(len(headings), 3)
