"""
Test-Skript: Untersucht die mod_folder_get_folders_by_courses API.

Dieses Skript testet:
1. Was mod_folder_get_folders_by_courses zurückgibt
2. Wie Dateien in Folder-Modulen abgerufen werden können
3. Vergleich mit core_course_get_contents für Folder-Module
"""

import json
import logging
import os
from pathlib import Path

from azure.identity import DefaultAzureCredential
from azure.keyvault.secrets import SecretClient

from src.loaders.APICaller import APICaller
from src.loaders.moodle import Moodle

# Logging Setup
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s:%(name)s: %(message)s')
logger = logging.getLogger(__name__)

# ⚙️ KONFIGURATION
TEST_COURSE_ID = 41  # Beispiel-Kurs zum Testen
OUTPUT_DIR = Path(__file__).parent / "api_outputs"
OUTPUT_DIR.mkdir(exist_ok=True)


def setup_production_moodle():
    """Setup Moodle mit Production Credentials aus Azure Key Vault."""
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
    
    return moodle


def test_folder_api(moodle: Moodle, course_id: int):
    """
    Testet mod_folder_get_folders_by_courses API.
    
    Args:
        moodle: Moodle instance mit Production Setup
        course_id: ID des Kurses zum Testen
    """
    logger.info(f"\n{'='*80}")
    logger.info(f"TEST 1: mod_folder_get_folders_by_courses für Kurs {course_id}")
    logger.info(f"{'='*80}")
    
    try:
        # API Call: mod_folder_get_folders_by_courses
        caller = APICaller(
            url=moodle.api_endpoint,
            params={**moodle.function_params, "courseids[0]": course_id},
            wsfunction="mod_folder_get_folders_by_courses"
        )
        
        folders_response = caller.getJSON()
        
        # Speichere vollständige Response
        output_file = OUTPUT_DIR / f"mod_folder_get_folders_by_courses_course_{course_id}.json"
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(folders_response, f, indent=2, ensure_ascii=False)
        
        logger.info(f"✅ API Response gespeichert: {output_file}")
        
        # Analysiere Response
        folders = folders_response.get("folders", [])
        logger.info(f"\n📁 Gefundene Folder: {len(folders)}")
        
        if folders:
            logger.info("\n--- Folder Übersicht ---")
            for idx, folder in enumerate(folders, 1):
                logger.info(f"\nFolder {idx}:")
                logger.info(f"  ID: {folder.get('id')}")
                logger.info(f"  Name: {folder.get('name')}")
                logger.info(f"  CourseModule ID: {folder.get('coursemodule')}")
                logger.info(f"  Course ID: {folder.get('course')}")
                logger.info(f"  Intro: {folder.get('intro', '')[:100]}...")
                logger.info(f"  Display: {folder.get('display')}")
                logger.info(f"  Revision: {folder.get('revision')}")
                logger.info(f"  TimeModified: {folder.get('timemodified')}")
                
                # Wichtig: Wo sind die Dateien?
                logger.info(f"  Alle Felder: {list(folder.keys())}")
        
        return folders
        
    except Exception as e:
        logger.error(f"❌ Fehler bei mod_folder_get_folders_by_courses: {e}")
        return []


def test_core_course_get_contents_for_folders(moodle: Moodle, course_id: int):
    """
    Testet core_course_get_contents und filtert Folder-Module.
    
    Args:
        moodle: Moodle instance mit Production Setup
        course_id: ID des Kurses zum Testen
    """
    logger.info(f"\n{'='*80}")
    logger.info(f"TEST 2: core_course_get_contents - Folder Module")
    logger.info(f"{'='*80}")
    
    try:
        # API Call: core_course_get_contents
        caller = APICaller(
            url=moodle.api_endpoint,
            params=moodle.function_params,
            wsfunction="core_course_get_contents",
            courseid=course_id
        )
        
        course_contents = caller.getJSON()
        
        # Finde alle Folder-Module
        folder_modules = []
        for topic in course_contents:
            for module in topic.get("modules", []):
                if module.get("modname") == "folder":
                    folder_modules.append(module)
        
        logger.info(f"\n📁 Gefundene Folder Module in core_course_get_contents: {len(folder_modules)}")
        
        if folder_modules:
            # Speichere Folder-Module
            output_file = OUTPUT_DIR / f"core_course_get_contents_folders_course_{course_id}.json"
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(folder_modules, f, indent=2, ensure_ascii=False)
            
            logger.info(f"✅ Folder Module gespeichert: {output_file}")
            
            logger.info("\n--- Folder Module Details (aus core_course_get_contents) ---")
            for idx, module in enumerate(folder_modules, 1):
                logger.info(f"\nFolder Modul {idx}:")
                logger.info(f"  ID: {module.get('id')}")
                logger.info(f"  Name: {module.get('name')}")
                logger.info(f"  Instance: {module.get('instance')}")
                logger.info(f"  ModName: {module.get('modname')}")
                logger.info(f"  URL: {module.get('url')}")
                
                # WICHTIG: contents Feld - enthält die Dateien!
                contents = module.get('contents', [])
                logger.info(f"  Contents (Dateien): {len(contents)}")
                
                if contents:
                    logger.info(f"\n  --- Dateien in diesem Folder ---")
                    for file_idx, file_content in enumerate(contents, 1):
                        logger.info(f"\n    Datei {file_idx}:")
                        logger.info(f"      Filename: {file_content.get('filename')}")
                        logger.info(f"      Filepath: {file_content.get('filepath')}")
                        logger.info(f"      Type: {file_content.get('type')}")
                        logger.info(f"      Filesize: {file_content.get('filesize', 0)} bytes")
                        logger.info(f"      FileURL: {file_content.get('fileurl')}")
                        logger.info(f"      MimeType: {file_content.get('mimetype')}")
                        logger.info(f"      TimeCreated: {file_content.get('timecreated')}")
                        logger.info(f"      TimeModified: {file_content.get('timemodified')}")
        
        return folder_modules
        
    except Exception as e:
        logger.error(f"❌ Fehler bei core_course_get_contents: {e}")
        return []


