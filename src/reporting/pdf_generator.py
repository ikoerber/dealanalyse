"""
PDF Generator for HubSpot Deal Analysis Reports

Generates professional PDF reports with:
- Pipeline metrics comparison
- Closed deals summary
- Detailed deal comparison table with color-coding
- German number formatting
"""

from datetime import datetime
from typing import Dict, List, Tuple, Optional
import logging
from pathlib import Path
import math

import pandas as pd
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT
from reportlab.platypus import (
    SimpleDocTemplate, Table, TableStyle, Paragraph,
    Spacer, PageBreak
)
from reportlab.pdfgen import canvas

from src.utils.formatting import format_euro, format_percentage, format_number_compact

logger = logging.getLogger(__name__)


# Color mapping (matching dashboard colors)
COLORS = {
    'gewonnen': colors.Color(0.831, 0.929, 0.855),   # #d4edda (Green)
    'verloren': colors.Color(0.973, 0.843, 0.855),   # #f8d7da (Red)
    'changed': colors.Color(0.820, 0.925, 0.945),    # #d1ecf1 (Blue)
    'neu': colors.Color(1.0, 0.953, 0.804),          # #fff3cd (Yellow)
    'closed': colors.Color(0.914, 0.925, 0.937),     # #e9ecef (Gray)
    'white': colors.white,
    'header': colors.Color(0.4, 0.4, 0.4),           # Dark gray for headers
}

# Pagination constants
DEALS_PER_PAGE_COMPARISON = 20  # Rows per page in deal comparison table
DEALS_PER_PAGE_2025_OVERVIEW = 25  # Rows per page in 2025 deals overview


