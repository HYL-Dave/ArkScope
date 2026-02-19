"""
File attachment support for multimodal agent input.

Handles PDF, image, and text files. Converts to provider-specific
content blocks for Anthropic (native PDF/image) and OpenAI (text extraction + images).

Usage:
    att = AttachmentManager.load("report.pdf", pages="1-5")
    blocks = AttachmentManager.to_anthropic_blocks([att])
"""

from __future__ import annotations

import base64
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import List, Tuple

logger = logging.getLogger(__name__)

# ── MIME type detection ───────────────────────────────────────

_MIME_MAP = {
    ".pdf": "application/pdf",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".gif": "image/gif",
    ".webp": "image/webp",
    ".txt": "text/plain",
    ".csv": "text/csv",
    ".md": "text/markdown",
    ".json": "application/json",
    ".py": "text/x-python",
    ".js": "text/javascript",
    ".ts": "text/typescript",
    ".yaml": "text/yaml",
    ".yml": "text/yaml",
    ".xml": "text/xml",
    ".html": "text/html",
    ".log": "text/plain",
}

_IMAGE_TYPES = {"image/png", "image/jpeg", "image/gif", "image/webp"}
_TEXT_TYPES = {
    "text/plain", "text/csv", "text/markdown", "text/x-python",
    "text/javascript", "text/typescript", "text/yaml", "text/xml",
    "text/html", "application/json",
}


def _detect_mime(path: str) -> str:
    """Detect MIME type from file extension."""
    ext = Path(path).suffix.lower()
    return _MIME_MAP.get(ext, "application/octet-stream")


# ── Attachment dataclass ──────────────────────────────────────

@dataclass
class Attachment:
    """A file attachment ready to send to an LLM provider."""
    path: str           # Original file path
    filename: str       # Display name
    media_type: str     # MIME type
    data: bytes         # Raw file bytes (PDF trimmed to specified pages)
    pages: str = ""     # Page range spec (e.g. "1-5", "3", "")

    @property
    def is_pdf(self) -> bool:
        return self.media_type == "application/pdf"

    @property
    def is_image(self) -> bool:
        return self.media_type in _IMAGE_TYPES

    @property
    def is_text(self) -> bool:
        return self.media_type in _TEXT_TYPES

    @property
    def size_kb(self) -> float:
        return len(self.data) / 1024


# ── PDF Processor (PyMuPDF) ───────────────────────────────────

class PDFProcessor:
    """Static methods for PDF operations using PyMuPDF (fitz)."""

    @staticmethod
    def parse_page_range(spec: str, total: int) -> List[int]:
        """Parse page range spec to 0-indexed page numbers.

        Supports: "1-5", "3", "1-3,8", "1,3,5-7"
        Input is 1-indexed, output is 0-indexed.

        Args:
            spec: Page range string (1-indexed)
            total: Total number of pages in the document

        Returns:
            Sorted list of 0-indexed page numbers
        """
        if not spec or not spec.strip():
            return list(range(total))

        pages = set()
        for part in spec.split(","):
            part = part.strip()
            if "-" in part:
                start_s, end_s = part.split("-", 1)
                start = max(1, int(start_s.strip()))
                end = min(total, int(end_s.strip()))
                for p in range(start, end + 1):
                    pages.add(p - 1)  # Convert to 0-indexed
            else:
                p = int(part.strip())
                if 1 <= p <= total:
                    pages.add(p - 1)

        return sorted(pages)

    @staticmethod
    def page_count(pdf_bytes: bytes) -> int:
        """Return the number of pages in a PDF."""
        import fitz
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        count = len(doc)
        doc.close()
        return count

    @staticmethod
    def extract_pages(pdf_bytes: bytes, pages: str) -> bytes:
        """Extract specific pages from a PDF, returning new PDF bytes.

        Args:
            pdf_bytes: Original PDF bytes
            pages: Page range spec (1-indexed, e.g. "1-5")

        Returns:
            New PDF bytes containing only the specified pages
        """
        import fitz
        src = fitz.open(stream=pdf_bytes, filetype="pdf")
        total = len(src)
        page_nums = PDFProcessor.parse_page_range(pages, total)

        if len(page_nums) == total:
            # All pages — return original
            result = pdf_bytes
        else:
            dst = fitz.open()
            dst.insert_pdf(src, from_page=0, to_page=0)  # placeholder
            dst.delete_page(0)  # remove placeholder
            for pn in page_nums:
                dst.insert_pdf(src, from_page=pn, to_page=pn)
            result = dst.tobytes()
            dst.close()

        src.close()
        return result

    @staticmethod
    def extract_text(pdf_bytes: bytes, pages: str = "") -> str:
        """Extract text content from PDF pages.

        Args:
            pdf_bytes: PDF bytes
            pages: Page range spec (empty = all pages)

        Returns:
            Extracted text with page separators
        """
        import fitz
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        total = len(doc)
        page_nums = PDFProcessor.parse_page_range(pages, total)

        text_parts = []
        for pn in page_nums:
            page = doc[pn]
            text = page.get_text()
            if text.strip():
                text_parts.append(f"--- Page {pn + 1} ---\n{text.strip()}")

        doc.close()
        return "\n\n".join(text_parts)

    @staticmethod
    def page_to_images(
        pdf_bytes: bytes, pages: str = "", dpi: int = 150
    ) -> List[Tuple[bytes, str]]:
        """Convert PDF pages to PNG images.

        Args:
            pdf_bytes: PDF bytes
            pages: Page range spec (empty = all pages)
            dpi: Resolution for rendering (default 150)

        Returns:
            List of (png_bytes, "page_N.png") tuples
        """
        import fitz
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        total = len(doc)
        page_nums = PDFProcessor.parse_page_range(pages, total)

        images = []
        zoom = dpi / 72.0
        mat = fitz.Matrix(zoom, zoom)

        for pn in page_nums:
            page = doc[pn]
            pix = page.get_pixmap(matrix=mat)
            png_bytes = pix.tobytes("png")
            images.append((png_bytes, f"page_{pn + 1}.png"))

        doc.close()
        return images


