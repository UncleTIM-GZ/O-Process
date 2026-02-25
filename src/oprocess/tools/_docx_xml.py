"""Low-level XML helpers for python-docx document construction.

Provides OoXML manipulation utilities used by _docx_builder:
- Font helpers (East Asian font setting)
- Paragraph border helpers
- Table border/shading helpers
- Field code insertion (TOC, PAGE)
"""

from __future__ import annotations

from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm


def setup_page_section(sec) -> None:
    """Configure A4 page with legal document margins."""
    sec.page_height, sec.page_width = Cm(29.7), Cm(21.0)
    sec.top_margin, sec.bottom_margin = Cm(2.54), Cm(2.54)
    sec.left_margin, sec.right_margin = Cm(3.17), Cm(3.17)


def set_run_east_asian(run, font_name: str) -> None:
    """Set East Asian font on a run."""
    rpr = run._r.get_or_add_rPr()
    fonts = rpr.find(qn("w:rFonts"))
    if fonts is None:
        fonts = OxmlElement("w:rFonts")
        rpr.insert(0, fonts)
    fonts.set(qn("w:eastAsia"), font_name)


def add_bottom_border(paragraph, color: str = "003D6B") -> None:
    """Add bottom border line to a paragraph."""
    p_pr = paragraph._p.get_or_add_pPr()
    p_bdr = OxmlElement("w:pBdr")
    bottom = OxmlElement("w:bottom")
    bottom.set(qn("w:val"), "single")
    bottom.set(qn("w:sz"), "6")
    bottom.set(qn("w:space"), "1")
    bottom.set(qn("w:color"), color)
    p_bdr.append(bottom)
    p_pr.append(p_bdr)


def remove_table_borders(table) -> None:
    """Remove all borders from a table (for cover metadata)."""
    tbl = table._tbl
    tbl_pr = tbl.tblPr if tbl.tblPr is not None else OxmlElement("w:tblPr")
    borders = OxmlElement("w:tblBorders")
    for edge in ("top", "left", "bottom", "right", "insideH", "insideV"):
        el = OxmlElement(f"w:{edge}")
        el.set(qn("w:val"), "none")
        el.set(qn("w:sz"), "0")
        el.set(qn("w:space"), "0")
        el.set(qn("w:color"), "auto")
        borders.append(el)
    tbl_pr.append(borders)


def shade_row(row, fill: str) -> None:
    """Apply background shading to all cells in a table row."""
    for cell in row.cells:
        tc_pr = cell._tc.get_or_add_tcPr()
        shd = OxmlElement("w:shd")
        shd.set(qn("w:val"), "clear")
        shd.set(qn("w:color"), "auto")
        shd.set(qn("w:fill"), fill)
        tc_pr.append(shd)


def bold_row(row) -> None:
    """Set all runs in a table row to bold."""
    for cell in row.cells:
        for p in cell.paragraphs:
            for run in p.runs:
                run.bold = True


def insert_field(run_element, field_code: str, placeholder: str = "") -> None:
    """Insert a Word field code (TOC, PAGE, etc.) into a run element."""
    fld_begin = OxmlElement("w:fldChar")
    fld_begin.set(qn("w:fldCharType"), "begin")
    instr = OxmlElement("w:instrText")
    instr.set(qn("xml:space"), "preserve")
    instr.text = field_code
    fld_sep = OxmlElement("w:fldChar")
    fld_sep.set(qn("w:fldCharType"), "separate")
    elements = [fld_begin, instr, fld_sep]
    if placeholder:
        ph = OxmlElement("w:t")
        ph.text = placeholder
        elements.append(ph)
    fld_end = OxmlElement("w:fldChar")
    fld_end.set(qn("w:fldCharType"), "end")
    elements.append(fld_end)
    run_element.extend(elements)
