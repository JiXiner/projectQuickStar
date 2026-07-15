"""Persist Markdown and HTML project reports."""

from __future__ import annotations

from pathlib import Path

from analyzer.project_scan import ScanResult
from .html_report import markdown_to_html
from .markdown_report import render_markdown


def write_reports(result: ScanResult, output_directory: str | Path) -> dict[str, str]:
    output = Path(output_directory).resolve()
    output.mkdir(parents=True, exist_ok=True)
    markdown_path = output / "project_analysis.md"
    html_path = output / "project_analysis.html"
    markdown = render_markdown(result)
    markdown_path.write_text(markdown, encoding="utf-8")
    html_path.write_text(markdown_to_html(markdown), encoding="utf-8")
    paths = {"markdown": str(markdown_path), "html": str(html_path)}
    result.report_paths = paths
    return paths
