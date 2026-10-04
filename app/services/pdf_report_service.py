import io
from datetime import datetime
from typing import Dict, Any, List, Optional

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, KeepTogether, HRFlowable, PageBreak
)
from reportlab.pdfgen import canvas


PROCEDURE_STEPS_SPEC = [
    {"id": 0, "name": "Wash Hands", "trigger": "Sink / WaterTrigger"},
    {"id": 1, "name": "Wear Gloves", "trigger": "Glove Box / Gloves"},
    {"id": 2, "name": "Apply Tourniquet", "trigger": "Tourniquet"},
    {"id": 3, "name": "Take Cotton", "trigger": "Cotton Box"},
    {"id": 4, "name": "Dip Cotton in Spirit", "trigger": "Spirit Bottle"},
    {"id": 5, "name": "Clean Area", "trigger": "Patient Arm"},
    {"id": 6, "name": "Dispose Cotton", "trigger": "Dustbin"},
    {"id": 7, "name": "Take Cannula", "trigger": "Cannula"},
    {"id": 8, "name": "Insert Cannula", "trigger": "Vein Trigger"},
    {"id": 9, "name": "Remove Tourniquet", "trigger": "Tourniquet"},
    {"id": 10, "name": "Take Blood Collection Tube", "trigger": "Blood Collection Tube"},
    {"id": 11, "name": "Insert Tube", "trigger": "Tube Slot / SnapZone"},
    {"id": 12, "name": "Blood Collection", "trigger": "Blood Trigger"},
    {"id": 13, "name": "Remove Tube", "trigger": "Tube"},
    {"id": 14, "name": "Remove Cannula", "trigger": "Cannula"},
    {"id": 15, "name": "Dispose Cannula", "trigger": "Dustbin"},
]


class NumberedCanvas(canvas.Canvas):
    """Two-pass canvas to dynamically compute and draw 'Page X of Y' on all pages."""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_footer(num_pages)
            super().showPage()
        super().save()

    def draw_footer(self, page_count):
        self.saveState()
        self.setFont("Helvetica", 8)
        self.setFillColor(colors.HexColor("#718096"))
        # Top footer line
        self.setStrokeColor(colors.HexColor("#E2E8F0"))
        self.setLineWidth(0.5)
        self.line(36, 28, 612 - 36, 28)
        # Left brand text
        self.drawString(36, 16, "Medical VR Venipuncture Training Simulation • Authoritative Assessment Engine")
        # Right page number
        page_text = f"Page {self._pageNumber} of {page_count}"
        self.drawRightString(612 - 36, 16, page_text)
        self.restoreState()


class PortfolioNumberedCanvas(NumberedCanvas):
    """Two-pass canvas for Longitudinal Portfolio PDF with customized brand footer."""
    def draw_footer(self, page_count):
        self.saveState()
        self.setFont("Helvetica", 8)
        self.setFillColor(colors.HexColor("#718096"))
        self.setStrokeColor(colors.HexColor("#E2E8F0"))
        self.setLineWidth(0.5)
        self.line(36, 28, 612 - 36, 28)
        self.drawString(36, 16, "Medical VR Venipuncture Training Simulation • Trainee Clinical Portfolio")
        page_text = f"Page {self._pageNumber} of {page_count}"
        self.drawRightString(612 - 36, 16, page_text)
        self.restoreState()


