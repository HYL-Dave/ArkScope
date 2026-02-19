"""Tests for file attachment support (Phase D).

Tests PDFProcessor, AttachmentManager, and Attachment dataclass.
Uses dynamically-created PDF fixtures via PyMuPDF.
"""

import base64
import os
import tempfile

import pytest

from src.agents.shared.attachments import (
    Attachment,
    AttachmentManager,
    PDFProcessor,
    _detect_mime,
)


# ── Fixtures ──────────────────────────────────────────────────


@pytest.fixture
def sample_pdf_bytes():
    """Create a simple 3-page PDF for testing."""
    import fitz

    doc = fitz.open()
    for i in range(3):
        page = doc.new_page()
        page.insert_text((50, 50), f"Page {i + 1} content")
    pdf_bytes = doc.tobytes()
    doc.close()
    return pdf_bytes


@pytest.fixture
def sample_pdf_file(sample_pdf_bytes):
    """Write sample PDF to a temp file."""
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
        f.write(sample_pdf_bytes)
        path = f.name
    yield path
    os.unlink(path)


@pytest.fixture
def sample_image_bytes():
    """Create a minimal PNG image (1x1 red pixel)."""
    # Minimal valid PNG
    import struct
    import zlib

    def _make_png():
        signature = b"\x89PNG\r\n\x1a\n"

        # IHDR
        ihdr_data = struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0)
        ihdr_crc = zlib.crc32(b"IHDR" + ihdr_data) & 0xFFFFFFFF
        ihdr = struct.pack(">I", 13) + b"IHDR" + ihdr_data + struct.pack(">I", ihdr_crc)

        # IDAT (1x1 RGB red pixel)
        raw_data = b"\x00\xff\x00\x00"  # filter byte + RGB
        compressed = zlib.compress(raw_data)
        idat_crc = zlib.crc32(b"IDAT" + compressed) & 0xFFFFFFFF
        idat = struct.pack(">I", len(compressed)) + b"IDAT" + compressed + struct.pack(">I", idat_crc)

        # IEND
        iend_crc = zlib.crc32(b"IEND") & 0xFFFFFFFF
        iend = struct.pack(">I", 0) + b"IEND" + struct.pack(">I", iend_crc)

        return signature + ihdr + idat + iend

    return _make_png()


@pytest.fixture
def sample_image_file(sample_image_bytes):
    """Write sample PNG to a temp file."""
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
        f.write(sample_image_bytes)
        path = f.name
    yield path
    os.unlink(path)


@pytest.fixture
def sample_text_file():
    """Write sample text to a temp file."""
    with tempfile.NamedTemporaryFile(suffix=".txt", delete=False, mode="w") as f:
        f.write("Hello, this is a test file.\nLine 2.")
        path = f.name
    yield path
    os.unlink(path)


# ── MIME Detection ────────────────────────────────────────────


class TestMimeDetection:
    def test_pdf(self):
        assert _detect_mime("report.pdf") == "application/pdf"

    def test_png(self):
        assert _detect_mime("chart.png") == "image/png"

    def test_jpg(self):
        assert _detect_mime("photo.jpg") == "image/jpeg"

    def test_jpeg(self):
        assert _detect_mime("photo.jpeg") == "image/jpeg"

    def test_txt(self):
        assert _detect_mime("notes.txt") == "text/plain"

    def test_csv(self):
        assert _detect_mime("data.csv") == "text/csv"

    def test_md(self):
        assert _detect_mime("README.md") == "text/markdown"

    def test_json(self):
        assert _detect_mime("config.json") == "application/json"

    def test_python(self):
        assert _detect_mime("script.py") == "text/x-python"

    def test_unknown(self):
        assert _detect_mime("file.xyz") == "application/octet-stream"


# ── Attachment Dataclass ──────────────────────────────────────


