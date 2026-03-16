"""
FlowForge PDF Parser Microservice
Extracts text from PDFs given a URL. URL-based only (no file upload).
"""

import io
import httpx
import pdfplumber
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, HttpUrl

app = FastAPI(title="FlowForge PDF Parser", version="1.0.0")

MAX_BYTES = 20 * 1024 * 1024  # 20 MB
TIMEOUT_SECONDS = 30


class ParseRequest(BaseModel):
    url: HttpUrl


class ParseResponse(BaseModel):
    text: str
    pages: int
    chars: int
    source_url: str


def extract_text_from_pdf_bytes(pdf_bytes: bytes, source_url: str) -> dict:
    """Extract text from PDF bytes using pdfplumber."""
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        pages = pdf.pages
        text_parts = [page.extract_text() or "" for page in pages]
        full_text = "\n".join(text_parts)
        return {
            "text": full_text,
            "pages": len(pages),
            "chars": len(full_text),
            "source_url": source_url,
        }


@app.post("/parse", response_model=ParseResponse)
async def parse_pdf(request: ParseRequest):
    url = str(request.url)

    # Only allow http/https (pydantic HttpUrl already enforces this, but be explicit)
    if not url.startswith(("http://", "https://")):
        raise HTTPException(
            status_code=400, detail="Only http and https URLs are supported"
        )

    try:
        async with httpx.AsyncClient(
            timeout=TIMEOUT_SECONDS, follow_redirects=True
        ) as client:
            # HEAD request first to check Content-Length without downloading
            try:
                head = await client.head(url)
                content_length = int(head.headers.get("content-length", 0))
                if content_length > MAX_BYTES:
                    raise HTTPException(
                        status_code=413,
                        detail=f"File too large (>{MAX_BYTES // 1024 // 1024}MB)",
                    )
            except httpx.HTTPError:
                pass  # HEAD not supported — proceed with GET and check during download

            # Download the PDF
            response = await client.get(url)
            response.raise_for_status()

            content = response.content
            if len(content) > MAX_BYTES:
                raise HTTPException(
                    status_code=413,
                    detail=f"File too large (>{MAX_BYTES // 1024 // 1024}MB)",
                )

    except HTTPException:
        raise
    except httpx.HTTPError as e:
        raise HTTPException(status_code=502, detail=f"Failed to fetch PDF: {e}")

    try:
        result = extract_text_from_pdf_bytes(content, url)
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"Failed to parse PDF: {e}")

    return ParseResponse(**result)


@app.get("/health")
async def health():
    return {"status": "ok"}
