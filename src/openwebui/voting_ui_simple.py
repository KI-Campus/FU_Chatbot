"""
Vereinfachtes Arena Voting UI - direkt und einfach
"""

import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
import requests

app = FastAPI()

# CORS mit konfigurierbaren Origins
allowed_origins = os.getenv("CORS_ORIGINS", "*").split(",")
if allowed_origins == ["*"]:
    # Development: Allow all
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )
else:
    # Production: Restrict to specific domains
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["*"],
        allow_credentials=True,
    )

@app.get("/", response_class=HTMLResponse)
def index():
    """Einfaches Voting UI"""
    api_override = os.getenv("ARENA_API_BASE", "").rstrip("/")
    html = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Arena Voting</title>
    <style>
        body {
            font-family: system-ui, -apple-system, "Segoe UI", sans-serif;
            max-width: 1000px;
            margin: 0 auto;
            padding: 24px;
            background: #f4f4f4;
            color: #1f1f1f;
        }
        h1 { margin: 0 0 12px; font-weight: 600; }
        .comparison {
            background: white;
            padding: 20px;
            margin: 15px 0;
            border-radius: 8px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
        }
        .answers {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 15px;
            margin: 15px 0;
        }
        .answer {
            padding: 12px;
            background: #fafafa;
            border: 1px solid #e2e2e2;
            border-radius: 4px;
            font-size: 13px;
            line-height: 1.5;
        }
        .buttons {
            display: flex;
            gap: 10px;
            margin: 15px 0;
        }
        button {
            flex: 1;
            padding: 10px;
            border: 1px solid #d0d0d0;
            background: #fbfbfb;
            cursor: pointer;
            border-radius: 4px;
            font-weight: 600;
        }
        button:hover { background: #ededed; }
        button.active {
            background: #333;
            color: white;
            border-color: #333;
        }
        .submit {
            width: 100%;
            background: #333;
            color: white;
            border: none;
        }
        .submit:hover { background: #1f1f1f; }
        .voted { opacity: 0.6; }
        .voted p { color: #666; font-size: 12px; }
        .error {
            background: #f8d7da;
            color: #721c24;
            padding: 12px;
            border-radius: 4px;
            margin: 10px 0;
        }
        .loading {
            text-align: center;
            color: #999;
            padding: 20px;
        }
    </style>
</head>
<body>
    <h1>Arena Vergleich</h1>
    
    <div id="container">
        <div class="loading">⏳ Lade Vergleiche...</div>
    </div>

    <script>
        // API base: allow override for direct UI (8002) vs. nginx proxy
        const API_OVERRIDE = "__API_OVERRIDE__";
        const API = (API_OVERRIDE && API_OVERRIDE.trim() !== "")
            ? API_OVERRIDE.replace(/\/$/, '')
            : (window.location.port === "8002"
                ? window.location.origin.replace(":8002", ":8001").replace(/\/$/, '')
                : window.location.origin.replace(/\/$/, ''));
        let comparisons = [];
        let currentIndex = 0;
        let selectedVote = null;
        let assignedSubset = null;
        let totalInSubset = 0;
        let votedInSubset = 0;

        // Session-Tracking via LocalStorage
        function getAssignedSubset() {
            const stored = localStorage.getItem('arena_subset');
            if (stored) {
                return parseInt(stored, 10);
            }
            return null;
        }

        function setAssignedSubset(subset) {
            localStorage.setItem('arena_subset', subset.toString());
            assignedSubset = subset;
        }

        async function assignSubsetIfNeeded() {
            assignedSubset = getAssignedSubset();
            if (assignedSubset === null) {
                try {
                    const resp = await fetch(API + '/arena/assign-subset');
                    const data = await resp.json();
                    setAssignedSubset(data.subset_id);
                    console.log('Assigned subset:', data.subset_id);
                } catch (e) {
                    console.error('Failed to assign subset:', e);
                    assignedSubset = 1; // Fallback
                }
            }
        }

        // Debug: Show we started
        document.getElementById('container').innerHTML = '<div class="loading">⏳ JavaScript läuft, starte Fetch...</div>';

        async function load() {
            const container = document.getElementById('container');
            
            // Subset zuweisen falls noch nicht geschehen
            await assignSubsetIfNeeded();
            
            container.innerHTML = '<div class="loading">⏳ Fetching Subset ' + assignedSubset + ' von ' + API + '...</div>';
            
            try {
                const resp = await fetch(API + '/arena/comparisons?subset=' + assignedSubset, {
                    method: 'GET',
                    headers: {
                        'Accept': 'application/json'
                    }
                });
                
                container.innerHTML = '<div class="loading">⏳ Response erhalten, Status: ' + resp.status + '</div>';
                
                if (!resp.ok) {
                    throw new Error('HTTP ' + resp.status + ' ' + resp.statusText);
                }
                
                const data = await resp.json();
                comparisons = data.comparisons || [];
                totalInSubset = comparisons.length;
                votedInSubset = comparisons.filter(c => c.vote).length;
                
                container.innerHTML = '<div class="loading">⏳ ' + comparisons.length + ' Vergleiche in Subset ' + assignedSubset + ' geladen...</div>';
                
                if (comparisons.length === 0) {
                    container.innerHTML = '<div class="error">⚠️ Keine Vergleiche in diesem Subset</div>';
                    return;
                }
                
                render();
            } catch (e) {
                container.innerHTML = 
                    '<div class="error">❌ Fehler beim Laden<br>' + 
                    'API: ' + API + '/arena/comparisons?subset=' + assignedSubset + '<br>' +
                    'Error: ' + e.message + '<br>' +
                    'Stack: ' + (e.stack || 'no stack') + '</div>';
            }
        }

        function render() {
            const container = document.getElementById('container');

            if (!comparisons || comparisons.length === 0) {
                container.innerHTML = '<div class="error">⚠️ Keine Vergleiche geladen</div>';
                return;
            }

            const unvoted = comparisons.filter(c => !c.vote);

            if (unvoted.length === 0) {
                container.innerHTML = `
                    <div class="loading">
                        <h2>✅ Alle Fragen in deinem Subset beantwortet!</h2>
                        <p>Du hast ${totalInSubset} von ${totalInSubset} Fragen bewertet.</p>
                        <p>Vielen Dank für deine Teilnahme! 🎉</p>
                    </div>
                `;
                return;
            }

            const comp = unvoted[0];
            selectedVote = null;
            
            // Progress-Indicator
            const progress = `Frage ${votedInSubset + 1} von ${totalInSubset} (Subset ${assignedSubset})`;

            container.innerHTML = `
                <div class="comparison">
                    <p style="color: #666; font-size: 14px; margin: 0 0 12px;">${progress}</p>
                    <h2 id="question"></h2>
                    <div class="answers">
                        <div class="answer a">
                            <strong>Antwort A</strong><br>
                            <div id="ansA"></div>
                        </div>
                        <div class="answer b">
                            <strong>Antwort B</strong><br>
                            <div id="ansB"></div>
                        </div>
                    </div>
                    <div class="buttons">
                        <button onclick="selectVote('A')" id="btn-A">A ist besser</button>
                        <button onclick="selectVote('tie')" id="btn-tie">Unentschieden</button>
                        <button onclick="selectVote('B')" id="btn-B">B ist besser</button>
                        <button onclick="selectVote('both_bad')" id="btn-both_bad">Beide schlecht</button>
                    </div>
                    <button class="submit" onclick="submitVote('${comp.id}')">Vote abgeben</button>
                </div>
            `;

            // Safely inject text to avoid breaking markup
            const qEl = document.getElementById('question');
            const aEl = document.getElementById('ansA');
            const bEl = document.getElementById('ansB');

            if (qEl) qEl.textContent = comp.question || '';
            if (aEl) aEl.textContent = comp.answer_a || '';
            if (bEl) bEl.textContent = comp.answer_b || '';
        }

        function selectVote(vote) {
            selectedVote = vote;
            ['A', 'tie', 'B', 'both_bad'].forEach(v => {
                const btn = document.getElementById('btn-' + v);
                if (btn) btn.className = v === vote ? 'active' : '';
            });
        }

        async function submitVote(id) {
            if (!selectedVote) {
                alert('Bitte wähle eine Option!');
                return;
            }
            
            try {
                const resp = await fetch(API + '/arena/vote', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        comparison_id: id,
                        vote: selectedVote,
                        comment: null
                    })
                });
                
                if (resp.ok) {
                    selectedVote = null;
                    votedInSubset++;
                    await load();
                } else {
                    alert('❌ Fehler: ' + resp.statusText);
                }
            } catch (e) {
                alert('❌ Fehler: ' + e.message);
            }
        }

        // Start immediately
        load();
        
        // Timeout fallback
        setTimeout(function() {
            if (comparisons.length === 0 && assignedSubset === null) {
                document.getElementById('container').innerHTML = 
                    '<div class="error">⚠️ Timeout beim Laden<br>' +
                    'API: <a href="http://127.0.0.1:8001/arena/comparisons" target="_blank">http://127.0.0.1:8001/arena/comparisons</a><br>' +
                    'Prüfe Browser Console für Details</div>';
            }
        }, 5000);
    </script>
