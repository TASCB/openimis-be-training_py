"""TASAF brand tokens for generated reports.

Same palette as the reportlab documents in docs/ (generate_payment_module_pdf.py and
friends), so a report downloaded from the app sits next to them without looking like it
came from a different system. Those are hand-drawn one-off documents; these reports are
data-driven and rendered by the core openIMIS report app, so only the palette and the
typographic hierarchy are shared — not the code.
"""

ORGANISATION = 'TANZANIA SOCIAL ACTION FUND'

TEAL = '#00695C'        # TASAF brand
TEAL_DEEP = '#004D40'
TEAL_LIGHT = '#4DB6AC'
INK = '#1F2933'         # body text
MUTED = '#5F6368'       # labels, secondary text
FAINT = '#8A96A0'       # footer, timestamps
LINE = '#CBD5D0'        # rules and table borders
PAPER = '#F6F9F7'       # zebra/section tint
WHITE = '#FFFFFF'
