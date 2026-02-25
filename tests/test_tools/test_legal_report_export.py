"""Tests for legal report export tool."""

from __future__ import annotations

from pathlib import Path

import pytest

from oprocess.tools.legal_report_export import _split_sections, export_legal_report

DEMO5_PATH = Path("docs/demos/demo-05-jinyuan-legal-dd-report.md")


@pytest.fixture()
def demo5_md() -> str:
    if not DEMO5_PATH.exists():
        pytest.skip("Demo 5 report file not found")
    return DEMO5_PATH.read_text(encoding="utf-8")


@pytest.fixture()
def parsed(demo5_md: str) -> dict:
    return _split_sections(demo5_md)


class TestSplitSections:
    def test_body_has_13_chapters(self, parsed: dict) -> None:
        assert len(parsed["body"]) == 13

    def test_appendix_a_has_items(self, parsed: dict) -> None:
        assert len(parsed["appendix_a"]) >= 13  # 13 MCP + 1 O'Process

    def test_appendix_b_has_13_items(self, parsed: dict) -> None:
        assert len(parsed["appendix_b"]) == 13

    def test_tail_sections_preserved(self, parsed: dict) -> None:
        assert len(parsed["tail_sections"]) == 2

    def test_header_contains_metadata(self, parsed: dict) -> None:
        assert "广州市金元物业" in parsed["header"]
        assert "委托方" in parsed["header"]


class TestNoTechnicalLeakage:
    def test_body_no_mcp(self, parsed: dict) -> None:
        body_text = "\n".join(parsed["body"])
        assert "MCP 流程定位" not in body_text

    def test_body_no_provenance_chain(self, parsed: dict) -> None:
        body_text = "\n".join(parsed["body"])
        assert "provenance_chain" not in body_text

    def test_body_no_search_process(self, parsed: dict) -> None:
        body_text = "\n".join(parsed["body"])
        assert "search_process" not in body_text

    def test_body_no_oprocess_framework(self, parsed: dict) -> None:
        body_text = "\n".join(parsed["body"])
        assert "O'Process 流程框架" not in body_text


class TestAppendixCompleteness:
    def test_appendix_a_contains_mcp(self, parsed: dict) -> None:
        a_text = " ".join(item["content"] for item in parsed["appendix_a"])
        assert "MCP" in a_text

    def test_appendix_b_contains_provenance(self, parsed: dict) -> None:
        b_text = " ".join(item["content"] for item in parsed["appendix_b"])
        assert "provenance_chain" in b_text

    def test_appendix_items_have_chapter_ref(self, parsed: dict) -> None:
        for item in parsed["appendix_a"]:
            assert "chapter" in item
            assert "第" in item["chapter"]


class TestExportEndToEnd:
    def test_generates_docx(self, tmp_path: Path, demo5_md: str) -> None:
        output = tmp_path / "output.docx"
        result = export_legal_report(str(DEMO5_PATH), str(output))
        assert output.exists()
        assert result["chapters"] == 13
        assert result["appendix_a_items"] >= 13
        assert result["appendix_b_items"] == 13

    def test_docx_has_content(self, tmp_path: Path, demo5_md: str) -> None:
        output = tmp_path / "output.docx"
        export_legal_report(str(DEMO5_PATH), str(output))

        from docx import Document

        doc = Document(str(output))
        assert len(doc.paragraphs) > 100
        assert len(doc.tables) > 10

    def test_docx_body_clean(self, tmp_path: Path, demo5_md: str) -> None:
        """Verify the Word body has no technical content."""
        output = tmp_path / "output.docx"
        export_legal_report(str(DEMO5_PATH), str(output))

        from docx import Document

        doc = Document(str(output))
        # Collect text before the appendix section break
        body_text = ""
        for p in doc.paragraphs:
            if "附录：流程分类节点映射" in p.text:
                break
            body_text += p.text + "\n"

        assert "MCP 流程定位" not in body_text
        assert "provenance_chain" not in body_text


class TestCjkFontStyles:
    def test_normal_style_has_songti(self, tmp_path: Path, demo5_md: str) -> None:
        output = tmp_path / "output.docx"
        export_legal_report(str(DEMO5_PATH), str(output))

        from docx import Document
        from docx.oxml.ns import qn

        doc = Document(str(output))
        normal = doc.styles["Normal"]
        run_props = normal.element.get_or_add_rPr()
        east_asian = run_props.rFonts.get(qn("w:eastAsia"))
        assert east_asian == "宋体"

    def test_heading_style_has_heiti(self, tmp_path: Path, demo5_md: str) -> None:
        output = tmp_path / "output.docx"
        export_legal_report(str(DEMO5_PATH), str(output))

        from docx import Document
        from docx.oxml.ns import qn

        doc = Document(str(output))
        h2 = doc.styles["Heading 2"]
        h_run_props = h2.element.get_or_add_rPr()
        east_asian = h_run_props.rFonts.get(qn("w:eastAsia"))
        assert east_asian == "黑体"
