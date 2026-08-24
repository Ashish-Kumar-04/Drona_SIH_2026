"""
Verified PDF certificate generator (reportlab + segno).

Produces a printable, tamper-evident assessment certificate: athlete identity, the
test result and normalized index, authenticity indicators, the mandated
"Prototype / Research Benchmark" label, a short HMAC signature, and a QR code that
links to the public /verify/{id} endpoint. The QR is drawn as vector rectangles
straight from segno's module matrix, so there is no Pillow / raster dependency.
"""

import io

import segno
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas

PAGE_W, PAGE_H = A4  # points

# Palette (print-friendly, not the neon UI colours)
INK = (0.043, 0.118, 0.200)      # deep navy  #0b1e33
ACCENT = (0.0, 0.478, 0.549)     # teal       #007a8c
MUTED = (0.40, 0.45, 0.52)
GOLD = (0.83, 0.63, 0.22)
WHITE = (1, 1, 1)

STATUS_COLORS = {
    "VALID": (0.13, 0.55, 0.34),      # green
    "SUSPICIOUS": (0.82, 0.55, 0.10), # amber
    "INVALID": (0.78, 0.22, 0.26),    # red
}


def _draw_qr(c, data, x, y, size):
    """Render a QR for `data` as filled vector squares inside an x,y,size box (points)."""
    qr = segno.make(data, error="m")
    matrix = list(qr.matrix)
    n = len(matrix)
    border = 4  # quiet zone in modules
    total = n + 2 * border
    module = size / total

    # White backing card
    c.setFillColorRGB(*WHITE)
    c.rect(x, y, size, size, fill=1, stroke=0)

    c.setFillColorRGB(0, 0, 0)
    for r, row in enumerate(matrix):
        for ci, bit in enumerate(row):
            if bit:
                mx = x + (ci + border) * module
                # row 0 is the top of the QR; PDF y grows upward, so flip
                my = y + size - (r + border + 1) * module
                c.rect(mx, my, module, module, fill=1, stroke=0)


def _centered(c, text, cx, y, font, size, color):
    c.setFont(font, size)
    c.setFillColorRGB(*color)
    c.drawCentredString(cx, y, text)


