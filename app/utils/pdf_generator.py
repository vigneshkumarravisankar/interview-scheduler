"""
PDF generator for offer letters and other documents
"""
import os
import tempfile
from datetime import datetime
from typing import Dict, Any, Optional

try:
    # Use reportlab for PDF generation
    from reportlab.lib.pagesizes import letter
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image
    from reportlab.lib.units import inch
    REPORTLAB_AVAILABLE = True
except ImportError:
    print("ReportLab not installed. PDF generation will not be available.")
    REPORTLAB_AVAILABLE = False


def generate_offer_letter_pdf(
    candidate_name: str,
    job_title: str, 
    compensation: str,
    company_name: str = "Your Company",
    logo_path: Optional[str] = None,
    hr_name: str = "HR Representative"
) -> Optional[str]:
    """
    Generate a PDF offer letter
    
    Args:
        candidate_name: Name of the candidate
        job_title: Job title
        compensation: Compensation details
        company_name: Name of the company
        logo_path: Path to company logo image file (optional)
    
    Returns:
        Path to the generated PDF file, or None if generation failed
    """
    if not REPORTLAB_AVAILABLE:
        print("Cannot generate PDF: ReportLab not installed")
        return None
    
    try:
        # Create a temporary file for the PDF
        temp_file = tempfile.NamedTemporaryFile(suffix='.pdf', delete=False)
        pdf_path = temp_file.name
        temp_file.close()  # Close so we can write to it
        
        # Create the document
        doc = SimpleDocTemplate(
            pdf_path,
            pagesize=letter,
            rightMargin=72,
            leftMargin=72,
            topMargin=72,
            bottomMargin=72
        )
        
        # Styles
        styles = getSampleStyleSheet()
        
        # Custom styles
        styles.add(ParagraphStyle(
            name='CompanyName',
            parent=styles['Heading1'],
            fontSize=18,
            textColor=colors.navy,
            spaceAfter=12
        ))
        
        styles.add(ParagraphStyle(
            name='Heading2Bold',
            parent=styles['Heading2'],
            fontSize=14,
            textColor=colors.navy,
            spaceAfter=8
        ))
        
        styles.add(ParagraphStyle(
            name='Normal_Right',
            parent=styles['Normal'],
            alignment=2  # Right alignment
        ))
        
        # Build content
        content = []
        
        # Company logo if available
        if logo_path and os.path.exists(logo_path):
            img = Image(logo_path, width=2*inch, height=1*inch)
            content.append(img)
            content.append(Spacer(1, 0.25*inch))
        
        # Letterhead
        content.append(Paragraph(company_name, styles['CompanyName']))
        content.append(Spacer(1, 0.1*inch))
        
        # Date
        date_text = datetime.now().strftime("%B %d, %Y")
        content.append(Paragraph(date_text, styles['Normal']))
        content.append(Spacer(1, 0.3*inch))
        
        # Recipient
        content.append(Paragraph(f"Dear {candidate_name},", styles['Normal']))
        content.append(Spacer(1, 0.2*inch))
        
        # Offer introduction
        content.append(Paragraph(
            f"We are pleased to offer you the position of <b>{job_title}</b> at {company_name}. "
            f"After careful consideration of your qualifications and experience, we believe you "
            f"would be a valuable addition to our team.", 
            styles['Normal']
        ))
        content.append(Spacer(1, 0.2*inch))
        
        # Offer details
        content.append(Paragraph("Offer Details", styles['Heading2Bold']))
        content.append(Spacer(1, 0.1*inch))
        
        # Create a table for offer details
        data = [
            ["Position:", job_title],
            ["Compensation:", compensation],
            ["Start Date:", "To be determined upon acceptance"]
        ]
        
        table = Table(data, colWidths=[1.5*inch, 4*inch])
        table.setStyle(TableStyle([
            ('GRID', (0, 0), (-1, -1), 1, colors.white),
            ('BACKGROUND', (0, 0), (0, -1), colors.lightgrey),
            ('ALIGNMENT', (0, 0), (0, -1), 'RIGHT'),
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
        ]))
        
        content.append(table)
        content.append(Spacer(1, 0.2*inch))
        
        # Additional details
        content.append(Paragraph(
            "This offer includes our standard benefits package, including health insurance, retirement benefits, "
            "and paid time off. Details of these benefits will be provided separately.", 
            styles['Normal']
        ))
        content.append(Spacer(1, 0.2*inch))
        
        # Acceptance terms
        content.append(Paragraph(
            "To accept this offer, please sign below and return this letter within 7 days. "
            "If you have any questions or concerns, please don't hesitate to contact us.", 
            styles['Normal']
        ))
        content.append(Spacer(1, 0.2*inch))
        
        # Closing
        content.append(Paragraph(
            f"We are excited about the possibility of you joining the {company_name} team and "
            f"look forward to working with you.", 
            styles['Normal']
        ))
        content.append(Spacer(1, 0.3*inch))
        
        # Signature lines
        content.append(Paragraph("Sincerely,", styles['Normal']))
        content.append(Spacer(1, 0.4*inch))
        content.append(Paragraph("_______________________________", styles['Normal']))
        content.append(Paragraph(hr_name, styles['Normal']))
        content.append(Paragraph("Human Resources Department", styles['Normal']))
        content.append(Paragraph(company_name, styles['Normal']))
        content.append(Spacer(1, 0.5*inch))
        
        # Acceptance signature
        content.append(Paragraph("ACCEPTANCE OF OFFER:", styles['Heading2Bold']))
        content.append(Spacer(1, 0.2*inch))
        content.append(Paragraph("I accept the terms of employment described in this letter.", styles['Normal']))
        content.append(Spacer(1, 0.3*inch))
        content.append(Paragraph("_______________________________", styles['Normal']))
        content.append(Paragraph(candidate_name, styles['Normal']))
        content.append(Spacer(1, 0.2*inch))
        content.append(Paragraph("Date: _______________________", styles['Normal']))
        
        # Build the PDF
        doc.build(content)
        
        print(f"PDF offer letter generated at {pdf_path}")
        return pdf_path
        
    except Exception as e:
        print(f"Error generating PDF: {e}")
        return None