# ── Attachment Manager ────────────────────────────────────────

class AttachmentManager:
    """Load files and convert to provider-specific content blocks."""

    @staticmethod
    def load(path: str, pages: str = "") -> Attachment:
        """Load a file and create an Attachment.

        For PDFs with a page range, trims to the specified pages.

        Args:
            path: File path (absolute or relative)
            pages: Page range for PDFs (e.g. "1-5", empty = all)

        Returns:
            Attachment ready for conversion to provider blocks

        Raises:
            FileNotFoundError: If file doesn't exist
            ValueError: If file type is unsupported or too large
        """
        p = Path(path).expanduser().resolve()
        if not p.exists():
            raise FileNotFoundError(f"File not found: {path}")

        media_type = _detect_mime(str(p))
        raw_data = p.read_bytes()

        # For PDF with page range, extract only those pages
        if media_type == "application/pdf" and pages:
            data = PDFProcessor.extract_pages(raw_data, pages)
        else:
            data = raw_data

        # Validate size (Anthropic limit: 32MB for PDFs, 20MB for images)
        size_mb = len(data) / (1024 * 1024)
        if media_type == "application/pdf" and size_mb > 32:
            raise ValueError(f"PDF too large: {size_mb:.1f} MB (max 32 MB)")
        if media_type in _IMAGE_TYPES and size_mb > 20:
            raise ValueError(f"Image too large: {size_mb:.1f} MB (max 20 MB)")

        return Attachment(
            path=str(p),
            filename=p.name,
            media_type=media_type,
            data=data,
            pages=pages,
        )

    @staticmethod
    def to_anthropic_blocks(attachments: List[Attachment]) -> List[dict]:
        """Convert attachments to Anthropic content blocks.

        - PDF -> {"type": "document", "source": {"type": "base64", ...}}
        - Image -> {"type": "image", "source": {"type": "base64", ...}}
        - Text -> {"type": "text", "text": "[File: name]\\ncontent"}
        """
        blocks = []
        for att in attachments:
            if att.is_pdf:
                blocks.append({
                    "type": "document",
                    "source": {
                        "type": "base64",
                        "media_type": "application/pdf",
                        "data": base64.standard_b64encode(att.data).decode("ascii"),
                    },
                })
            elif att.is_image:
                blocks.append({
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": att.media_type,
                        "data": base64.standard_b64encode(att.data).decode("ascii"),
                    },
                })
            elif att.is_text:
                try:
                    text_content = att.data.decode("utf-8")
                except UnicodeDecodeError:
                    text_content = att.data.decode("utf-8", errors="replace")
                blocks.append({
                    "type": "text",
                    "text": f"[File: {att.filename}]\n{text_content}",
                })
            else:
                # Unsupported type — try text extraction
                try:
                    text_content = att.data.decode("utf-8")
                    blocks.append({
                        "type": "text",
                        "text": f"[File: {att.filename}]\n{text_content}",
                    })
                except UnicodeDecodeError:
                    logger.warning(
                        f"Skipping unsupported binary file: {att.filename}"
                    )
        return blocks

    @staticmethod
    def to_openai_blocks(attachments: List[Attachment]) -> List[dict]:
        """Convert attachments to OpenAI Agents SDK content blocks.

        - Image -> {"type": "input_image", "image_url": "data:...;base64,..."}
        - PDF -> text extraction -> {"type": "input_text", "text": ...}
        - Text -> {"type": "input_text", "text": "[File: name]\\ncontent"}
        """
        blocks = []
        for att in attachments:
            if att.is_image:
                b64 = base64.standard_b64encode(att.data).decode("ascii")
                blocks.append({
                    "type": "input_image",
                    "image_url": f"data:{att.media_type};base64,{b64}",
                })
            elif att.is_pdf:
                # OpenAI doesn't support native PDF — extract text
                text = PDFProcessor.extract_text(att.data, pages="")
                blocks.append({
                    "type": "input_text",
                    "text": f"[PDF: {att.filename}]\n{text}",
                })
            elif att.is_text:
                try:
                    text_content = att.data.decode("utf-8")
                except UnicodeDecodeError:
                    text_content = att.data.decode("utf-8", errors="replace")
                blocks.append({
                    "type": "input_text",
                    "text": f"[File: {att.filename}]\n{text_content}",
                })
            else:
                try:
                    text_content = att.data.decode("utf-8")
                    blocks.append({
                        "type": "input_text",
                        "text": f"[File: {att.filename}]\n{text_content}",
                    })
                except UnicodeDecodeError:
                    logger.warning(
                        f"Skipping unsupported binary file: {att.filename}"
                    )
        return blocks
