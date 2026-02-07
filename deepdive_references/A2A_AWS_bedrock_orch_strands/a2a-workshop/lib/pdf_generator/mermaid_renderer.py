"""
Mermaid Renderer

Renders mermaid diagrams to PNG images using Playwright.
"""

import asyncio
from pathlib import Path
import re


class MermaidRenderer:
    """Renders mermaid diagrams using headless browser."""

    def __init__(self, output_dir: Path, skip: bool = False):
        """
        Initialize mermaid renderer.

        Args:
            output_dir: Directory to save rendered images
            skip: If True, use placeholders instead of rendering
        """
        self.output_dir = Path(output_dir)
        self.skip = skip
        self.diagram_count = 0
        self.output_dir.mkdir(parents=True, exist_ok=True)

    async def render_diagrams(self, content: str) -> str:
        """
        Find all mermaid code blocks and render them to PNG.

        Args:
            content: Markdown content with mermaid blocks

        Returns:
            Content with mermaid blocks replaced by image tags
        """
        if self.skip:
            return self._use_placeholders(content)

        pattern = r"```mermaid\n([\s\S]*?)```"
        matches = list(re.finditer(pattern, content))

        if not matches:
            return content

        try:
            from playwright.async_api import async_playwright

            async with async_playwright() as p:
                browser = await p.chromium.launch()
                page = await browser.new_page()

                for match in matches:
                    diagram_code = match.group(1).strip()
                    img_path = await self._render_single(page, diagram_code)

                    if img_path:
                        # Replace with img tag (relative path)
                        img_tag = f'<img src="{img_path.name}" class="mermaid-diagram" alt="Mermaid Diagram"/>'
                        content = content.replace(match.group(0), img_tag)

                await browser.close()

        except ImportError:
            print(
                "Warning: Playwright not available, using placeholders for mermaid diagrams"
            )
            return self._use_placeholders(content)
        except Exception as e:
            print(f"Warning: Failed to render mermaid diagrams: {e}")
            return self._use_placeholders(content)

        return content

    async def _render_single(self, page, mermaid_code: str) -> Path | None:
        """
        Render a single mermaid diagram to PNG.

        Args:
            page: Playwright page instance
            mermaid_code: Mermaid diagram code

        Returns:
            Path to rendered PNG or None if failed
        """
        try:
            self.diagram_count += 1
            output_path = self.output_dir / f"mermaid_{self.diagram_count}.png"

            # Create HTML with mermaid
            html = f"""
            <!DOCTYPE html>
            <html>
            <head>
                <script src="https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.min.js"></script>
                <style>
                    body {{
                        margin: 0;
                        padding: 20px;
                        background: white;
                    }}
                </style>
            </head>
            <body>
                <div class="mermaid">
{mermaid_code}
                </div>
                <script>
                    mermaid.initialize({{ startOnLoad: true, theme: 'default' }});
                </script>
            </body>
            </html>
            """

            await page.set_content(html)
            await page.wait_for_selector(".mermaid svg", timeout=5000)

            # Give it a moment to fully render
            await asyncio.sleep(0.5)

            # Screenshot the diagram
            element = await page.query_selector(".mermaid")
            await element.screenshot(path=str(output_path))

            return output_path

        except Exception as e:
            print(f"Warning: Failed to render diagram {self.diagram_count}: {e}")
            return None

    def _use_placeholders(self, content: str) -> str:
        """
        Replace mermaid blocks with styled placeholders.

        Args:
            content: Markdown content with mermaid blocks

        Returns:
            Content with placeholders
        """
        pattern = r"```mermaid\n([\s\S]*?)```"

        def replace(match):
            mermaid_code = match.group(1).strip()
            escaped_code = mermaid_code.replace("<", "&lt;").replace(">", "&gt;")

            return f"""<div class="mermaid-fallback">
  <p><em>Diagram (mermaid syntax):</em></p>
  <pre><code>{escaped_code}</code></pre>
</div>"""

        return re.sub(pattern, replace, content)
