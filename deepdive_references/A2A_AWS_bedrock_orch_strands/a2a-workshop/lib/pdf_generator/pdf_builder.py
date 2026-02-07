"""
PDF Builder

Assembles processed content and generates PDF using WeasyPrint.
"""

from __future__ import annotations

import html
from pathlib import Path
from typing import TYPE_CHECKING

import markdown

if TYPE_CHECKING:
    from .content_collector import ContentFile


class PDFBuilder:
    """Builds PDF from processed workshop content."""

    def __init__(self, css_path: Path, base_path: Path):
        """
        Initialize PDF builder.

        Args:
            css_path: Path to CSS stylesheet
            base_path: Base path for resolving relative paths (project root)
        """
        self.css_path = Path(css_path)
        self.base_path = Path(base_path)

        # Initialize markdown processor with extensions
        self.md = markdown.Markdown(
            extensions=[
                "extra",  # Tables, fenced code, etc.
                "codehilite",  # Syntax highlighting
                "toc",  # Table of contents
                "sane_lists",  # Better list handling
            ]
        )

    def build(
        self, sections: list[ContentFile], output_path: Path, metadata: dict[str, str]
    ) -> None:
        """
        Generate PDF from content sections.

        Args:
            sections: List of ContentFile objects with processed content
            output_path: Path where PDF should be written
            metadata: Dictionary with title, subtitle, etc.
        """
        print("  Generating HTML structure...")
        html_content = self._generate_html(sections, metadata)

        print("  Converting HTML to PDF...")
        self._write_pdf(html_content, output_path)

        print(f"  PDF written to: {output_path}")

    def _generate_html(self, sections: list, metadata: dict[str, str]) -> str:
        """
        Generate complete HTML document from sections.

        Args:
            sections: List of ContentFile objects
            metadata: Metadata for cover page

        Returns:
            Complete HTML document as string
        """
        # Generate table of contents
        toc_html = self._generate_toc(sections)

        # Generate body content
        body_html = self._generate_body(sections)

        # Assemble complete HTML
        return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <title>{html.escape(metadata.get('title', 'Workshop'))}</title>
</head>
<body>
    {self._generate_cover_page(metadata)}
    {toc_html}
    {body_html}
</body>
</html>"""

    def _generate_cover_page(self, metadata: dict[str, str]) -> str:
        """Generate cover page HTML."""
        title = metadata.get("title", "Workshop")
        subtitle = metadata.get("subtitle", "Guide")

        return f"""<div class="cover-page">
    <h1>{html.escape(title)}</h1>
    <p class="subtitle">{html.escape(subtitle)}</p>
</div>"""

    def _generate_toc(self, sections: list) -> str:
        """
        Generate table of contents with clickable links.

        Args:
            sections: List of ContentFile objects

        Returns:
            HTML for table of contents
        """
        toc_items = []

        for idx, section in enumerate(sections):
            section_id = f"section-{idx}"

            # Determine class based on level
            if section.level == 0 or section.level == 1:
                css_class = "toc-chapter"
            else:
                css_class = "toc-section"

            # Create TOC entry
            title_escaped = html.escape(section.title)
            toc_items.append(
                f'<li class="{css_class}"><a href="#{section_id}">{title_escaped}</a></li>'
            )

        toc_list = "\n".join(toc_items)

        return f"""<div class="toc">
    <h2>Table of Contents</h2>
    <ul>
        {toc_list}
    </ul>
</div>"""

    def _generate_body(self, sections: list) -> str:
        """
        Generate body content from sections.

        Args:
            sections: List of ContentFile objects

        Returns:
            HTML for main content
        """
        body_parts = []

        for idx, section in enumerate(sections):
            section_id = f"section-{idx}"

            # Determine class based on level
            css_class = "chapter" if section.level == 1 else "section"

            # Convert markdown to HTML
            html_content = self.md.convert(section.content)

            # Reset markdown processor for next section
            self.md.reset()

            # Add section header
            title_escaped = html.escape(section.title)

            if section.level == 0:
                # Root section (main index) - no special header
                body_parts.append(
                    f"""<div id="{section_id}" class="section">
    {html_content}
</div>"""
                )
            elif section.level == 1:
                # Chapter
                body_parts.append(
                    f"""<div id="{section_id}" class="{css_class}">
    <h1>{title_escaped}</h1>
    {html_content}
</div>"""
                )
            else:
                # Section
                body_parts.append(
                    f"""<div id="{section_id}" class="{css_class}">
    <h2>{title_escaped}</h2>
    {html_content}
</div>"""
                )

        return "\n".join(body_parts)

    def _write_pdf(self, html_content: str, output_path: Path) -> None:
        """
        Convert HTML to PDF using WeasyPrint.

        Args:
            html_content: Complete HTML document
            output_path: Path where PDF should be written
        """
        from weasyprint import CSS, HTML

        # Create HTML object with base URL for resolving relative paths
        html_obj = HTML(string=html_content, base_url=str(self.base_path))

        # Load CSS
        css_obj = CSS(filename=str(self.css_path))

        # Generate PDF
        html_obj.write_pdf(str(output_path), stylesheets=[css_obj])