class TestAttachment:
    def test_is_pdf(self):
        att = Attachment(
            path="/tmp/test.pdf", filename="test.pdf",
            media_type="application/pdf", data=b"fake",
        )
        assert att.is_pdf
        assert not att.is_image
        assert not att.is_text

    def test_is_image(self):
        att = Attachment(
            path="/tmp/test.png", filename="test.png",
            media_type="image/png", data=b"fake",
        )
        assert att.is_image
        assert not att.is_pdf
        assert not att.is_text

    def test_is_text(self):
        att = Attachment(
            path="/tmp/test.txt", filename="test.txt",
            media_type="text/plain", data=b"hello",
        )
        assert att.is_text
        assert not att.is_pdf
        assert not att.is_image

    def test_size_kb(self):
        att = Attachment(
            path="/tmp/test.txt", filename="test.txt",
            media_type="text/plain", data=b"x" * 2048,
        )
        assert att.size_kb == 2.0


# ── PDFProcessor ──────────────────────────────────────────────


class TestPDFProcessor:
    def test_parse_page_range_empty(self):
        result = PDFProcessor.parse_page_range("", 5)
        assert result == [0, 1, 2, 3, 4]

    def test_parse_page_range_single(self):
        result = PDFProcessor.parse_page_range("2", 5)
        assert result == [1]  # 0-indexed

    def test_parse_page_range_range(self):
        result = PDFProcessor.parse_page_range("1-3", 5)
        assert result == [0, 1, 2]

    def test_parse_page_range_mixed(self):
        result = PDFProcessor.parse_page_range("1-2,5", 5)
        assert result == [0, 1, 4]

    def test_parse_page_range_out_of_bounds(self):
        result = PDFProcessor.parse_page_range("1-10", 3)
        assert result == [0, 1, 2]

    def test_parse_page_range_complex(self):
        result = PDFProcessor.parse_page_range("1,3,5-7", 10)
        assert result == [0, 2, 4, 5, 6]

    def test_page_count(self, sample_pdf_bytes):
        assert PDFProcessor.page_count(sample_pdf_bytes) == 3

    def test_extract_text(self, sample_pdf_bytes):
        text = PDFProcessor.extract_text(sample_pdf_bytes)
        assert "Page 1 content" in text
        assert "Page 2 content" in text
        assert "Page 3 content" in text

    def test_extract_text_specific_pages(self, sample_pdf_bytes):
        text = PDFProcessor.extract_text(sample_pdf_bytes, pages="1-2")
        assert "Page 1 content" in text
        assert "Page 2 content" in text
        assert "Page 3 content" not in text

    def test_extract_pages(self, sample_pdf_bytes):
        trimmed = PDFProcessor.extract_pages(sample_pdf_bytes, "1-2")
        assert PDFProcessor.page_count(trimmed) == 2
        text = PDFProcessor.extract_text(trimmed)
        assert "Page 1 content" in text
        assert "Page 3 content" not in text

    def test_extract_pages_all(self, sample_pdf_bytes):
        """Extracting all pages returns original bytes."""
        trimmed = PDFProcessor.extract_pages(sample_pdf_bytes, "1-3")
        assert trimmed == sample_pdf_bytes

    def test_page_to_images(self, sample_pdf_bytes):
        images = PDFProcessor.page_to_images(sample_pdf_bytes, pages="1")
        assert len(images) == 1
        png_bytes, name = images[0]
        assert name == "page_1.png"
        assert png_bytes[:4] == b"\x89PNG"

    def test_page_to_images_all(self, sample_pdf_bytes):
        images = PDFProcessor.page_to_images(sample_pdf_bytes)
        assert len(images) == 3


# ── AttachmentManager ─────────────────────────────────────────


