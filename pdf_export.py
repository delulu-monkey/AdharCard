import io
from datetime import datetime
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    HRFlowable,
    KeepTogether
)
from reportlab.pdfgen import canvas

class NumberedCanvas(canvas.Canvas):
    """Two-pass canvas to dynamically compute and draw total page count."""
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
            self.draw_page_decorations(num_pages)
            super().showPage()
        super().save()

    def draw_page_decorations(self, total_pages):
        self.saveState()
        self.setFont("Helvetica", 8)
        self.setFillColor(colors.HexColor("#64748B"))
        
        # Header (pages after page 1)
        if self._pageNumber > 1:
            self.drawString(54, letter[1] - 36, "EchoNotes — Lecture Digest & Summary")
            self.drawRightString(letter[0] - 54, letter[1] - 36, "MIT 8.02: Electricity & Magnetism")
            self.setStrokeColor(colors.HexColor("#E2E8F0"))
            self.setLineWidth(0.5)
            self.line(54, letter[1] - 42, letter[0] - 54, letter[1] - 42)

        # Running Footer
        self.setStrokeColor(colors.HexColor("#E2E8F0"))
        self.setLineWidth(0.5)
        self.line(54, 46, letter[0] - 54, 46)
        
        self.drawString(54, 32, "EchoNotes Academic Summary Report")
        self.drawRightString(
            letter[0] - 54, 32, f"Page {self._pageNumber} of {total_pages}"
        )
        self.restoreState()


