# Workshop PDF Generator

Generates a professional PDF from all workshop markdown content in `./content/`, including images and mermaid diagrams.

## Features

- ✅ Converts all 45 markdown files to a single comprehensive PDF
- ✅ Handles Workshop Studio custom syntax (`:image[]`, `::alert[]`, etc.)
- ✅ Renders mermaid diagrams as PNG images using Playwright
- ✅ Generates clickable table of contents
- ✅ Professional AWS-themed styling
- ✅ Embeds all 24 workshop images
- ✅ Syntax highlighting for code blocks
- ✅ Page numbers and proper pagination

## Installation

### 1. Install Python Dependencies

```bash
pip install -r requirements-pdf.txt
```

### 2. Install Playwright Browser (for Mermaid Rendering)

```bash
playwright install chromium
```

## Usage

### Basic Usage

Generate PDF with default settings:

```bash
python scripts/generate-pdf.py
```

This creates `output/workshop.pdf`.

### Custom Output Path

Specify a custom output location:

```bash
python scripts/generate-pdf.py --output ~/Desktop/my-workshop.pdf
```

### Skip Mermaid Rendering (Faster)

For testing or environments without Playwright:

```bash
python scripts/generate-pdf.py --skip-mermaid
```

This uses text placeholders for mermaid diagrams instead of rendering them.

### Verbose Output

See detailed processing information:

```bash
python scripts/generate-pdf.py --verbose
```

## Output

The generated PDF includes:

- **Cover page** with workshop title
- **Table of contents** with clickable links to all chapters and sections
- **All chapters** in order (Prologue through Epilogue)
- **All images** embedded and properly sized
- **Mermaid diagrams** rendered as PNG images
- **Professional formatting** with AWS branding

Typical output size: ~100+ pages, 10-15 MB

## Architecture

### Components

1. **ContentCollector** (`content_collector.py`)
   - Discovers all markdown files in `./content/`
   - Parses frontmatter (title, weight)
   - Orders files by directory prefix and weight

2. **SyntaxConverter** (`syntax_converter.py`)
   - Converts Workshop Studio custom syntax to HTML
   - Handles: `:image[]`, `::alert[]`, `:::alert{}`, `::code[]`

3. **MermaidRenderer** (`mermaid_renderer.py`)
   - Uses Playwright to render mermaid diagrams
   - Generates PNG images from mermaid code blocks
   - Falls back to text placeholders if rendering fails

4. **PDFBuilder** (`pdf_builder.py`)
   - Converts markdown to HTML using Python-Markdown
   - Generates table of contents with links
   - Creates cover page
   - Uses WeasyPrint to generate PDF with CSS styling

5. **Main Script** (`scripts/generate-pdf.py`)
   - Orchestrates all components
   - Provides CLI interface
   - Handles errors and progress reporting

### Custom Syntax Conversions

| Workshop Studio Syntax | Converted to |
|------------------------|--------------|
| `:image[Alt]{src="/static/img/x.png" width=800}` | HTML `<figure>` with styled image |
| `::alert[Content]{header="Title"}` | HTML `<div class="alert alert-info">` |
| `:::alert{type="success"}\nContent\n:::` | HTML alert box with styling |
| `::code[command]{showCopyAction=true}` | HTML `<pre class="code-snippet">` |
| <code>```mermaid</code> | Rendered PNG image |

## Troubleshooting

### "playwright not found"

Install Playwright:
```bash
pip install playwright
playwright install chromium
```

Or use `--skip-mermaid` flag to skip diagram rendering.

### "weasyprint failed"

WeasyPrint requires system libraries. On macOS:
```bash
brew install cairo pango gdk-pixbuf libffi
```

On Ubuntu/Debian:
```bash
sudo apt-get install python3-cffi python3-brotli libpango-1.0-0 libpangoft2-1.0-0
```

### Images not appearing

Ensure images exist in `./static/img/` and paths in markdown are correct (`/static/img/filename.png`).

### PDF too large

Images are embedded at their original size. To reduce file size, compress images before generation.

## Development

### Adding New Syntax Patterns

Edit `lib/pdf_generator/syntax_converter.py` and add a new conversion method.

### Customizing Styling

Edit `lib/pdf_generator/styles/workshop.css` to change colors, fonts, spacing, etc.

### Testing Individual Components

```python
from pathlib import Path
from pdf_generator import ContentCollector

collector = ContentCollector(Path('./content'), Path('./static'))
files = collector.collect_files()
print(f"Found {len(files)} files")
```

## License

Part of the workshop materials. See main repository for license information.
