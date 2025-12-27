"""
PDF text extractor using PyMuPDF (fitz).
Extracts text content from native PDF files for use in Module documents.
"""

import logging
from pathlib import Path

import fitz  # PyMuPDF


class PDF:
    """
    PDF text extractor for extracting text content from PDF files.
    
    Uses PyMuPDF (fitz) for text extraction from native PDF files.
    Does not handle OCR, tables, or images.
    
    Returns plain text that can be integrated into Module.to_document().
    """

    def __init__(self) -> None:
        self.logger = logging.getLogger("loader.pdf")

    def _is_diagram_noise(self, line: str) -> bool:
        """
        Detect if a line is likely diagram/chart noise (scattered letters).
        
        Args:
            line: A single line of text
            
        Returns:
            bool: True if line appears to be diagram noise
        """
        stripped = line.strip()
        if not stripped:
            return False
        
        # Single character lines are almost always diagram noise
        if len(stripped) <= 2:
            return True
        
        # Count words
        words = line.split()
        if len(words) == 0:
            return False
        
        # Check for single character words
        single_char_words = sum(1 for word in words if len(word) == 1)
        
        # Check for 2-character words (often repeated like "GG")
        two_char_words = sum(1 for word in words if len(word) == 2)
        
        # If more than 60% are single or double characters, it's likely a diagram
        short_words = single_char_words + two_char_words
        if short_words / len(words) > 0.6 and len(words) > 3:
            return True
        
        # Check for excessive repetition of same character
        unique_chars = set(line.replace(" ", "").replace("\n", ""))
        if len(unique_chars) <= 2 and len(line.replace(" ", "")) > 15:
            return True
        
        # Check if line consists mainly of repeated single letters with numbers
        # Pattern like: "G G G 0.0 0.5 1.0"
        if len(words) > 4:
            letter_count = sum(1 for word in words if len(word) <= 2 and word.isalpha())
            if letter_count / len(words) > 0.5:
                return True
        
        return False

    def _clean_page_text(self, text: str) -> str:
        """
        Clean page text by removing diagram noise and excessive whitespace.
        
        Args:
            text: Raw text from a PDF page
            
        Returns:
            str: Cleaned text
        """
        lines = text.split('\n')
        cleaned_lines = []
        
        # Track consecutive noise lines to identify diagram blocks
        consecutive_noise = 0
        skip_until_content = False
        
        for i, line in enumerate(lines):
            # Skip diagram noise
            if self._is_diagram_noise(line):
                consecutive_noise += 1
                # If we see 3+ consecutive noise lines, skip this entire block
                if consecutive_noise >= 3:
                    skip_until_content = True
                continue
            else:
                # Reset counter when we hit real content
                if not skip_until_content:
                    consecutive_noise = 0
                # Check if this line is substantial content (not just numbers/labels)
                if len(line.strip()) > 10 or any(word for word in line.split() if len(word) > 3):
                    skip_until_content = False
                    consecutive_noise = 0
            
            # Skip this line if we're in a diagram block
            if skip_until_content:
                continue
            
            # Skip lines with only whitespace
            if not line.strip():
                continue
            
            cleaned_lines.append(line.rstrip())
        
        return '\n'.join(cleaned_lines)

    def extract_text_from_bytes(self, pdf_bytes: bytes, filename: str = "document.pdf") -> str:
        """
        Extract all text content from PDF bytes (downloaded file).
        
        Args:
            pdf_bytes: PDF file content as bytes
            filename: Optional filename for logging purposes
            
        Returns:
            str: Extracted text content from all pages
            
        Raises:
            fitz.FileDataError: If PDF is corrupted or invalid
        """
        self.logger.info(f"Extracting text from PDF bytes: {filename}")
        
        text_content = []
        
        try:
            # Open PDF from bytes
            doc = fitz.open(stream=pdf_bytes, filetype="pdf")
            total_pages = len(doc)
            
            # Extract text from each page
            for page_num in range(total_pages):
                page = doc[page_num]
                page_text = page.get_text()
                
                if page_text.strip():
                    cleaned_text = self._clean_page_text(page_text)
                    
                    if cleaned_text.strip():
                        text_content.append(f"--- Page {page_num + 1} ---")
                        text_content.append(cleaned_text)
            
            doc.close()
            
            total_chars = sum(len(t) for t in text_content)
            
            self.logger.info(
                f"Successfully extracted text from {total_pages} pages "
                f"({total_chars} characters) from {filename}"
            )
            
            return "\n\n".join(text_content)
            
        except fitz.FileDataError as e:
            self.logger.error(f"Invalid or corrupted PDF {filename}: {e}")
            raise
        except Exception as e:
            self.logger.error(f"Error extracting text from {filename}: {e}")
            raise

    def extract_text(self, pdf_path: str | Path) -> str:
        """
        Extract all text content from a PDF file.
        
        Args:
            pdf_path: Path to the PDF file (str or Path object)
            
        Returns:
            str: Extracted text content from all pages
            
        Raises:
            FileNotFoundError: If PDF file doesn't exist
            fitz.FileDataError: If PDF is corrupted or invalid
        """
        pdf_path = Path(pdf_path)
        
        if not pdf_path.exists():
            raise FileNotFoundError(f"PDF file not found: {pdf_path}")
        
        if not pdf_path.suffix.lower() == '.pdf':
            raise ValueError(f"File is not a PDF: {pdf_path}")
        
        self.logger.info(f"Extracting text from PDF: {pdf_path.name}")
        
        text_content = []
        
        try:
            # Open PDF document
            doc = fitz.open(pdf_path)
            total_pages = len(doc)  # Get page count before closing
            
            # Extract text from each page
            for page_num in range(total_pages):
                page = doc[page_num]
                page_text = page.get_text()
                
                if page_text.strip():  # Only add non-empty pages
                    # Clean text to remove diagram noise
                    cleaned_text = self._clean_page_text(page_text)
                    
                    if cleaned_text.strip():  # Only add if there's actual content
                        # Add page marker for better structure
                        text_content.append(f"--- Page {page_num + 1} ---")
                        text_content.append(cleaned_text)
            
            doc.close()
            
            total_chars = sum(len(t) for t in text_content)
            
            self.logger.info(
                f"Successfully extracted text from {total_pages} pages "
                f"({total_chars} characters) from {pdf_path.name}"
            )
            
            return "\n\n".join(text_content)
            
        except fitz.FileDataError as e:
            self.logger.error(f"Invalid or corrupted PDF file {pdf_path.name}: {e}")
            raise
        except Exception as e:
            self.logger.error(f"Error extracting text from {pdf_path.name}: {e}")
            raise

    def extract_page(self, pdf_path: str | Path, page_number: int) -> str:
        """
        Extract text from a specific page.
        
        Args:
            pdf_path: Path to the PDF file
            page_number: Page number (1-indexed)
            
        Returns:
            str: Extracted text from the specified page
            
        Raises:
            ValueError: If page number is invalid
        """
        pdf_path = Path(pdf_path)
        
        if not pdf_path.exists():
            raise FileNotFoundError(f"PDF file not found: {pdf_path}")
        
        try:
            doc = fitz.open(pdf_path)
            
            if page_number < 1 or page_number > len(doc):
                raise ValueError(
                    f"Invalid page number {page_number}. "
                    f"PDF has {len(doc)} pages."
                )
            
            # Convert to 0-indexed
            page = doc[page_number - 1]
            text = page.get_text()
            doc.close()
            
            return text.strip()
            
        except Exception as e:
            self.logger.error(f"Error extracting page {page_number}: {e}")
            raise


if __name__ == "__main__":
    # Example usage
    logging.basicConfig(level=logging.INFO)
    
    pdf_extractor = PDF()
    sample_pdf = Path("sample.pdf")
    
    if sample_pdf.exists():
        text = pdf_extractor.extract_text(sample_pdf)
        print(f"Extracted {len(text)} characters")
        print("\nFull text:")
        print(text)
