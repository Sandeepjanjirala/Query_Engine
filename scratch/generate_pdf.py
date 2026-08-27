import sys
from pathlib import Path
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable

def generate_pdf(output_path: str):
    doc = SimpleDocTemplate(
        output_path,
        pagesize=letter,
        rightMargin=36,
        leftMargin=36,
        topMargin=36,
        bottomMargin=36
    )

    styles = getSampleStyleSheet()

    # Custom styles
    title_style = ParagraphStyle(
        'DocTitle',
        parent=styles['Heading1'],
        fontSize=20,
        leading=24,
        textColor=colors.HexColor('#1A365D'),
        spaceAfter=6
    )

    subtitle_style = ParagraphStyle(
        'DocSubTitle',
        parent=styles['Normal'],
        fontSize=10,
        leading=14,
        textColor=colors.HexColor('#4A5568'),
        spaceAfter=15
    )

    h2_style = ParagraphStyle(
        'SectionH2',
        parent=styles['Heading2'],
        fontSize=12,
        leading=16,
        textColor=colors.HexColor('#2B6CB0'),
        spaceBefore=12,
        spaceAfter=6
    )

    body_style = ParagraphStyle(
        'BodyText',
        parent=styles['Normal'],
        fontSize=9,
        leading=13,
        textColor=colors.HexColor('#2D3748')
    )

    bullet_style = ParagraphStyle(
        'BulletItem',
        parent=styles['Normal'],
        fontSize=9,
        leading=13,
        textColor=colors.HexColor('#2D3748'),
        leftIndent=15,
        spaceAfter=3
    )

    elements = []

    # Title & Header
    elements.append(Paragraph("Branch Analytics AI Assistant — Query Reference Guide", title_style))
    elements.append(Paragraph("A quick-reference guide of supported questions, metrics, dimensions, and natural language query patterns.", subtitle_style))
    elements.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor('#CBD5E0'), spaceAfter=12))

    categories = [
        ("1. Fee Due & Books Queries", [
            ("Current Year Fee Due", "Show top 10 branches by fee due<br/>What is the live student fee due for KAKINADA 1?<br/>Give me total fee due by zone"),
            ("Fee Due Count & Zero Paid", "Show top 5 branches by current year due count<br/>Which branches have the highest actual zero paid count?<br/>Show branches by current year zero paid fee due"),
            ("Last Year Fee Due & Count", "Show top 5 branches by last year fee due<br/>What was the last year due count for KAKINADA 1?"),
            ("Books Not Purchased", "Show branches with fee paid but books not purchased<br/>Which branches have fee not paid and books not purchased?")
        ]),
        ("2. Dropout & Student Strength Queries", [
            ("Dropout Percentage & Counts", "Which are the top 5 branches by dropout percentage?<br/>Show branches with dropout percentage above 15%<br/>How many students dropped out from KAKINADA 1?"),
            ("Net & Grant Strength", "Which branches have the highest net strength?<br/>Give me total strength by AGM<br/>Show strength difference ranking across branches")
        ]),
        ("3. Staff & Section Queries", [
            ("Staff Breakdown", "Give me the total staff count by zone<br/>What is the activity staff count at KAKINADA 1?<br/>Show administration staff count by RI"),
            ("Sections & Ratios", "Which branches have the highest student teacher ratio?<br/>Show average students per section by zone")
        ]),
        ("4. Room Utilization & Vacancy Queries", [
            ("Occupancy & Vacancy Rates", "Show the bottom 3 branches by room occupancy percentage<br/>Show branches with more than 20% vacant rooms<br/>Compare occupied and empty rooms by zone<br/>What is the total number of occupied rooms in current scope?")
        ]),
        ("5. Year-over-Year (YoY) & Scorecard Queries", [
            ("YoY Comparisons", "Which branches improved their dropout percentage compared with last year?<br/>Show branches with the biggest gain in net strength from last year<br/>Compare current year vs last year staff count by RI"),
            ("Branch Scorecard / Snapshot", "Show the complete scorecard for KAKINADA 1 branch<br/>Show the dropout and strength details for KAKINADA 1<br/>Give me all metrics for this branch")
        ]),
        ("6. Multi-Dataset Queries", [
            ("Cross-Dataset Queries", "Show top branches by fee due along with dropout percentage<br/>Show branches with high dropout percentage and high fee due")
        ])
    ]

    for cat_title, items in categories:
        elements.append(Paragraph(cat_title, h2_style))
        table_data = [[Paragraph("<b>Query Category</b>", body_style), Paragraph("<b>Example Natural-Language Questions</b>", body_style)]]
        
        for sub_cat, sample_q in items:
            table_data.append([
                Paragraph(f"<b>{sub_cat}</b>", body_style),
                Paragraph(sample_q, body_style)
            ])

        t = Table(table_data, colWidths=[160, 380])
        t.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#EDF2F7')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.HexColor('#2D3748')),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#E2E8F0')),
            ('TOPPADDING', (0, 0), (-1, -1), 4),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ]))
        elements.append(t)
        elements.append(Spacer(1, 8))

    doc.build(elements)

if __name__ == '__main__':
    out = sys.argv[1]
    generate_pdf(out)
    print(f"Successfully generated PDF at {out}")
