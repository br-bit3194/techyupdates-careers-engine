"""In-memory Excel workbook generator using openpyxl with 4 styled tabs and clickable links."""

import io
import re
from typing import List, Dict
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

from services.ai_extractor import OpportunityRecord

TIER_CONFIG = [
    {
        "tier_name": "Internship",
        "sheet_name": "🎓 Internships",
        "color_hex": "1E3A8A",  # Navy Blue
        "zebra_hex": "F0F4F8",
    },
    {
        "tier_name": "Fresher / 0-2 YOE",
        "sheet_name": "🚀 Freshers (0-2 YOE)",
        "color_hex": "065F46",  # Emerald Green
        "zebra_hex": "F0FDF4",
    },
    {
        "tier_name": "Mid-Level (2-5 YOE)",
        "sheet_name": "⚡ Mid-Level (2-5 YOE)",
        "color_hex": "0E7490",  # Deep Teal
        "zebra_hex": "F0F9FF",
    },
    {
        "tier_name": "Senior / Staff / Lead (5+ YOE)",
        "sheet_name": "🏆 Senior & Staff (5+ YOE)",
        "color_hex": "581C87",  # Royal Purple
        "zebra_hex": "FAF5FF",
    },
]

HEADERS = [
    "Company",
    "Role Title",
    "Domain",
    "Experience",
    "Workplace",
    "Location",
    "Salary / CTC",
    "Tech Stack",
    "Posted Date",
    "Why Apply?",
    "Direct Apply Link",
]


def _extract_numeric_salary(salary_str: str) -> float:
    """Extract a numeric heuristic from salary string for sorting."""
    if not salary_str or "Not Disclosed" in salary_str:
        return 0.0
    # Match numbers like $120k, 15 LPA, 150000
    numbers = re.findall(r"(\d+(?:\.\d+)?)", salary_str)
    if not numbers:
        return 0.0
    val = float(numbers[-1])
    if "lpa" in salary_str.lower() or "lakh" in salary_str.lower():
        return val * 1200  # Normalize to rough USD comparable for sorting
    if "k" in salary_str.lower():
        return val * 1000
    return val


def _sort_records(tier_name: str, records: List[OpportunityRecord]) -> List[OpportunityRecord]:
    """Sort records per PRD Section 6.3 specifications."""
    if tier_name == "Internship":
        # Newest / company
        return sorted(records, key=lambda r: (r.company_name.lower(), r.job_title.lower()))
    elif tier_name == "Fresher / 0-2 YOE":
        # Max salary / match rank
        return sorted(records, key=lambda r: _extract_numeric_salary(r.salary_package), reverse=True)
    elif tier_name == "Mid-Level (2-5 YOE)":
        # Domain, then Company
        return sorted(records, key=lambda r: (r.technical_domain, r.company_name.lower()))
    elif tier_name == "Senior / Staff / Lead (5+ YOE)":
        # Max compensation
        return sorted(records, key=lambda r: _extract_numeric_salary(r.salary_package), reverse=True)
    return records