class PDFGenerator:
    """
    PDF Generator for HubSpot Deal Comparison Reports

    Creates professional PDF reports with metrics, summaries, and detailed
    deal comparison tables with German formatting.
    """

    def __init__(self, company_name: str = "Smart Commerce SE"):
        """
        Initialize PDF Generator.

        Args:
            company_name: Company name to display in header
        """
        self.company_name = company_name
        self.styles = getSampleStyleSheet()
        self._setup_custom_styles()

    def _setup_custom_styles(self):
        """Set up custom paragraph styles for the PDF."""
        # Title style
        self.styles.add(ParagraphStyle(
            name='CustomTitle',
            parent=self.styles['Heading1'],
            fontSize=16,
            textColor=COLORS['header'],
            alignment=TA_CENTER,
            spaceAfter=12
        ))

        # Subtitle style
        self.styles.add(ParagraphStyle(
            name='CustomSubtitle',
            parent=self.styles['Normal'],
            fontSize=12,
            textColor=COLORS['header'],
            alignment=TA_CENTER,
            spaceAfter=6
        ))

        # Section heading
        self.styles.add(ParagraphStyle(
            name='SectionHeading',
            parent=self.styles['Heading2'],
            fontSize=14,
            textColor=COLORS['header'],
            spaceBefore=12,
            spaceAfter=8
        ))

        # Table cell style (for wrapping text like Deal Name)
        self.styles.add(ParagraphStyle(
            name='TableCell',
            parent=self.styles['Normal'],
            fontSize=7,
            leading=9,  # Line height
            alignment=TA_LEFT,
            wordWrap='CJK'  # Enable aggressive word wrapping
        ))

        # Right-aligned table cell style (for amounts/numbers)
        self.styles.add(ParagraphStyle(
            name='TableCellRight',
            parent=self.styles['Normal'],
            fontSize=7,
            leading=9,
            alignment=TA_RIGHT
        ))

        # Header cell style (centered with word wrap)
        self.styles.add(ParagraphStyle(
            name='TableHeader',
            parent=self.styles['Normal'],
            fontSize=7,
            leading=9,
            alignment=TA_CENTER,
            textColor=colors.white,
            fontName='Helvetica-Bold',
            wordWrap='CJK'
        ))

    def generate_comparison_pdf(
        self,
        comparison_df: pd.DataFrame,
        month_a: str,
        month_b: str,
        metrics: dict,
        output_path: str,
        contact_data: Optional[dict] = None,
        deals_2025_df: Optional[pd.DataFrame] = None
    ) -> str:
        """
        Generate complete PDF report with metrics and comparison table.

        Args:
            comparison_df: DataFrame with deal comparison data
            month_a: First month name (e.g., "Januar 2026")
            month_b: Second month name (e.g., "Februar 2026")
            metrics: Dictionary with calculated metrics
            output_path: Path where PDF should be saved
            contact_data: Optional dictionary with contact analysis data
                         {'kpis': DataFrame, 'sql_details': DataFrame, 'source_breakdown': DataFrame}
            deals_2025_df: Optional DataFrame with all 2025 deals
                          (columns: deal_name, amount, status, contact_source, rejection_reason)

        Returns:
            Path to the generated PDF file
        """
        logger.info(f"Generating PDF report for {month_a} vs {month_b}")

        # Ensure output directory exists
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)

        # Create PDF document
        doc = SimpleDocTemplate(
            output_path,
            pagesize=landscape(A4),
            rightMargin=20*mm,
            leftMargin=20*mm,
            topMargin=20*mm,
            bottomMargin=15*mm
        )

        # Build document content
        story = []

        # Page 1: Metrics Summary
        story.extend(self._create_metrics_page(month_a, month_b, metrics))

        # Page 2+: Detailed Comparison Table
        story.append(PageBreak())
        story.extend(self._create_comparison_table(comparison_df, month_a, month_b))

        # Page N+1: Contact Report Section (if data provided)
        if contact_data:
            logger.info("Adding contact report section to PDF")
            story.append(PageBreak())
            story.extend(self._create_contact_report_section(contact_data))

        # Page N+X: 2025 Deals Overview (if data provided)
        if deals_2025_df is not None and not deals_2025_df.empty:
            logger.info("Adding 2025 deals overview to PDF")
            story.append(PageBreak())
            story.extend(self._create_2025_deals_section(deals_2025_df))

        # Build PDF
        doc.build(
            story,
            onFirstPage=lambda canvas, doc: self._create_header(canvas, month_a, month_b),
            onLaterPages=lambda canvas, doc: self._create_header(canvas, month_a, month_b)
        )

        logger.info(f"PDF successfully generated: {output_path}")
        return output_path

    def _create_header(self, canvas_obj: canvas.Canvas, month_a: str, month_b: str):
        """
        Create page header with company name and report title.

        Args:
            canvas_obj: ReportLab canvas object
            month_a: First month name
            month_b: Second month name
        """
        canvas_obj.saveState()

        # Company name (top left)
        canvas_obj.setFont('Helvetica-Bold', 14)
        canvas_obj.setFillColor(COLORS['header'])
        canvas_obj.drawString(20*mm, 200*mm, self.company_name)

        # Report title (center)
        canvas_obj.setFont('Helvetica-Bold', 12)
        canvas_obj.drawCentredString(
            landscape(A4)[0] / 2,
            200*mm,
            f"HubSpot Deal Analysis - Monatsvergleich"
        )

        # Month comparison and date (top right)
        canvas_obj.setFont('Helvetica', 10)
        canvas_obj.drawRightString(
            landscape(A4)[0] - 20*mm,
            200*mm,
            f"{month_a} vs. {month_b}"
        )
        canvas_obj.setFont('Helvetica', 8)
        canvas_obj.drawRightString(
            landscape(A4)[0] - 20*mm,
            195*mm,
            f"Erstellt: {datetime.now().strftime('%d.%m.%Y %H:%M')}"
        )

        # Horizontal line under header
        canvas_obj.setStrokeColor(COLORS['header'])
        canvas_obj.setLineWidth(0.5)
        canvas_obj.line(20*mm, 193*mm, landscape(A4)[0] - 20*mm, 193*mm)

        canvas_obj.restoreState()

    def _create_metrics_page(self, month_a: str, month_b: str, metrics: dict) -> List:
        """
        Create metrics summary page with pipeline and closed deals tables.

        Args:
            month_a: First month name
            month_b: Second month name
            metrics: Dictionary with all metrics

        Returns:
            List of Flowables for the page
        """
        elements = []

        # Title
        elements.append(Spacer(1, 15*mm))
        title = Paragraph("Übersicht", self.styles['SectionHeading'])
        elements.append(title)
        elements.append(Spacer(1, 8*mm))

        # Pipeline Metrics Table
        elements.append(Paragraph("PIPELINE METRIKEN", self.styles['Heading3']))
        elements.append(Spacer(1, 3*mm))

        pipeline_data = [
            ['', month_a, month_b],
            [
                'Pipeline Wert',
                format_euro(metrics.get('total_weighted_a', 0)),
                format_euro(metrics.get('total_weighted_b', 0))
            ],
            [
                'Veränderung',
                '',
                f"{format_euro(metrics.get('weighted_change', 0))} "
                f"({format_percentage(metrics.get('weighted_change_pct', 0), include_sign=True)})"
            ]
        ]

        pipeline_table = Table(pipeline_data, colWidths=[80*mm, 50*mm, 50*mm])
        pipeline_table.setStyle(TableStyle([
            # Header row
            ('BACKGROUND', (0, 0), (-1, 0), COLORS['header']),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 11),
            ('ALIGN', (1, 0), (-1, 0), 'CENTER'),

            # Data rows
            ('FONTNAME', (0, 1), (0, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 1), (-1, -1), 10),
            ('ALIGN', (1, 1), (-1, -1), 'RIGHT'),

            # Grid
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('LEFTPADDING', (0, 0), (-1, -1), 6),
            ('RIGHTPADDING', (0, 0), (-1, -1), 6),
            ('TOPPADDING', (0, 0), (-1, -1), 4),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ]))

        elements.append(pipeline_table)
        elements.append(Spacer(1, 10*mm))

        # Closed Deals Table
        elements.append(Paragraph("ABGESCHLOSSENE DEALS", self.styles['Heading3']))
        elements.append(Spacer(1, 3*mm))

        closed_data = [
            ['Status', 'Anzahl', 'Gesamtwert'],
            [
                'Gewonnen',
                str(metrics.get('gewonnen_count', 0)),
                format_euro(metrics.get('gewonnen_amount', 0))
            ],
            [
                'Verloren',
                str(metrics.get('verloren_count', 0)),
                format_euro(metrics.get('verloren_amount', 0))
            ],
            [
                'Kein Angebot',
                str(metrics.get('kein_angebot_count', 0)),
                format_euro(metrics.get('kein_angebot_amount', 0))
            ]
        ]

        closed_table = Table(closed_data, colWidths=[60*mm, 40*mm, 60*mm])
        closed_table.setStyle(TableStyle([
            # Header row
            ('BACKGROUND', (0, 0), (-1, 0), COLORS['header']),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 11),
            ('ALIGN', (0, 0), (0, 0), 'LEFT'),
            ('ALIGN', (1, 0), (-1, 0), 'CENTER'),

            # Data rows
            ('FONTSIZE', (0, 1), (-1, -1), 10),
            ('ALIGN', (1, 1), (-1, -1), 'RIGHT'),

            # Grid
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('LEFTPADDING', (0, 0), (-1, -1), 6),
            ('RIGHTPADDING', (0, 0), (-1, -1), 6),
            ('TOPPADDING', (0, 0), (-1, -1), 4),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ]))

        elements.append(closed_table)

        return elements

    def _create_comparison_table(
        self,
        comparison_df: pd.DataFrame,
        month_a: str,
        month_b: str
    ) -> List:
        """
        Create detailed comparison table with pagination and color-coding.

        Args:
            comparison_df: DataFrame with deal comparison data
            month_a: First month name
            month_b: Second month name

        Returns:
            List of Flowables for the table pages
        """
        elements = []

        # Page title
        elements.append(Spacer(1, 10*mm))
        title = Paragraph(f"Deal-Vergleich Detail", self.styles['SectionHeading'])
        elements.append(title)
        elements.append(Spacer(1, 5*mm))

        # Prepare data
        # Select and order columns (matching plan)
        display_cols = [
            'Deal Name',
            'Owner_Name',
            'Deal_Value',
            'Deal_Age_Days',
            f'Current_Phase_A',  # Will use month_a
            'Probability_A',
            'Weighted_Value_A',
            f'Current_Phase_B',  # Will use month_b
            'Probability_B',
            'Weighted_Value_B',
            'Status_Änderung'
        ]

        # Filter to available columns
        available_cols = [col for col in display_cols if col in comparison_df.columns]
        df_subset = comparison_df[available_cols].copy()

        # Convert owner names to initials (e.g., "Max Mustermann" -> "MM")
        def get_initials(name):
            if pd.isna(name) or name in ['', 'Unbekannt', 'nan']:
                return '-'
            parts = str(name).strip().split()
            if len(parts) >= 2:
                return f"{parts[0][0]}{parts[-1][0]}".upper()
            elif len(parts) == 1 and parts[0]:
                return parts[0][0].upper()
            return '-'

        if 'Owner_Name' in df_subset.columns:
            df_subset['Owner_Name'] = df_subset['Owner_Name'].apply(get_initials)

        # Shorten month names for headers (Dezember -> Dez, Januar -> Jan, etc.)
        def shorten_month(month_str):
            """Shorten month name: 'Dezember 2025' -> 'Dez 25'"""
            month_map = {
                'Januar': 'Jan', 'Februar': 'Feb', 'März': 'Mär', 'April': 'Apr',
                'Mai': 'Mai', 'Juni': 'Jun', 'Juli': 'Jul', 'August': 'Aug',
                'September': 'Sep', 'Oktober': 'Okt', 'November': 'Nov', 'Dezember': 'Dez'
            }
            parts = month_str.split(' ')
            if len(parts) == 2:
                month, year = parts
                short_month = month_map.get(month, month[:3])
                short_year = year[-2:]  # 2025 -> 25
                return f"{short_month} {short_year}"
            return month_str

        month_a_short = shorten_month(month_a)
        month_b_short = shorten_month(month_b)

        # Rename columns for display with shortened month names
        df_subset = df_subset.rename(columns={
            'Owner_Name': 'Vtw',  # Verantwortlicher (initials)
            'Deal_Value': 'Wert',
            'Deal_Age_Days': 'Alter',
            'Current_Phase_A': f'Phase\n{month_a_short}',
            'Current_Phase_B': f'Phase\n{month_b_short}',
            'Probability_A': f'%\n{month_a_short}',
            'Probability_B': f'%\n{month_b_short}',
            'Weighted_Value_A': f'Gewichtet\n{month_a_short}',
            'Weighted_Value_B': f'Gewichtet\n{month_b_short}',
            'Status_Änderung': 'Status'
        })

        # Pagination
        rows_per_page = DEALS_PER_PAGE_COMPARISON
        total_rows = len(df_subset)
        total_pages = math.ceil(total_rows / rows_per_page)

        for page_num in range(total_pages):
            start_idx = page_num * rows_per_page
            end_idx = min(start_idx + rows_per_page, total_rows)
            page_df = df_subset.iloc[start_idx:end_idx]

            # Create table data with header (using Paragraph for word wrap)
            # Convert \n to <br/> for ReportLab Paragraph
            header_row = [
                Paragraph(col.replace('\n', '<br/>'), self.styles['TableHeader'])
                for col in page_df.columns
            ]
            table_data = [header_row]

            # Add data rows - use plain strings for amounts (TableStyle handles alignment)
            for _, row in page_df.iterrows():
                formatted_row = []
                for col in page_df.columns:
                    value = row[col]

                    # Format based on column type
                    if col == 'Deal Name':
                        # Use Paragraph for Deal Name to allow word wrap
                        text = str(value) if pd.notna(value) else '-'
                        formatted_row.append(Paragraph(text, self.styles['TableCell']))
                    elif col == 'Status':
                        # Use Paragraph for Status to allow word wrap
                        text = str(value) if pd.notna(value) else '-'
                        formatted_row.append(Paragraph(text, self.styles['TableCell']))
                    elif 'Phase' in col:
                        # Use Paragraph for Phase columns to allow word wrap
                        text = str(value) if pd.notna(value) else '-'
                        formatted_row.append(Paragraph(text, self.styles['TableCell']))
                    elif col == 'Wert' or 'Gewichtet' in col:
                        # Amounts - plain string, alignment via TableStyle
                        formatted_row.append(format_euro(value) if pd.notna(value) else '-')
                    elif col == 'Alter':
                        # Age - plain string, alignment via TableStyle
                        try:
                            formatted_row.append(str(int(value)) if pd.notna(value) and value != '' else '-')
                        except (ValueError, TypeError):
                            formatted_row.append('-')
                    elif col.startswith('%'):
                        # Percentage - plain string, alignment via TableStyle
                        try:
                            formatted_row.append(f"{int(value)}%" if pd.notna(value) else '-')
                        except (ValueError, TypeError):
                            formatted_row.append('-')
                    else:
                        formatted_row.append(str(value) if pd.notna(value) else '-')

                table_data.append(formatted_row)

            # Create table
            # Column widths (landscape A4 is 297mm, minus margins 257mm available)
            num_cols = len(page_df.columns)
            col_widths = self._calculate_column_widths(page_df.columns)

            table = Table(table_data, colWidths=col_widths)

            # Build style commands
            style_commands = [
                # Header row styling
                ('BACKGROUND', (0, 0), (-1, 0), COLORS['header']),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 8),
                ('ALIGN', (0, 0), (-1, 0), 'CENTER'),

                # Data rows styling
                ('FONTSIZE', (0, 1), (-1, -1), 7),
                ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),

                # Grid
                ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('LEFTPADDING', (0, 0), (-1, -1), 3),
                ('RIGHTPADDING', (0, 0), (-1, -1), 3),
                ('TOPPADDING', (0, 0), (-1, -1), 2),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
            ]

            # Add alignment for columns
            col_list = list(page_df.columns)
            for col_idx, col_name in enumerate(col_list):
                # Right-align amount/number columns (Wert, Alter, %, Gewichtet)
                if col_name in ['Wert', 'Alter'] or 'Gewichtet' in col_name or col_name.startswith('%'):
                    style_commands.append(('ALIGN', (col_idx, 1), (col_idx, -1), 'RIGHT'))
                # Center-align initials column (Vtw)
                elif col_name == 'Vtw':
                    style_commands.append(('ALIGN', (col_idx, 1), (col_idx, -1), 'CENTER'))

            # Apply row colors based on status change
            for row_idx, (_, row) in enumerate(page_df.iterrows(), start=1):
                if 'Status' in row:
                    bg_color = self._get_row_color(row['Status'])
                    if bg_color != COLORS['white']:
                        style_commands.append(
                            ('BACKGROUND', (0, row_idx), (-1, row_idx), bg_color)
                        )

            table.setStyle(TableStyle(style_commands))

            elements.append(table)

            # Page break between table pages (except last)
            if page_num < total_pages - 1:
                elements.append(PageBreak())
                elements.append(Spacer(1, 10*mm))

        return elements

    def _calculate_column_widths(self, columns: List[str]) -> List[float]:
        """
        Calculate appropriate column widths based on column names.

        Args:
            columns: List of column names

        Returns:
            List of column widths in mm
        """
        # Available width: landscape A4 (297mm) - margins (40mm) = 257mm
        # Distribute based on content type
        widths = []
        for col in columns:
            if col == 'Deal Name':
                widths.append(54*mm)  # Wider for text wrapping
            elif col == 'Vtw':
                widths.append(10*mm)  # Initials only (2 chars)
            elif col == 'Wert':
                widths.append(18*mm)
            elif col == 'Alter':
                widths.append(12*mm)
            elif 'Phase' in col:
                widths.append(26*mm)  # Wider for text wrapping
            elif col.startswith('%'):
                widths.append(14*mm)
            elif 'Gewichtet' in col:
                widths.append(22*mm)
            elif col == 'Status':
                widths.append(40*mm)  # Wider for text wrapping
            else:
                widths.append(18*mm)  # Default

        # Adjust if total width exceeds available space
        total_width = sum(widths)
        available_width = 257*mm
        if total_width > available_width:
            scale_factor = available_width / total_width
            widths = [w * scale_factor for w in widths]

        return widths

    def _create_contact_report_section(self, contact_data: dict) -> List:
        """
        Create contact/lead analysis section for PDF

        Args:
            contact_data: Dictionary with 'kpis', 'sql_details', 'source_breakdown' DataFrames

        Returns:
            List of Flowables for PDF
        """
        elements = []

        kpis_df = contact_data.get('kpis')
        sql_details_df = contact_data.get('sql_details')
        source_breakdown_df = contact_data.get('source_breakdown')

        # Page N+1: KPI Overview (12 months)
        if kpis_df is not None and not kpis_df.empty:
            title = Paragraph("Lead Funnel - KPI Übersicht", self.styles['SectionHeading'])
            elements.append(title)
            elements.append(Spacer(1, 10*mm))

            # Prepare table data
            table_data = []
            header_row = [
                Paragraph(col, self.styles['TableHeader'])
                for col in kpis_df.columns
            ]
            table_data.append(header_row)

            # Add data rows
            for _, row in kpis_df.iterrows():
                formatted_row = []
                for col in kpis_df.columns:
                    value = row[col]
                    if pd.notna(value):
                        # Format numbers with German locale
                        if isinstance(value, (int, float)) and col != 'Monat':
                            if 'Conv.Rate' in col or '%' in col:
                                text = f"{value:.1f}%"
                            else:
                                text = f"{int(value):,}".replace(',', '.')
                        else:
                            text = str(value)
                    else:
                        text = '-'
                    formatted_row.append(text)
                table_data.append(formatted_row)

            # Create table
            col_widths = [50*mm, 25*mm, 25*mm, 30*mm, 35*mm]  # Monat, MQLs, SQLs, Conv.Rate, Ø Tage
            table = Table(table_data, colWidths=col_widths, repeatRows=1)

            # Style table
            table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), COLORS['header']),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 9),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('ALIGN', (1, 1), (-1, -1), 'RIGHT'),  # Right-align numbers
                ('ALIGN', (0, 1), (0, -1), 'LEFT'),     # Left-align month names
            ]))

            elements.append(table)
            elements.append(PageBreak())

        # Page N+2: SQL Details List (last month)
        if sql_details_df is not None and not sql_details_df.empty:
            title = Paragraph("SQL Details - Letzter abgeschlossener Monat", self.styles['SectionHeading'])
            elements.append(title)
            elements.append(Spacer(1, 10*mm))

            # Prepare table data
            table_data = []
            header_row = [
                Paragraph(col, self.styles['TableHeader'])
                for col in sql_details_df.columns
            ]
            table_data.append(header_row)

            # Add data rows (use Paragraph for text wrapping)
            for _, row in sql_details_df.iterrows():
                formatted_row = []
                for col in sql_details_df.columns:
                    value = row[col]
                    text = str(value) if pd.notna(value) else '-'

                    # Use Paragraph for Firma and Quelle columns (potential text wrapping)
                    if col in ['Firma', 'Quelle']:
                        formatted_row.append(Paragraph(text, self.styles['TableCell']))
                    else:
                        formatted_row.append(text)

                table_data.append(formatted_row)

            # Create table
            col_widths = [25*mm, 50*mm, 70*mm, 70*mm]  # Datum, Kontakt, Firma, Quelle
            table = Table(table_data, colWidths=col_widths, repeatRows=1)

            # Style table
            table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), COLORS['header']),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 9),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('ALIGN', (0, 1), (0, -1), 'CENTER'),  # Center-align dates
            ]))

            elements.append(table)
            elements.append(PageBreak())

        # Page N+3: Source Breakdown Matrix (12 months)
        if source_breakdown_df is not None and not source_breakdown_df.empty:
            title = Paragraph("Lead-Qualität nach Kanal - 12 Monate Matrix", self.styles['SectionHeading'])
            elements.append(title)
            elements.append(Spacer(1, 10*mm))

            # Prepare table data
            table_data = []
            header_row = [
                Paragraph(col.replace('\n', '<br/>'), self.styles['TableHeader'])
                for col in source_breakdown_df.columns
            ]
            table_data.append(header_row)

            # Add data rows
            for _, row in source_breakdown_df.iterrows():
                formatted_row = []
                for idx, col in enumerate(source_breakdown_df.columns):
                    value = row[col]
                    text = str(value) if pd.notna(value) else '-'

                    # Use Paragraph for Quelle column (first column) to allow text wrapping
                    if idx == 0:
                        formatted_row.append(Paragraph(text, self.styles['TableCell']))
                    else:
                        formatted_row.append(text)

                table_data.append(formatted_row)

            # Calculate column widths dynamically
            # Quelle column: 40mm, Month columns: equal split of remaining space
            num_cols = len(source_breakdown_df.columns)
            available_width = 257*mm  # Landscape A4 minus margins
            quelle_width = 40*mm
            remaining_width = available_width - quelle_width
            month_col_width = remaining_width / (num_cols - 1)  # -1 for Quelle column

            col_widths = [quelle_width] + [month_col_width] * (num_cols - 1)

            table = Table(table_data, colWidths=col_widths, repeatRows=1)

            # Style table
            table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), COLORS['header']),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 7),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 6),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('ALIGN', (1, 1), (-1, -1), 'CENTER'),  # Center-align all data cells except Quelle
                ('ALIGN', (0, 1), (0, -1), 'LEFT'),      # Left-align Quelle column
                ('FONTSIZE', (0, 0), (-1, -1), 6),       # Smaller font for matrix
            ]))

            elements.append(table)

        return elements

    def _create_2025_deals_section(self, deals_2025_df: pd.DataFrame) -> List:
        """
        Create PDF section for all deals created in 2025

        Args:
            deals_2025_df: DataFrame with 2025 deals data

        Returns:
            List of ReportLab Flowables
        """
        elements = []

        # Title
        title = Paragraph("Alle Deals aus 2025 - Übersicht", self.styles['SectionHeading'])
        elements.append(title)
        elements.append(Spacer(1, 10*mm))

        # Summary statistics
        total_deals = len(deals_2025_df)
        won_deals = len(deals_2025_df[deals_2025_df['status'] == 'Won'])
        lost_deals = len(deals_2025_df[deals_2025_df['status'] == 'Lost'])
        no_offer_deals = len(deals_2025_df[deals_2025_df['status'] == 'Kein Angebot'])
        active_deals = len(deals_2025_df[deals_2025_df['status'] == 'Active'])

        summary_text = f"Gesamt: {total_deals} Deals | Gewonnen: {won_deals} | Verloren: {lost_deals} | Kein Angebot: {no_offer_deals} | Aktiv: {active_deals}"
        summary_para = Paragraph(summary_text, self.styles['Normal'])
        elements.append(summary_para)
        elements.append(Spacer(1, 8*mm))

        # Select columns for display (basis columns as requested)
        display_columns = ['deal_name', 'amount', 'status', 'contact_source', 'rejection_reason']
        df_display = deals_2025_df[display_columns].copy()

        # Rename columns for German display
        df_display = df_display.rename(columns={
            'deal_name': 'Deal Name',
            'amount': 'Wert',
            'status': 'Status',
            'contact_source': 'Quelle',
            'rejection_reason': 'Ablehnungsgrund'
        })

        # Pagination
        rows_per_page = DEALS_PER_PAGE_2025_OVERVIEW
        total_rows = len(df_display)
        total_pages = math.ceil(total_rows / rows_per_page)

        for page_num in range(total_pages):
            start_idx = page_num * rows_per_page
            end_idx = min(start_idx + rows_per_page, total_rows)
            page_df = df_display.iloc[start_idx:end_idx]

            # Create table header
            header_row = [
                Paragraph(col, self.styles['TableHeader'])
                for col in page_df.columns
            ]
            table_data = [header_row]

            # Add data rows
            for _, row in page_df.iterrows():
                formatted_row = []
                for col in page_df.columns:
                    value = row[col]

                    if col == 'Deal Name':
                        # Use Paragraph for Deal Name to allow word wrap
                        text = str(value) if pd.notna(value) else '-'
                        formatted_row.append(Paragraph(text, self.styles['TableCell']))
                    elif col == 'Wert':
                        # Format as Euro
                        formatted_row.append(format_euro(value) if pd.notna(value) and value != 0 else '-')
                    elif col in ['Quelle', 'Ablehnungsgrund']:
                        # Use Paragraph for text wrapping
                        text = str(value) if pd.notna(value) and str(value) != '–' else '–'
                        formatted_row.append(Paragraph(text, self.styles['TableCell']))
                    else:
                        # Plain text for Status
                        text = str(value) if pd.notna(value) else '-'
                        formatted_row.append(text)

                table_data.append(formatted_row)

            # Column widths (landscape A4: 257mm available)
            # Deal Name: 60mm, Wert: 25mm, Status: 20mm, Quelle: 70mm, Ablehnungsgrund: 82mm
            col_widths = [60*mm, 25*mm, 20*mm, 70*mm, 82*mm]

            table = Table(table_data, colWidths=col_widths, repeatRows=1)

            # Build table style
            style_commands = [
                # Header row styling
                ('BACKGROUND', (0, 0), (-1, 0), COLORS['header']),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 8),
                ('ALIGN', (0, 0), (-1, 0), 'CENTER'),

                # Data rows styling
                ('FONTSIZE', (0, 1), (-1, -1), 7),
                ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),

                # Grid
                ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('LEFTPADDING', (0, 0), (-1, -1), 3),
                ('RIGHTPADDING', (0, 0), (-1, -1), 3),
                ('TOPPADDING', (0, 0), (-1, -1), 2),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 2),

                # Column alignment
                ('ALIGN', (1, 1), (1, -1), 'RIGHT'),    # Wert - right align
                ('ALIGN', (2, 1), (2, -1), 'CENTER'),   # Status - center align
            ]

            # Apply row colors based on status
            for row_idx, (_, row) in enumerate(page_df.iterrows(), start=1):
                status = row['Status']
                if status == 'Won':
                    bg_color = COLORS['gewonnen']
                elif status == 'Lost' or status == 'Kein Angebot':
                    bg_color = COLORS['verloren']
                else:
                    bg_color = COLORS['white']

                if bg_color != COLORS['white']:
                    style_commands.append(
                        ('BACKGROUND', (0, row_idx), (-1, row_idx), bg_color)
                    )

            table.setStyle(TableStyle(style_commands))

            elements.append(table)

            # Add page break if not last page
            if page_num < total_pages - 1:
                elements.append(PageBreak())

        return elements

    def _get_row_color(self, status_change: str) -> colors.Color:
        """
        Get background color for table row based on status change.

        Args:
            status_change: Status change string (with emoji)

        Returns:
            ReportLab Color object
        """
        status_str = str(status_change)

        if '🟢' in status_str:  # Gewonnen
            return COLORS['gewonnen']
        elif '🔴' in status_str:  # Verloren or Kein Angebot
            return COLORS['verloren']
        elif '⚫' in status_str:  # Bereits abgeschlossen
            return COLORS['closed']
        elif '🔵' in status_str:  # Phase geändert
            return COLORS['changed']
        elif '🆕' in status_str:  # Neu
            return COLORS['neu']
        else:
            return COLORS['white']