class TestAttachmentManagerLoad:
    def test_load_pdf(self, sample_pdf_file):
        att = AttachmentManager.load(sample_pdf_file)
        assert att.is_pdf
        assert att.filename.endswith(".pdf")
        assert att.media_type == "application/pdf"
        assert att.pages == ""

    def test_load_pdf_with_pages(self, sample_pdf_file):
        att = AttachmentManager.load(sample_pdf_file, pages="1-2")
        assert att.is_pdf
        assert att.pages == "1-2"
        # Trimmed PDF should have 2 pages
        assert PDFProcessor.page_count(att.data) == 2

    def test_load_image(self, sample_image_file):
        att = AttachmentManager.load(sample_image_file)
        assert att.is_image
        assert att.media_type == "image/png"

    def test_load_text(self, sample_text_file):
        att = AttachmentManager.load(sample_text_file)
        assert att.is_text
        assert att.media_type == "text/plain"
        assert b"Hello" in att.data

    def test_load_nonexistent(self):
        with pytest.raises(FileNotFoundError):
            AttachmentManager.load("/tmp/nonexistent_12345.pdf")


class TestAttachmentManagerAnthropicBlocks:
    def test_pdf_block(self, sample_pdf_file):
        att = AttachmentManager.load(sample_pdf_file)
        blocks = AttachmentManager.to_anthropic_blocks([att])
        assert len(blocks) == 1
        block = blocks[0]
        assert block["type"] == "document"
        assert block["source"]["type"] == "base64"
        assert block["source"]["media_type"] == "application/pdf"
        # Verify base64 is valid
        decoded = base64.b64decode(block["source"]["data"])
        assert decoded[:4] == b"%PDF"

    def test_image_block(self, sample_image_file):
        att = AttachmentManager.load(sample_image_file)
        blocks = AttachmentManager.to_anthropic_blocks([att])
        assert len(blocks) == 1
        block = blocks[0]
        assert block["type"] == "image"
        assert block["source"]["type"] == "base64"
        assert block["source"]["media_type"] == "image/png"

    def test_text_block(self, sample_text_file):
        att = AttachmentManager.load(sample_text_file)
        blocks = AttachmentManager.to_anthropic_blocks([att])
        assert len(blocks) == 1
        block = blocks[0]
        assert block["type"] == "text"
        assert "[File:" in block["text"]
        assert "Hello" in block["text"]

    def test_multiple_attachments(self, sample_pdf_file, sample_text_file):
        atts = [
            AttachmentManager.load(sample_pdf_file),
            AttachmentManager.load(sample_text_file),
        ]
        blocks = AttachmentManager.to_anthropic_blocks(atts)
        assert len(blocks) == 2
        assert blocks[0]["type"] == "document"
        assert blocks[1]["type"] == "text"


class TestAttachmentManagerOpenAIBlocks:
    def test_image_block(self, sample_image_file):
        att = AttachmentManager.load(sample_image_file)
        blocks = AttachmentManager.to_openai_blocks([att])
        assert len(blocks) == 1
        block = blocks[0]
        assert block["type"] == "input_image"
        assert block["image_url"].startswith("data:image/png;base64,")

    def test_pdf_block_text_extraction(self, sample_pdf_file):
        att = AttachmentManager.load(sample_pdf_file)
        blocks = AttachmentManager.to_openai_blocks([att])
        assert len(blocks) == 1
        block = blocks[0]
        assert block["type"] == "input_text"
        assert "[PDF:" in block["text"]
        assert "Page 1 content" in block["text"]

    def test_text_block(self, sample_text_file):
        att = AttachmentManager.load(sample_text_file)
        blocks = AttachmentManager.to_openai_blocks([att])
        assert len(blocks) == 1
        block = blocks[0]
        assert block["type"] == "input_text"
        assert "[File:" in block["text"]
        assert "Hello" in block["text"]

    def test_multiple_attachments(self, sample_image_file, sample_text_file):
        atts = [
            AttachmentManager.load(sample_image_file),
            AttachmentManager.load(sample_text_file),
        ]
        blocks = AttachmentManager.to_openai_blocks(atts)
        assert len(blocks) == 2
        assert blocks[0]["type"] == "input_image"
        assert blocks[1]["type"] == "input_text"