def mmss(s):
    m = int(s // 60)
    sec = int(s % 60)
    return f"{m}:{sec:02d}"


def build_lecture_pdf(chunks: list[dict], course_name: str = "MIT 8.02: Electricity and Magnetism") -> bytes:
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        leftMargin=54,
        rightMargin=54,
        topMargin=54,
        bottomMargin=54
    )

    styles = getSampleStyleSheet()

    # Custom styles
    title_style = ParagraphStyle(
        'DocTitle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=20,
        leading=24,
        textColor=colors.HexColor('#0F172A'),
        spaceAfter=4
    )
    subtitle_style = ParagraphStyle(
        'DocSubtitle',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=11,
        leading=15,
        textColor=colors.HexColor('#475569'),
        spaceAfter=14
    )
    section_title_style = ParagraphStyle(
        'SectionTitle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=13,
        leading=16,
        textColor=colors.HexColor('#0F172A'),
        spaceAfter=6
    )
    meta_style = ParagraphStyle(
        'MetaStyle',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9,
        leading=12,
        textColor=colors.HexColor('#334155')
    )
    meta_bold = ParagraphStyle(
        'MetaBold',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=9,
        leading=12,
        textColor=colors.HexColor('#0F172A')
    )
    h3_style = ParagraphStyle(
        'H3Style',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=10,
        leading=14,
        textColor=colors.HexColor('#1E293B'),
        spaceBefore=8,
        spaceAfter=4
    )
    body_style = ParagraphStyle(
        'BodyStyle',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9.5,
        leading=14,
        textColor=colors.HexColor('#334155'),
        spaceAfter=4
    )
    bullet_style = ParagraphStyle(
        'BulletStyle',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9,
        leading=13.5,
        textColor=colors.HexColor('#334155'),
        leftIndent=14,
        firstLineIndent=-10,
        spaceAfter=3
    )
    term_style = ParagraphStyle(
        'TermStyle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=9,
        leading=13,
        textColor=colors.HexColor('#0F172A')
    )
    def_style = ParagraphStyle(
        'DefStyle',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=8.5,
        leading=12,
        textColor=colors.HexColor('#475569')
    )
    resource_style = ParagraphStyle(
        'ResourceStyle',
        parent=styles['Normal'],
        fontName='Helvetica-Oblique',
        fontSize=8.5,
        leading=12.5,
        textColor=colors.HexColor('#2563EB'),
        leftIndent=14,
        firstLineIndent=-10,
        spaceAfter=2
    )

    story = []

    # Title block
    story.append(Paragraph("EchoNotes — Lecture Summary Report", title_style))
    story.append(Paragraph(f"Course: {course_name} &nbsp;|&nbsp; Generated on: {datetime.now().strftime('%B %d, %Y, %I:%M %p')}", subtitle_style))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#CBD5E1"), spaceAfter=14))

    # Summary overview box
    total_chunks = len(chunks)
    flagged_chunks = sum(1 for c in chunks if c.get("important"))
    duration_secs = chunks[-1]["end"] if chunks else 0
    duration_str = mmss(duration_secs)

    summary_data = [
        [
            Paragraph(f"<b>Total Segments:</b> {total_chunks}", meta_style),
            Paragraph(f"<b>Flagged Key Topics:</b> {flagged_chunks}", meta_style),
            Paragraph(f"<b>Coverage Window:</b> 00:00 – {duration_str}", meta_style)
        ]
    ]
    summary_table = Table(summary_data, colWidths=[168, 168, 168])
    summary_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#F8FAFC')),
        ('BOX', (0,0), (-1,-1), 0.5, colors.HexColor('#E2E8F0')),
        ('INNERGRID', (0,0), (-1,-1), 0.5, colors.HexColor('#E2E8F0')),
        ('PADDING', (0,0), (-1,-1), 8),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
    ]))
    story.append(summary_table)
    story.append(Spacer(1, 16))

    # Iterate through chunks
    for idx, c in enumerate(chunks, 1):
        chunk_story = []

        start_str = mmss(c.get("start", 0))
        end_str = mmss(c.get("end", 0))
        time_badge = f"{start_str} – {end_str}"
        topic = c.get("topic", f"Lecture Segment {idx}")
        importance = c.get("importance", "Core")
        difficulty = c.get("difficulty", "Intermediate")
        is_important = c.get("important", False)

        # Header for the chunk
        header_text = f"<b>{idx}. [{time_badge}] &nbsp; {topic}</b>"
        chunk_story.append(Paragraph(header_text, section_title_style))

        # Metadata badges row
        meta_items = [
            f"<b>Importance:</b> {importance}",
            f"<b>Difficulty:</b> {difficulty}"
        ]
        if is_important:
            meta_items.append("<b>Status:</b> Key Topic (Flagged)")
        
        meta_line = " &nbsp;&nbsp;|&nbsp;&nbsp; ".join(meta_items)
        meta_table = Table([[Paragraph(meta_line, meta_style)]], colWidths=[504])
        meta_table.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#FFFBEB' if is_important else '#F1F5F9')),
            ('BOX', (0,0), (-1,-1), 0.5, colors.HexColor('#FCD34D' if is_important else '#E2E8F0')),
            ('PADDING', (0,0), (-1,-1), 5),
        ]))
        chunk_story.append(meta_table)
        chunk_story.append(Spacer(1, 6))

        # Notes section
        notes = c.get("notes", [])
        if notes:
            chunk_story.append(Paragraph("Key Takeaways & Lecture Notes", h3_style))
            for note in notes:
                chunk_story.append(Paragraph(f"&bull;&nbsp; {note}", bullet_style))

        # Concepts section
        concepts = c.get("concepts", [])
        if concepts:
            chunk_story.append(Paragraph("Core Terminology & Defined Concepts", h3_style))
            concept_rows = []
            for item in concepts:
                term_p = Paragraph(item.get("term", ""), term_style)
                def_p = Paragraph(item.get("definition", ""), def_style)
                concept_rows.append([term_p, def_p])
            
            c_table = Table(concept_rows, colWidths=[140, 364])
            c_table.setStyle(TableStyle([
                ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#FAFAFA')),
                ('BOX', (0,0), (-1,-1), 0.5, colors.HexColor('#E2E8F0')),
                ('INNERGRID', (0,0), (-1,-1), 0.5, colors.HexColor('#E2E8F0')),
                ('PADDING', (0,0), (-1,-1), 5),
                ('VALIGN', (0,0), (-1,-1), 'TOP'),
            ]))
            chunk_story.append(c_table)

        # Questions section
        questions = c.get("questions", [])
        if questions:
            chunk_story.append(Paragraph("Conceptual Review Questions", h3_style))
            for q_idx, q in enumerate(questions, 1):
                chunk_story.append(Paragraph(f"<b>Q{q_idx}:</b> {q.get('question', '')}", body_style))
                options = q.get("options")
                if options:
                    for o_idx, opt in enumerate(options):
                        letter_tag = chr(65 + o_idx)
                        chunk_story.append(Paragraph(f"&nbsp;&nbsp;&nbsp;&nbsp;<b>{letter_tag}.</b> {opt}", bullet_style))
                chunk_story.append(Paragraph(f"&nbsp;&nbsp;&nbsp;&nbsp;<i>Confirmed Answer:</i> {q.get('answer', '')}", body_style))
                chunk_story.append(Spacer(1, 3))

        # Study resources section (where you can study the topics)
        study_resources = c.get("study_resources", [])
        if study_resources:
            chunk_story.append(Paragraph("Recommended Study Resources & References", h3_style))
            for res in study_resources:
                chunk_story.append(Paragraph(f"&rarr;&nbsp; {res}", resource_style))

        # Action items section
        actions = c.get("action_items", [])
        if actions:
            chunk_story.append(Paragraph("Action Items & Deliverables", h3_style))
            for act in actions:
                chunk_story.append(Paragraph(f"&bull;&nbsp; [ ] {act}", bullet_style))

        chunk_story.append(Spacer(1, 10))
        chunk_story.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#E2E8F0"), spaceAfter=14))

        story.append(KeepTogether(chunk_story[:4]))  # keep header & meta together
        story.extend(chunk_story[4:])

    doc.build(story, canvasmaker=NumberedCanvas)
    return buffer.getvalue()
