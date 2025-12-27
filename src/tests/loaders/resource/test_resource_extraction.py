"""
Test-Skript zum Testen der Resource-Extraktion.

Testet die Integration des RESOURCE-Modultyps mit PDF-Extraktion.
"""

import logging
import os
import sys
from pathlib import Path

from azure.identity import DefaultAzureCredential
from azure.keyvault.secrets import SecretClient

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from src.loaders.moodle import Moodle

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def setup_production_moodle():
    """Setup Moodle with Production Credentials from Azure Key Vault."""
    key_vault_name = os.environ.get("KEY_VAULT_NAME", "kicwa-keyvault-lab")
    key_vault_uri = f"https://{key_vault_name}.vault.azure.net/"
    credential = DefaultAzureCredential()
    secret_client = SecretClient(vault_url=key_vault_uri, credential=credential)
    
    prod_url = secret_client.get_secret("DATA-SOURCE-PRODUCTION-MOODLE-URL").value
    prod_token = secret_client.get_secret("DATA-SOURCE-PRODUCTION-MOODLE-TOKEN").value
    
    moodle = Moodle()
    moodle.base_url = prod_url
    moodle.api_endpoint = f"{prod_url}webservice/rest/server.php"
    moodle.token = prod_token
    moodle.function_params["wstoken"] = prod_token
    moodle.download_params["token"] = prod_token
    
    logger.info(f"✅ Connected to Production Moodle: {prod_url}")
    return moodle


def test_resource_extraction():
    """Testet die Extraktion eines Resource-Moduls mit PDF."""
    
    moodle = setup_production_moodle()
    
    # Test mit Kurs 121, Modul 14458 (Resource mit PDF)
    test_course_id = 121
    test_module_id = 14458
    
    print(f"\n{'='*80}")
    print(f"Teste Resource-Extraktion für Modul {test_module_id} in Kurs {test_course_id}")
    print(f"{'='*80}\n")
    
    # Hole alle Kurse
    courses = moodle.get_courses()
    test_course = None
    
    for course in courses:
        if course.id == test_course_id:
            test_course = course
            break
    
    if not test_course:
        print(f"❌ Kurs {test_course_id} nicht gefunden!")
        return
    
    print(f"✓ Kurs gefunden: {test_course.fullname}\n")
    
    # Hole Kurs-Inhalte
    course_content = moodle.get_course_contents(test_course.id)
    
    # Suche Modul 14458
    target_module = None
    target_topic = None
    
    for topic in course_content:
        for module in topic.modules:
            if module.id == test_module_id:
                target_module = module
                target_topic = topic
                break
        if target_module:
            break
    
    if not target_module:
        print(f"❌ Modul {test_module_id} nicht gefunden!")
        return
    
    print(f"✓ Modul gefunden!\n")
    
    # Teste Extraktion für Modul 14458
    topic = target_topic
    module = target_module
    
    print(f"{'-'*80}")
    print(f"Modul ID: {module.id}")
    print(f"Name: {module.name}")
    print(f"Modultyp: {module.modname}")
    print(f"Topic: {topic.name}")
    
    if module.contents:
        file_info = module.contents[0]
        print(f"Datei: {file_info.filename}")
        print(f"Dateityp: {file_info.type}")
        print(f"URL: {file_info.fileurl}")
    
    # Extrahiere Inhalt
    print("\nStarte Extraktion...")
    
    err = moodle.extract_resource(module)
    
    if err:
        print(f"❌ Fehler bei Extraktion: {err}")
    elif module.resource:
        resource = module.resource
        print(f"✓ Extraktion erfolgreich!")
        print(f"\nResource-Details:")
        print(f"  - Dateiname: {resource.filename}")
        print(f"  - MIME-Type: {resource.mimetype}")
        print(f"  - Unterstützt: {resource.is_supported}")
        print(f"  - PDF: {resource.is_pdf}")
        
        if resource.extracted_text:
            text_preview = resource.extracted_text[:500]
            print(f"\nExtrahierter Text (erste 500 Zeichen):")
            print(f"{'-'*80}")
            print(text_preview)
            print(f"{'-'*80}")
            print(f"\nGesamtlänge: {len(resource.extracted_text)} Zeichen")
        else:
            print("\n⚠️  Kein Text extrahiert (möglicherweise leeres PDF oder Bild-PDF)")
        
        # Teste Document-Generierung
        print("\nTeste Document-Generierung...")
        doc = module.to_document(test_course.id)
        print(f"✓ Document erstellt")
        print(f"  - Metadaten: {doc.metadata}")
        print(f"  - Text-Länge: {len(doc.text)} Zeichen")
        
        if "--- Dokument" in doc.text:
            print(f"  - ✓ Resource-Inhalt in Document enthalten")
        else:
            print(f"  - ⚠️  Resource-Inhalt NICHT in Document gefunden!")
    else:
        print(f"⚠️  module.resource ist None nach Extraktion")
    
    print(f"\n{'='*80}")
    print("Test abgeschlossen!")
    print(f"{'='*80}\n")


if __name__ == "__main__":
    test_resource_extraction()
