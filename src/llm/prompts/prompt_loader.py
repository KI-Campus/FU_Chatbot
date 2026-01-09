from pathlib import Path

BASE_PROMPT_DIR = Path("src/llm/prompts")

def load_prompt(prompt_name: str) -> str:
    """
    Lädt eine Prompt-Datei aus src/llm/prompts anhand des Namens (ohne .txt).

    :param prompt_name: Dateiname ohne Endung, z. B. "system_prompt"
    :return: Inhalt der Prompt-Datei als String
    """
    file_path = BASE_PROMPT_DIR / f"{prompt_name}.txt"

    if not file_path.is_file():
        raise FileNotFoundError(f"Prompt nicht gefunden: {file_path}")

    return file_path.read_text(encoding="utf-8")