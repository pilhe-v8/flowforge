"""Unit tests for PDF parser — no HTTP calls needed."""

import io
import pytest
from unittest.mock import patch, MagicMock


def test_extract_text_from_pdf_bytes_returns_dict():
    """extract_text_from_pdf_bytes should return dict with text, pages, chars, source_url."""
    fake_pdf_bytes = b"%PDF-1.4 fake pdf content"
    fake_source_url = "https://example.com/test.pdf"

    mock_page1 = MagicMock()
    mock_page1.extract_text.return_value = "Hello world"
    mock_page2 = MagicMock()
    mock_page2.extract_text.return_value = "Second page"

    mock_pdf = MagicMock()
    mock_pdf.pages = [mock_page1, mock_page2]
    mock_pdf.__enter__ = lambda s: mock_pdf
    mock_pdf.__exit__ = MagicMock(return_value=False)

    with patch("pdfplumber.open", return_value=mock_pdf):
        from main import extract_text_from_pdf_bytes

        result = extract_text_from_pdf_bytes(fake_pdf_bytes, fake_source_url)

    assert result["pages"] == 2
    assert "Hello world" in result["text"]
    assert "Second page" in result["text"]
    assert result["chars"] == len(result["text"])
    assert result["source_url"] == fake_source_url


def test_extract_text_handles_none_pages():
    """Pages returning None from extract_text should be treated as empty string."""
    mock_page = MagicMock()
    mock_page.extract_text.return_value = None

    mock_pdf = MagicMock()
    mock_pdf.pages = [mock_page]
    mock_pdf.__enter__ = lambda s: mock_pdf
    mock_pdf.__exit__ = MagicMock(return_value=False)

    with patch("pdfplumber.open", return_value=mock_pdf):
        from main import extract_text_from_pdf_bytes

        result = extract_text_from_pdf_bytes(b"fake", "https://example.com/empty.pdf")

    assert result["text"] == ""
    assert result["pages"] == 1
    assert result["chars"] == 0