</body>
</html>
"""
    return html.replace("__API_OVERRIDE__", api_override)


@app.get("/results", response_class=HTMLResponse)
def results():
    """Neutrale, read-only Ergebnisliste als Tabelle"""
    api_override = os.getenv("ARENA_API_BASE", "").rstrip("/")
    html = """
<!DOCTYPE html>
<html>
<head>
    <meta charset=\"UTF-8\">
    <title>Arena Ergebnisse</title>
    <style>
        body { font-family: system-ui, -apple-system, \"Segoe UI\", sans-serif; margin: 0 auto; max-width: 1200px; padding: 24px; background: #f6f6f6; color: #1f1f1f; }
        h1 { margin: 0 0 12px; font-weight: 600; }
        .controls { display: flex; gap: 10px; align-items: center; margin: 12px 0 16px; }
        select, button, input { padding: 8px 10px; border: 1px solid #d0d0d0; border-radius: 4px; background: #fff; }
        table { width: 100%; border-collapse: collapse; background: #fff; box-shadow: 0 2px 8px rgba(0,0,0,0.06); }
        th, td { padding: 10px 12px; border-bottom: 1px solid #eee; text-align: left; vertical-align: top; }
        th { background: #fafafa; font-weight: 600; position: sticky; top: 0; }
        tbody tr:hover { background: #fafafa; }
        .pill { display: inline-block; padding: 2px 8px; border-radius: 999px; border: 1px solid #ddd; font-size: 12px; }
        .vote-A { background:#eef6ff; border-color:#cfe3ff; }
        .vote-B { background:#f4e8ff; border-color:#e3d3ff; }
        .vote-tie { background:#eef7ee; border-color:#d7ead7; }
        .vote-both_bad { background:#ffe8e8; border-color:#ffcccc; }
        .muted { color:#666; font-size:12px; }
        .nowrap { white-space: nowrap; }
        .q { max-width: 420px; }
        .ans { max-width: 460px; }
    </style>
    <script>
        // API base: allow override for direct UI (8002) vs. nginx proxy
        const API_OVERRIDE = "__API_OVERRIDE__";
        const API = (API_OVERRIDE && API_OVERRIDE.trim() !== "")
            ? API_OVERRIDE.replace(/\/$/, '')
            : (window.location.port === "8002"
                ? window.location.origin.replace(":8002", ":8001").replace(/\/$/, '')
                : window.location.origin.replace(/\/$/, ''));
        let all = [];
        let filtered = [];

        async function load() {
            const container = document.getElementById('status');
            const subsetSel = document.getElementById('subset');
            const subset = subsetSel ? subsetSel.value : 'all';
            const url = subset === 'all' ? `${API}/arena/comparisons` : `${API}/arena/comparisons?subset=${subset}`;
            container.textContent = 'Lade von ' + url;
            try {
                console.log('Fetching from:', url);
                const resp = await fetch(url, {
                    method: 'GET',
                    headers: {'Accept': 'application/json'},
                    mode: 'cors'
                });
                console.log('Response status:', resp.status);
                
                if (!resp.ok) {
                    throw new Error('HTTP ' + resp.status + ': ' + resp.statusText);
                }
                
                const data = await resp.json();
                console.log('Data received:', data);
                
                all = data.comparisons || [];
                console.log('Loaded comparisons:', all.length);
                
                applyFilters();
                const subsetLabel = subset === 'all' ? 'alle Subsets' : 'Subset ' + subset;
                container.textContent = all.length + ' Vergleiche geladen (' + subsetLabel + ')';
            } catch (e) {
                console.error('Load error:', e);
                container.textContent = '❌ Fehler: ' + e.message + ' | API: ' + API;
            }
        }

        function applyFilters() {
            const sel = document.getElementById('filter');
            const q = (document.getElementById('search').value || '').toLowerCase();
            filtered = all.filter(c => {
                const voted = !!c.vote;
                const voteOk = sel.value === 'all' || (sel.value === 'voted' && voted) || (sel.value === 'unvoted' && !voted);
                const text = ((c.question||'') + ' ' + (c.answer_a||'') + ' ' + (c.answer_b||'')).toLowerCase();
                const searchOk = !q || text.includes(q);
                return voteOk && searchOk;
            });
            renderTable();
        }

        function pill(vote) {
            if (!vote) return '<span class="pill">-</span>';
            const cls = vote === 'A' ? 'vote-A' : vote === 'B' ? 'vote-B' : vote === 'tie' ? 'vote-tie' : 'vote-both_bad';
            const label = vote === 'both_bad' ? 'Beide schlecht' : vote;
            return `<span class="pill ${cls}">${label}</span>`;
        }

        function truncate(t, n=140) { if (!t) return ''; return t.length>n ? t.slice(0,n)+'…' : t; }

        function renderTable() {
            const tbody = document.querySelector('tbody');
            tbody.innerHTML = filtered.map(c => `
                <tr>
                    <td class="nowrap muted">${(c.timestamp||'').replace('T',' ')}</td>
                    <td class="q">${truncate(c.question, 160)}</td>
                    <td class="ans">${truncate(c.answer_a, 160)}</td>
                    <td class="ans">${truncate(c.answer_b, 160)}</td>
                    <td>${pill(c.vote)}</td>
                    <td class="nowrap muted">${c.vote_timestamp ? c.vote_timestamp.replace('T',' ') : ''}</td>
                    <td class="nowrap muted">${c.subset_id || '-'}</td>
                </tr>
            `).join('');
            const status = document.getElementById('status');
            if (status) status.textContent = filtered.length + ' von ' + all.length + ' Einträgen angezeigt';
        }


        function exportCSV() {
            const header = ['id','timestamp','question','model_a','answer_a','model_b','answer_b','vote','vote_timestamp','subset_id'];
            const rows = filtered.map(c => header.map(h => {
                let val = (c[h] || '').toString();
                val = val.split('\\n').join(' ');
                val = val.split('"').join('""');
                return val;
            }));
            const csv = [header.join(','), ...rows.map(r => '"' + r.join('","') + '"')].join('\\n');
            const blob = new Blob([csv], {type:'text/csv;charset=utf-8;'});
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = 'arena_results.csv';
            a.click();
            URL.revokeObjectURL(url);
        }

        window.addEventListener('DOMContentLoaded', load);
    </script>
</head>
<body>
    <h1>Arena Ergebnisse</h1>
    <div class="controls">
        <span id="status" class="muted">-</span>
        <select id="subset" onchange="load()">
            <option value="all">Alle Subsets</option>
            <option value="1">Subset 1</option>
            <option value="2">Subset 2</option>
            <option value="3">Subset 3</option>
            <option value="4">Subset 4</option>
        </select>
        <select id="filter" onchange="applyFilters()">
            <option value="all">Alle</option>
            <option value="voted">Nur gevotet</option>
            <option value="unvoted">Nur offen</option>
        </select>
        <input id="search" type="search" placeholder="Suche in Frage/Antworten" oninput="applyFilters()"/>
        <button onclick="exportCSV()">CSV Export</button>
    </div>
    <table>
        <thead>
            <tr>
                <th>Erstellt</th>
                <th>Frage</th>
                <th>Antwort A</th>
                <th>Antwort B</th>
                <th>Vote</th>
                <th>Vote-Zeit</th>
                <th>Subset</th>
            </tr>
        </thead>
        <tbody>
            <tr><td colspan="7" class="muted">Lade…</td></tr>
        </tbody>
    </table>
</body>
</html>
"""
    return html.replace("__API_OVERRIDE__", api_override)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8002)
