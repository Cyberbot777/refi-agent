"""
Simple markdown-to-PDF converter for underwriting reports.
Takes the agent's markdown output and creates a professional PDF.
"""

import io
import re
from datetime import date
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.enums import TA_LEFT, TA_CENTER


def markdown_to_pdf(markdown_text: str, refi_id: str) -> bytes:
    """
    Convert markdown report to PDF bytes.
    
    Args:
        markdown_text: The agent's markdown report
        refi_id: Application ID for the filename
        
    Returns:
        PDF as bytes
    """
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        rightMargin=0.75*inch,
        leftMargin=0.75*inch,
        topMargin=0.75*inch,
        bottomMargin=0.75*inch
    )
    
    # Styles
    styles = getSampleStyleSheet()
    
    # Custom styles
    styles.add(ParagraphStyle(
        name='ReportTitle',
        parent=styles['Heading1'],
        fontSize=18,
        spaceAfter=20,
        textColor=colors.HexColor('#1e3a5f'),
        alignment=TA_CENTER
    ))
    
    styles.add(ParagraphStyle(
        name='SectionHeader',
        parent=styles['Heading2'],
        fontSize=14,
        spaceBefore=15,
        spaceAfter=10,
        textColor=colors.HexColor('#2c5282'),
        borderPadding=(5, 0, 5, 0)
    ))
    
    styles.add(ParagraphStyle(
        name='SubHeader',
        parent=styles['Heading3'],
        fontSize=11,
        spaceBefore=10,
        spaceAfter=5,
        textColor=colors.HexColor('#4a5568')
    ))
    
    styles.add(ParagraphStyle(
        name='BodyText',
        parent=styles['Normal'],
        fontSize=10,
        spaceAfter=6,
        leading=14
    ))
    
    styles.add(ParagraphStyle(
        name='BulletItem',
        parent=styles['Normal'],
        fontSize=10,
        leftIndent=20,
        spaceAfter=4,
        leading=12
    ))
    
    styles.add(ParagraphStyle(
        name='PassText',
        parent=styles['Normal'],
        fontSize=10,
        textColor=colors.HexColor('#22543d'),
        leftIndent=20,
        spaceAfter=4
    ))
    
    styles.add(ParagraphStyle(
        name='FailText',
        parent=styles['Normal'],
        fontSize=10,
        textColor=colors.HexColor('#c53030'),
        leftIndent=20,
        spaceAfter=4
    ))
    
    # Build content
    story = []
    
    # Title
    story.append(Paragraph("UNDERWRITING REPORT", styles['ReportTitle']))
    story.append(Paragraph(f"Application: {refi_id}", styles['BodyText']))
    story.append(Paragraph(f"Generated: {date.today().strftime('%B %d, %Y')}", styles['BodyText']))
    story.append(Spacer(1, 20))
    
    # Parse and convert markdown
    lines = markdown_text.split('\n')
    
    for line in lines:
        line = line.strip()
        if not line:
            story.append(Spacer(1, 6))
            continue
        
        # Headers
        if line.startswith('# '):
            story.append(Paragraph(clean_text(line[2:]), styles['ReportTitle']))
        elif line.startswith('## '):
            story.append(Paragraph(clean_text(line[3:]), styles['SectionHeader']))
        elif line.startswith('### '):
            story.append(Paragraph(clean_text(line[4:]), styles['SubHeader']))
        
        # Pass/Fail items (with checkmarks)
        elif '✓' in line or 'PASS' in line.upper():
            text = clean_text(line.replace('✓', '✓ ').replace('✗', '✗ '))
            story.append(Paragraph(f"✓ {text}", styles['PassText']))
        elif '✗' in line or 'FAIL' in line.upper():
            text = clean_text(line.replace('✓', '✓ ').replace('✗', '✗ '))
            story.append(Paragraph(f"✗ {text}", styles['FailText']))
        
        # Bullet points
        elif line.startswith('- ') or line.startswith('* '):
            story.append(Paragraph(f"• {clean_text(line[2:])}", styles['BulletItem']))
        elif line.startswith('  - ') or line.startswith('  * '):
            story.append(Paragraph(f"  ◦ {clean_text(line[4:])}", styles['BulletItem']))
        
        # Numbered items
        elif re.match(r'^\d+\.', line):
            story.append(Paragraph(clean_text(line), styles['BulletItem']))
        
        # Decision highlight
        elif '**APPROVED**' in line:
            story.append(Spacer(1, 10))
            story.append(Paragraph(
                '<b><font color="#22543d">DECISION: APPROVED</font></b>',
                styles['SectionHeader']
            ))
        elif '**DENIED**' in line:
            story.append(Spacer(1, 10))
            story.append(Paragraph(
                '<b><font color="#c53030">DECISION: DENIED</font></b>',
                styles['SectionHeader']
            ))
        elif '**NEEDS_REVIEW**' in line or '**NEEDS REVIEW**' in line:
            story.append(Spacer(1, 10))
            story.append(Paragraph(
                '<b><font color="#c05621">DECISION: NEEDS REVIEW</font></b>',
                styles['SectionHeader']
            ))
        
        # Regular text
        else:
            story.append(Paragraph(clean_text(line), styles['BodyText']))
    
    # Footer
    story.append(Spacer(1, 30))
    story.append(Paragraph(
        "This report was generated by the Streamline Refi Agent. "
        "All decisions require human review and approval.",
        ParagraphStyle(
            name='Footer',
            parent=styles['Normal'],
            fontSize=8,
            textColor=colors.gray,
            alignment=TA_CENTER
        )
    ))
    
    # Build PDF
    doc.build(story)
    
    buffer.seek(0)
    return buffer.getvalue()


def clean_text(text: str) -> str:
    """Clean markdown formatting for PDF."""
    # Remove markdown bold/italic
    text = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', text)
    text = re.sub(r'\*(.+?)\*', r'<i>\1</i>', text)
    # Remove backticks
    text = text.replace('`', '')
    # Handle special chars
    text = text.replace('&', '&amp;')
    text = text.replace('<b>', '<<<B>>>').replace('</b>', '<<<EB>>>')
    text = text.replace('<i>', '<<<I>>>').replace('</i>', '<<<EI>>>')
    text = text.replace('<', '&lt;').replace('>', '&gt;')
    text = text.replace('<<<B>>>', '<b>').replace('<<<EB>>>', '</b>')
    text = text.replace('<<<I>>>', '<i>').replace('<<<EI>>>', '</i>')
    return text