def generate_certificate_pdf(
    *, name, athlete_id, age, category, location, test_label,
    raw_score, unit, normalized_score, validation_score, status,
    timestamp_text, verify_url, signature_display, benchmark_label="Prototype / Research Benchmark",
) -> bytes:
    """Build the certificate and return the PDF as bytes."""
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    cx = PAGE_W / 2

    # ── Outer decorative border ──
    c.setLineWidth(2)
    c.setStrokeColorRGB(*ACCENT)
    c.rect(18 * mm, 16 * mm, PAGE_W - 36 * mm, PAGE_H - 32 * mm, fill=0, stroke=1)
    c.setLineWidth(0.6)
    c.setStrokeColorRGB(*GOLD)
    c.rect(21 * mm, 19 * mm, PAGE_W - 42 * mm, PAGE_H - 38 * mm, fill=0, stroke=1)

    # ── Header ──
    top = PAGE_H - 40 * mm
    _centered(c, "SAI TalentAI", cx, top, "Helvetica-Bold", 26, INK)
    _centered(c, "Sports Authority of India  ·  AI Talent Assessment", cx, top - 16, "Helvetica", 10.5, MUTED)

    # Accent rule
    c.setStrokeColorRGB(*ACCENT)
    c.setLineWidth(1.4)
    c.line(cx - 45 * mm, top - 26, cx + 45 * mm, top - 26)

    _centered(c, "ASSESSMENT  CERTIFICATE", cx, top - 52, "Helvetica-Bold", 16, ACCENT)

    # Benchmark label pill
    pill_w, pill_h = 78 * mm, 8 * mm
    c.setFillColorRGB(0.93, 0.96, 0.97)
    c.roundRect(cx - pill_w / 2, top - 70, pill_w, pill_h, 4, fill=1, stroke=0)
    _centered(c, benchmark_label.upper(), cx, top - 70 + 2.4 * mm, "Helvetica-Bold", 8, ACCENT)

    # ── Recipient ──
    y = top - 96
    _centered(c, "This certifies that", cx, y, "Helvetica-Oblique", 11, MUTED)
    _centered(c, name, cx, y - 26, "Helvetica-Bold", 24, INK)
    meta = f"{athlete_id}   ·   Age {age}   ·   {category}   ·   {location}"
    _centered(c, meta, cx, y - 44, "Helvetica", 10, MUTED)

    # ── Result panel ──
    panel_y = y - 150
    panel_h = 88
    c.setFillColorRGB(0.97, 0.98, 0.99)
    c.setStrokeColorRGB(0.85, 0.89, 0.92)
    c.setLineWidth(1)
    c.roundRect(30 * mm, panel_y, PAGE_W - 60 * mm, panel_h, 6, fill=1, stroke=1)

    _centered(c, "completed the assessment", cx, panel_y + panel_h - 16, "Helvetica", 9.5, MUTED)
    _centered(c, test_label, cx, panel_y + panel_h - 36, "Helvetica-Bold", 15, INK)

    # Two result columns: raw score & normalized index
    left_cx = 30 * mm + (PAGE_W - 60 * mm) * 0.28
    right_cx = 30 * mm + (PAGE_W - 60 * mm) * 0.72
    _centered(c, f"{raw_score:g} {unit}", left_cx, panel_y + 20, "Helvetica-Bold", 20, ACCENT)
    _centered(c, "Measured result", left_cx, panel_y + 8, "Helvetica", 8, MUTED)
    _centered(c, f"{normalized_score:.1f} / 100", right_cx, panel_y + 20, "Helvetica-Bold", 20, ACCENT)
    _centered(c, "Performance index", right_cx, panel_y + 8, "Helvetica", 8, MUTED)

    # Divider between columns
    c.setStrokeColorRGB(0.85, 0.89, 0.92)
    c.setLineWidth(0.8)
    c.line(cx, panel_y + 10, cx, panel_y + 34)

    # ── Authenticity row ──
    auth_y = panel_y - 30
    status_color = STATUS_COLORS.get((status or "").upper(), MUTED)
    c.setFont("Helvetica", 10)
    c.setFillColorRGB(*MUTED)
    c.drawString(30 * mm, auth_y, f"AI authenticity score:  {validation_score:.0f}%")

    # Status badge (right aligned)
    badge_text = f"STATUS: {status}"
    c.setFont("Helvetica-Bold", 10)
    tw = c.stringWidth(badge_text, "Helvetica-Bold", 10)
    bx = PAGE_W - 30 * mm - tw - 12
    c.setFillColorRGB(*status_color)
    c.roundRect(bx, auth_y - 4, tw + 12, 16, 4, fill=1, stroke=0)
    c.setFillColorRGB(*WHITE)
    c.drawString(bx + 6, auth_y, badge_text)

    c.setFont("Helvetica", 9.5)
    c.setFillColorRGB(*MUTED)
    c.drawString(30 * mm, auth_y - 18, f"Assessed on:  {timestamp_text}")

    # ── QR + signature footer ──
    qr_size = 34 * mm
    qr_x = 30 * mm
    qr_y = 30 * mm
    _draw_qr(c, verify_url, qr_x, qr_y, qr_size)
    c.setFont("Helvetica-Bold", 8.5)
    c.setFillColorRGB(*INK)
    c.drawString(qr_x, qr_y - 11, "Scan to verify authenticity")
    c.setFont("Helvetica", 7)
    c.setFillColorRGB(*MUTED)
    c.drawString(qr_x, qr_y - 21, verify_url)

    # Signature block (right)
    sig_x = PAGE_W - 30 * mm
    c.setStrokeColorRGB(*INK)
    c.setLineWidth(0.8)
    c.line(sig_x - 62 * mm, qr_y + 20, sig_x, qr_y + 20)
    c.setFont("Helvetica", 8.5)
    c.setFillColorRGB(*MUTED)
    c.drawRightString(sig_x, qr_y + 8, "Digital signature (HMAC-SHA256)")
    c.setFont("Courier-Bold", 11)
    c.setFillColorRGB(*INK)
    c.drawRightString(sig_x, qr_y + 24, signature_display)

    # ── Footer disclaimer ──
    _centered(
        c,
        "This is a prototype research benchmark, not an official Government of India certification.",
        cx, 22 * mm, "Helvetica-Oblique", 7.5, MUTED,
    )

    c.showPage()
    c.save()
    buf.seek(0)
    return buf.read()
