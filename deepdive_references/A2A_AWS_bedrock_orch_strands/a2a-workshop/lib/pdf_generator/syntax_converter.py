"""
Syntax Converter

Converts Workshop Studio custom syntax to HTML for PDF generation.
"""

import html
from pathlib import Path
import re


class SyntaxConverter:
    """Converts Workshop Studio custom syntax to PDF-compatible HTML."""

    def __init__(self, static_dir: Path):
        """
        Initialize syntax converter.

        Args:
            static_dir: Path to static/ directory for image resolution
        """
        self.static_dir = Path(static_dir)

    def convert(self, content: str) -> str:
        """
        Apply all syntax conversions.

        Args:
            content: Markdown content with custom syntax

        Returns:
            Content with custom syntax converted to HTML
        """
        # Apply conversions in order
        # Note: Order matters! Process block directives before inline ones
        content = self._convert_block_code_directives(content)
        content = self._convert_block_alerts(content)
        content = self._convert_images(content)
        content = self._convert_inline_alerts(content)
        content = self._convert_inline_code_directives(content)

        return content

    def _convert_images(self, content: str) -> str:
        """
        Convert image directives to HTML figures.

        :image[Alt Text]{src="/static/img/file.png" width=800}
        ->
        <figure>
          <img src="./static/img/file.png" alt="Alt Text" style="max-width: 800px;"/>
          <figcaption>Alt Text</figcaption>
        </figure>
        """
        pattern = r":image\[([^\]]*)\]\{([^}]*)\}"

        def replace(match):
            alt_text = match.group(1)
            params = match.group(2)

            # Parse parameters
            src_match = re.search(r'src="([^"]+)"', params)
            width_match = re.search(r"width=(\d+)", params)

            if not src_match:
                return match.group(0)  # Return original if no src

            src = src_match.group(1)
            width = width_match.group(1) if width_match else "800"

            # Convert /static/ to relative path
            if src.startswith("/static/"):
                src = "." + src

            return f"""<figure class="image-figure">
  <img src="{src}" alt="{html.escape(alt_text)}" style="max-width: {width}px; width: 100%;"/>
  <figcaption>{html.escape(alt_text)}</figcaption>
</figure>"""

        return re.sub(pattern, replace, content)

    def _convert_inline_alerts(self, content: str) -> str:
        """
        Convert inline alert directives to HTML.

        ::alert[Content]
        ::alert[Content]{header="Title"}
        ->
        <div class="alert alert-info">
          <div class="alert-header">Title</div>
          <div class="alert-content">Content</div>
        </div>
        """
        pattern = r"::alert\[([^\]]+)\](?:\{([^}]*)\})?"

        def replace(match):
            content_text = match.group(1)
            params = match.group(2) or ""

            # Parse header
            header_match = re.search(r'header="([^"]*)"', params)
            header = header_match.group(1) if header_match else ""

            # Parse type (default to info)
            type_match = re.search(r'type="([^"]*)"', params)
            alert_type = type_match.group(1) if type_match else "info"

            html_parts = [f'<div class="alert alert-{alert_type}">']

            if header:
                html_parts.append(
                    f'  <div class="alert-header">{html.escape(header)}</div>'
                )

            html_parts.append(
                f'  <div class="alert-content">{html.escape(content_text)}</div>'
            )
            html_parts.append("</div>")

            return "\n".join(html_parts)

        return re.sub(pattern, replace, content)

    def _convert_block_alerts(self, content: str) -> str:
        """
        Convert block alert directives to HTML.

        :::alert{type="success" header="Title"}
        Content here
        :::

        ::::alert{type="info" header="Title"}
        Content here
        ::::
        ->
        <div class="alert alert-success">
          <div class="alert-header">Title</div>
          <div class="alert-content">Content here</div>
        </div>
        """
        # Handle both ::: and :::: variants (closing is always :::)
        pattern = r":{3,4}alert(?:\{([^}]*)\})?\n([\s\S]*?):{3}"

        def replace(match):
            params = match.group(1) or ""
            content_text = match.group(2).strip()

            # Parse parameters
            type_match = re.search(r'type="([^"]*)"', params)
            header_match = re.search(r'header="([^"]*)"', params)

            alert_type = type_match.group(1) if type_match else "info"
            header = header_match.group(1) if header_match else ""

            html_parts = [f'<div class="alert alert-{alert_type}">']

            if header:
                html_parts.append(
                    f'  <div class="alert-header">{html.escape(header)}</div>'
                )

            html_parts.append(
                f'  <div class="alert-content">{html.escape(content_text)}</div>'
            )
            html_parts.append("</div>")

            return "\n".join(html_parts)

        return re.sub(pattern, replace, content)

    def _convert_inline_code_directives(self, content: str) -> str:
        """
        Convert inline code directives to styled HTML.

        ::code[command text]{showCopyAction=true}
        ->
        <pre class="code-snippet"><code>command text</code></pre>
        """
        pattern = r"::code\[([^\]]+)\](?:\{([^}]*)\})?"

        def replace(match):
            code_text = match.group(1)
            params = match.group(2) or ""

            # Parse language if present
            lang_match = re.search(r"language=(\w+)", params)
            language = lang_match.group(1) if lang_match else "text"

            return f'<pre class="code-snippet"><code class="language-{language}">{html.escape(code_text)}</code></pre>'

        return re.sub(pattern, replace, content)

    def _convert_block_code_directives(self, content: str) -> str:
        """
        Convert block code directives to standard fenced code blocks.

        :::code{language=yaml showCopyAction=false}
        content here
        :::
        ->
        ```yaml
        content here
        ```
        """
        pattern = r":::code(?:\{([^}]*)\})?\n([\s\S]*?):::"

        def replace(match):
            params = match.group(1) or ""
            code_text = match.group(2).rstrip()

            # Parse language
            lang_match = re.search(r"language=(\w+)", params)
            language = lang_match.group(1) if lang_match else "text"

            # Convert to standard markdown code block
            return f"```{language}\n{code_text}\n```"

        return re.sub(pattern, replace, content)
