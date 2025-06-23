"""
Offer Letter Generator - PDF generation utility
"""
import os
import tempfile
import datetime
from typing import Optional
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import Paragraph
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY

def create_offer_letter_pdf(name: str, job_title: str, joining_date: str = None, compensation: str = None) -> str:
    """
    Creates a modern, professional offer letter PDF with clean blue and white design.

    Args:
        name (str): The candidate's full name
        job_title (str): The offered position/title
        joining_date (str): Joining date (optional)
        compensation (str): Compensation details (optional)

    Returns:
        str: Path to the generated PDF file
    """
    try:
        # Create a file in the temp directory to avoid cluttering the workspace
        temp_dir = tempfile.gettempdir()
        pdf_path = os.path.join(temp_dir, f"offer_letter_{name.replace(' ', '_')}.pdf")

        # Set up the document
        c = canvas.Canvas(pdf_path, pagesize=letter)
        width, height = letter
       
        # Define modern color palette
        primary_blue = colors.HexColor('#004080')      # Darker primary blue
        secondary_blue = colors.HexColor('#005cb8')    # Darker secondary blue
        text_color = colors.HexColor('#333333')        # Dark gray for text
        light_blue_bg = colors.HexColor('#d0e4ff')     # Background blue
        border_color = colors.HexColor('#e6e6e6')      # Light gray for borders

        # Fill the entire page with white background
        c.setFillColor(colors.white)
        c.rect(0, 0, width, height, fill=1)

        # Document margins
        margin_left = 72
        margin_right = width - 72
        usable_width = margin_right - margin_left

        # Header with subtle gradient effect
        c.setFillColor(primary_blue)
        c.rect(0, height-90, width, 90, fill=1, stroke=0)
       
        # Company name in header
        c.setFillColor(colors.white)
        c.setFont("Helvetica-Bold", 24)
        c.drawString(margin_left, height-40, "COMPANY NAME")

        # Company tagline
        c.setFont("Helvetica", 12)
        c.drawString(margin_left, height-60, "Transforming Ideas into Reality")

        # Contact information on right side of header
        c.setFont("Helvetica", 10)
        c.drawRightString(margin_right, height-40, "123 Business Avenue, City, State 12345")
        c.drawRightString(margin_right, height-55, "Tel: (555) 123-4567 • www.company.com")

        # Document reference number
        ref_num = f"REF: HR-{datetime.datetime.now().strftime('%y%m%d')}"
        c.setFillColor(text_color)
        c.setFont("Helvetica", 9)
        c.drawString(margin_left, height-120, ref_num)

        # Current date - right aligned
        current_date = datetime.datetime.now().strftime("%B %d, %Y")
        c.setFont("Helvetica", 10)
        c.drawRightString(margin_right, height-120, current_date)

        # Offer title with proper spacing
        c.setFillColor(primary_blue)
        c.setFont("Helvetica-Bold", 18)
        c.drawCentredString(width/2, height-160, "OFFER OF EMPLOYMENT")

        # Subtle divider
        c.setStrokeColor(secondary_blue)
        c.setLineWidth(1)
        c.line(margin_left + 100, height-175, margin_right - 100, height-175)

        # Recipient information block
        c.setFillColor(text_color)
        c.setFont("Helvetica-Bold", 11)
        c.drawString(margin_left, height-200, name)
        c.setFont("Helvetica", 10)
        c.drawString(margin_left, height-215, "123 Recipient Street")
        c.drawString(margin_left, height-230, "City, State 12345")

        # Formal greeting with proper spacing
        c.setFont("Helvetica-Bold", 11)
        c.drawString(margin_left, height-265, f"Dear {name},")

        # Main content
        c.setFillColor(text_color)
        c.setFont("Helvetica", 11)

        # First paragraph with proper line spacing
        offer_y = height-295
        intro_text = "We are pleased to offer you the position of "
        c.drawString(margin_left, offer_y, intro_text)

        # Job title in bold blue for emphasis
        c.setFont("Helvetica-Bold", 11)
        c.setFillColor(primary_blue)
        job_title_position = margin_left + c.stringWidth(intro_text, "Helvetica", 11)
        c.drawString(job_title_position, offer_y, job_title)
       
        # Continue with regular text
        c.setFont("Helvetica", 11)
        c.setFillColor(text_color)
        next_position = job_title_position + c.stringWidth(job_title, "Helvetica-Bold", 11)
        c.drawString(next_position, offer_y, " with Company Name.")

        # Second paragraph
        c.drawString(margin_left, offer_y-25, "This offer is contingent upon the successful completion of background checks and is")
        c.drawString(margin_left, offer_y-40, "subject to the terms and conditions outlined below.")

        # Employment Details section
        c.setFillColor(primary_blue)
        c.setFont("Helvetica-Bold", 14)
        c.drawString(margin_left, offer_y-75, "EMPLOYMENT DETAILS")
       
        # Employment details with compact spacing - FIXED SPACING
        details_y = offer_y-105
        row_gap = 35
        label_width = 115  # Width for the labels
        col2_start = margin_left + usable_width/2  # Start of second column
       
        # FIXED: Reduced spacing between label and value
        # First row - Start Date and Employment Type
        c.setFillColor(primary_blue)
        c.setFont("Helvetica-Bold", 11)
        c.drawString(margin_left, details_y, "Start Date:")
        c.drawString(col2_start, details_y, "Employment Type:")
       
        c.setFillColor(text_color)
        c.setFont("Helvetica", 11)
        # Use provided joining date or default
        start_date_text = joining_date if joining_date else "Upon agreement"
        c.drawString(margin_left + 85, details_y, start_date_text)
        c.drawString(col2_start + 130, details_y, "Full-time, Exempt")
       
        # Second row - Position and Working Hours
        c.setFillColor(primary_blue)
        c.setFont("Helvetica-Bold", 11)
        c.drawString(margin_left, details_y - row_gap, "Position:")
        c.drawString(col2_start, details_y - row_gap, "Working Hours:")
       
        c.setFillColor(text_color)
        c.setFont("Helvetica", 11)
        # Reduced gap between label and value
        c.drawString(margin_left + 85, details_y - row_gap, job_title)
        c.drawString(col2_start + 130, details_y - row_gap, "9:00 AM - 5:00 PM")

        # Compensation section - adjusted position for better spacing
        comp_y = details_y - (2 * row_gap) - 20
        c.setFillColor(primary_blue)
        c.setFont("Helvetica-Bold", 14)
        c.drawString(margin_left, comp_y, "COMPENSATION & BENEFITS")

        # Benefits with modern bullet points
        c.setFillColor(text_color)
        c.setFont("Helvetica", 11)

        benefits = [
            f"Competitive salary package{f': {compensation}' if compensation else ''}",
            "Paid time off and holidays",
            "Professional development opportunities"
        ]

        benefits_y = comp_y - 30
        for benefit in benefits:
            # Modern bullet point
            c.setFillColor(secondary_blue)
            c.circle(margin_left + 5, benefits_y + 3, 3, fill=1, stroke=0)

            # Benefit text
            c.setFillColor(text_color)
            c.drawString(margin_left + 15, benefits_y, benefit)
            benefits_y -= 20

        # Closing paragraph
        closing_y = benefits_y - 20
        c.setFillColor(text_color)
        c.setFont("Helvetica", 11)
        c.drawString(margin_left, closing_y, "We are excited about the possibility of you joining our team. To indicate your acceptance")
        c.drawString(margin_left, closing_y-20, "of this offer, please sign below and return this letter by")

        # Calculate due date (7 days from now)
        due_date = (datetime.datetime.now() + datetime.timedelta(days=7)).strftime("%B %d, %Y")
        c.setFillColor(primary_blue)
        c.setFont("Helvetica-Bold", 11)
        c.drawString(margin_left + c.stringWidth("of this offer, please sign below and return this letter by ", "Helvetica", 11),
                    closing_y-20,
                    f"{due_date}.")

        # Signature section
        c.setFillColor(text_color)
        c.setFont("Helvetica", 11)
        sig_y = closing_y - 60
        c.drawString(margin_left, sig_y, "Sincerely,")

        # HR signature line
        c.setStrokeColor(primary_blue)
        c.line(margin_left, sig_y-30, margin_left + 180, sig_y-30)
        c.setFillColor(text_color)
        c.setFont("Helvetica", 10)
        c.drawString(margin_left, sig_y-45, "Sarah Johnson, HR Director")
       
        # Candidate acceptance section
        accept_y = sig_y - 75
        c.setFillColor(primary_blue)
        c.setFont("Helvetica-Bold", 11)
        c.drawString(margin_left, accept_y, "ACCEPTANCE")

        c.setFillColor(text_color)
        c.setFont("Helvetica", 9)
        c.drawString(margin_left, accept_y-18, "I accept the offer of employment as described in this letter.")

        # Signature lines
        c.setStrokeColor(border_color)
        c.line(margin_left, accept_y-50, margin_left + 180, accept_y-50)
        c.line(margin_right - 180, accept_y-50, margin_right, accept_y-50)

        c.setFillColor(text_color)
        c.setFont("Helvetica", 9)
        c.drawString(margin_left, accept_y-65, "Signature")
        c.drawString(margin_right - 180, accept_y-65, "Date")

        # Footer with subtle gradient
        c.setFillColor(primary_blue)
        c.rect(0, 0, width, 25, fill=1, stroke=0)

        # Footer text in white
        c.setFillColor(colors.white)
        c.setFont("Helvetica", 9)
        c.drawCentredString(width/2, 10, "This offer letter is valid for 7 days from the date listed above.")

        # Save the PDF
        c.save()
        print(f"Professional PDF created at {pdf_path}")
        return pdf_path

    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        print(f"Error in PDF creation: {str(e)}")
        print(f"Error details: {error_details}")
        raise
