"""
Test script to check which Moodle Web Service API functions are available.
Tests different module types to determine which APIs need to be enabled.
"""

import json
import logging
import os
import time
from pathlib import Path

from azure.identity import DefaultAzureCredential
from azure.keyvault.secrets import SecretClient

from src.loaders.APICaller import APICaller
from src.loaders.moodle import Moodle

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def setup_production_moodle():
    """Setup Moodle client with Production credentials from Lab Key Vault"""
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


# Modul-Typen und ihre API-Funktionen
MODULE_TYPE_TESTS = {
    "folder": {
        "description": "Folder - Verzeichnisse mit Dateien",
        "test_course": 134,  # Die Welt der KI entdecken
        "api_functions": [
            {
                "name": "mod_folder_get_folders_by_courses",
                "params": lambda course_id: {"courseids[0]": course_id},
                "description": "Holt alle Folder eines Kurses"
            }
        ]
    },
    "book": {
        "description": "Book - Mehrseitige Bücher/Lernmaterialien",
        "test_course": 41,  # Artificial Intelligence
        "api_functions": [
            {
                "name": "mod_book_get_books_by_courses",
                "params": lambda course_id: {"courseids[0]": course_id},
                "description": "Holt alle Books eines Kurses"
            }
        ]
    },
    "hvp": {
        "description": "HVP - H5P Interactive Content (alternative implementation)",
        "test_course": 99,  # KI für Alle 1: Einführung in die Künstliche Intelligenz
        "api_functions": [
            {
                "name": "mod_hvp_get_hvps_by_courses",
                "params": lambda course_id: {"courseids[0]": course_id},
                "description": "Holt alle HVP Activities eines Kurses"
            }
        ]
    },
    "label": {
        "description": "Label - Text- und Medienfelder (inline content)",
        "test_course": 152,  # DHBW: Einführung in die KI
        "api_functions": [
            {
                "name": "mod_label_get_labels_by_courses",
                "params": lambda course_id: {"courseids[0]": course_id},
                "description": "Holt alle Labels eines Kurses"
            }
        ]
    },
    "lesson": {
        "description": "Lesson - Interaktive Lektionen mit Verzweigungen",
        "test_course": 51,  # LUH: Semantic Technologies
        "api_functions": [
            {
                "name": "mod_lesson_get_lessons_by_courses",
                "params": lambda course_id: {"courseids[0]": course_id},
                "description": "Holt alle Lessons eines Kurses"
            }
        ]
    },
    "resource": {
        "description": "Resource - Einzelne Dateien (PDF, etc.)",
        "test_course": 152,  # DHBW: Einführung in die KI
        "api_functions": [
            {
                "name": "mod_resource_get_resources_by_courses",
                "params": lambda course_id: {"courseids[0]": course_id},
                "description": "Holt alle Resources eines Kurses"
            }
        ]
    },
    "url": {
        "description": "URL - Externe Links",
        "test_course": 180,  # DHBW: Wissenschaftlich Arbeiten mit KI
        "api_functions": [
            {
                "name": "mod_url_get_urls_by_courses",
                "params": lambda course_id: {"courseids[0]": course_id},
                "description": "Holt alle URLs eines Kurses"
            }
        ]
    },
    "data": {
        "description": "Data - Datenbank-Aktivitäten",
        "test_course": 313,  # EU AI Act Essentials
        "api_functions": [
            {
                "name": "mod_data_get_databases_by_courses",
                "params": lambda course_id: {"courseids[0]": course_id},
                "description": "Holt alle Database Activities eines Kurses"
            }
        ]
    },
    "quiz": {
        "description": "Quiz - Prüfungen und Tests",
        "test_course": 313,
        "api_functions": [
            {
                "name": "mod_quiz_get_quizzes_by_courses",
                "params": lambda course_id: {"courseids[0]": course_id},
                "description": "Holt alle Quizzes eines Kurses"
            }
        ]
    },
    "glossary": {
        "description": "Glossary - Begriffslexikon",
        "test_course": 313,
        "api_functions": [
            {
                "name": "mod_glossary_get_glossaries_by_courses",
                "params": lambda course_id: {"courseids[0]": course_id},
                "description": "Holt alle Glossaries eines Kurses"
            },
            {
                "name": "mod_glossary_get_entries_by_letter",
                "params": lambda glossary_id: {"id": glossary_id, "letter": "ALL", "from": 0, "limit": 10},
                "description": "Holt Einträge eines Glossars",
                "needs_instance_id": True
            }
        ]
    },
    "forum": {
        "description": "Forum - Diskussionsforen",
        "test_course": 313,
        "api_functions": [
            {
                "name": "mod_forum_get_forums_by_courses",
                "params": lambda course_id: {"courseids[0]": course_id},
                "description": "Holt alle Foren eines Kurses"
            }
        ]
    },
    "assign": {
        "description": "Assignment - Aufgaben/Einreichungen",
        "test_course": 313,
        "api_functions": [
            {
                "name": "mod_assign_get_assignments",
                "params": lambda course_id: {"courseids[0]": course_id},
                "description": "Holt alle Assignments eines Kurses"
            }
        ]
    }
}


