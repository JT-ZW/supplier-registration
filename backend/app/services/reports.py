"""
Report generation service for PDF and Excel exports.
"""

from datetime import datetime, date
from typing import List, Dict, Any, Optional
from io import BytesIO
import os
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter, A4, landscape
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak, Image
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from openpyxl import Workbook
from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
from openpyxl.utils import get_column_letter
from openpyxl.drawing.image import Image as ExcelImage

from ..db.supabase import db
from ..models import BusinessCategory, SupplierStatus
from ..core.timezone import get_cat_now, format_cat_datetime
from ..core.timezone import get_cat_now, format_cat_datetime


class ReportService:
    """Service for generating supplier reports in various formats."""
    
    def __init__(self):
        self.company_name = "Rainbow Tourism Group"
        self.report_title = "Supplier Report"
    
    async def get_filtered_suppliers(
        self,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        status: Optional[List[SupplierStatus]] = None,
        category: Optional[List[BusinessCategory]] = None,
        location: Optional[str] = None,
        min_years: Optional[int] = None,
        max_years: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """
        Get filtered list of suppliers based on criteria.
        """
        # Get all suppliers directly from table
        result = db.client.table("suppliers").select("*").execute()
        suppliers = result.data if result.data else []
        
        # Apply filters
        filtered = []
        for supplier in suppliers:
            # Date filter (created_at or submitted_at)
            if start_date or end_date:
                supplier_date_str = supplier.get("submitted_at") or supplier.get("created_at")
                if supplier_date_str:
                    try:
                        supplier_date = datetime.fromisoformat(supplier_date_str.replace('Z', '+00:00')).date()
                        if start_date and supplier_date < start_date:
                            continue
                        if end_date and supplier_date > end_date:
                            continue
                    except:
                        pass
            
            # Status filter
            if status and supplier.get("status"):
                if supplier["status"] not in [s.value for s in status]:
                    continue
            
            # Category filter
            if category and supplier.get("business_category"):
                if supplier["business_category"] not in [c.value for c in category]:
                    continue
            
            # Location filter (check both city and country)
            if location:
                location_lower = location.lower()
                city = (supplier.get("city") or "").lower()
                country = (supplier.get("country") or "").lower()
                if location_lower not in city and location_lower not in country:
                    continue
            
            # Years in business filter
            years = supplier.get("years_in_business")
            if years is not None:
                if min_years is not None and years < min_years:
                    continue
                if max_years is not None and years > max_years:
                    continue
            
            filtered.append(supplier)
        
        return filtered
    
    async def generate_pdf_report(
        self,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        status: Optional[List[SupplierStatus]] = None,
        category: Optional[List[BusinessCategory]] = None,
        location: Optional[str] = None,
        min_years: Optional[int] = None,
        max_years: Optional[int] = None,
    ) -> BytesIO:
        """
        Generate a PDF report of suppliers.
        """
        # Get filtered data
        suppliers = await self.get_filtered_suppliers(
            start_date, end_date, status, category, location, min_years, max_years
        )
        
        # Create PDF buffer
        buffer = BytesIO()
        
        # Create document with landscape orientation for better table fit
        doc = SimpleDocTemplate(
            buffer,
            pagesize=landscape(A4),
            rightMargin=30,
            leftMargin=30,
            topMargin=30,
            bottomMargin=30,
        )
        
        # Container for PDF elements
        elements = []
        styles = getSampleStyleSheet()
        
        # Custom styles with RTG branding
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=24,
            textColor=colors.HexColor('#0066cc'),  # RTG Blue
            spaceAfter=30,
            alignment=TA_CENTER,
            fontName='Helvetica-Bold',
        )
        
        heading_style = ParagraphStyle(
            'CustomHeading',
            parent=styles['Heading2'],
            fontSize=14,
            textColor=colors.HexColor('#004c99'),  # RTG Dark Blue
            spaceAfter=12,
            fontName='Helvetica-Bold',
        )
        
        normal_style = ParagraphStyle(
            'CustomNormal',
            parent=styles['Normal'],
            fontSize=10,
            textColor=colors.HexColor('#4b5563'),
        )
        
        # Add title
        logo_path = os.path.join(os.path.dirname(__file__), '..', 'core', 'rtg-logo.png')
        if os.path.exists(logo_path):
            logo = Image(logo_path, width=2*inch, height=0.6*inch, kind='proportional')
            elements.append(logo)
            elements.append(Spacer(1, 0.2 * inch))
        
        elements.append(Paragraph(f"{self.company_name}", title_style))
        elements.append(Paragraph("Supplier Details Report", heading_style))
        elements.append(Spacer(1, 0.2 * inch))
        
        # Add report metadata
        report_info = [
            f"<b>Generated:</b> {get_cat_now().strftime('%B %d, %Y at %I:%M %p CAT')}",
            f"<b>Total Suppliers:</b> {len(suppliers)}",
        ]
        
        if start_date:
            report_info.append(f"<b>From:</b> {start_date.strftime('%B %d, %Y')}")
        if end_date:
            report_info.append(f"<b>To:</b> {end_date.strftime('%B %d, %Y')}")
        if status:
            report_info.append(f"<b>Status Filter:</b> {', '.join([s.value for s in status])}")
        if category:
            report_info.append(f"<b>Category Filter:</b> {', '.join([c.value.replace('_', ' ').title() for c in category])}")
        if location:
            report_info.append(f"<b>Location Filter:</b> {location}")
        
        for info in report_info:
            elements.append(Paragraph(info, normal_style))
        
        elements.append(Spacer(1, 0.3 * inch))
        
        # Create table data
        table_data = [
            ['Company Name', 'Category', 'Location', 'Contact', 'Email', 'Status', 'Years in Business', 'Registered']
        ]
        
        for supplier in suppliers:
            row = [
                supplier.get('company_name', 'N/A')[:30],
                (supplier.get('business_category') or 'N/A').replace('_', ' ').title()[:20],
                f"{supplier.get('city', 'N/A')}, {supplier.get('country', 'N/A')}"[:25],
                supplier.get('contact_person_name', 'N/A')[:20],
                supplier.get('email', 'N/A')[:30],
                (supplier.get('status') or 'N/A').upper()[:15],
                str(supplier.get('years_in_business', 'N/A')),
                format_cat_datetime(supplier.get('created_at'), '%Y-%m-%d') if supplier.get('created_at') else 'N/A',
            ]
            table_data.append(row)
        
        # Create table
        table = Table(table_data, repeatRows=1)
        
        # Style the table with RTG branding
        table.setStyle(TableStyle([
            # Header row - RTG Blue
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#0066cc')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 9),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('TOPPADDING', (0, 0), (-1, 0), 12),
            
            # Data rows
            ('BACKGROUND', (0, 1), (-1, -1), colors.white),
            ('TEXTCOLOR', (0, 1), (-1, -1), colors.HexColor('#1f2937')),
            ('ALIGN', (0, 1), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 1), (-1, -1), 8),
            ('TOPPADDING', (0, 1), (-1, -1), 6),
            ('BOTTOMPADDING', (0, 1), (-1, -1), 6),
            
            # Grid
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#d1d5db')),
            
            # Alternating row colors
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f0f7ff')]),
        ]))
        
        elements.append(table)
        
        # Add summary statistics on new page if there's data
        if suppliers:
            elements.append(PageBreak())
            elements.append(Paragraph("Report Summary", heading_style))
            elements.append(Spacer(1, 0.2 * inch))
            
            # Calculate statistics
            status_counts = {}
            category_counts = {}
            
            for supplier in suppliers:
                status = supplier.get('status', 'Unknown')
                category = supplier.get('business_category', 'Unknown')
                
                status_counts[status] = status_counts.get(status, 0) + 1
                category_counts[category] = category_counts.get(category, 0) + 1
            
            # Status distribution table
            elements.append(Paragraph("Status Distribution", normal_style))
            elements.append(Spacer(1, 0.1 * inch))
            
            status_table_data = [['Status', 'Count', 'Percentage']]
            for status, count in sorted(status_counts.items()):
                percentage = (count / len(suppliers)) * 100
                status_table_data.append([
                    status.upper(),
                    str(count),
                    f"{percentage:.1f}%"
                ])
            
            status_table = Table(status_table_data, colWidths=[3*inch, 1.5*inch, 1.5*inch])
            status_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#3b82f6')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 10),
                ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
                ('FONTSIZE', (0, 1), (-1, -1), 9),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#eff6ff')]),
            ]))
            elements.append(status_table)
            
            elements.append(Spacer(1, 0.3 * inch))
            
            # Category distribution table
            elements.append(Paragraph("Category Distribution", normal_style))
            elements.append(Spacer(1, 0.1 * inch))
            
            category_table_data = [['Business Category', 'Count', 'Percentage']]
            for cat, count in sorted(category_counts.items(), key=lambda x: x[1], reverse=True):
                percentage = (count / len(suppliers)) * 100
                category_table_data.append([
                    cat.replace('_', ' ').title(),
                    str(count),
                    f"{percentage:.1f}%"
                ])
            
            category_table = Table(category_table_data, colWidths=[3*inch, 1.5*inch, 1.5*inch])
            category_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#3b82f6')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 10),
                ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
                ('FONTSIZE', (0, 1), (-1, -1), 9),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#eff6ff')]),
            ]))
            elements.append(category_table)
        
        # Build PDF
        doc.build(elements)
        buffer.seek(0)
        return buffer
    
    async def generate_excel_report(
        self,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        status: Optional[List[SupplierStatus]] = None,
        category: Optional[List[BusinessCategory]] = None,
        location: Optional[str] = None,
        min_years: Optional[int] = None,
        max_years: Optional[int] = None,
    ) -> BytesIO:
        """
        Generate an Excel report of suppliers with multiple sheets.
        """
        # Get filtered data
        suppliers = await self.get_filtered_suppliers(
            start_date, end_date, status, category, location, min_years, max_years
        )
        
        # Create workbook
        wb = Workbook()
        
        # Remove default sheet
        if 'Sheet' in wb.sheetnames:
            del wb['Sheet']
        
        # ===== Sheet 1: Supplier Details =====
        ws_details = wb.create_sheet("Supplier Details")
        
        # Header styling
        header_fill = PatternFill(start_color="2563EB", end_color="2563EB", fill_type="solid")
        header_font = Font(bold=True, color="FFFFFF", size=11)
        header_alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        
        border = Border(
            left=Side(style='thin', color='D1D5DB'),
            right=Side(style='thin', color='D1D5DB'),
            top=Side(style='thin', color='D1D5DB'),
            bottom=Side(style='thin', color='D1D5DB')
        )
        
        # Define headers
        headers = [
            'Company Name', 'Business Category', 'Registration Number', 'Tax ID',
            'Years in Business', 'Website', 'Contact Person', 'Title',
            'Email', 'Phone', 'Street Address', 'City', 'State/Province',
            'Postal Code', 'Country', 'Status', 'Created Date', 'Submitted Date', 'Updated Date'
        ]
        
        # Write headers
        for col_num, header in enumerate(headers, 1):
            cell = ws_details.cell(row=1, column=col_num, value=header)
            cell.fill = header_fill
            cell.font = header_font
            cell.alignment = header_alignment
            cell.border = border
        
        # Write data
        for row_num, supplier in enumerate(suppliers, 2):
            data = [
                supplier.get('company_name', ''),
                (supplier.get('business_category') or '').replace('_', ' ').title(),
                supplier.get('registration_number', ''),
                supplier.get('tax_id', ''),
                supplier.get('years_in_business', ''),
                supplier.get('website', ''),
                supplier.get('contact_person_name', ''),
                supplier.get('contact_person_title', ''),
                supplier.get('email', ''),
                supplier.get('phone', ''),
                supplier.get('street_address', ''),
                supplier.get('city', ''),
                supplier.get('state_province', ''),
                supplier.get('postal_code', ''),
                supplier.get('country', ''),
                (supplier.get('status') or '').upper(),
                self._format_date(supplier.get('created_at')),
                self._format_date(supplier.get('submitted_at')),
                self._format_date(supplier.get('updated_at')),
            ]
            
            for col_num, value in enumerate(data, 1):
                cell = ws_details.cell(row=row_num, column=col_num, value=value)
                cell.border = border
                cell.alignment = Alignment(vertical="center", wrap_text=True)
                
                # Alternate row coloring
                if row_num % 2 == 0:
                    cell.fill = PatternFill(start_color="F9FAFB", end_color="F9FAFB", fill_type="solid")
        
        # Auto-adjust column widths
        for col_num, header in enumerate(headers, 1):
            column_letter = get_column_letter(col_num)
            max_length = len(header)
            for row in ws_details.iter_rows(min_col=col_num, max_col=col_num, min_row=2):
                for cell in row:
                    if cell.value:
                        max_length = max(max_length, len(str(cell.value)))
            adjusted_width = min(max_length + 2, 50)
            ws_details.column_dimensions[column_letter].width = adjusted_width
        
        # ===== Sheet 2: Summary Statistics =====
        ws_summary = wb.create_sheet("Summary")
        
        # Title
        ws_summary.cell(row=1, column=1, value="Report Summary").font = Font(bold=True, size=16)
        ws_summary.cell(row=2, column=1, value=f"Generated: {get_cat_now().strftime('%B %d, %Y at %I:%M %p CAT')}")
        ws_summary.cell(row=3, column=1, value=f"Total Suppliers: {len(suppliers)}")
        
        row_offset = 5
        
        # Filters applied
        if any([start_date, end_date, status, category, location]):
            ws_summary.cell(row=row_offset, column=1, value="Filters Applied:").font = Font(bold=True)
            row_offset += 1
            if start_date:
                ws_summary.cell(row=row_offset, column=1, value=f"From: {start_date.strftime('%B %d, %Y')}")
                row_offset += 1
            if end_date:
                ws_summary.cell(row=row_offset, column=1, value=f"To: {end_date.strftime('%B %d, %Y')}")
                row_offset += 1
            if status:
                ws_summary.cell(row=row_offset, column=1, value=f"Status: {', '.join([s.value for s in status])}")
                row_offset += 1
            if category:
                ws_summary.cell(row=row_offset, column=1, value=f"Category: {', '.join([c.value for c in category])}")
                row_offset += 1
            if location:
                ws_summary.cell(row=row_offset, column=1, value=f"Location: {location}")
                row_offset += 1
            row_offset += 1
        
        # Status distribution
        ws_summary.cell(row=row_offset, column=1, value="Status Distribution").font = Font(bold=True, size=12)
        row_offset += 1
        
        status_counts = {}
        for supplier in suppliers:
            status_val = supplier.get('status', 'Unknown')
            status_counts[status_val] = status_counts.get(status_val, 0) + 1
        
        # Status headers
        for col, header in enumerate(['Status', 'Count', 'Percentage'], 1):
            cell = ws_summary.cell(row=row_offset, column=col, value=header)
            cell.fill = header_fill
            cell.font = header_font
            cell.border = border
        row_offset += 1
        
        for status_val, count in sorted(status_counts.items()):
            percentage = (count / len(suppliers)) * 100 if suppliers else 0
            ws_summary.cell(row=row_offset, column=1, value=status_val.upper()).border = border
            ws_summary.cell(row=row_offset, column=2, value=count).border = border
            ws_summary.cell(row=row_offset, column=3, value=f"{percentage:.1f}%").border = border
            row_offset += 1
        
        row_offset += 2
        
        # Category distribution
        ws_summary.cell(row=row_offset, column=1, value="Category Distribution").font = Font(bold=True, size=12)
        row_offset += 1
        
        category_counts = {}
        for supplier in suppliers:
            cat = supplier.get('category', 'Unknown')
            category_counts[cat] = category_counts.get(cat, 0) + 1
        
        # Category headers
        for col, header in enumerate(['Business Category', 'Count', 'Percentage'], 1):
            cell = ws_summary.cell(row=row_offset, column=col, value=header)
            cell.fill = header_fill
            cell.font = header_font
            cell.border = border
        row_offset += 1
        
        for cat, count in sorted(category_counts.items(), key=lambda x: x[1], reverse=True):
            percentage = (count / len(suppliers)) * 100 if suppliers else 0
            ws_summary.cell(row=row_offset, column=1, value=cat.replace('_', ' ').title()).border = border
            ws_summary.cell(row=row_offset, column=2, value=count).border = border
            ws_summary.cell(row=row_offset, column=3, value=f"{percentage:.1f}%").border = border
            row_offset += 1
        
        # Adjust column widths for summary
        for col in range(1, 4):
            ws_summary.column_dimensions[get_column_letter(col)].width = 25
        
        # Save to buffer
        buffer = BytesIO()
        wb.save(buffer)
        buffer.seek(0)
        return buffer
    
    def _format_date(self, date_str: Optional[str]) -> str:
        """Format ISO date string to readable format."""
        if not date_str:
            return ''
        try:
            return format_cat_datetime(date_str, '%Y-%m-%d %H:%M')
        except:
            return date_str


# Global instance
report_service = ReportService()
