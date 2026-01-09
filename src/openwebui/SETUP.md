# OpenWebUI Arena Mode - Setup & Neustart Anleitung

Diese Anleitung beschreibt, wie du nach einem Neustart oder in einer neuen Session die OpenWebUI Arena Mode Umgebung wieder startest.

## 🚀 Quick Start (Nach Neustart)

**Alle 3 Services starten (nur einmal eingeben):**

```bash
cd /Users/browse/FU_Chatbot_RD_Zitho
```bash
# Mit echten Azure OpenAI Antworten (empfohlen)
export KEY_VAULT_NAME="kicwa-keyvault-lab"
/Users/browse/.pyenv/versions/3.11.7/bin/python -m uvicorn src.openwebui.openwebui_api_llm:app --host 0.0.0.0 --port 8001 > /tmp/llm_api.log 2>&1 &
```

**Oder für schnelle Tests ohne Azure (Mock API):**
```bash
/Users/browse/.pyenv/versions/3.11.7/bin/python -m uvicorn src.openwebui.openwebui_api_simple:app --host 0.0.0.0 --port 8001 > /tmp/api.log 2>&1 &
```
```bash
cd /Users/browse/FU_Chatbot_RD_Zitho

# Starte Mock-API (schnell, für Tests)
/Users/browse/.pyenv/versions/3.11.7/bin/python -m uvicorn src.openwebui.openwebui_api_simple:app --host 0.0.0.0 --port 8001 > /tmp/api.log 2>&1 &
```

**Oder für echte Azure OpenAI Antworten:**

```bash
# Erst: Azure CLI Login (falls Session abgelaufen oder nach Neustart)
az login --tenant "c6ff58bc-993e-4bdb-8d10-6013e2cd361f"

# Dann: API mit Lab Key Vault starten
export KEY_VAULT_NAME="kicwa-keyvault-lab"
/Users/browse/.pyenv/versions/3.11.7/bin/python -m uvicorn src.openwebui.openwebui_api_llm:app --host 0.0.0.0 --port 8001 > /tmp/llm_api.log 2>&1 &
```

**Verifiziere dass API läuft:**
```bash
curl http://localhost:8001/v1/models
# Sollte beide Modelle zeigen: kicampus-original, kicampus-improved
```

### 2. OpenWebUI Docker Container starten

```bash
# Entferne alte Container (falls vorhanden)
docker rm -f openwebui 2>/dev/null

# Starte OpenWebUI
docker run -d \
  --name openwebui \
  -p 3001:8080 \
  -v open-webui:/app/backend/data \
  --add-host=host.docker.internal:host-gateway \
  ghcr.io/open-webui/open-webui:main

# Warte ~15 Sekunden bis Container gestartet ist
sleep 15
### 3. Öffne die Dienste im VS Code Simple Browser

```bash
# Terminal: Simple Browser öffnen (oder manuell Cmd+Shift+P → Simple Browser: Show)
```

**Drei Browser-Tabs:**
1. **OpenWebUI Chat** → http://localhost:3001 (Zum Chatten)
2. **Voting Dashboard** → http://localhost:8002 (Zum Voten & Statistiken)VS Code:
1. **Drücke** `Cmd+Shift+P` (Mac) oder `Ctrl+Shift+P` (Windows/Linux)
2. **Tippe:** `Simple Browser: Show`
3. **URL eingeben:** `http://localhost:3001`

**Oder** nutze GitHub Copilot Chat:
```
@workspace öffne http://localhost:3001 im Simple Browser
```

### 4. OpenWebUI konfigurieren (Einmalig pro Installation)

Im Simple Browser:

1. **Anmelden/Registrieren** (oder Skip)
2. **Gehe zu:** Settings ⚙️ → Connections → OpenAI
3. **Klicke:** "Add Connection"
4. **Fülle aus:**
### 5. Arena Mode aktivieren & Chatten

1. **Neuer Chat** erstellen
2. **Klicke auf Modell-Dropdown** (oben)
3. **Wähle:** "Arena (Side-by-side)" oder "Compare Models"
4. **Wähle beide Modelle:**
   - ✅ `kicampus-original`
   - ✅ `kicampus-improved`
5. **Stelle eine Frage** - beide Modelle antworten parallel!

---

## 🏆 Voting System

Nach jedem Chat im Arena Mode können die Antworten bewertet werden.

### Workflow:

