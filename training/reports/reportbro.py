"""Minimal builders for ReportBro template JSON.

The other openIMIS modules ship a template pasted out of the ReportBro designer —
several thousand lines of JSON per report, most of it defaults. These helpers emit the
same structure from a handful of readable calls, so a column can be added without
editing generated JSON by hand. The output is an ordinary dict, which is exactly what
``report.services.generate_report`` accepts.

Keys and their defaults mirror a designer export (see product/reports/product_sales.py).
"""
from itertools import count

_ids = count(1000)


def _next_id():
    return next(_ids)


def _style(**over):
    """Font/border/padding defaults shared by text and table cells."""
    # notosans, not the core helvetica: helvetica is latin-1 only, so anything outside it
    # (an em dash, an accented name) renders as mojibake. generate_report registers
    # several unicode fonts, but the DejaVuSans*.ttf files it points at ship as 0 bytes
    # in this build and blow up fpdf's TTF parser — NotoSans is the one that is intact.
    base = {
        'bold': False, 'italic': False, 'underline': False, 'strikethrough': False,
        'horizontalAlignment': 'left', 'verticalAlignment': 'top',
        'textColor': '#000000', 'backgroundColor': '',
        'font': 'notosans', 'fontSize': 9, 'lineSpacing': 1,
        'paddingLeft': 2, 'paddingTop': 2, 'paddingRight': 2, 'paddingBottom': 2,
        'pattern': '', 'link': '', 'styleId': '',
    }
    base.update(over)
    return base


def _conditional_style():
    """cs_* keys are required even when no conditional style is used."""
    return {
        'cs_condition': '', 'cs_styleId': '', 'cs_bold': False, 'cs_italic': False,
        'cs_underline': False, 'cs_strikethrough': False,
        'cs_horizontalAlignment': 'left', 'cs_verticalAlignment': 'top',
        'cs_textColor': '#000000', 'cs_backgroundColor': '',
        'cs_font': 'notosans', 'cs_fontSize': 9, 'cs_lineSpacing': 1,
        'cs_paddingLeft': 2, 'cs_paddingTop': 2, 'cs_paddingRight': 2, 'cs_paddingBottom': 2,
        'cs_borderAll': False, 'cs_borderLeft': False, 'cs_borderTop': False,
        'cs_borderRight': False, 'cs_borderBottom': False,
        'cs_borderColor': '#000000', 'cs_borderWidth': '1',
    }


def _borders():
    return {
        'borderAll': False, 'borderLeft': False, 'borderTop': False,
        'borderRight': False, 'borderBottom': False,
        'borderColor': '#000000', 'borderWidth': '1',
    }


def _spreadsheet():
    return {
        'spreadsheet_hide': False, 'spreadsheet_column': '', 'spreadsheet_colspan': '',
        'spreadsheet_addEmptyRow': False, 'spreadsheet_textWrap': False,
    }


def text(content, *, x=0, y=0, width=575, height=14, container='0_content', **style):
    """A free-standing text block. ``content`` may contain ${parameter} placeholders."""
    element = {
        'elementType': 'text', 'id': _next_id(), 'containerId': container,
        'x': x, 'y': y, 'width': width, 'height': height,
        'content': content, 'eval': False,
        'richText': False, 'richTextContent': None, 'richTextHtml': '',
        'printIf': '', 'removeEmptyElement': False, 'alwaysPrintOnSamePage': True,
    }
    element.update(_style(**style))
    element.update(_borders())
    element.update(_conditional_style())
    element.update(_spreadsheet())
    return element


def _cell(content, width, **style):
    cell = {
        'elementType': 'table_text', 'id': _next_id(), 'width': width,
        'content': content, 'eval': False, 'colspan': '',
    }
    cell.update(_style(**style))
    cell.update(_conditional_style())
    cell.update({'spreadsheet_hide': False, 'spreadsheet_column': '',
                 'spreadsheet_colspan': '', 'spreadsheet_addEmptyRow': False,
                 'spreadsheet_textWrap': False})
    return cell


def _row(cells, *, height=16, background='', repeat_header=False):
    return {
        'elementType': 'table_row', 'id': _next_id(), 'height': height,
        'backgroundColor': background, 'columnData': cells,
        'repeatHeader': repeat_header,
    }


def table(data_source, columns, *, x=0, y=0, container='0_content',
          header_background='', header_color='#000000', text_color='#000000',
          border_color='#7a7a7a'):
    """A data table.

    ``data_source`` is the array parameter name (e.g. ``participants``).
    ``columns`` is a list of ``(heading, expression, width)``; the expression is
    evaluated per row, so it is usually ``${field}``. A column may also carry an
    alignment as a 4th item, e.g. ``('Male', '${male}', 80, 'right')``.
    """
    def align(column):
        return column[3] if len(column) > 3 else 'left'

    headings = [_cell(column[0], column[2], bold=True, textColor=header_color,
                      horizontalAlignment=align(column))
                for column in columns]
    values = [_cell(column[1], column[2], textColor=text_color,
                    horizontalAlignment=align(column))
              for column in columns]
    return {
        'elementType': 'table', 'id': _next_id(), 'containerId': container,
        'x': x, 'y': y, 'width': sum(column[2] for column in columns),
        'dataSource': data_source,
        'columns': len(columns),
        'header': True, 'contentRows': 1, 'footer': False,
        'headerData': _row(headings, background=header_background, repeat_header=True),
        'contentDataRows': [_row(values)],
        'footerData': _row([_cell('', column[2]) for column in columns]),
        'border': 'grid', 'borderColor': border_color, 'borderWidth': '0.5',
        'printIf': '', 'removeEmptyElement': False,
        'spreadsheet_hide': False, 'spreadsheet_column': '', 'spreadsheet_addEmptyRow': False,
    }


def parameter(name, type_='string', *, children=None, pattern=''):
    param = {
        'id': _next_id(), 'name': name, 'type': type_, 'arrayItemType': 'string',
        'eval': False, 'nullable': True, 'pattern': pattern, 'expression': '',
        'showOnlyNameType': False, 'testData': '',
    }
    if children is not None:
        param['children'] = children
    return param


# page_count/page_number are supplied by ReportBro itself and must be declared.
def page_parameters():
    return [parameter('page_count', 'number'), parameter('page_number', 'number')]


def document(*, doc_elements, parameters, header_size=60, footer_size=20):
    return {
        'docElements': doc_elements,
        'parameters': parameters,
        'styles': [],
        'version': 3,
        'documentProperties': {
            'pageFormat': 'A4', 'pageWidth': '', 'pageHeight': '',
            'unit': 'mm', 'orientation': 'portrait', 'contentHeight': '',
            'marginLeft': '10', 'marginTop': '10', 'marginRight': '10', 'marginBottom': '10',
            'header': True, 'headerSize': str(header_size), 'headerDisplay': 'always',
            'footer': True, 'footerSize': str(footer_size), 'footerDisplay': 'always',
            'patternLocale': 'en', 'patternCurrencySymbol': 'TZS',
        },
    }