def test_api_function(moodle, function_name, params, description):
    """
    Testet eine einzelne API-Funktion
    
    Returns:
        tuple: (success: bool, response: dict or None, error: str or None)
    """
    logger.info(f"  Testing: {function_name}")
    logger.info(f"    Description: {description}")
    
    try:
        caller = APICaller(
            url=moodle.api_endpoint,
            params=moodle.function_params,
            wsfunction=function_name,
            **params
        )

        start_time = time.perf_counter()
        response = caller.getJSON()
        duration = time.perf_counter() - start_time
        logger.info(f"    Duration: {duration:.2f}s")
        
        # Check if response has data
        result_count = 0
        if isinstance(response, dict):
            # Count items in various possible response structures
            for key in ["books", "quizzes", "glossaries", "forums", "urls", "assignments", "entries"]:
                if key in response:
                    result_count = len(response[key])
                    break
        elif isinstance(response, list):
            result_count = len(response)
        
        logger.info(f"    ✅ SUCCESS - Found {result_count} items")
        return True, response, None
        
    except Exception as e:
        error_str = str(e)
        if "accessexception" in error_str.lower():
            logger.warning(f"    ❌ ACCESS DENIED - Function not enabled")
            return False, None, "Access denied - function not enabled in web service"
        else:
            logger.error(f"    ❌ ERROR: {error_str[:200]}")
            return False, None, error_str


def get_module_instance_from_course(moodle, course_id, modname):
    """
    Holt die Instance-ID eines Moduls aus core_course_get_contents
    """
    try:
        caller = APICaller(
            url=moodle.api_endpoint,
            params=moodle.function_params,
            wsfunction="core_course_get_contents",
            courseid=course_id
        )
        topics = caller.getJSON()
        
        for topic in topics:
            for module in topic.get("modules", []):
                if module.get("modname") == modname:
                    return module.get("instance")
        
        return None
    except Exception as e:
        logger.error(f"Failed to get module instance: {e}")
        return None