def build_excel_workbook(opportunities: List[OpportunityRecord]) -> io.BytesIO:
    """Generate a 4-tab styled Excel workbook in memory."""
    wb = openpyxl.Workbook()
    # Remove default sheet
    default_sheet = wb.active
    if default_sheet is not None:
        wb.remove(default_sheet)

    thin_border = Border(
        left=Side(style="thin", color="E2E8F0"),
        right=Side(style="thin", color="E2E8F0"),
        top=Side(style="thin", color="E2E8F0"),
        bottom=Side(style="thin", color="E2E8F0"),
    )

    link_font = Font(name="Segoe UI", size=10, color="0000EE", underline="single", bold=True)
    data_font = Font(name="Segoe UI", size=10, color="1E293B")

    # Group opportunities by tier
    tiered_records: Dict[str, List[OpportunityRecord]] = {
        config["tier_name"]: [] for config in TIER_CONFIG
    }
    for opp in opportunities:
        if opp.seniority_tier in tiered_records:
            tiered_records[opp.seniority_tier].append(opp)
        else:
            # Fallback to Mid-Level if unmapped
            tiered_records["Mid-Level (2-5 YOE)"].append(opp)

    for config in TIER_CONFIG:
        tier_name = config["tier_name"]
        sheet_name = config["sheet_name"]
        color_hex = config["color_hex"]
        zebra_hex = config["zebra_hex"]

        ws = wb.create_sheet(title=sheet_name)
        ws.sheet_properties.tabColor = color_hex
        ws.views.sheetView[0].showGridLines = True

        # Header Styling
        header_fill = PatternFill(start_color=color_hex, end_color=color_hex, fill_type="solid")
        header_font = Font(name="Segoe UI", size=11, bold=True, color="FFFFFF")
        header_align = Alignment(horizontal="center", vertical="center", wrap_text=True)

        ws.append(HEADERS)
        ws.row_dimensions[1].height = 28

        for col_idx in range(1, len(HEADERS) + 1):
            cell = ws.cell(row=1, column=col_idx)
            cell.fill = header_fill
            cell.font = header_font
            cell.alignment = header_align
            cell.border = thin_border

        # Sort items for this tier
        records = _sort_records(tier_name, tiered_records[tier_name])

        # Write data rows
        row_idx = 2
        for opp in records:
            # Format experience string
            if opp.min_exp_years is not None and opp.max_exp_years is not None:
                exp_str = f"{opp.min_exp_years}-{opp.max_exp_years} yrs"
            elif opp.min_exp_years is not None:
                exp_str = f"{opp.min_exp_years}+ yrs"
            else:
                exp_str = "0+ yrs"

            tech_stack_str = ", ".join(opp.core_tech_stack) if opp.core_tech_stack else "Python, Cloud"
            posted_date_str = opp.posted_date or "Recent"

            # Clean apply url for hyperlink
            clean_url = opp.apply_url.replace('"', '""')
            hyperlink_formula = f'=HYPERLINK("{clean_url}", "Apply Direct ↗")'

            row_data = [
                opp.company_name,
                opp.job_title,
                opp.technical_domain,
                exp_str,
                opp.workplace_type,
                opp.location,
                opp.salary_package,
                tech_stack_str,
                posted_date_str,
                opp.why_it_matters,
                hyperlink_formula,
            ]
            ws.append(row_data)
            ws.row_dimensions[row_idx].height = 24

            # Alternate row background
            is_even = (row_idx % 2 == 0)
            fill_color = zebra_hex if is_even else "FFFFFF"
            row_fill = PatternFill(start_color=fill_color, end_color=fill_color, fill_type="solid")

            for col_idx in range(1, len(HEADERS) + 1):
                cell = ws.cell(row=row_idx, column=col_idx)
                cell.fill = row_fill
                cell.border = thin_border

                if col_idx == 11:  # Direct Apply Link column
                    cell.font = link_font
                    cell.alignment = Alignment(horizontal="center", vertical="center")
                elif col_idx in (1, 2, 8, 10):  # Text columns (Company, Title, Tech Stack, Why Apply)
                    cell.font = data_font
                    cell.alignment = Alignment(horizontal="left", vertical="center")
                else:  # Metadata columns (Domain, Exp, Workplace, Location, Salary, Posted Date)
                    cell.font = data_font
                    cell.alignment = Alignment(horizontal="center", vertical="center")

            row_idx += 1

        # Freeze top row
        ws.freeze_panes = "A2"

        # Apply Auto-Filter
        last_row = max(row_idx - 1, 1)
        ws.auto_filter.ref = f"A1:K{last_row}"

        # Calculate Column Widths
        column_widths = {
            1: 20,  # Company
            2: 32,  # Role Title
            3: 30,  # Domain
            4: 14,  # Experience
            5: 14,  # Workplace
            6: 22,  # Location
            7: 20,  # Salary / CTC
            8: 28,  # Tech Stack
            9: 16,  # Posted Date
            10: 44, # Why Apply?
            11: 18, # Direct Apply Link
        }
        for col_idx, width in column_widths.items():
            col_letter = get_column_letter(col_idx)
            ws.column_dimensions[col_letter].width = width

    # Save to BytesIO in memory
    buffer = io.BytesIO()
    wb.save(buffer)
    buffer.seek(0)
    return buffer
