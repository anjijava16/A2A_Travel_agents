"""
Content Collector

Discovers and orders workshop markdown files by directory prefix and weight.
"""

from dataclasses import dataclass
from pathlib import Path
import re

import frontmatter


@dataclass
class ContentFile:
    """Represents a markdown content file with metadata."""

    path: Path
    title: str
    weight: int
    content: str
    level: int  # 0=root, 1=chapter, 2=section
    order_key: tuple[int, ...]  # For sorting


class ContentCollector:
    """Collects and orders workshop markdown content files."""

    def __init__(self, content_dir: Path, static_dir: Path):
        """
        Initialize content collector.

        Args:
            content_dir: Path to content/ directory
            static_dir: Path to static/ directory (for image resolution)
        """
        self.content_dir = Path(content_dir)
        self.static_dir = Path(static_dir)

    def collect_files(self) -> list[ContentFile]:
        """
        Discover all markdown files and return them in sorted order.

        Returns:
            List of ContentFile objects sorted by directory prefix and weight
        """
        files = []

        # Process root index.en.md first
        root_file = self.content_dir / "index.en.md"
        if root_file.exists():
            content_file = self._process_file(root_file, level=0)
            if content_file:
                files.append(content_file)

        # Process all subdirectories
        for item in sorted(self.content_dir.iterdir()):
            if item.is_dir():
                files.extend(self._process_directory(item))

        # Sort by order_key
        files.sort(key=lambda f: f.order_key)

        return files

    def _process_directory(self, dir_path: Path) -> list[ContentFile]:
        """
        Process a directory and its subdirectories.

        Args:
            dir_path: Path to directory (e.g., "20 - prologue")

        Returns:
            List of ContentFile objects from this directory
        """
        files = []
        dir_order = self._extract_numeric_prefix(dir_path.name)

        # Process chapter index.en.md
        index_file = dir_path / "index.en.md"
        if index_file.exists():
            content_file = self._process_file(index_file, level=1, dir_order=dir_order)
            if content_file:
                files.append(content_file)

        # Process subdirectories (sections)
        for item in sorted(dir_path.iterdir()):
            if item.is_dir():
                section_file = item / "index.en.md"
                if section_file.exists():
                    section_order = self._extract_numeric_prefix(item.name)
                    content_file = self._process_file(
                        section_file,
                        level=2,
                        dir_order=dir_order,
                        section_order=section_order,
                    )
                    if content_file:
                        files.append(content_file)

        return files

    def _process_file(
        self, file_path: Path, level: int, dir_order: int = 0, section_order: int = 0
    ) -> ContentFile:
        """
        Read and parse a markdown file.

        Args:
            file_path: Path to markdown file
            level: Nesting level (0=root, 1=chapter, 2=section)
            dir_order: Directory numeric prefix
            section_order: Section numeric prefix

        Returns:
            ContentFile object or None if parsing fails
        """
        try:
            # Parse frontmatter and content
            with Path(file_path).open(encoding="utf-8") as f:
                post = frontmatter.load(f)

            title = post.get("title", file_path.parent.name)
            weight = post.get("weight", 0)
            content = post.content

            # Create ordering key: (dir_order, section_order, weight)
            if level == 0:
                order_key = (0, 0, 0)  # Root file first
            elif level == 1:
                order_key = (dir_order, 0, weight)
            else:  # level == 2
                order_key = (dir_order, section_order, weight)

            return ContentFile(
                path=file_path,
                title=title,
                weight=weight,
                content=content,
                level=level,
                order_key=order_key,
            )

        except Exception as e:
            print(f"Warning: Failed to process {file_path}: {e}")
            return None

    @staticmethod
    def _extract_numeric_prefix(name: str) -> int:
        """
        Extract numeric prefix from directory or file name.

        Examples:
            "20 - prologue" -> 20
            "10-access-environment" -> 10
            "chapter 1" -> 0 (no numeric prefix)

        Args:
            name: Directory or file name

        Returns:
            Numeric prefix or 0 if not found
        """
        match = re.match(r"^(\d+)", name)
        if match:
            return int(match.group(1))
        return 0