1. **Chat in OpenWebUI** (http://localhost:3001)
   - Arena Mode aktivieren
   - Beide Modelle fragen
   - Antworten vergleichen

2. **Voting UI öffnen** (http://localhost:8002)
   - Alle Vergleiche werden automatisch angezeigt
   - **Vote abgeben**: 👈 Model A / 🤝 Unentschieden / 👉 Model B
   - **Optional**: Kommentar hinzufügen
   - **Submit** klicken

3. **Statistiken sehen**
   - Win Rate von Model A vs B
   - Anzahl Unentschieden
   - Live-Updates

### Alternative: CLI Voting Tool

Falls du lieber im Terminal votieren möchtest:

```bash
/Users/browse/.pyenv/versions/3.11.7/bin/python src/openwebui/arena_voting.py
```

Features:
- ✅ Interaktive Fragen stellen
- ✅ Side-by-Side Vergleich
- ✅ Voting mit Kommentaren
- ✅ Live Statistiken

**Beispiel Befehle:**

```bash
# Statistiken anzeigen
python src/openwebui/arena_voting.py --stats

# Alle Votes exportieren
python src/openwebui/arena_voting.py --export results.json
```

### Daten speichern

Alle Votes werden persistent in JSONL Format gespeichert:
```
src/openwebui/data/arena_votes.jsonl
```

Format je Zeile:
```json
{
  "id": "uuid",
  "question": "Die Frage",
  "model_a": "kicampus-original",
  "answer_a": "Antwort A...",
  "model_b": "kicampus-improved",
  "answer_b": "Antwort B...",
  "vote": "A|B|tie",
  "vote_timestamp": "2025-12-10T12:30:00",
  "comment": "Optionaler Kommentar"
}
```
2. **Klicke auf Modell-Dropdown** (oben)
3. **Wähle:** "Arena (Side-by-side)" oder "Compare Models"
4. **Wähle beide Modelle:**
   - ✅ `kicampus-original`
   - ✅ `kicampus-improved`
5. **Stelle eine Frage** - beide Modelle antworten parallel!

---

## 🔧 Troubleshooting

### Problem: API startet nicht

**Prüfe ob Port 8001 schon belegt ist:**
```bash
lsof -i :8001
# Falls ein Prozess läuft:
pkill -f "uvicorn"
```

**Prüfe API Logs:**
```bash
tail -50 /tmp/api.log
# oder
tail -50 /tmp/llm_api.log
```

### Problem: OpenWebUI Container startet nicht

**Prüfe ob Port 3001 belegt ist:**
```bash
lsof -i :3001
```

**Entferne alle OpenWebUI Container:**
```bash
docker ps -a | grep openwebui
docker rm -f $(docker ps -a | grep openwebui | awk '{print $1}')
```

**Prüfe Container Logs:**
```bash
docker logs openwebui
```

### Problem: Simple Browser zeigt leere Seite

1. **Klicke auf Refresh** im Simple Browser
2. **Warte 30 Sekunden** - Container braucht Zeit zum Starten
3. **Prüfe mit curl ob OpenWebUI antwortet:**
   ```bash
   curl http://localhost:3001 | head -c 200
   ```
4. **Falls immer noch leer:** Öffne in normalem Browser `http://localhost:3001`

### Problem: OpenWebUI findet keine Modelle

**Base URL prüfen:**
- ✅ Richtig: `http://host.docker.internal:8001/v1`
- ❌ Falsch: `http://localhost:8001/v1` (funktioniert nicht in Docker)

**API Status prüfen:**
```bash
curl http://localhost:8001/v1/models | python3 -m json.tool
```

### Problem: Azure Authentication abgelaufen (für echte LLMs)
## 🛑 Alles stoppen

**Wenn du fertig bist:**

```bash
# Stoppe alle uvicorn Prozesse (API + Voting UI)
pkill -f "uvicorn"

# Stoppe OpenWebUI Container
docker stop openwebui
```

**Oder behalte beides laufend** für spätere Tests! uvicorn src.openwebui.openwebui_api_llm:app --host 0.0.0.0 --port 8001 > /tmp/llm_api.log 2>&1 &
```

**Testen ob echte Antworten kommen:**
```bash
curl -X POST http://localhost:8001/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model":"kicampus-original","messages":[{"role":"user","content":"Was ist KI?"}],"stream":false}' \
  | python3 -c "import sys, json; print(json.load(sys.stdin)['choices'][0]['message']['content'][:200])"
```

Sollte eine echte KI-Definition zurückgeben, nicht "[Original] Demo-Antwort..."

---

## 📊 Verfügbare Modelle

### `kicampus-original`
- **Beschreibung:** Standard-Version des KI-Campus Chatbots
- **Chat-History:** 10 Nachrichten
- **Verwendung:** Baseline für Vergleiche

### `kicampus-improved`
- **Beschreibung:** Verbesserte Version mit erweitertem Kontext
- **Chat-History:** 15 Nachrichten
- **Verwendung:** Optimierte Version zum Vergleich

---

## 🎯 Alternative: CLI Benchmark Tool

Falls OpenWebUI nicht funktioniert, nutze das Terminal-basierte Tool:

```bash
cd /Users/browse/FU_Chatbot_RD_Zitho
/Users/browse/.pyenv/versions/3.11.7/bin/python src/openwebui/arena_benchmark_interactive.py
```

**Features:**
- ✅ Batch Mode: 5 vordefinierte Fragen
- ✅ Interaktiv: Beliebige Fragen eingeben
- ✅ Single Query: Eine Frage testen
- ✅ Side-by-Side Vergleiche mit Metriken

---

## 🛑 Alles stoppen

**Wenn du fertig bist:**

```bash
# Stoppe API
pkill -f "uvicorn"

# Stoppe OpenWebUI
docker stop openwebui
docker rm openwebui
```

**Oder behalte beides laufend** für spätere Tests!

---

## 📝 Nützliche Befehle

**Status prüfen:**
```bash
# API Status
ps aux | grep uvicorn

# Docker Status
docker ps | grep openwebui

# Ports prüfen
lsof -i :8001  # API
lsof -i :3001  # OpenWebUI
```

**Logs ansehen:**
```bash
# API Logs (Mock)
tail -f /tmp/api.log

---

## 📊 Verfügbare API Endpoints

Alle Endpoints sind dokumentiert unter: http://localhost:8001/docs

**Wichtigste Endpoints:**

```
# Chat Completions (OpenAI compatible)
POST /v1/chat/completions
GET /v1/models

# Arena Voting
POST /arena/save-comparison       # Speichern eines Vergleichs
POST /arena/vote                  # Vote abgeben
GET  /arena/statistics            # Statistiken
GET  /arena/comparisons           # Alle Vergleiche
GET  /arena/comparison/{id}       # Spezifischer Vergleich
```

---

## 🎯 Typischer Ablauf für Massentests

1. **Startup Script (einmalig)**
   ```bash
   # Alle Services starten
   ```

2. **Tägliche Tests**
   - Öffne OpenWebUI (Port 3001)
   - Aktiviere Arena Mode
   - Stelle 10-20 Fragen
   - Vergleiche Antworten

3. **Voting**
   - Öffne Voting Dashboard (Port 8002)
   - Bewerte alle Vergleiche
   - Speichern erfolgt automatisch

4. **Ergebnisse**
   - Statistiken im Dashboard
   - Export via CLI: `python arena_voting.py --export results.json`
   - Analyse der Win Rates

---

Viel Erfolg beim Benchmarking! 🚀
# OpenWebUI Logs
docker logs -f openwebui
```

**Container Management:**
```bash
# Container neu starten
docker restart openwebui

# Container stoppen
docker stop openwebui

# Container entfernen
docker rm -f openwebui

# Alle Logs löschen
docker logs openwebui --tail 0
```

---

## 🎓 Workflow für Massentests

1. **Starte beide Services** (API + OpenWebUI)
2. **Öffne OpenWebUI** im Simple Browser
3. **Aktiviere Arena Mode** und wähle beide Modelle
4. **Stelle Testfragen** - z.B.:
   - "Was ist Künstliche Intelligenz?"
   - "Erkläre Machine Learning"
   - "Was sind Neural Networks?"
   - "Wie funktioniert Deep Learning?"
   - "Nenne Anwendungen von KI"
5. **Vergleiche Antworten** side-by-side
6. **Dokumentiere Unterschiede** in Qualität, Länge, Präzision

---

## 💡 Tipps

- **Mock-API** ist schneller zum Testen der UI-Funktionalität
- **LLM-API** braucht Azure Auth aber gibt echte Antworten
- **Simple Browser** kann manchmal träge sein - refresh hilft
- **Port 3001** ist OpenWebUI, **Port 8001** ist deine API
- **host.docker.internal** ist wichtig für Docker→Host Kommunikation
- **Logs** sind dein Freund beim Debuggen

---

## 🔗 Wichtige URLs

- **OpenWebUI:** http://localhost:3001
- **API Root:** http://localhost:8001
- **API Models:** http://localhost:8001/v1/models
- **API Health:** http://localhost:8001/health

---

Viel Erfolg beim Benchmarking! 🚀