def test_file_download(moodle: Moodle, fileurl: str, filename: str):
    """
    Testet das Herunterladen einer Datei aus einem Folder.
    
    Args:
        moodle: Moodle instance
        fileurl: URL der Datei
        filename: Name der Datei
    """
    logger.info(f"\n{'='*80}")
    logger.info(f"TEST 3: Datei-Download Test")
    logger.info(f"{'='*80}")
    logger.info(f"Datei: {filename}")
    logger.info(f"URL: {fileurl}")
    
    try:
        caller = APICaller(url=fileurl, params=moodle.download_params)
        caller.get()
        
        content_type = caller.response.headers.get('Content-Type', '')
        content_length = caller.response.headers.get('Content-Length', 0)
        
        logger.info(f"\n✅ Download erfolgreich!")
        logger.info(f"  Content-Type: {content_type}")
        logger.info(f"  Content-Length: {content_length} bytes")
        logger.info(f"  Status Code: {caller.response.status_code}")
        
        # Erste 200 Bytes als Preview
        preview = caller.response.content[:200]
        logger.info(f"\n  Preview (erste 200 bytes): {preview[:100]}...")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Fehler beim Download: {e}")
        return False


def compare_apis(folders_from_mod_api, folders_from_core_api):
    """
    Vergleicht die Rückgaben beider APIs.
    
    Args:
        folders_from_mod_api: Ergebnis von mod_folder_get_folders_by_courses
        folders_from_core_api: Folder-Module aus core_course_get_contents
    """
    logger.info(f"\n{'='*80}")
    logger.info(f"VERGLEICH: mod_folder_get_folders_by_courses vs core_course_get_contents")
    logger.info(f"{'='*80}")
    
    logger.info(f"\nAnzahl Folders:")
    logger.info(f"  mod_folder_get_folders_by_courses: {len(folders_from_mod_api)}")
    logger.info(f"  core_course_get_contents (folder): {len(folders_from_core_api)}")
    
    # Vergleiche verfügbare Felder
    if folders_from_mod_api and folders_from_core_api:
        logger.info(f"\nVerfügbare Felder im Vergleich:")
        logger.info(f"  mod_folder API: {list(folders_from_mod_api[0].keys())}")
        logger.info(f"  core_course API: {list(folders_from_core_api[0].keys())}")
        
        # Wichtig: Welche API hat die Datei-Liste?
        mod_has_files = 'contents' in folders_from_mod_api[0]
        core_has_files = 'contents' in folders_from_core_api[0]
        
        logger.info(f"\n📂 Datei-Listen verfügbar:")
        logger.info(f"  mod_folder API hat 'contents': {mod_has_files}")
        logger.info(f"  core_course API hat 'contents': {core_has_files}")
        
        if core_has_files:
            logger.info(f"\n✅ ERGEBNIS: core_course_get_contents liefert direkt die Datei-Liste!")
            logger.info(f"   → Wir können Folder-Module wie Resource-Module behandeln")
        
        if mod_has_files:
            logger.info(f"\n✅ HINWEIS: mod_folder API liefert auch 'contents'")


def main():
    """Hauptfunktion: Führt alle Tests aus."""
    logger.info("🔧 Setup Production Moodle...")
    moodle = setup_production_moodle()
    logger.info("✅ Moodle Setup abgeschlossen\n")
    
    # Test 1: mod_folder_get_folders_by_courses
    folders_from_mod_api = test_folder_api(moodle, TEST_COURSE_ID)
    
    # Test 2: core_course_get_contents (Filter: folder)
    folders_from_core_api = test_core_course_get_contents_for_folders(moodle, TEST_COURSE_ID)
    
    # Test 3: Datei-Download (wenn Dateien gefunden)
    if folders_from_core_api and folders_from_core_api[0].get('contents'):
        first_file = folders_from_core_api[0]['contents'][0]
        test_file_download(
            moodle, 
            first_file.get('fileurl'), 
            first_file.get('filename')
        )
    
    # Vergleich der APIs
    compare_apis(folders_from_mod_api, folders_from_core_api)
    
    logger.info(f"\n{'='*80}")
    logger.info("✅ ALLE TESTS ABGESCHLOSSEN")
    logger.info(f"{'='*80}")
    logger.info(f"\n📁 Ausgabedateien: {OUTPUT_DIR}")
    logger.info("\nNächste Schritte:")
    logger.info("1. JSON-Dateien in api_outputs/ prüfen")
    logger.info("2. Entscheiden: Welche API verwenden?")
    logger.info("3. extract_folder() Methode in moodle.py implementieren")


if __name__ == "__main__":
    main()
