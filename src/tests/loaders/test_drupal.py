"""
Script to retrieve and inspect all Drupal content, replicating the behavior from get_data.py.
Uses actual production data from ki-campus.org via environment variables.

Usage:
    python src/tests/loaders/test_drupal.py
"""
import logging
import json
from datetime import datetime
from pathlib import Path
from src.loaders.drupal import Drupal
from src.env import env


def main():
    """Fetch all Drupal content and save to JSON"""
    print("Initializing Drupal connection with production credentials...")
    print(f"Connecting to: {env.DRUPAL_URL}")
    
    try:
        # Replicate the exact call from get_data.py
        drupal_content = Drupal(
            base_url=env.DRUPAL_URL,
            username=env.DRUPAL_USERNAME,
            client_id=env.DRUPAL_CLIENT_ID,
            client_secret=env.DRUPAL_CLIENT_SECRET,
            grant_type=env.DRUPAL_GRANT_TYPE,
        ).extract()
        
        print(f"✓ Successfully extracted {len(drupal_content)} documents\n")
        
        # Prepare data structure for JSON output
        output_data = {
            "retrieval_timestamp": datetime.now().isoformat(),
            "total_documents": len(drupal_content),
            "documents": []
        }
        
        # Convert all documents to JSON-serializable format
        for i, doc in enumerate(drupal_content):
            output_data["documents"].append({
                "index": i,
                "metadata": doc.metadata,
                "text": doc.text,
                "text_length": len(doc.text)
            })
            
            # Print progress every 50 documents
            if (i + 1) % 50 == 0:
                print(f"Processed {i + 1}/{len(drupal_content)} documents...")
        
        # Display summary by document type
        type_counts = {}
        for doc in drupal_content:
            doc_type = doc.metadata.get("type", "unknown")
            type_counts[doc_type] = type_counts.get(doc_type, 0) + 1
        
        print(f"\n{'='*80}")
        print("DOCUMENT SUMMARY")
        print(f"{'='*80}")
        for doc_type, count in sorted(type_counts.items()):
            print(f"  {doc_type}: {count} documents")
        
        # Display preview of first document
        if drupal_content:
            first_doc = drupal_content[0]
            print(f"\n{'='*80}")
            print("FIRST DOCUMENT PREVIEW")
            print(f"{'='*80}")
            print(f"\n--- METADATA ---")
            print(json.dumps(first_doc.metadata, indent=2, ensure_ascii=False))
            
            print(f"\n--- TEXT (first 500 chars) ---")
            text_preview = first_doc.text[:500] if len(first_doc.text) > 500 else first_doc.text
            print(text_preview)
            if len(first_doc.text) > 500:
                print(f"\n... (truncated, total length: {len(first_doc.text)} characters)")
        
    except Exception as e:
        print(f"✗ Error during extraction: {str(e)}")
        import traceback
        traceback.print_exc()
        return

    # Save to JSON file
    output_file = Path("drupal_documents.json")
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(output_data, f, indent=2, ensure_ascii=False)

    print(f"\n{'='*80}")
    print("Document retrieval complete!")
    print(f"✓ Results saved to: {output_file.absolute()}")
    print(f"{'='*80}")


if __name__ == "__main__":
    # Configure logging with force=True to override any existing configuration
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        force=True
    )
    main()