def generate_assessment_pdf(
    user_info: Dict[str, Any],
    session_info: Dict[str, Any],
    assessment_data: Dict[str, Any],
    step_performance: list,
    mistakes: list,
    weak_areas: list,
    historical_context: Dict[str, Any],
    ai_feedback: Optional[Dict[str, Any]] = None,
    ai_status: str = "SUCCESS",
    model_name: str = "openbiollm",
    cumulative_weak_areas: Optional[list] = None,
    adaptive_guidance: Optional[Dict[str, Any]] = None
) -> io.BytesIO:
    """
    Generate a professional two-page clinical evaluation PDF report.
    Page 1: Clinical Executive Summary (Header, Trainee Info, Deterministic Result,
            Assessment Criteria Comparison, 10-Field Performance Grid, AI Feedback).
    Page 2: Detailed Procedure Telemetry & Guidance (16-Step Checklist, Mistake Analysis,
            Session Weak Areas, Longitudinal Progress, Cumulative Weak Areas, Adaptive Guidance,
            Final Sign-off).
    """
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        leftMargin=36,
        rightMargin=36,
        topMargin=36,
        bottomMargin=36
    )

    styles = getSampleStyleSheet()

    # Color tokens
    c_primary = colors.HexColor("#1A365D")      # Deep Navy
    c_secondary = colors.HexColor("#2B6CB0")    # Medical Blue
    c_text = colors.HexColor("#2D3748")         # Slate Dark Text
    c_muted = colors.HexColor("#718096")        # Muted Gray
    c_bg_light = colors.HexColor("#F7FAFC")     # Light background
    c_border = colors.HexColor("#E2E8F0")       # Border gray
    c_green = colors.HexColor("#047857")        # Pass green
    c_red = colors.HexColor("#B91C1C")          # Fail red

    # Typography styles
    title_style = ParagraphStyle(
        "HeaderTitle",
        parent=styles["Heading1"],
        fontSize=16,
        leading=20,
        textColor=c_primary,
        fontName="Helvetica-Bold",
        spaceAfter=1
    )
    subtitle_style = ParagraphStyle(
        "HeaderSub",
        parent=styles["Normal"],
        fontSize=8.5,
        leading=11,
        textColor=c_secondary,
        fontName="Helvetica-Bold",
        spaceAfter=5
    )
    page2_heading = ParagraphStyle(
        "Page2Heading",
        parent=styles["Heading2"],
        fontSize=10,
        leading=13,
        textColor=c_secondary,
        fontName="Helvetica-Bold",
        spaceAfter=4
    )
    section_title = ParagraphStyle(
        "SectionHeading",
        parent=styles["Heading2"],
        fontSize=9.5,
        leading=13,
        textColor=c_primary,
        fontName="Helvetica-Bold",
        spaceBefore=4,
        spaceAfter=2
    )
    body_style = ParagraphStyle(
        "BodyText",
        parent=styles["Normal"],
        fontSize=8,
        leading=11,
        textColor=c_text
    )
    body_bold = ParagraphStyle(
        "BodyBold",
        parent=body_style,
        fontName="Helvetica-Bold"
    )
    banner_ai = ParagraphStyle(
        "BannerAI",
        parent=styles["Normal"],
        fontSize=8,
        leading=10,
        textColor=colors.HexColor("#744210"),
        backColor=colors.HexColor("#FEFCBF"),
        borderColor=colors.HexColor("#D69E2E"),
        borderWidth=0.8,
        borderPadding=4,
        spaceBefore=3,
        spaceAfter=3
    )

    elements = []

    # =========================================================================
    # PAGE 1: CLINICAL EXECUTIVE SUMMARY
    # =========================================================================

    # 1. SECTION 1 — REPORT HEADER
    elements.append(Paragraph("Medical VR — Venipuncture Training", title_style))
    elements.append(Paragraph("Performance / Assessment Report", subtitle_style))
    elements.append(HRFlowable(width="100%", thickness=1.2, color=c_secondary, spaceAfter=5))

    session_type = session_info.get("session_type", "TEST")
    report_id = assessment_data.get("id", session_info.get("session_id", "N/A"))
    date_str = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")

    meta_table_data = [
        [
            Paragraph(f"<b>Report ID:</b> {report_id}", body_style),
            Paragraph(f"<b>Session ID:</b> {session_info.get('session_id', 'N/A')}", body_style),
            Paragraph(f"<b>Session Type:</b> {session_type}", body_style),
            Paragraph(f"<b>Date:</b> {date_str}", body_style)
        ]
    ]
    meta_table = Table(meta_table_data, colWidths=[135, 135, 135, 135])
    meta_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), c_bg_light),
        ("BOX", (0, 0), (-1, -1), 0.5, c_border),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    elements.append(meta_table)
    elements.append(Spacer(1, 4))

    # 2. SECTION 2 — TRAINEE INFORMATION
    elements.append(Paragraph("SECTION 2 — TRAINEE INFORMATION", section_title))
    trainee_data = [
        [
            Paragraph(f"<b>Trainee ID:</b> {user_info.get('id', session_info.get('user_id', 'N/A'))}", body_style),
            Paragraph(f"<b>Name:</b> {user_info.get('name', 'N/A')}", body_style),
            Paragraph(f"<b>Session Number:</b> {session_info.get('session_number', '1')}", body_style)
        ]
    ]
    trainee_table = Table(trainee_data, colWidths=[160, 240, 140])
    trainee_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#FFFFFF")),
        ("BOX", (0, 0), (-1, -1), 0.5, c_border),
        ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#EDF2F7")),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    elements.append(trainee_table)
    elements.append(Spacer(1, 4))

    # 3. SECTION 4 — DETERMINISTIC RESULT BADGE
    elements.append(Paragraph("SECTION 4 — DETERMINISTIC RESULT", section_title))
    raw_result = assessment_data.get("result") or assessment_data.get("overall_result", "EVALUATED")

    if session_type == "TEST":
        result_label = f"RESULT: {raw_result}"
        is_positive = (raw_result == "PASS")
        engine_note = "Authoritative deterministic test assessment result (PASS / FAIL). Unalterable by LLM."
    else:
        result_label = f"TRAINING STATUS: {raw_result}"
        is_positive = raw_result in ["EXCELLENT", "SATISFACTORY"]
        engine_note = "Authoritative deterministic training evaluation status. Unalterable by LLM."

    badge_bg = colors.HexColor("#DEF7EC") if is_positive else colors.HexColor("#FDE8E8")
    badge_border = colors.HexColor("#31C48D") if is_positive else colors.HexColor("#F98080")
    badge_color = colors.HexColor("#03543F") if is_positive else colors.HexColor("#9B1C1C")

    result_p = Paragraph(
        f"<font size=12 color='{badge_color}'><b>{result_label}</b></font><br/>"
        f"<font size=7 color='#4A5568'>{engine_note}</font>",
        ParagraphStyle("ResultBox", alignment=1, leading=14)
    )
    result_table = Table([[result_p]], colWidths=[540])
    result_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), badge_bg),
        ("BOX", (0, 0), (-1, -1), 1.2, badge_border),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    elements.append(result_table)
    elements.append(Spacer(1, 4))

    # 4. ASSESSMENT CRITERIA VERIFICATION (Required vs Actual)
    elements.append(Paragraph("ASSESSMENT CRITERIA VERIFICATION", section_title))
    total_steps = assessment_data.get("total_steps", 16)
    completed_steps = assessment_data.get("completed_steps", 0)
    correct_steps = assessment_data.get("correct_steps", 0)
    accuracy = round(float(assessment_data.get("accuracy", 0.0)), 2)
    total_attempts = assessment_data.get("total_attempts", 0)
    total_mistakes = assessment_data.get("total_mistakes", 0)
    first_attempt_correct_count = assessment_data.get("first_attempt_correct_count", 0)
    first_attempt_acc = round(float(assessment_data.get("first_attempt_accuracy", 0.0)), 2)
    total_time = round(float(assessment_data.get("total_time_seconds", 0.0)), 1)
    avg_step_time = round(float(assessment_data.get("average_step_time_seconds", 0.0)), 1)

    if session_type == "TEST":
        crit_met_style_pass = "<font color='#047857'><b>MET</b></font>"
        crit_met_style_fail = "<font color='#B91C1C'><b>UNMET</b></font>"
        crit_rows = [
            [
                Paragraph("<b>Assessment Metric</b>", body_bold),
                Paragraph("<b>Passing Standard</b>", body_bold),
                Paragraph("<b>Trainee Actual</b>", body_bold),
                Paragraph("<b>Criterion Status</b>", body_bold)
            ],
            [
                Paragraph("Completed Steps", body_style),
                Paragraph("Exactly 16 / 16", body_style),
                Paragraph(f"{completed_steps} / 16", body_style),
                Paragraph(crit_met_style_pass if completed_steps == 16 else crit_met_style_fail, body_style)
            ],
            [
                Paragraph("Procedural Accuracy", body_style),
                Paragraph("≥ 80.0%", body_style),
                Paragraph(f"{accuracy}%", body_style),
                Paragraph(crit_met_style_pass if accuracy >= 80.0 else crit_met_style_fail, body_style)
            ],
            [
                Paragraph("Total Clinical Mistakes", body_style),
                Paragraph("Exactly 0 Mistakes", body_style),
                Paragraph(f"{total_mistakes} Mistake(s)", body_style),
                Paragraph(crit_met_style_pass if total_mistakes == 0 else crit_met_style_fail, body_style)
            ]
        ]
    else:
        crit_rows = [
            [
                Paragraph("<b>Formative Metric</b>", body_bold),
                Paragraph("<b>Proficiency Target</b>", body_bold),
                Paragraph("<b>Trainee Actual</b>", body_bold),
                Paragraph("<b>Formative Status</b>", body_bold)
            ],
            [
                Paragraph("Completed Steps", body_style),
                Paragraph("16 / 16 Steps", body_style),
                Paragraph(f"{completed_steps} / 16", body_style),
                Paragraph("<font color='#047857'><b>COMPLETED</b></font>" if completed_steps == 16 else "<font color='#D97706'><b>PARTIAL</b></font>", body_style)
            ],
            [
                Paragraph("Procedural Accuracy", body_style),
                Paragraph("≥ 80.0% (Proficient)", body_style),
                Paragraph(f"{accuracy}%", body_style),
                Paragraph("<font color='#047857'><b>PROFICIENT</b></font>" if accuracy >= 80.0 else ("<font color='#2563EB'><b>SATISFACTORY</b></font>" if accuracy >= 70.0 else "<font color='#D97706'><b>PRACTICE NEEDED</b></font>"), body_style)
            ],
            [
                Paragraph("Clinical Mistakes", body_style),
                Paragraph("0 Mistakes (Target)", body_style),
                Paragraph(f"{total_mistakes} Mistake(s)", body_style),
                Paragraph("<font color='#047857'><b>CLEAN</b></font>" if total_mistakes == 0 else "<font color='#D97706'><b>IDENTIFIED</b></font>", body_style)
            ]
        ]

    crit_table = Table(crit_rows, colWidths=[170, 140, 120, 110])
    crit_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), c_secondary),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
        ("BOX", (0, 0), (-1, -1), 0.5, c_border),
        ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#EDF2F7")),
        ("TOPPADDING", (0, 0), (-1, -1), 2.5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2.5),
    ]))
    elements.append(crit_table)
    elements.append(Spacer(1, 4))

    # 5. SECTION 3 — PERFORMANCE SUMMARY (10-Field Telemetry Grid)
    elements.append(Paragraph("SECTION 3 — PERFORMANCE SUMMARY", section_title))
    perf_data = [
        [
            Paragraph(f"<b>Total Steps:</b> {total_steps}", body_style),
            Paragraph(f"<b>Completed Steps:</b> {completed_steps}", body_style),
            Paragraph(f"<b>Correct Steps:</b> {correct_steps}", body_style),
            Paragraph(f"<b>Accuracy:</b> {accuracy}%", body_style)
        ],
        [
            Paragraph(f"<b>Total Attempts:</b> {total_attempts}", body_style),
            Paragraph(f"<b>Total Mistakes:</b> {total_mistakes}", body_style),
            Paragraph(f"<b>First-Attempt Correct:</b> {first_attempt_correct_count} / {total_steps}", body_style),
            Paragraph(f"<b>First-Attempt Accuracy:</b> {first_attempt_acc}%", body_style)
        ],
        [
            Paragraph(f"<b>Total Time:</b> {total_time}s", body_style),
            Paragraph(f"<b>Average Step Time:</b> {avg_step_time}s", body_style),
            Paragraph(f"<b>Session Mode:</b> {session_type}", body_style),
            Paragraph(f"<b>Deterministic Result:</b> {raw_result}", body_style)
        ]
    ]
    perf_table = Table(perf_data, colWidths=[135, 135, 135, 135])
    perf_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), c_bg_light),
        ("BOX", (0, 0), (-1, -1), 0.5, c_border),
        ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#EDF2F7")),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    elements.append(perf_table)
    elements.append(Spacer(1, 4))

    # 6. AI-GENERATED FEEDBACK (Executive Narrative & Strengths)
    elements.append(Paragraph(
        "<b>AI-GENERATED TRAINING FEEDBACK</b> (SUPPLEMENTARY &mdash; EXPLANATION ONLY)",
        banner_ai
    ))
    elements.append(Paragraph(
        "AI-generated feedback is supplementary and does not determine assessment results.",
        ParagraphStyle("Notice", parent=body_style, fontSize=7, textColor=c_muted, spaceAfter=3)
    ))

    if ai_feedback:
        elements.append(Paragraph(f"<b>Model:</b> {model_name} &nbsp;&bull;&nbsp; <b>Status:</b> {ai_status}", ParagraphStyle("AIModelStatus", parent=body_style, fontSize=7.5, textColor=c_secondary, spaceAfter=2)))
        summary_text = ai_feedback.get("summary", "No AI summary available.")
        elements.append(Paragraph(f"<b>Clinical Summary:</b> {summary_text}", body_style))
        elements.append(Spacer(1, 3))

        str_list = ai_feedback.get("strengths", [])
        str_text = "<b>Observed Strengths:</b><br/>" + ("<br/>".join([f"✓ {s}" for s in str_list]) if str_list else "<i>None listed</i>")

        imp_list = ai_feedback.get("improvement_areas", [])
        imp_items = []
        for imp in imp_list:
            if isinstance(imp, dict):
                imp_items.append(f"⚠ <b>Step {imp.get('step_id')}: {imp.get('step_name')}</b> &mdash; {imp.get('evidence')}")
            else:
                imp_items.append(f"⚠ {imp}")
        imp_text = "<b>Areas for Practice:</b><br/>" + ("<br/>".join(imp_items) if imp_items else "<i>None listed</i>")

        ai_box_data = [[Paragraph(str_text, body_style), Paragraph(imp_text, body_style)]]
        ai_box_table = Table(ai_box_data, colWidths=[270, 270])
        ai_box_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (0, 0), colors.HexColor("#F0FFF4")),
            ("BACKGROUND", (1, 0), (1, 0), colors.HexColor("#FFFAF0")),
            ("BOX", (0, 0), (0, 0), 0.5, colors.HexColor("#9AE6B4")),
            ("BOX", (1, 0), (1, 0), 0.5, colors.HexColor("#FBD38D")),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ]))
        elements.append(ai_box_table)
    else:
        elements.append(Paragraph("AI feedback unavailable. Deterministic assessment remains fully valid.", body_style))

    # =========================================================================
    # INTENTIONAL PAGE BREAK — PAGE 1 TO PAGE 2
    # =========================================================================
    elements.append(PageBreak())

    # =========================================================================
    # PAGE 2: DETAILED PROCEDURE TELEMETRY & LONGITUDINAL ANALYSIS
    # =========================================================================
    elements.append(Paragraph("DETAILED PROCEDURE TELEMETRY & LONGITUDINAL ANALYSIS", page2_heading))
    elements.append(HRFlowable(width="100%", thickness=1, color=c_secondary, spaceAfter=4))

    # 7. SECTION 5 — STEP PERFORMANCE (16-Step Checklist)
    sp_elements = []
    sp_elements.append(Paragraph("SECTION 5 — STEP PERFORMANCE", section_title))

    sp_map = {sp.get("step_id"): sp for sp in step_performance} if step_performance else {}
    step_headers = ["ID", "Step Name", "Target / Trigger", "Attempts", "Mistakes", "1st Try", "Duration", "Status"]
    step_rows = [step_headers]

    for item in PROCEDURE_STEPS_SPEC:
        s_id = item["id"]
        s_name = item["name"]
        s_trigger = item["trigger"]

        telemetry = sp_map.get(s_id)
        if telemetry:
            attempts_str = str(telemetry.get("attempts", 1))
            mistakes_str = str(telemetry.get("mistakes", 0))
            first_str = "Yes" if telemetry.get("first_attempt_correct") else "No"
            time_str = f"{round(float(telemetry.get('step_time_seconds', 0)), 1)}s"
            status_str = "Completed" if telemetry.get("completed") else "Incomplete"
        else:
            attempts_str = "-"
            mistakes_str = "-"
            first_str = "-"
            time_str = "-"
            status_str = "Not Reached"

        step_rows.append([
            str(s_id),
            s_name[:24],
            s_trigger[:22],
            attempts_str,
            mistakes_str,
            first_str,
            time_str,
            status_str
        ])

    steps_table = Table(step_rows, colWidths=[20, 125, 120, 48, 48, 48, 55, 76])
    steps_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), c_secondary),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 7),
        ("ALIGN", (0, 0), (0, -1), "CENTER"),
        ("ALIGN", (3, 0), (6, -1), "CENTER"),
        ("ALIGN", (7, 0), (7, -1), "CENTER"),
        ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E0")),
        ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#A0AEC0")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, c_bg_light]),
        ("TOPPADDING", (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
    ]))
    sp_elements.append(steps_table)
    elements.append(KeepTogether(sp_elements))
    elements.append(Spacer(1, 4))

    # 8. SECTION 6 — MISTAKES
    m_elements = []
    m_elements.append(Paragraph("SECTION 6 — MISTAKES", section_title))
    if mistakes:
        m_rows = [["Step", "Step Name", "Mistake Type", "Attempt"]]
        for m in mistakes:
            s_id = m.get("step_id", 0)
            step_name = next((s["name"] for s in PROCEDURE_STEPS_SPEC if s["id"] == s_id), f"Step {s_id}")
            m_rows.append([
                str(s_id),
                step_name,
                str(m.get("mistake_type", "UNKNOWN")),
                str(m.get("attempt_number", m.get("attempt", 1)))
            ])
        m_table = Table(m_rows, colWidths=[50, 180, 210, 100])
        m_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#E53E3E")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 7.5),
            ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#FEB2B2")),
            ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#E53E3E")),
            ("TOPPADDING", (0, 0), (-1, -1), 2.5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 2.5),
        ]))
        m_elements.append(m_table)
    else:
        m_elements.append(Paragraph("No mistakes recorded.", body_style))
    elements.append(KeepTogether(m_elements))
    elements.append(Spacer(1, 4))

    # 9. SECTION 7 — SESSION WEAK AREAS (Current Session Errors)
    wa_elements = []
    wa_elements.append(Paragraph("SECTION 7 — WEAK AREAS", section_title))
    if weak_areas:
        wa_rows = [["Step", "Step Name", "Severity", "Deterministic Evidence"]]
        for wa in weak_areas:
            s_id = wa.get("step_id", 0)
            step_name = wa.get("step_name") or next((s["name"] for s in PROCEDURE_STEPS_SPEC if s["id"] == s_id), f"Step {s_id}")
            severity = wa.get("severity", "MEDIUM")
            mistakes_cnt = wa.get("mistakes", wa.get("total_mistakes", 1))
            attempts_cnt = wa.get("attempts", wa.get("total_attempts", 1))
            ratio = wa.get("mistake_ratio", 0.0)
            evidence_str = f"{mistakes_cnt} mistake(s) across {attempts_cnt} attempt(s) ({ratio}% error ratio)"
            wa_rows.append([str(s_id), step_name, severity, evidence_str])

        wa_table = Table(wa_rows, colWidths=[50, 170, 80, 240])
        wa_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#DD6B20")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 7.5),
            ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#FBD38D")),
            ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#DD6B20")),
            ("TOPPADDING", (0, 0), (-1, -1), 2.5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 2.5),
        ]))
        wa_elements.append(wa_table)
    else:
        wa_elements.append(Paragraph("No weak areas identified.", body_style))
    elements.append(KeepTogether(wa_elements))
    elements.append(Spacer(1, 4))

    # 10. SECTION 8 — HISTORICAL PROGRESS (Longitudinal Trend)
    hist_elements = []
    hist_elements.append(Paragraph("SECTION 8 — HISTORICAL PROGRESS", section_title))
    prior_sessions_count = historical_context.get("previous_sessions", historical_context.get("total_previous_sessions", 0))

    if prior_sessions_count > 0:
        prior_acc_list = historical_context.get("previous_accuracy", historical_context.get("previous_accuracy_trend", []))
        acc_trend_str = " → ".join([f"{a}%" for a in prior_acc_list]) if prior_acc_list else "None recorded"
        prior_results = historical_context.get("previous_results", [])
        results_str = ", ".join(prior_results) if prior_results else "Recorded"

        hist_items = [
            f"<b>Previous Completed Sessions:</b> {prior_sessions_count}",
            f"<b>Previous Accuracy Trend:</b> {acc_trend_str}",
            f"<b>Current Session Accuracy:</b> {accuracy}%",
            f"<b>Previous Results:</b> {results_str}",
            f"<b>Average Historical Accuracy:</b> {historical_context.get('average_historical_accuracy', accuracy)}%"
        ]

        recurring = historical_context.get("recurring_weak_areas", [])
        if recurring:
            rec_str = ", ".join([f"Step {r.get('step_id')} ({r.get('step_name')}) - {r.get('occurrences', r.get('total_prior_mistakes', 1))}x" for r in recurring])
            hist_items.append(f"<b>Recurring Weak Areas:</b> {rec_str}")

        hist_elements.append(Paragraph("<br/>".join(hist_items), body_style))
    else:
        hist_elements.append(Paragraph("No previous historical session data recorded.", body_style))
    elements.append(KeepTogether(hist_elements))
    elements.append(Spacer(1, 4))

    # 11. CUMULATIVE WEAK AREAS (Multi-Session Recurring Vulnerabilities)
    cum_elements = []
    cum_elements.append(Paragraph("CUMULATIVE WEAK AREAS", section_title))
    if cumulative_weak_areas:
        cwa_rows = [["Step", "Step Name", "Attempts", "Mistakes", "Error Rate", "Severity", "Rank"]]
        for cwa in cumulative_weak_areas:
            s_id = cwa.get("step_id", 0)
            step_name = cwa.get("step_name") or next((s["name"] for s in PROCEDURE_STEPS_SPEC if s["id"] == s_id), f"Step {s_id}")
            attempts_c = cwa.get("total_attempts", cwa.get("attempts", 0))
            mistakes_c = cwa.get("total_mistakes", cwa.get("mistakes", 0))
            ratio_c = f"{cwa.get('mistake_ratio', 0.0)}%"
            severity_c = cwa.get("severity", "MEDIUM")
            rank_c = str(cwa.get("rank", "-"))
            cwa_rows.append([str(s_id), step_name, str(attempts_c), str(mistakes_c), ratio_c, severity_c, rank_c])

        cwa_table = Table(cwa_rows, colWidths=[40, 160, 65, 65, 80, 70, 60])
        cwa_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#C53030")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 7.5),
            ("ALIGN", (0, 0), (0, -1), "CENTER"),
            ("ALIGN", (2, 0), (6, -1), "CENTER"),
            ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#FEB2B2")),
            ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#C53030")),
            ("TOPPADDING", (0, 0), (-1, -1), 2.5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 2.5),
        ]))
        cum_elements.append(cwa_table)
    else:
        cum_elements.append(Paragraph("No recurring historical weak areas identified.", body_style))
    elements.append(KeepTogether(cum_elements))
    elements.append(Spacer(1, 4))

    # 12. ADAPTIVE GUIDANCE / NEXT TRAINING FOCUS
    guidance_elements = []
    guidance_elements.append(Paragraph("ADAPTIVE GUIDANCE & NEXT TRAINING FOCUS", section_title))
    guidance_steps = adaptive_guidance.get("guidance", []) if adaptive_guidance else []

    if guidance_steps:
        g_rows = [["Step", "Step Name", "Guidance Level", "Targeted Clinical Directive"]]
        for g in guidance_steps:
            s_id = g.get("step_id", 0)
            step_name = g.get("step_name") or next((s["name"] for s in PROCEDURE_STEPS_SPEC if s["id"] == s_id), f"Step {s_id}")
            level = g.get("guidance_level", "LOW")
            message = g.get("guidance_message", "Review step protocol.")
            g_rows.append([str(s_id), step_name, level, message])

        g_table = Table(g_rows, colWidths=[40, 140, 80, 280])
        g_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2C5282")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 7.5),
            ("ALIGN", (0, 0), (0, -1), "CENTER"),
            ("ALIGN", (2, 0), (2, -1), "CENTER"),
            ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#BEE3F8")),
            ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#2C5282")),
            ("TOPPADDING", (0, 0), (-1, -1), 2.5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 2.5),
        ]))
        guidance_elements.append(g_table)
    else:
        guidance_elements.append(Paragraph("Standard curriculum protocol — no adaptive guidance overrides active.", body_style))
    elements.append(KeepTogether(guidance_elements))
    elements.append(Spacer(1, 4))

    # 13. SECTION 10 — FINAL SUMMARY & SIGN-OFF
    sum_elements = []
    sum_elements.append(Paragraph("SECTION 10 — FINAL SUMMARY", section_title))

    next_action = "Advance to next curriculum tier or clinical observation." if is_positive else "Repeat simulation focusing on identified weak areas."
    if weak_areas:
        next_action = f"Complete guided review for {weak_areas[0].get('step_name', 'identified weak steps')} before re-attempting."

    summary_items = [
        f"<b>Deterministic Assessment Result:</b> {raw_result}",
        f"<b>AI Feedback:</b> {ai_feedback.get('summary', 'Educational analysis completed.') if ai_feedback else 'Deterministic metrics authoritative.'}",
        f"<b>Recommended next action:</b> {next_action}"
    ]
    sum_table = Table([[Paragraph("<br/>".join(summary_items), body_style)]], colWidths=[540])
    sum_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), c_bg_light),
        ("BOX", (0, 0), (-1, -1), 0.5, c_primary),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    sum_elements.append(sum_table)
    elements.append(KeepTogether(sum_elements))

    # Build PDF with two-pass NumberedCanvas
    doc.build(elements, canvasmaker=NumberedCanvas)
    buffer.seek(0)
    return buffer


