"""
Improved PDF text extractor using PyMuPDF (fitz).

Goals:
- Robust extraction across many PDF layouts (portrait/landscape, single/multi-column).
- Header/footer suppression based on repeated margin text (conservative).
- Optional suppression of diagram/figure label noise without OCR by filtering:
  - image blocks
  - nearby short/fragmented text blocks

This module only depends on PyMuPDF.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Sequence, Tuple

import fitz  # PyMuPDF


@dataclass(frozen=True)
class PDFExtractConfig:
    # Geometry ratios for margin candidate regions (relative to page height).
    header_ratio: float = 0.12
    footer_ratio: float = 0.12

    # Detect repeated header/footer strings using first N pages.
    header_footer_probe_pages: int = 10
    repeated_text_min_fraction: float = 0.65  # only remove if seen on >= 65% probe pages

    # If page becomes "too empty" after filtering, fall back to less aggressive extraction.
    min_chars_per_page_after_filter: int = 200

    # Diagram/figure noise filtering
    suppress_image_blocks: bool = True
    suppress_text_near_images: bool = True
    near_image_expand_ratio: float = 0.02  # expand image rectangles by 2% of max(page_w, page_h)
    # Only drop near-image text if it looks like "diagram label noise"
    aggressive_diagram_text_filter: bool = False

    # Multi-column handling (light heuristic)
    enable_two_column_sort: bool = True
    two_column_gap_ratio: float = 0.15  # gap threshold relative to page width
    two_column_min_blocks_per_column: int = 3

    # Output
    include_page_markers: bool = True


class PDF:
    """
    PDF text extractor for extracting text content from PDF files.

    Uses PyMuPDF (fitz) for text extraction from native PDF files.
    """

    _re_page_number = re.compile(r"\b(page|seite)\s*\d+\b", re.IGNORECASE)
    _re_digits_only = re.compile(r"^\s*[\dIVXivx\-\–—]+\s*$")

    def __init__(self, config: PDFExtractConfig | None = None) -> None:
        self.logger = logging.getLogger("loader.pdf")
        self.config = config or PDFExtractConfig()

    # ----------------------------
    # Public API
    # ----------------------------

    def extract_text(self, pdf_path: str | Path) -> str:
        """
        Extract all text content from a PDF file.

        Args:
            pdf_path: Path to the PDF file

        Returns:
            str: Extracted text content from all pages
        """
        pdf_path = Path(pdf_path)
        self.logger.info("Extracting text from PDF file: %s", pdf_path)

        try:
            with pdf_path.open("rb") as f:
                pdf_bytes = f.read()
            return self.extract_text_from_bytes(pdf_bytes, filename=pdf_path.name)
        except Exception as e:
            self.logger.error("Error extracting text from %s: %s", pdf_path.name, e)
            raise

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
        self.logger.info("Extracting text from PDF bytes: %s", filename)

        try:
            doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        except fitz.FileDataError as e:
            self.logger.error("Invalid or corrupted PDF file %s: %s", filename, e)
            raise

        try:
            total_pages = doc.page_count
            # Learn repeated header/footer strings conservatively.
            header_texts, footer_texts = self._learn_repeated_margin_texts(doc)

            text_content: List[str] = []
            for page_index in range(total_pages):
                page = doc[page_index]
                page_text = self._extract_page_text_blocks(
                    page,
                    header_texts=header_texts,
                    footer_texts=footer_texts,
                )

                # Fallback: if too little extracted, use less aggressive extraction
                if len(page_text.strip()) < self.config.min_chars_per_page_after_filter:
                    fallback = self._extract_page_text_fallback(page)
                    # If fallback has meaningfully more text, use it.
                    if len(fallback.strip()) > len(page_text.strip()):
                        page_text = self._clean_text(fallback)

                if page_text.strip():
                    if self.config.include_page_markers:
                        text_content.append(f"--- Page {page_index + 1} ---")
                    text_content.append(page_text)

            total_chars = sum(len(t) for t in text_content)
            self.logger.info(
                "Successfully extracted text from %s pages (%s characters) from %s",
                total_pages,
                total_chars,
                filename,
            )
            return "\n\n".join(text_content)
        finally:
            doc.close()

    def extract_page(self, pdf_path: str | Path, page_number: int) -> str:
        """
        Extract text from a specific page.

        Args:
            pdf_path: Path to the PDF file
            page_number: Page number (1-indexed)

        Returns:
            str: Extracted text from the specified page
        """
        pdf_path = Path(pdf_path)
        if page_number < 1:
            raise ValueError("page_number must be >= 1")

        with pdf_path.open("rb") as f:
            pdf_bytes = f.read()

        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        try:
            if page_number > doc.page_count:
                raise ValueError(f"PDF has only {doc.page_count} pages, requested {page_number}")

            header_texts, footer_texts = self._learn_repeated_margin_texts(doc)
            page = doc[page_number - 1]
            txt = self._extract_page_text_blocks(page, header_texts, footer_texts)

            if len(txt.strip()) < self.config.min_chars_per_page_after_filter:
                fallback = self._extract_page_text_fallback(page)
                if len(fallback.strip()) > len(txt.strip()):
                    txt = self._clean_text(fallback)
            return txt
        finally:
            doc.close()

    # ----------------------------
    # Core extraction
    # ----------------------------

    def _extract_page_text_fallback(self, page: fitz.Page) -> str:
        """
        Less aggressive extraction used when filtering removed too much.
        """
        # 'sort=True' improves reading order for many PDFs.
        # Still returns a single string (no geometry).
        return page.get_text("text", sort=True)

    def _extract_page_text_blocks(
        self,
        page: fitz.Page,
        header_texts: set[str],
        footer_texts: set[str],
    ) -> str:
        """
        Extracts text using geometry-aware blocks and conservative filtering.
        """
        cfg = self.config
        rect = page.rect
        page_w, page_h = float(rect.width), float(rect.height)

        header_y_max = rect.y0 + cfg.header_ratio * page_h
        footer_y_min = rect.y1 - cfg.footer_ratio * page_h

        # Get blocks: tuples (x0, y0, x1, y1, "text", block_no, block_type)
        blocks = page.get_text("blocks")  # fast, geometry included
        text_blocks: List[Tuple[float, float, float, float, str]] = []
        image_rects: List[fitz.Rect] = []

        for b in blocks:
            x0, y0, x1, y1, txt, *_rest = b
            # block_type is last element in blocks tuple in most PyMuPDF versions
            block_type = b[-1]

            if block_type == 1:
                # image block
                if cfg.suppress_image_blocks:
                    image_rects.append(fitz.Rect(x0, y0, x1, y1))
                continue

            # Only keep text blocks with content
            if not txt or not txt.strip():
                continue

            # Conservative header/footer removal: only if repeated text matches.
            in_header = y1 <= header_y_max
            in_footer = y0 >= footer_y_min
            norm = self._normalize_margin_text(txt)

            if in_header and norm and norm in header_texts:
                continue
            if in_footer and norm and norm in footer_texts:
                continue

            text_blocks.append((float(x0), float(y0), float(x1), float(y1), txt))

        # Optional: suppress "diagram label noise" near images (conservative by default)
        if cfg.suppress_text_near_images and image_rects:
            text_blocks = self._filter_text_near_images(
                text_blocks=text_blocks,
                image_rects=image_rects,
                page_w=page_w,
                page_h=page_h,
            )

        # Sort blocks in a way that works for many layouts.
        text_blocks = self._sort_text_blocks(text_blocks, page_w=page_w)

        # Concatenate block texts and clean
        combined = "\n".join(self._clean_text(tb[4]) for tb in text_blocks if tb[4].strip())
        combined = self._clean_text(combined)

        # Final sanity: if we removed too much, allow mild fallback later in caller.
        return combined

    def _sort_text_blocks(
        self,
        text_blocks: List[Tuple[float, float, float, float, str]],
        page_w: float,
    ) -> List[Tuple[float, float, float, float, str]]:
        """
        Sort text blocks for reading order. Uses a lightweight two-column heuristic
        if enabled and the page seems clearly multi-column.
        """
        if not self.config.enable_two_column_sort or len(text_blocks) < 10:
            return sorted(text_blocks, key=lambda b: (b[1], b[0]))

        x0s = sorted(b[0] for b in text_blocks)
        if len(x0s) < 2:
            return sorted(text_blocks, key=lambda b: (b[1], b[0]))

        # Find largest gap in x0 positions
        gaps = [(x0s[i + 1] - x0s[i], i) for i in range(len(x0s) - 1)]
        max_gap, idx = max(gaps, key=lambda t: t[0])
        if max_gap < self.config.two_column_gap_ratio * page_w:
            return sorted(text_blocks, key=lambda b: (b[1], b[0]))

        split_x = (x0s[idx] + x0s[idx + 1]) / 2.0
        left = [b for b in text_blocks if b[0] <= split_x]
        right = [b for b in text_blocks if b[0] > split_x]

        if (
            len(left) < self.config.two_column_min_blocks_per_column
            or len(right) < self.config.two_column_min_blocks_per_column
        ):
            return sorted(text_blocks, key=lambda b: (b[1], b[0]))

        left_sorted = sorted(left, key=lambda b: (b[1], b[0]))
        right_sorted = sorted(right, key=lambda b: (b[1], b[0]))
        return left_sorted + right_sorted

    # ----------------------------
    # Header/Footer detection
    # ----------------------------

    def _learn_repeated_margin_texts(self, doc: fitz.Document) -> Tuple[set[str], set[str]]:
        """
        Learn repeated header/footer texts across the first N pages.

        Conservative: only removes strings that repeat across many pages.
        Also strips page numbers so "Page 3" doesn't block detection.
        """
        cfg = self.config
        probe_pages = min(cfg.header_footer_probe_pages, doc.page_count)
        if probe_pages <= 1:
            return set(), set()

        header_counts: dict[str, int] = {}
        footer_counts: dict[str, int] = {}

        for i in range(probe_pages):
            page = doc[i]
            rect = page.rect
            h = float(rect.height)
            header_y_max = rect.y0 + cfg.header_ratio * h
            footer_y_min = rect.y1 - cfg.footer_ratio * h

            for b in page.get_text("blocks"):
                x0, y0, x1, y1, txt, *_rest = b
                block_type = b[-1]
                if block_type != 0:
                    continue
                if not txt or not txt.strip():
                    continue

                norm = self._normalize_margin_text(txt)
                if not norm:
                    continue

                if float(y1) <= header_y_max:
                    header_counts[norm] = header_counts.get(norm, 0) + 1
                elif float(y0) >= footer_y_min:
                    footer_counts[norm] = footer_counts.get(norm, 0) + 1

        min_count = max(2, int(cfg.repeated_text_min_fraction * probe_pages))
        header_texts = {t for t, c in header_counts.items() if c >= min_count}
        footer_texts = {t for t, c in footer_counts.items() if c >= min_count}

        return header_texts, footer_texts

    def _normalize_margin_text(self, txt: str) -> str:
        """
        Normalize margin text for stable repetition matching.
        """
        s = " ".join(txt.split())
        if not s:
            return ""
        s = self._re_page_number.sub("", s)
        s = re.sub(r"\b\d+\b", "", s)  # remove digits (page numbers, years)
        s = re.sub(r"[\(\)\[\]\{\}]", "", s)
        s = s.strip(" -–—|·•\t")
        s = " ".join(s.split()).lower()
        # Drop meaningless normals
        if not s or len(s) < 3:
            return ""
        if self._re_digits_only.match(s):
            return ""
        return s

    # ----------------------------
    # Diagram / noise filtering
    # ----------------------------

    def _filter_text_near_images(
        self,
        text_blocks: List[Tuple[float, float, float, float, str]],
        image_rects: Sequence[fitz.Rect],
        page_w: float,
        page_h: float,
    ) -> List[Tuple[float, float, float, float, str]]:
        """
        Remove some text blocks near images if they look like diagram label noise.

        Conservative mode:
        - only removes near-image blocks when they are strongly "noise-like".
        Aggressive mode:
        - removes any near-image text blocks that are mostly short tokens.
        """
        cfg = self.config
        expand = cfg.near_image_expand_ratio * max(page_w, page_h)

        expanded_images = [r + (-expand, -expand, expand, expand) for r in image_rects]

        kept: List[Tuple[float, float, float, float, str]] = []
        for x0, y0, x1, y1, txt in text_blocks:
            block_rect = fitz.Rect(x0, y0, x1, y1)

            near_image = any(block_rect.intersects(img_r) for img_r in expanded_images)
            if not near_image:
                kept.append((x0, y0, x1, y1, txt))
                continue

            # Determine whether this is likely diagram noise
            if cfg.aggressive_diagram_text_filter:
                if self._looks_like_diagram_text(txt):
                    continue
                kept.append((x0, y0, x1, y1, txt))
                continue

            # Conservative: only remove if very likely noise
            if self._looks_like_diagram_text(txt, strict=True):
                continue

            kept.append((x0, y0, x1, y1, txt))
        return kept

    def _looks_like_diagram_text(self, text: str, strict: bool = False) -> bool:
        """
        Heuristic to detect chart/diagram labels:
        - many very short tokens
        - scattered single letters
        - axes-like numeric tick sequences
        - very low "wordiness"
        """
        s = " ".join(text.split())
        if not s:
            return False

        # If it contains a long sentence, it's probably real content.
        if not strict and len(s) >= 80 and sum(ch.isalpha() for ch in s) / max(1, len(s)) > 0.4:
            return False

        tokens = [t for t in re.split(r"\s+", s) if t]
        if len(tokens) <= 1:
            return True if strict else False

        short = sum(1 for t in tokens if len(t) <= 2)
        alpha_short = sum(1 for t in tokens if len(t) <= 2 and t.isalpha())
        numeric = sum(1 for t in tokens if re.fullmatch(r"[-+]?\d+([.,]\d+)?", t) is not None)

        # Typical axes ticks: lots of numbers with a few single letters
        if len(tokens) >= 5 and numeric / len(tokens) >= 0.5 and alpha_short / len(tokens) >= 0.2:
            return True

        # Many short tokens suggests labels
        if short / len(tokens) >= (0.75 if strict else 0.85):
            return True

        # Excessive repetition of same character (e.g., "IIIIIIII" or "----")
        condensed = re.sub(r"\s+", "", s)
        uniq = set(condensed)
        if len(condensed) > 15 and len(uniq) <= 2:
            return True

        # Fallback to legacy line-level heuristic
        if strict:
            for line in text.splitlines():
                if self._is_diagram_noise_line(line):
                    return True

        return False

    def _is_diagram_noise_line(self, line: str) -> bool:
        """
        Legacy line-level heuristic from the original implementation, kept for compatibility.
        """
        stripped = line.strip()
        if not stripped:
            return False

        words = stripped.split()

        # Very short lines with single characters
        if len(stripped) <= 4 and len(words) <= 2:
            return True

        # Lines with many single letters/spaces
        if len(words) >= 5:
            single_char_count = sum(1 for word in words if len(word) == 1)
            if single_char_count / len(words) > 0.6:
                return True

        # Lines with only numbers and very short words
        if len(words) >= 3:
            short_word_count = sum(1 for word in words if len(word) <= 2)
            if short_word_count / len(words) > 0.8:
                return True

        # Check for excessive repetition of same character
        unique_chars = set(line.replace(" ", "").replace("\n", ""))
        if len(unique_chars) <= 2 and len(line.replace(" ", "")) > 15:
            return True

        # Check if line consists mainly of repeated single letters with numbers
        if len(words) > 4:
            letter_count = sum(1 for word in words if len(word) <= 2 and word.isalpha())
            if letter_count / len(words) > 0.5:
                return True

        return False

    # ----------------------------
    # Cleaning / formatting
    # ----------------------------

    def _clean_text(self, text: str) -> str:
        """
        Clean extracted text: remove excessive blank lines and trim trailing spaces.
        Keeps paragraphs intact.
        """
        # Normalize line endings
        text = text.replace("\r\n", "\n").replace("\r", "\n")
        lines = [ln.rstrip() for ln in text.split("\n")]

        cleaned: List[str] = []
        blank_run = 0
        for ln in lines:
            if not ln.strip():
                blank_run += 1
                if blank_run <= 1:
                    cleaned.append("")
                continue
            blank_run = 0
            cleaned.append(ln)

        # Strip leading/trailing blank lines
        while cleaned and not cleaned[0].strip():
            cleaned.pop(0)
        while cleaned and not cleaned[-1].strip():
            cleaned.pop()

        return "\n".join(cleaned)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    pdf_extractor = PDF()

    sample_pdf = Path("sample.pdf")
    if sample_pdf.exists():
        text = pdf_extractor.extract_text(sample_pdf)
        print(f"Extracted {len(text)} characters")
        print("\nFull text:")
        print(text)