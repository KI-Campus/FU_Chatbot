"""Integration tests for Moochup API.

These tests make real API calls and are marked with @pytest.mark.integration.
Run with: pytest src/tests/loaders/test_moochup_integration.py -v -m integration
"""

import os
import sys

import pytest

# Add project root to path for direct script execution
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../"))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from src.env import env
from src.loaders.moochup import Moochup


@pytest.mark.integration
def test_moochup_fetch_moodle_courses():
    """Test fetching real course data from Moochup Moodle API."""
    
    # Verify env variable is set
    assert env.DATA_SOURCE_MOOCHUP_MOODLE_URL != "UNSET", (
        "DATA_SOURCE_MOOCHUP_MOODLE_URL not configured. "
        "Set it in .env file or environment variables."
    )
    
    moochup = Moochup(env.DATA_SOURCE_MOOCHUP_MOODLE_URL)
    
    # Fetch courses
    courses = moochup.fetch_data()
    
    # Basic assertions
    assert isinstance(courses, list), "fetch_data should return a list"
    assert len(courses) > 0, "Should fetch at least one course"
    
    # Check first course structure
    first_course = courses[0]
    assert hasattr(first_course, 'id'), "Course should have id"
    assert hasattr(first_course, 'type'), "Course should have type"
    assert hasattr(first_course, 'attributes'), "Course should have attributes"
    assert first_course.type == 'course', "Type should be normalized to 'course'"
    
    # Check attributes
    attrs = first_course.attributes
    assert hasattr(attrs, 'name'), "Attributes should have name"
    assert hasattr(attrs, 'description'), "Attributes should have description"
    assert hasattr(attrs, 'url'), "Attributes should have url"
    
    print(f"\n✓ Fetched {len(courses)} courses from Moochup Moodle API")
    print(f"  First course: {first_course.attributes.name}")
    print(f"  URL: {first_course.attributes.url}")


@pytest.mark.integration
def test_moochup_get_course_documents():
    """Test converting Moochup courses to LlamaIndex Documents."""
    
    assert env.DATA_SOURCE_MOOCHUP_MOODLE_URL != "UNSET", (
        "DATA_SOURCE_MOOCHUP_MOODLE_URL not configured"
    )
    
    moochup = Moochup(env.DATA_SOURCE_MOOCHUP_MOODLE_URL)
    
    # Get documents
    documents = moochup.get_course_documents()
    
    assert isinstance(documents, list), "Should return a list of documents"
    assert len(documents) > 0, "Should have at least one document"
    
    # Check first document
    first_doc = documents[0]
    assert hasattr(first_doc, 'text'), "Document should have text"
    assert hasattr(first_doc, 'metadata'), "Document should have metadata"
    
    # Check text content
    assert "Kursname:" in first_doc.text, "Text should contain 'Kursname:'"
    assert "Kursbeschreibung:" in first_doc.text, "Text should contain 'Kursbeschreibung:'"
    
    # Check metadata
    metadata = first_doc.metadata
    assert 'source' in metadata, "Metadata should have 'source'"
    assert metadata['source'] == 'Moochup', "Source should be 'Moochup'"
    assert 'type' in metadata, "Metadata should have 'type'"
    assert metadata['type'] == 'Kurs', "Type should be 'Kurs'"
    assert 'url' in metadata, "Metadata should have 'url'"
    assert 'course_id' in metadata, "Metadata should have 'course_id'"
    
    print(f"\n✓ Converted {len(documents)} courses to Documents")
    print(f"  First doc course_id: {metadata['course_id']}")
    print(f"  Text preview: {first_doc.text[:100]}...")


@pytest.mark.integration
@pytest.mark.skip(reason="Only run when HPI URL is available")
def test_moochup_fetch_hpi_courses():
    """Test fetching real course data from Moochup HPI API."""
    
    assert env.DATA_SOURCE_MOOCHUP_HPI_URL != "UNSET", (
        "DATA_SOURCE_MOOCHUP_HPI_URL not configured"
    )
    
    moochup = Moochup(env.DATA_SOURCE_MOOCHUP_HPI_URL)
    courses = moochup.fetch_data()
    
    assert isinstance(courses, list)
    assert len(courses) > 0
    
    print(f"\n✓ Fetched {len(courses)} courses from Moochup HPI API")


if __name__ == "__main__":
    # Quick manual test
    print("Running Moochup integration tests manually...")
    print("=" * 60)
    
    try:
        test_moochup_fetch_moodle_courses()
        test_moochup_get_course_documents()
        print("\n" + "=" * 60)
        print("✓ All tests passed!")
    except AssertionError as e:
        print(f"\n✗ Test failed: {e}")
    except Exception as e:
        print(f"\n✗ Error: {e}")