def generate_dashboard_pdf(dashboard_data: Dict[str, Any]) -> io.BytesIO:
    """
    Generate a professional 5-page Longitudinal Trainee Clinical Portfolio PDF.
    Page 1: Trainee Clinical Overview & Performance Snapshot
    Page 2: Longitudinal Performance Progression
    Page 3: Cumulative Weak Areas — Historical
    Page 4: Adaptive Guidance / Next Training Focus
    Page 5: Assessment History & Supervisor Sign-off
    """
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        leftMargin=36,
        rightMargin=36,
        topMargin=36,
        bottomMargin=36
    )

    styles = getSampleStyleSheet()

    # Color tokens
    c_primary = colors.HexColor("#1A365D")      # Deep Navy
    c_secondary = colors.HexColor("#2B6CB0")    # Medical Blue
    c_text = colors.HexColor("#2D3748")         # Slate Dark Text
    c_muted = colors.HexColor("#718096")        # Muted Gray
    c_bg_light = colors.HexColor("#F7FAFC")     # Light background
    c_border = colors.HexColor("#E2E8F0")       # Border gray
    c_green = colors.HexColor("#047857")        # Pass green
    c_red = colors.HexColor("#B91C1C")          # Fail red

    # Typography styles
    title_style = ParagraphStyle(
        "PortTitle",
        parent=styles["Heading1"],
        fontSize=16,
        leading=20,
        textColor=c_primary,
        fontName="Helvetica-Bold",
        spaceAfter=1
    )
    subtitle_style = ParagraphStyle(
        "PortSub",
        parent=styles["Normal"],
        fontSize=8.5,
        leading=11,
        textColor=c_secondary,
        fontName="Helvetica-Bold",
        spaceAfter=5
    )
    page_heading = ParagraphStyle(
        "PortPageHeading",
        parent=styles["Heading2"],
        fontSize=11,
        leading=14,
        textColor=c_secondary,
        fontName="Helvetica-Bold",
        spaceAfter=3
    )
    section_title = ParagraphStyle(
        "PortSectionHeading",
        parent=styles["Heading2"],
        fontSize=9.5,
        leading=13,
        textColor=c_primary,
        fontName="Helvetica-Bold",
        spaceBefore=4,
        spaceAfter=2
    )
    body_style = ParagraphStyle(
        "PortBody",
        parent=styles["Normal"],
        fontSize=8,
        leading=11,
        textColor=c_text
    )
    body_bold = ParagraphStyle(
        "PortBodyBold",
        parent=body_style,
        fontName="Helvetica-Bold"
    )
    banner_ai = ParagraphStyle(
        "PortBannerAI",
        parent=styles["Normal"],
        fontSize=8,
        leading=10,
        textColor=colors.HexColor("#744210"),
        backColor=colors.HexColor("#FEFCBF"),
        borderColor=colors.HexColor("#D69E2E"),
        borderWidth=0.8,
        borderPadding=4,
        spaceBefore=3,
        spaceAfter=3
    )

    user = dashboard_data.get("user") or {}
    user_id = user.get("id", "N/A")
    user_name = user.get("name", "N/A")
    user_email = user.get("email", "N/A")
    date_str = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")

    latest_training = dashboard_data.get("latest_training")
    latest_test = dashboard_data.get("latest_test")
    progress = dashboard_data.get("progress") or []
    cumulative_weak_areas = dashboard_data.get("cumulative_weak_areas") or []
    adaptive_guidance = dashboard_data.get("adaptive_guidance") or {}

    elements = []

    # =========================================================================
    # PAGE 1 — TRAINEE CLINICAL OVERVIEW
    # =========================================================================
    p1_elements = []
    p1_elements.append(Paragraph("Medical VR — Venipuncture Training Portfolio", title_style))
    p1_elements.append(Paragraph("Longitudinal Trainee Clinical Performance & Competency Portfolio", subtitle_style))
    p1_elements.append(HRFlowable(width="100%", thickness=1.2, color=c_secondary, spaceAfter=5))

    # Trainee Demographics Table
    user_table_data = [
        [
            Paragraph(f"<b>Trainee ID:</b> {user_id}", body_style),
            Paragraph(f"<b>Name:</b> {user_name}", body_style),
            Paragraph(f"<b>Email:</b> {user_email}", body_style),
            Paragraph(f"<b>Date:</b> {date_str}", body_style)
        ]
    ]
    u_table = Table(user_table_data, colWidths=[110, 160, 160, 110])
    u_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), c_bg_light),
        ("BOX", (0, 0), (-1, -1), 0.5, c_border),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    p1_elements.append(u_table)
    p1_elements.append(Spacer(1, 4))

    # Overall Session Statistics
    total_sess = len(progress)
    test_cnt = sum(1 for p in progress if p.get("session_type") == "TEST")
    train_cnt = sum(1 for p in progress if p.get("session_type") == "TRAINING" or not p.get("session_type"))
    avg_hist_acc = f"{round(sum(p['accuracy'] for p in progress) / total_sess, 2)}%" if total_sess > 0 else "N/A"

    p1_elements.append(Paragraph("OVERALL SIMULATION STATISTICS", section_title))
    stats_data = [
        [
            Paragraph(f"<b>Total Sessions:</b> {total_sess}", body_style),
            Paragraph(f"<b>Training Sessions:</b> {train_cnt}", body_style),
            Paragraph(f"<b>TEST Sessions:</b> {test_cnt}", body_style),
            Paragraph(f"<b>Historical Avg Accuracy:</b> {avg_hist_acc}", body_style)
        ]
    ]
    stats_table = Table(stats_data, colWidths=[135, 135, 135, 135])
    stats_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.white),
        ("BOX", (0, 0), (-1, -1), 0.5, c_border),
        ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#EDF2F7")),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    p1_elements.append(stats_table)
    p1_elements.append(Spacer(1, 5))

    # Latest Authoritative TEST Snapshot
    p1_elements.append(Paragraph("LATEST TEST ASSESSMENT (AUTHORITATIVE)", section_title))
    if latest_test:
        t_res = latest_test.get("result", "NOT_ASSESSED")
        is_pass = (t_res == "PASS")
        t_bg = colors.HexColor("#DEF7EC") if is_pass else colors.HexColor("#FDE8E8")
        t_border = colors.HexColor("#31C48D") if is_pass else colors.HexColor("#F98080")
        t_color = colors.HexColor("#03543F") if is_pass else colors.HexColor("#9B1C1C")

        badge_p = Paragraph(
            f"<font size=11 color='{t_color}'><b>LATEST TEST RESULT: {t_res}</b></font><br/>"
            f"<font size=7 color='#4A5568'>Authoritative deterministic test assessment result. Unalterable by LLM.</font>",
            ParagraphStyle("TBadge", alignment=1, leading=13)
        )
        badge_tab = Table([[badge_p]], colWidths=[540])
        badge_tab.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), t_bg),
            ("BOX", (0, 0), (-1, -1), 1.0, t_border),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ]))
        p1_elements.append(badge_tab)
        p1_elements.append(Spacer(1, 3))

        t_perf = [
            [
                Paragraph(f"<b>Session:</b> #{latest_test.get('session_number', '1')}", body_style),
                Paragraph(f"<b>Completed Steps:</b> {latest_test.get('completed_steps', 0)} / 16", body_style),
                Paragraph(f"<b>Accuracy:</b> {latest_test.get('accuracy', 0.0)}%", body_style),
                Paragraph(f"<b>Total Mistakes:</b> {latest_test.get('total_mistakes', 0)}", body_style)
            ],
            [
                Paragraph(f"<b>Total Attempts:</b> {latest_test.get('total_attempts', 0)}", body_style),
                Paragraph(f"<b>1st Try Correct:</b> {latest_test.get('first_attempt_correct_count', 0)} / 16", body_style),
                Paragraph(f"<b>Total Time:</b> {round(float(latest_test.get('total_time_seconds', 0.0)), 1)}s", body_style),
                Paragraph(f"<b>Avg Step Time:</b> {round(float(latest_test.get('average_step_time_seconds', 0.0)), 1)}s", body_style)
            ]
        ]
        t_perf_tab = Table(t_perf, colWidths=[135, 135, 135, 135])
        t_perf_tab.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), c_bg_light),
            ("BOX", (0, 0), (-1, -1), 0.5, c_border),
            ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#EDF2F7")),
            ("TOPPADDING", (0, 0), (-1, -1), 2.5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 2.5),
        ]))
        p1_elements.append(t_perf_tab)
    else:
        p1_elements.append(Paragraph("No recorded TEST sessions.", body_style))

    p1_elements.append(Spacer(1, 5))

    # Latest Formative TRAINING Snapshot
    p1_elements.append(Paragraph("LATEST TRAINING EVALUATION (FORMATIVE)", section_title))
    if latest_training:
        tr_stat = latest_training.get("overall_result", "EVALUATED")
        is_sat = tr_stat in ["EXCELLENT", "SATISFACTORY", "COMPLETED"]
        tr_bg = colors.HexColor("#EBF8FF") if is_sat else colors.HexColor("#FFFBEB")
        tr_border = colors.HexColor("#3182CE") if is_sat else colors.HexColor("#F59E0B")
        tr_color = colors.HexColor("#1E3A8A") if is_sat else colors.HexColor("#92400E")

        badge_tr = Paragraph(
            f"<font size=11 color='{tr_color}'><b>TRAINING STATUS: {tr_stat}</b></font><br/>"
            f"<font size=7 color='#4A5568'>Formative training evaluation status. Unalterable by LLM.</font>",
            ParagraphStyle("TrBadge", alignment=1, leading=13)
        )
        badge_tr_tab = Table([[badge_tr]], colWidths=[540])
        badge_tr_tab.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), tr_bg),
            ("BOX", (0, 0), (-1, -1), 1.0, tr_border),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ]))
        p1_elements.append(badge_tr_tab)
        p1_elements.append(Spacer(1, 3))

        tr_perf = [
            [
                Paragraph(f"<b>Session:</b> #{latest_training.get('session_number', '1')}", body_style),
                Paragraph(f"<b>Completed Steps:</b> {latest_training.get('completed_steps', 0)} / 16", body_style),
                Paragraph(f"<b>Accuracy:</b> {latest_training.get('accuracy', 0.0)}%", body_style),
                Paragraph(f"<b>Total Mistakes:</b> {latest_training.get('total_mistakes', 0)}", body_style)
            ],
            [
                Paragraph(f"<b>Total Attempts:</b> {latest_training.get('total_attempts', 0)}", body_style),
                Paragraph(f"<b>1st Try Correct:</b> {latest_training.get('first_attempt_correct_count', 0)} / 16", body_style),
                Paragraph(f"<b>Total Time:</b> {round(float(latest_training.get('total_time_seconds', 0.0)), 1)}s", body_style),
                Paragraph(f"<b>Avg Step Time:</b> {round(float(latest_training.get('average_step_time_seconds', 0.0)), 1)}s", body_style)
            ]
        ]
        tr_perf_tab = Table(tr_perf, colWidths=[135, 135, 135, 135])
        tr_perf_tab.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), c_bg_light),
            ("BOX", (0, 0), (-1, -1), 0.5, c_border),
            ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#EDF2F7")),
            ("TOPPADDING", (0, 0), (-1, -1), 2.5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 2.5),
        ]))
        p1_elements.append(tr_perf_tab)
    else:
        p1_elements.append(Paragraph("No recorded training sessions.", body_style))

    elements.append(KeepTogether(p1_elements))

    # =========================================================================
    # PAGE BREAK — TO PAGE 2
    # =========================================================================
    elements.append(PageBreak())

    # =========================================================================
    # PAGE 2 — LONGITUDINAL PERFORMANCE PROGRESSION
    # =========================================================================
    p2_elements = []
    p2_elements.append(Paragraph("LONGITUDINAL PERFORMANCE PROGRESSION", page_heading))
    p2_elements.append(Paragraph("Historical session-by-session procedure telemetry and accuracy trajectory.", subtitle_style))
    p2_elements.append(HRFlowable(width="100%", thickness=1, color=c_secondary, spaceAfter=5))

    if progress:
        p_rows = [
            [
                Paragraph("<b>Session</b>", body_bold),
                Paragraph("<b>Type</b>", body_bold),
                Paragraph("<b>Completed</b>", body_bold),
                Paragraph("<b>Accuracy</b>", body_bold),
                Paragraph("<b>Mistakes</b>", body_bold),
                Paragraph("<b>Attempts</b>", body_bold),
                Paragraph("<b>Duration</b>", body_bold),
                Paragraph("<b>Result / Status</b>", body_bold)
            ]
        ]
        for item in progress:
            p_rows.append([
                f"Session #{item['session_number']}",
                str(item.get("session_type", "TRAINING")),
                f"{item['completed_steps']} / 16",
                f"{item['accuracy']}%",
                str(item['total_mistakes']),
                str(item['total_attempts']),
                f"{round(float(item['total_time_seconds']), 1)}s",
                str(item.get("result_or_status", "-"))
            ])

        prog_table = Table(p_rows, colWidths=[60, 65, 75, 60, 55, 55, 65, 105])
        prog_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), c_secondary),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 7.5),
            ("ALIGN", (0, 0), (0, -1), "CENTER"),
            ("ALIGN", (1, 0), (6, -1), "CENTER"),
            ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E0")),
            ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#A0AEC0")),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, c_bg_light]),
            ("TOPPADDING", (0, 0), (-1, -1), 2.5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 2.5),
        ]))
        p2_elements.append(prog_table)
        p2_elements.append(Spacer(1, 6))

        # Trajectory Representation (existing accuracy values)
        acc_vals = [f"{p['accuracy']}%" for p in progress]
        acc_traj = " → ".join(acc_vals) if acc_vals else "None recorded"
        mist_vals = [f"{p['total_mistakes']} err" for p in progress]
        mist_traj = " → ".join(mist_vals) if mist_vals else "None recorded"

        traj_box = [
            f"<b>Accuracy Progression Trajectory:</b> {acc_traj}",
            f"<b>Mistakes Progression Trajectory:</b> {mist_traj}"
        ]
        t_box_table = Table([[Paragraph("<br/>".join(traj_box), body_style)]], colWidths=[540])
        t_box_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#EBF8FF")),
            ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#3182CE")),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ]))
        p2_elements.append(t_box_table)
    else:
        p2_elements.append(Paragraph("No recorded session performance history available.", body_style))

    elements.append(KeepTogether(p2_elements))

    # =========================================================================
    # PAGE BREAK — TO PAGE 3
    # =========================================================================
    elements.append(PageBreak())

    # =========================================================================
    # PAGE 3 — CUMULATIVE WEAK AREAS — HISTORICAL
    # =========================================================================
    p3_elements = []
    p3_elements.append(Paragraph("CUMULATIVE WEAK AREAS — HISTORICAL", page_heading))
    p3_elements.append(Paragraph("Cross-session vulnerability ranking aggregated across all historical simulations.", subtitle_style))
    p3_elements.append(HRFlowable(width="100%", thickness=1, color=c_secondary, spaceAfter=5))

    p3_elements.append(Paragraph(
        "<i>Note: Cumulative weak areas represent recurring procedural vulnerabilities across multiple historical sessions. "
        "Calculated by cumulative_weak_area_service using total attempts and mistakes. Distinct from session-level errors.</i>",
        ParagraphStyle("CwaNote", parent=body_style, fontSize=7.5, textColor=c_muted, spaceAfter=4)
    ))

    if cumulative_weak_areas:
        cwa_rows = [
            [
                Paragraph("<b>Rank</b>", body_bold),
                Paragraph("<b>Step ID</b>", body_bold),
                Paragraph("<b>Step Name</b>", body_bold),
                Paragraph("<b>Attempts</b>", body_bold),
                Paragraph("<b>Mistakes</b>", body_bold),
                Paragraph("<b>Mistake Ratio</b>", body_bold),
                Paragraph("<b>Severity</b>", body_bold),
                Paragraph("<b>Last Session</b>", body_bold)
            ]
        ]
        for area in cumulative_weak_areas:
            s_id = area.get("step_id", 0)
            step_name = area.get("step_name") or next((s["name"] for s in PROCEDURE_STEPS_SPEC if s["id"] == s_id), f"Step {s_id}")
            attempts_c = area.get("total_attempts", 0)
            mistakes_c = area.get("total_mistakes", 0)
            ratio_c = f"{round(float(area.get('mistake_ratio', 0.0)), 1)}%"
            severity_c = area.get("severity", "LOW")
            rank_c = str(area.get("rank", "-"))
            last_sess = f"Session #{area.get('last_session_id', '-')}" if area.get('last_session_id') else "-"

            cwa_rows.append([
                rank_c,
                str(s_id),
                step_name,
                str(attempts_c),
                str(mistakes_c),
                ratio_c,
                severity_c,
                last_sess
            ])

        cwa_table = Table(cwa_rows, colWidths=[35, 45, 145, 65, 65, 70, 60, 55])
        cwa_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#C53030")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 7.5),
            ("ALIGN", (0, 0), (1, -1), "CENTER"),
            ("ALIGN", (3, 0), (7, -1), "CENTER"),
            ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#FEB2B2")),
            ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#C53030")),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, c_bg_light]),
            ("TOPPADDING", (0, 0), (-1, -1), 2.5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 2.5),
        ]))
        p3_elements.append(cwa_table)
    else:
        p3_elements.append(Paragraph("No cumulative weak areas identified from available history.", body_style))

    elements.append(KeepTogether(p3_elements))

    # =========================================================================
    # PAGE BREAK — TO PAGE 4
    # =========================================================================
    elements.append(PageBreak())

    # =========================================================================
    # PAGE 4 — ADAPTIVE LEARNING PLAN / NEXT TRAINING FOCUS
    # =========================================================================
    p4_elements = []
    p4_elements.append(Paragraph("ADAPTIVE GUIDANCE / NEXT TRAINING FOCUS", page_heading))
    p4_elements.append(Paragraph("Targeted clinical directives and priority corrective actions for upcoming simulations.", subtitle_style))
    p4_elements.append(HRFlowable(width="100%", thickness=1, color=c_secondary, spaceAfter=5))

    p_ver = adaptive_guidance.get("profile_version")
    p_target = adaptive_guidance.get("session_target")
    g_avail = adaptive_guidance.get("guidance_available", False)

    guidance_meta = [
        [
            Paragraph(f"<b>Active Profile Version:</b> {p_ver if p_ver is not None else 'N/A'}", body_style),
            Paragraph(f"<b>Curriculum Target Session:</b> #{p_target if p_target is not None else 'N/A'}", body_style),
            Paragraph(f"<b>Guidance Status:</b> {'Active Profile' if g_avail else 'No Active Profile'}", body_style)
        ]
    ]
    gm_table = Table(guidance_meta, colWidths=[180, 180, 180])
    gm_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), c_bg_light),
        ("BOX", (0, 0), (-1, -1), 0.5, c_border),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    p4_elements.append(gm_table)
    p4_elements.append(Spacer(1, 5))

    guidance_steps = adaptive_guidance.get("guidance", [])
    if g_avail and guidance_steps:
        # Separate into priority focus (HIGH, MEDIUM) and standard protocol (LOW)
        priority_steps = [g for g in guidance_steps if g.get("guidance_level") in ["HIGH", "MEDIUM"]]
        standard_steps = [g for g in guidance_steps if g.get("guidance_level") == "LOW"]

        p4_elements.append(Paragraph("PRIORITY TRAINING FOCUS (HIGH & MEDIUM CORRECTIVE DIRECTIVES)", section_title))
        if priority_steps:
            g_rows = [
                [
                    Paragraph("<b>Step</b>", body_bold),
                    Paragraph("<b>Step Name</b>", body_bold),
                    Paragraph("<b>Guidance Level</b>", body_bold),
                    Paragraph("<b>Mistakes</b>", body_bold),
                    Paragraph("<b>Error Rate</b>", body_bold),
                    Paragraph("<b>Targeted Clinical Action</b>", body_bold)
                ]
            ]
            for g in priority_steps:
                s_id = g.get("step_id", 0)
                step_name = g.get("step_name") or next((s["name"] for s in PROCEDURE_STEPS_SPEC if s["id"] == s_id), f"Step {s_id}")
                level = g.get("guidance_level", "LOW")
                m_cnt = str(g.get("mistake_count", 0))
                m_rat = f"{round(float(g.get('mistake_ratio', 0.0)), 1)}%"
                msg = g.get("guidance_message", "Review step protocol.")
                g_rows.append([
                    str(s_id),
                    step_name,
                    level,
                    m_cnt,
                    m_rat,
                    msg
                ])

            p_table = Table(g_rows, colWidths=[35, 115, 70, 50, 55, 215])
            p_table.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2C5282")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 7.5),
                ("ALIGN", (0, 0), (0, -1), "CENTER"),
                ("ALIGN", (2, 0), (4, -1), "CENTER"),
                ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#BEE3F8")),
                ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#2C5282")),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F7FAFC")]),
                ("TOPPADDING", (0, 0), (-1, -1), 2.5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 2.5),
            ]))
            p4_elements.append(p_table)
        else:
            p4_elements.append(Paragraph("No HIGH or MEDIUM priority corrective directives currently assigned. All steps currently on standard protocol.", body_style))

        p4_elements.append(Spacer(1, 5))
        p4_elements.append(Paragraph("STANDARD PROTOCOL STEPS", section_title))
        if standard_steps:
            std_names = [f"Step {s.get('step_id')}: {s.get('step_name')}" for s in standard_steps]
            std_text = "The following steps have low or zero recorded errors and follow the standard procedure: " + ", ".join(std_names) + "."
            p4_elements.append(Paragraph(std_text, body_style))
        else:
            p4_elements.append(Paragraph("All steps currently assigned adaptive corrective guidance.", body_style))
    else:
        p4_elements.append(Paragraph("No active adaptive guidance available.", body_style))

    elements.append(KeepTogether(p4_elements))

    # =========================================================================
    # PAGE BREAK — TO PAGE 5
    # =========================================================================
    elements.append(PageBreak())

    # =========================================================================
    # PAGE 5 — ASSESSMENT HISTORY & SUPERVISOR SIGN-OFF
    # =========================================================================
    p5_elements = []
    p5_elements.append(Paragraph("ASSESSMENT HISTORY & CLINICAL SUPERVISOR REVIEW", page_heading))
    p5_elements.append(Paragraph("Authoritative summative & formative assessment log and manual review sign-off.", subtitle_style))
    p5_elements.append(HRFlowable(width="100%", thickness=1, color=c_secondary, spaceAfter=5))

    # 1. TEST History Log
    p5_elements.append(Paragraph("TEST ASSESSMENT LOG (AUTHORITATIVE SUMMATIVE EVALUATIONS)", section_title))
    test_prog = [p for p in progress if p.get("session_type") == "TEST"]
    if test_prog:
        t_log_rows = [
            [
                Paragraph("<b>Session</b>", body_bold),
                Paragraph("<b>Completed</b>", body_bold),
                Paragraph("<b>Accuracy</b>", body_bold),
                Paragraph("<b>Mistakes</b>", body_bold),
                Paragraph("<b>Attempts</b>", body_bold),
                Paragraph("<b>Duration</b>", body_bold),
                Paragraph("<b>Authoritative Result</b>", body_bold)
            ]
        ]
        for tp in test_prog:
            t_log_rows.append([
                f"Session #{tp['session_number']}",
                f"{tp['completed_steps']} / 16",
                f"{tp['accuracy']}%",
                str(tp['total_mistakes']),
                str(tp['total_attempts']),
                f"{round(float(tp['total_time_seconds']), 1)}s",
                str(tp.get("result_or_status", "NOT_ASSESSED"))
            ])
        t_log_table = Table(t_log_rows, colWidths=[70, 75, 75, 65, 65, 75, 115])
        t_log_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1A365D")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 7.5),
            ("ALIGN", (0, 0), (5, -1), "CENTER"),
            ("ALIGN", (6, 0), (6, -1), "CENTER"),
            ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E0")),
            ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#1A365D")),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, c_bg_light]),
            ("TOPPADDING", (0, 0), (-1, -1), 2.5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 2.5),
        ]))
        p5_elements.append(t_log_table)
    else:
        p5_elements.append(Paragraph("No recorded TEST sessions.", body_style))

    p5_elements.append(Spacer(1, 5))

    # 2. TRAINING History Log
    p5_elements.append(Paragraph("TRAINING LOG (FORMATIVE EVALUATIONS)", section_title))
    train_prog = [p for p in progress if p.get("session_type") == "TRAINING" or not p.get("session_type")]
    if train_prog:
        tr_log_rows = [
            [
                Paragraph("<b>Session</b>", body_bold),
                Paragraph("<b>Completed</b>", body_bold),
                Paragraph("<b>Accuracy</b>", body_bold),
                Paragraph("<b>Mistakes</b>", body_bold),
                Paragraph("<b>Attempts</b>", body_bold),
                Paragraph("<b>Duration</b>", body_bold),
                Paragraph("<b>Training Status</b>", body_bold)
            ]
        ]
        for trp in train_prog:
            tr_log_rows.append([
                f"Session #{trp['session_number']}",
                f"{trp['completed_steps']} / 16",
                f"{trp['accuracy']}%",
                str(trp['total_mistakes']),
                str(trp['total_attempts']),
                f"{round(float(trp['total_time_seconds']), 1)}s",
                str(trp.get("result_or_status", "COMPLETED" if trp['completed_steps'] == 16 else "NEEDS_PRACTICE"))
            ])
        tr_log_table = Table(tr_log_rows, colWidths=[70, 75, 75, 65, 65, 75, 115])
        tr_log_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2B6CB0")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 7.5),
            ("ALIGN", (0, 0), (5, -1), "CENTER"),
            ("ALIGN", (6, 0), (6, -1), "CENTER"),
            ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E0")),
            ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#2B6CB0")),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, c_bg_light]),
            ("TOPPADDING", (0, 0), (-1, -1), 2.5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 2.5),
        ]))
        p5_elements.append(tr_log_table)
    else:
        p5_elements.append(Paragraph("No recorded training sessions.", body_style))

    p5_elements.append(Spacer(1, 5))

    # 3. Educational & Deterministic Assessment Advisory
    p5_elements.append(Paragraph(
        "<b>EDUCATIONAL & DETERMINISTIC ASSESSMENT ADVISORY:</b><br/>"
        "Assessment results are determined by the deterministic backend assessment engine. "
        "The portfolio PDF does not independently calculate or alter assessment results. "
        "AI and adaptive guidance feedback are supplementary educational tools designed to support procedural deliberate practice.",
        banner_ai
    ))
    p5_elements.append(Spacer(1, 4))

    # 4. Manual Clinical Supervisor Review Block
    signoff_text = (
        f"<b>CLINICAL SUPERVISOR / FACULTY MANUAL REVIEW</b><br/>"
        f"<font size=7 color='#718096'>Trainee: {user_name} (ID: {user_id}) &nbsp;&bull;&nbsp; Portfolio Evaluation</font><br/><br/>"
        f"<b>Reviewer Name:</b> ____________________________________________________<br/><br/>"
        f"<b>Institutional Department / Role:</b> ____________________________________<br/><br/>"
        f"<b>Review Date:</b> ______________________________________________________<br/><br/>"
        f"<b>Supervisor Recommendation / Faculty Disposition:</b><br/>"
        f"[ &nbsp; ] Recommended for Clinical Observation &nbsp;&nbsp;&nbsp;&nbsp; [ &nbsp; ] Additional VR Simulation Prescribed<br/>"
        f"[ &nbsp; ] Repeat Formal TEST Simulation &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp; [ &nbsp; ] Formative Curriculum Milestone Documented<br/><br/>"
        f"<b>Supervisor Signature:</b> _______________________________________________<br/>"
        f"<font size=6.5 color='#A0AEC0'>* Note: This portfolio report provides deterministic telemetry and longitudinal analytics for faculty review. "
        f"It does not automatically certify or approve the trainee.</font>"
    )
    signoff_table = Table([[Paragraph(signoff_text, body_style)]], colWidths=[540])
    signoff_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), c_bg_light),
        ("BOX", (0, 0), (-1, -1), 0.8, c_primary),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    p5_elements.append(signoff_table)

    elements.append(KeepTogether(p5_elements))

    # Build PDF with two-pass PortfolioNumberedCanvas
    doc.build(elements, canvasmaker=PortfolioNumberedCanvas)
    buffer.seek(0)
    return buffer
