"""
Simple script to view the complete extracted text from a PDF file.
"""

import logging
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from src.loaders.pdf import PDF


def view_full_pdf_text():
    """Extract and display the complete text from the test PDF."""
    
    # Setup basic logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(levelname)s: %(message)s'
    )
    
    # Path to test PDF
    test_dir = Path(__file__).parent
    pdf_path = test_dir / "slides-basics-whatisml.pdf"
    
    if not pdf_path.exists():
        print(f"❌ ERROR: PDF file not found at {pdf_path}")
        return
    
    print("=" * 80)
    print(f"EXTRACTING FULL TEXT FROM: {pdf_path.name}")
    print("=" * 80)
    print()
    
    # Create PDF extractor
    pdf_extractor = PDF()
    
    try:
        # Extract full text
        text = pdf_extractor.extract_text(pdf_path)
        
        # Display statistics
        print(f"📊 STATISTICS:")
        print(f"   Total characters: {len(text):,}")
        print(f"   Total words: {len(text.split()):,}")
        print(f"   Total lines: {len(text.splitlines()):,}")
        print()
        print("=" * 80)
        print("FULL EXTRACTED TEXT:")
        print("=" * 80)
        print()
        
        # Display full text
        print(text)
        
        print()
        print("=" * 80)
        print("END OF DOCUMENT")
        print("=" * 80)
        
    except Exception as e:
        print(f"❌ ERROR: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    view_full_pdf_text()
