"""
OpenWebUI Arena Voting Plugin

Integriert Voting Buttons direkt in den Arena Mode Chat.
Wird als Custom Function/Tool in OpenWebUI registriert.
"""

import json
from datetime import datetime
from typing import Optional

from src.openwebui.voting_system import default_storage, ArenaComparison


def register_voting_functions():
    """
    Registriert Voting Funktionen für OpenWebUI.
    
    OpenWebUI erlaubt Custom Functions die im Chat aufgerufen werden können.
    Wir nutzen das um Voting zu integrieren.
    """
    pass


class ArenaVotingWidget:
    """
    JavaScript/HTML Widget das über OpenWebUI rendered wird.
    
    Das Widget zeigt Voting Buttons nach jeder Arena Antwort.
    """
    
    @staticmethod
    def get_html_widget(comparison_id: str, model_a: str, model_b: str) -> str:
        """
        Generiert HTML für Voting Buttons.
        
        Args:
            comparison_id: ID des Vergleichs (wird beim API-Call genutzt)
            model_a: Name von Model A
            model_b: Name von Model B
        
        Returns:
            HTML String mit Voting Buttons
        """
        html = f"""
<div id="arena-voting-{comparison_id}" class="arena-voting-widget" style="
    margin-top: 20px;
    padding: 15px;
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    border-radius: 8px;
    color: white;
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
">
    <div style="font-weight: 600; margin-bottom: 12px; font-size: 14px;">
        🏆 Welche Antwort ist besser?
    </div>
    
    <div style="display: flex; gap: 10px; flex-wrap: wrap; margin-bottom: 10px;">
        <button 
            class="vote-btn" 
            data-comparison-id="{comparison_id}" 
            data-vote="A"
            style="
                flex: 1;
                min-width: 120px;
                padding: 10px 16px;
                background: rgba(255,255,255,0.2);
                border: 2px solid rgba(255,255,255,0.5);
                color: white;
                border-radius: 6px;
                cursor: pointer;
                font-weight: 500;
                transition: all 0.2s ease;
            "
            onmouseover="this.style.background='rgba(255,255,255,0.3)'; this.style.borderColor='rgba(255,255,255,0.8)'"
            onmouseout="this.style.background='rgba(255,255,255,0.2)'; this.style.borderColor='rgba(255,255,255,0.5)'"
        >
            👈 Model A ({model_a})
        </button>
        
        <button 
            class="vote-btn" 
            data-comparison-id="{comparison_id}" 
            data-vote="tie"
            style="
                flex: 1;
                min-width: 120px;
                padding: 10px 16px;
                background: rgba(255,255,255,0.2);
                border: 2px solid rgba(255,255,255,0.5);
                color: white;
                border-radius: 6px;
                cursor: pointer;
                font-weight: 500;
                transition: all 0.2s ease;
            "
            onmouseover="this.style.background='rgba(255,255,255,0.3)'; this.style.borderColor='rgba(255,255,255,0.8)'"
            onmouseout="this.style.background='rgba(255,255,255,0.2)'; this.style.borderColor='rgba(255,255,255,0.5)'"
        >
            🤝 Unentschieden
        </button>
        
        <button 
            class="vote-btn" 
            data-comparison-id="{comparison_id}" 
            data-vote="B"
            style="
                flex: 1;
                min-width: 120px;
                padding: 10px 16px;
                background: rgba(255,255,255,0.2);
                border: 2px solid rgba(255,255,255,0.5);
                color: white;
                border-radius: 6px;
                cursor: pointer;
                font-weight: 500;
                transition: all 0.2s ease;
            "
            onmouseover="this.style.background='rgba(255,255,255,0.3)'; this.style.borderColor='rgba(255,255,255,0.8)'"
            onmouseout="this.style.background='rgba(255,255,255,0.2)'; this.style.borderColor='rgba(255,255,255,0.5)'"
        >
            👉 Model B ({model_b})
        </button>
    </div>
    
    <input 
        type="text" 
        class="vote-comment" 
        data-comparison-id="{comparison_id}"
        placeholder="Optional: Kommentar zu deinem Vote..."
        style="
            width: 100%;
            padding: 8px 12px;
            border: 1px solid rgba(255,255,255,0.3);
            border-radius: 4px;
            background: rgba(255,255,255,0.1);
            color: white;
            font-size: 12px;
            box-sizing: border-box;
        "
    />
    <small style="display: block; margin-top: 8px; opacity: 0.8;">
        Dein Vote wird gespeichert und trägt zum Benchmarking bei.
    </small>
</div>

<script>
// Vote Button Handler
document.addEventListener('click', async function(e) {{
    if (!e.target.classList.contains('vote-btn')) return;
    
    const btn = e.target;
    const comparisonId = btn.dataset.comparisonId;
    const vote = btn.dataset.vote;
    const widget = document.getElementById('arena-voting-' + comparisonId);
    const commentInput = widget.querySelector('.vote-comment');
    const comment = commentInput.value.trim() || null;
    
    // Disable buttons während Request
    const allBtns = widget.querySelectorAll('.vote-btn');
    allBtns.forEach(b => b.disabled = true);
    btn.style.opacity = '0.5';
    
    try {{
        const response = await fetch('/arena/vote', {{
            method: 'POST',
            headers: {{'Content-Type': 'application/json'}},
            body: JSON.stringify({{
                comparison_id: comparisonId,
                vote: vote,
                comment: comment
            }})
        }});
        
        if (response.ok) {{
            // Success - zeige Bestätigung
            widget.innerHTML = '<div style=\"padding: 10px; text-align: center; font-weight: 600;\">✅ Vote gespeichert! Danke für deine Teilnahme.</div>';
        }} else {{
            alert('Fehler beim Vote: ' + response.statusText);
            allBtns.forEach(b => b.disabled = false);
            btn.style.opacity = '1';
        }}
    }} catch (error) {{
        console.error('Vote error:', error);
        alert('Fehler beim Vote: ' + error.message);
        allBtns.forEach(b => b.disabled = false);
        btn.style.opacity = '1';
    }}
}});
</script>
"""
        return html
    
    @staticmethod
    def get_javascript_injection() -> str:
        """
        JavaScript das in OpenWebUI injiziert wird um Arena Chat zu detecten
        und Voting Buttons hinzuzufügen.
        """
        js = """
(function() {
    'use strict';
    
    console.log('[Arena Voting] Plugin loaded');
    
    // Observe für neue Chat Messages
    const observer = new MutationObserver(function(mutations) {
        // Schaue nach Arena Mode Markers
        const chatMessages = document.querySelectorAll('[class*="message"]');
        
        chatMessages.forEach(msg => {
            // Prüfe ob Message schon Voting Widget hat
            if (msg.querySelector('.arena-voting-widget')) return;
            
            // Prüfe ob es eine Arena Mode Message ist (zwei Antworten nebeneinander)
            const responses = msg.querySelectorAll('[class*="response"], [class*="answer"]');
            
            // Für jetzt: Zeige Voting Widget nach jedem Message
            // (Später: nur für Arena Mode)
            if (msg.textContent.length > 100) {
                const msgId = 'msg-' + Math.random().toString(36).substr(2, 9);
                const votingHtml = `
                    <div class="arena-voting-widget" style="margin-top: 15px; padding: 12px; background: #667eea20; border-radius: 8px; border-left: 4px solid #667eea;">
                        <small style="color: #667eea; font-weight: 600;">
                            🏆 Fand diese Antwort hilfreich?
                        </small>
                        <div style="display: flex; gap: 8px; margin-top: 8px;">
                            <button style="padding: 6px 12px; background: #667eea; color: white; border: none; border-radius: 4px; cursor: pointer; font-size: 12px;">
                                👍 Ja
                            </button>
                            <button style="padding: 6px 12px; background: #ccc; color: black; border: none; border-radius: 4px; cursor: pointer; font-size: 12px;">
                                👎 Nein
                            </button>
                        </div>
                    </div>
                `;
                msg.innerHTML += votingHtml;
            }
        });
    });
    
    // Starte Observer
    observer.observe(document.body, {
        childList: true,
        subtree: true,
        characterData: false,
        attributes: false
    });
    
    console.log('[Arena Voting] Observer registered');
})();
"""
        return js
