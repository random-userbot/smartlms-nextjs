"""
Smart LMS - PDF Processing Service
Handles text extraction from student assignment PDFs using PyPDF2
"""

import io
from typing import Optional
import PyPDF2
from app.services.debug_logger import debug_logger

class PDFService:
    @staticmethod
    def extract_text(pdf_bytes: bytes) -> str:
        """
        Extracts plain text from PDF bytes.
        """
        if not pdf_bytes:
            return ""
            
        try:
            pdf_file = io.BytesIO(pdf_bytes)
            reader = PyPDF2.PdfReader(pdf_file)
            
            text_content = []
            for page_num in range(len(reader.pages)):
                page = reader.pages[page_num]
                text = page.extract_text()
                if text:
                    text_content.append(text)
            
            return "\n\n".join(text_content).strip()
        except Exception as e:
            debug_logger.log("pdf_service", f"Failed to extract text from PDF: {e}")
            return ""

    @staticmethod
    def get_document_info(pdf_bytes: bytes) -> dict:
        """
        Returns metadata about the PDF (page count, author, etc.)
        """
        try:
            pdf_file = io.BytesIO(pdf_bytes)
            reader = PyPDF2.PdfReader(pdf_file)
            return {
                "pages": len(reader.pages),
                "metadata": dict(reader.metadata or {})
            }
        except Exception:
            return {"pages": 0, "metadata": {}}

pdf_service = PDFService()