def test_module_type(moodle, module_type, config):
    """Testet alle API-Funktionen für einen Modultyp"""
    
    logger.info("\n" + "=" * 80)
    logger.info(f"TESTING: {module_type.upper()}")
    logger.info("=" * 80)
    logger.info(f"Description: {config['description']}")
    logger.info(f"Test Course: {config['test_course']}")
    
    output_dir = Path(__file__).parent / "api_test_results" / module_type
    output_dir.mkdir(parents=True, exist_ok=True)
    
    results = {
        "module_type": module_type,
        "description": config["description"],
        "test_course": config["test_course"],
        "functions_tested": [],
        "summary": {
            "total": 0,
            "success": 0,
            "failed": 0
        }
    }
    
    # Special case: No API needed
    if not config["api_functions"]:
        logger.info("  ℹ️  No special API needed - uses core_course_get_contents")
        results["note"] = "Available via core_course_get_contents in contents[] array"
        
        # Save result
        with open(output_dir / "test_result.json", "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2, ensure_ascii=False)
        
        return results
    
    # Test each API function
    for idx, func_config in enumerate(config["api_functions"]):
        func_name = func_config["name"]
        func_desc = func_config["description"]
        needs_instance = func_config.get("needs_instance_id", False)
        
        # Get parameters
        if needs_instance:
            logger.info(f"\n  Function requires instance ID - fetching from course...")
            instance_id = get_module_instance_from_course(moodle, config["test_course"], module_type)
            if not instance_id:
                logger.warning(f"    ⚠️  No {module_type} found in course {config['test_course']}")
                results["functions_tested"].append({
                    "name": func_name,
                    "description": func_desc,
                    "status": "skipped",
                    "reason": f"No {module_type} module found in test course"
                })
                continue
            params = func_config["params"](instance_id)
        else:
            params = func_config["params"](config["test_course"])
        
        # Test function
        success, response, error = test_api_function(moodle, func_name, params, func_desc)
        
        results["summary"]["total"] += 1
        if success:
            results["summary"]["success"] += 1
        else:
            results["summary"]["failed"] += 1
        
        # Store result
        func_result = {
            "name": func_name,
            "description": func_desc,
            "status": "success" if success else "failed",
            "params_used": params
        }
        
        if success:
            # Save response
            response_file = output_dir / f"{idx}_{func_name}_response.json"
            with open(response_file, "w", encoding="utf-8") as f:
                json.dump(response, f, indent=2, ensure_ascii=False)
            func_result["response_file"] = str(response_file.name)
        else:
            func_result["error"] = error
        
        results["functions_tested"].append(func_result)
    
    # Save summary
    with open(output_dir / "test_result.json", "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    
    logger.info(f"\n  📊 Results: {results['summary']['success']}/{results['summary']['total']} successful")
    logger.info(f"  💾 Saved to: {output_dir}")
    
    return results


def run_api_tests(module_types=None):
    """Führt die API-Tests für die angegebenen Moodle-Modultypen aus.

    Args:
        module_types: Liste von Modultypen (Keys aus MODULE_TYPE_TESTS) oder None,
            um alle konfigurierten Typen zu testen.

    Returns:
        list[dict]: Ergebnisobjekte pro Modultyp (wie bislang in main).
    """
    logger.info("=" * 80)
    logger.info("MOODLE API FUNCTION AVAILABILITY TEST")
    logger.info("=" * 80)
    
    # Setup
    moodle = setup_production_moodle()
    logger.info(f"Connected to: {moodle.base_url}\n")
    
    # Determine which types to test
    if module_types is None:
        types_to_test = MODULE_TYPE_TESTS.keys()
    else:
        types_to_test = [t for t in module_types if t in MODULE_TYPE_TESTS]
    
    logger.info(f"Testing {len(types_to_test)} module type(s): {', '.join(types_to_test)}\n")
    
    # Run tests
    all_results = []
    for module_type in types_to_test:
        config = MODULE_TYPE_TESTS[module_type]
        result = test_module_type(moodle, module_type, config)
        all_results.append(result)
    
    # Final summary
    logger.info("\n" + "=" * 80)
    logger.info("FINAL SUMMARY")
    logger.info("=" * 80)
    
    for result in all_results:
        status = "✅" if result.get("note") or result["summary"].get("success", 0) == result["summary"].get("total", 1) else "⚠️"
        logger.info(f"{status} {result['module_type']:15s} - {result['description']}")
        if "note" in result:
            logger.info(f"     → {result['note']}")
        elif result["summary"]["total"] > 0:
            logger.info(f"     → {result['summary']['success']}/{result['summary']['total']} APIs available")
    
    logger.info("\n" + "=" * 80)
    logger.info("REQUIRED API FUNCTIONS TO REQUEST FROM ADMIN:")
    logger.info("=" * 80)
    
    failed_functions = []
    for result in all_results:
        for func in result.get("functions_tested", []):
            if func["status"] == "failed":
                failed_functions.append((result["module_type"], func["name"], func["description"]))
    
    if failed_functions:
        for mod_type, func_name, func_desc in failed_functions:
            logger.info(f"  • {func_name}")
            logger.info(f"      Module: {mod_type}")
            logger.info(f"      Purpose: {func_desc}")
    else:
        logger.info("  ✅ All tested functions are available!")

    logger.info("\n" + "=" * 80)

    return all_results


def main(module_types=None):
    """CLI-Wrapper um run_api_tests, damit das Skript direkt ausführbar bleibt."""
    return run_api_tests(module_types=module_types)


if __name__ == "__main__":
    # Test quiz module type
    main(module_types=["quiz"])
    
    # To test all:
    # main()
    
    # To test multiple:
    # main(module_types=["folder", "book", "hvp", "label", "lesson", "resource", "url", "data"])
