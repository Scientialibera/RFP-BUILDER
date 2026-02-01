"""
PDF Service - Handles PDF reading, text extraction, and image conversion.
"""

import base64
import io
from pathlib import Path
from typing import Optional

import pdfplumber
from pypdf import PdfReader
from PIL import Image

from app.core.config import get_config


class PDFService:
    """Service for handling PDF operations."""
    
    def __init__(self):
        self.config = get_config()
    
    def extract_text(self, pdf_path: Path | str) -> str:
        """
        Extract text content from a PDF file.
        
        Args:
            pdf_path: Path to the PDF file.
            
        Returns:
            Extracted text content.
        """
        pdf_path = Path(pdf_path)
        reader = PdfReader(pdf_path)
        
        text_parts = []
        for page_num, page in enumerate(reader.pages, 1):
            page_text = page.extract_text()
            if page_text:
                text_parts.append(f"PAGE TO CITE: {page_num}\n{page_text}")
        
        return "\n\n".join(text_parts)
    
    def extract_text_from_bytes(self, pdf_bytes: bytes) -> str:
        """
        Extract text content from PDF bytes.
        
        Args:
            pdf_bytes: PDF file content as bytes.
            
        Returns:
            Extracted text content.
        """
        reader = PdfReader(io.BytesIO(pdf_bytes))
        
        text_parts = []
        for page_num, page in enumerate(reader.pages, 1):
            page_text = page.extract_text()
            if page_text:
                text_parts.append(f"PAGE TO CITE: {page_num}\n{page_text}")
        
        return "\n\n".join(text_parts)
    
    def convert_to_images(
        self, 
        pdf_path: Path | str, 
        dpi: Optional[int] = None
    ) -> list[Image.Image]:
        """
        Convert PDF pages to images.
        
        Args:
            pdf_path: Path to the PDF file.
            dpi: Resolution for conversion. Defaults to config value.
            
        Returns:
            List of PIL Image objects, one per page.
        """
        from pdf2image import convert_from_path
        
        pdf_path = Path(pdf_path)
        dpi = dpi or self.config.features.image_dpi
        
        images = convert_from_path(pdf_path, dpi=dpi)
        return images
    
    def convert_bytes_to_images(
        self, 
        pdf_bytes: bytes, 
        dpi: Optional[int] = None
    ) -> list[Image.Image]:
        """
        Convert PDF bytes to images.
        
        Args:
            pdf_bytes: PDF file content as bytes.
            dpi: Resolution for conversion. Defaults to config value.
            
        Returns:
            List of PIL Image objects, one per page.
        """
        from pdf2image import convert_from_bytes
        
        dpi = dpi or self.config.features.image_dpi
        images = convert_from_bytes(pdf_bytes, dpi=dpi)
        return images
    
    def images_to_base64(self, images: list[Image.Image], format: str = "PNG") -> list[str]:
        """
        Convert PIL images to base64 encoded strings.
        
        Args:
            images: List of PIL Image objects.
            format: Image format (PNG, JPEG, etc.)
            
        Returns:
            List of base64 encoded strings.
        """
        base64_images = []
        for img in images:
            buffer = io.BytesIO()
            img.save(buffer, format=format)
            buffer.seek(0)
            b64 = base64.b64encode(buffer.getvalue()).decode('utf-8')
            base64_images.append(b64)
        
        return base64_images
    
    def pdf_to_base64_images(
        self, 
        pdf_bytes: bytes, 
        dpi: Optional[int] = None,
        max_pages: Optional[int] = None,
        min_table_rows: Optional[int] = None,
        min_table_cols: Optional[int] = None,
        prefer_tables: bool = True,
    ) -> list[dict]:
        """
        Convert PDF to base64 images suitable for LLM vision APIs.
        
        Args:
            pdf_bytes: PDF file content as bytes.
            dpi: Resolution for conversion.
            max_pages: Maximum number of pages to convert.
            
        Returns:
            List of dicts with 'type', 'image_url' structure for OpenAI API.
        """
        images = self.convert_bytes_to_images(pdf_bytes, dpi)
        page_indexes = list(range(len(images)))

        min_table_rows = min_table_rows or self.config.features.min_table_rows
        min_table_cols = min_table_cols or self.config.features.min_table_cols
        if prefer_tables and self.config.features.enable_tables:
            table_pages = self._table_pages_from_bytes(
                pdf_bytes,
                min_table_rows=min_table_rows,
                min_table_cols=min_table_cols,
            )
            if table_pages:
                table_indexes = [p - 1 for p in table_pages if 0 < p <= len(images)]
                remaining = [idx for idx in page_indexes if idx not in table_indexes]
                page_indexes = table_indexes + remaining
        
        if max_pages:
            page_indexes = page_indexes[:max_pages]
        
        result = []
        for idx in page_indexes:
            img = images[idx]
            buffer = io.BytesIO()
            img.save(buffer, format="PNG")
            buffer.seek(0)
            b64 = base64.b64encode(buffer.getvalue()).decode('utf-8')
            
            result.append({
                "type": "image_url",
                "image_url": {
                    "url": f"data:image/png;base64,{b64}",
                    "detail": "high"
                }
            })
        
        return result

    def _table_pages_from_bytes(
        self,
        pdf_bytes: bytes,
        min_table_rows: int,
        min_table_cols: int,
    ) -> list[int]:
        pages = []
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            for page_index, page in enumerate(pdf.pages, start=1):
                tables = page.extract_tables() or []
                if self._has_min_table(tables, min_table_rows, min_table_cols):
                    pages.append(page_index)
        return pages

    @staticmethod
    def _has_min_table(
        tables: list[list[list[Optional[str]]]],
        min_rows: int,
        min_cols: int,
    ) -> bool:
        for table in tables:
            if not table:
                continue
            row_count = len(table)
            col_count = max((len(row or []) for row in table), default=0)
            if row_count >= min_rows and col_count >= min_cols:
                return True
        return False
    
    def get_page_count(self, pdf_bytes: bytes) -> int:
        """Get the number of pages in a PDF."""
        reader = PdfReader(io.BytesIO(pdf_bytes))
        return len(reader.pages)
