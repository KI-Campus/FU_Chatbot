"""
Test script for PDF text extraction.
Tests the PDF loader with slides-basics-whatisml.pdf
"""

import logging
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from src.loaders.pdf import PDF


def setup_logging():
    """Configure logging for tests."""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )


def test_pdf_extraction():
    """Test basic PDF text extraction."""
    print("\n" + "="*80)
    print("TEST 1: Basic PDF Text Extraction")
    print("="*80)
    
    # Path to test PDF
    test_dir = Path(__file__).parent
    pdf_path = test_dir / "slides-basics-whatisml.pdf"
    
    if not pdf_path.exists():
        print(f"❌ ERROR: Test PDF not found at {pdf_path}")
        return False
    
    print(f"📄 Testing PDF: {pdf_path.name}")
    
    # Create PDF loader
    pdf_loader = PDF()
    
    try:
        # Extract text
        text = pdf_loader.extract_text(pdf_path)
        
        # Print statistics
        print(f"\n✅ Extraction successful!")
        print(f"   Total characters: {len(text):,}")
        print(f"   Total words: {len(text.split()):,}")
        print(f"   Total lines: {len(text.splitlines()):,}")
        
        # Print first 500 characters
        print("\n📝 First 500 characters:")
        print("-" * 80)
        print(text[:500])
        print("-" * 80)
        
        # Print last 300 characters
        print("\n📝 Last 300 characters:")
        print("-" * 80)
        print(text[-300:])
        print("-" * 80)
        
        return True
        
    except Exception as e:
        print(f"❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_pdf_to_document():
    """Test that PDF text can be used in a Module context."""
    print("\n" + "="*80)
    print("TEST 2: PDF Text for Module Integration")
    print("="*80)
    
    test_dir = Path(__file__).parent
    pdf_path = test_dir / "slides-basics-whatisml.pdf"
    
    if not pdf_path.exists():
        print(f"❌ ERROR: Test PDF not found at {pdf_path}")
        return False
    
    pdf_loader = PDF()
    
    try:
        # Extract text (as would be done in extract_resource())
        text = pdf_loader.extract_text(pdf_path)
        
        print(f"\n✅ Text extracted for module integration!")
        print(f"   Text length: {len(text):,} characters")
        print(f"   Can be used in: module.text = pdf_text")
        
        # Simulate how it would be used in Module.to_document()
        module_text_parts = [
            f"Module Name: ML Basics - Slides",
            f"\nPDF Content ({pdf_path.name}):",
            text[:500] + "..." if len(text) > 500 else text
        ]
        
        simulated_module_text = "\n".join(module_text_parts)
        
        print(f"\n📄 Simulated Module Document preview:")
        print("-" * 80)
        print(simulated_module_text[:600])
        print("-" * 80)
        
        return True
        
    except Exception as e:
        print(f"❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_extract_specific_page():
    """Test extracting a specific page."""
    print("\n" + "="*80)
    print("TEST 3: Extract Specific Page")
    print("="*80)
    
    test_dir = Path(__file__).parent
    pdf_path = test_dir / "slides-basics-whatisml.pdf"
    
    if not pdf_path.exists():
        print(f"❌ ERROR: Test PDF not found at {pdf_path}")
        return False
    
    pdf_loader = PDF()
    
    try:
        # Extract page 1
        page_text = pdf_loader.extract_page(pdf_path, page_number=1)
        
        print(f"\n✅ Page 1 extracted successfully!")
        print(f"   Page length: {len(page_text)} characters")
        print(f"\n📄 Page 1 content:")
        print("-" * 80)
        print(page_text)
        print("-" * 80)
        
        return True
        
    except Exception as e:
        print(f"❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_error_handling():
    """Test error handling for invalid inputs."""
    print("\n" + "="*80)
    print("TEST 4: Error Handling")
    print("="*80)
    
    pdf_loader = PDF()
    
    # Test 1: Non-existent file
    print("\n📌 Test 4a: Non-existent file")
    try:
        pdf_loader.extract_text("nonexistent.pdf")
        print("❌ FAILED: Should have raised FileNotFoundError")
        return False
    except FileNotFoundError:
        print("✅ PASSED: FileNotFoundError raised correctly")
    
    # Test 2: Invalid page number
    print("\n📌 Test 4b: Invalid page number")
    test_dir = Path(__file__).parent
    pdf_path = test_dir / "slides-basics-whatisml.pdf"
    
    if pdf_path.exists():
        try:
            pdf_loader.extract_page(pdf_path, page_number=9999)
            print("❌ FAILED: Should have raised ValueError")
            return False
        except ValueError:
            print("✅ PASSED: ValueError raised correctly for invalid page")
    
    return True


def run_all_tests():
    """Run all PDF loader tests."""
    print("\n" + "="*80)
    print("PDF LOADER TEST SUITE")
    print("="*80)
    
    setup_logging()
    
    results = []
    
    # Run tests
    results.append(("Basic Extraction", test_pdf_extraction()))
    results.append(("Module Integration", test_pdf_to_document()))
    results.append(("Specific Page", test_extract_specific_page()))
    results.append(("Error Handling", test_error_handling()))
    
    # Print summary
    print("\n" + "="*80)
    print("TEST SUMMARY")
    print("="*80)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✅ PASSED" if result else "❌ FAILED"
        print(f"{status}: {test_name}")
    
    print(f"\nTotal: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n🎉 All tests passed!")
    else:
        print(f"\n⚠️  {total - passed} test(s) failed")
    
    return passed == total


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
