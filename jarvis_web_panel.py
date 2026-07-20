#!/usr/bin/env python3
"""
Jarvis Web Panel - Painel de controle em http://localhost:5000/
Gerencia provedores de IA (Claude, Gemini, OpenAI, OpenRouter/Nvidia)
com toggle, ordem de prioridade e fallback automático.

Iniciar: python jarvis_web_panel.py
"""

import os
import json
from datetime import datetime
from flask import Flask, jsonify, request, Response

from jarvis_ai_router import get_router, OPENROUTER_FREE_MODELS

app = Flask(__name__)
app.secret_key = os.getenv("PANEL_SECRET", "jarvis-panel-secret")


# ─────────────────────────────────────────────
# HTML do painel (inline — sem templates externos)
# ─────────────────────────────────────────────

PANEL_HTML = r"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Jarvis AI — Painel de Provedores</title>
<style>
  :root {
    --bg: #0a0a1a; --card: #12122a; --border: #1e1e4a;
    --accent: #6c63ff; --accent2: #00d4ff; --text: #e0e0ff;
    --muted: #7070a0; --green: #00e676; --red: #ff5252;
    --yellow: #ffea00;
  }
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { background: var(--bg); color: var(--text); font-family: 'Segoe UI', sans-serif; min-height: 100vh; }
  header {
    background: linear-gradient(135deg, #1a1a3e, #0d0d2b);
    border-bottom: 1px solid var(--border);
    padding: 18px 32px;
    display: flex; align-items: center; gap: 16px;
  }
  .logo { font-size: 28px; font-weight: 800; letter-spacing: 2px; color: var(--accent2); }
  .logo span { color: var(--accent); }
  .subtitle { font-size: 13px; color: var(--muted); margin-top: 2px; }
  main { max-width: 920px; margin: 32px auto; padding: 0 20px; }

  /* Status bar */
  .status-bar {
    background: var(--card); border: 1px solid var(--border); border-radius: 12px;
    padding: 16px 24px; margin-bottom: 28px;
    display: flex; align-items: center; gap: 16px; flex-wrap: wrap;
  }
  .status-dot { width: 10px; height: 10px; border-radius: 50%; background: var(--green); animation: pulse 2s infinite; }
  @keyframes pulse { 0%,100%{opacity:1} 50%{opacity:.4} }
  .status-label { font-size: 13px; color: var(--muted); }
  .status-value { font-weight: 600; color: var(--accent2); }
  .badge {
    font-size: 11px; padding: 3px 10px; border-radius: 20px;
    background: rgba(108,99,255,.2); color: var(--accent); border: 1px solid var(--accent);
  }

  /* Cards de provedor */
  .section-title { font-size: 14px; color: var(--muted); text-transform: uppercase; letter-spacing: 1px; margin-bottom: 14px; }
  .providers { display: grid; gap: 14px; }
  .provider-card {
    background: var(--card); border: 1px solid var(--border); border-radius: 14px;
    padding: 20px 24px; display: flex; align-items: center; gap: 18px;
    transition: border-color .2s, transform .15s;
    cursor: grab;
  }
  .provider-card:hover { border-color: var(--accent); transform: translateY(-1px); }
  .provider-card.active-provider { border-color: var(--accent2); box-shadow: 0 0 12px rgba(0,212,255,.15); }
  .provider-card.disabled { opacity: .5; }
  .provider-card.suspended { border-color: var(--yellow); }

  .drag-handle { color: var(--muted); font-size: 18px; cursor: grab; user-select: none; }
  .priority-badge {
    min-width: 28px; height: 28px; border-radius: 8px;
    background: rgba(108,99,255,.15); color: var(--accent);
    font-size: 12px; font-weight: 700; display: flex; align-items: center; justify-content: center;
  }
  .provider-icon { font-size: 28px; flex-shrink: 0; }
  .provider-info { flex: 1; }
  .provider-name { font-size: 16px; font-weight: 600; }
  .provider-meta { font-size: 12px; color: var(--muted); margin-top: 3px; display: flex; gap: 12px; flex-wrap: wrap; }
  .meta-item { display: flex; align-items: center; gap: 4px; }
  .dot { width: 6px; height: 6px; border-radius: 50%; }
  .dot-green { background: var(--green); }
  .dot-red { background: var(--red); }
  .dot-yellow { background: var(--yellow); }

  /* Toggle switch */
  .toggle { position: relative; width: 48px; height: 26px; flex-shrink: 0; }
  .toggle input { opacity: 0; width: 0; height: 0; }
  .slider {
    position: absolute; inset: 0; background: #333; border-radius: 26px;
    transition: .3s; cursor: pointer;
  }
  .slider:before {
    content: ''; position: absolute; width: 20px; height: 20px;
    left: 3px; bottom: 3px; background: #fff; border-radius: 50%; transition: .3s;
  }
  input:checked + .slider { background: var(--accent); }
  input:checked + .slider:before { transform: translateX(22px); }

  /* Seção de modelos OpenRouter */
  .model-section {
    background: var(--card); border: 1px solid var(--border); border-radius: 14px;
    padding: 20px 24px; margin-top: 28px;
  }
  .model-section h3 { font-size: 14px; margin-bottom: 14px; color: var(--accent2); }
  .model-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(260px, 1fr)); gap: 8px; }
  .model-chip {
    background: rgba(108,99,255,.08); border: 1px solid var(--border); border-radius: 8px;
    padding: 8px 12px; font-size: 12px; cursor: pointer; transition: border-color .2s;
    display: flex; align-items: center; gap: 8px;
  }
  .model-chip:hover, .model-chip.selected { border-color: var(--accent); color: var(--accent2); }
  .model-chip .free-tag { font-size: 10px; padding: 1px 6px; border-radius: 4px; background: rgba(0,230,118,.15); color: var(--green); }

  /* Chat de teste */
  .test-section {
    background: var(--card); border: 1px solid var(--border); border-radius: 14px;
    padding: 20px 24px; margin-top: 20px;
  }
  .test-section h3 { font-size: 14px; margin-bottom: 14px; color: var(--accent2); }
  .test-row { display: flex; gap: 10px; }
  .test-input {
    flex: 1; background: #0d0d20; border: 1px solid var(--border); border-radius: 8px;
    color: var(--text); padding: 10px 14px; font-size: 14px; outline: none;
  }
  .test-input:focus { border-color: var(--accent); }
  .btn {
    background: var(--accent); color: #fff; border: none; border-radius: 8px;
    padding: 10px 20px; font-size: 14px; font-weight: 600; cursor: pointer; transition: opacity .2s;
  }
  .btn:hover { opacity: .85; }
  .btn:disabled { opacity: .4; cursor: not-allowed; }
  .test-response {
    margin-top: 14px; background: #0d0d20; border: 1px solid var(--border); border-radius: 8px;
    padding: 14px; font-size: 13px; line-height: 1.6; min-height: 60px;
    white-space: pre-wrap; color: var(--text); display: none;
  }
  .test-response.visible { display: block; }
  .response-meta { font-size: 11px; color: var(--muted); margin-bottom: 8px; }

  /* Toast */
  .toast {
    position: fixed; bottom: 24px; right: 24px;
    background: #1a1a3e; border: 1px solid var(--accent); color: var(--text);
    padding: 12px 20px; border-radius: 10px; font-size: 13px;
    opacity: 0; transform: translateY(10px); transition: .3s;
    z-index: 999; pointer-events: none;
  }
  .toast.show { opacity: 1; transform: translateY(0); }

  /* Drag-and-drop highlight */
  .provider-card.drag-over { border-color: var(--accent2); background: rgba(0,212,255,.05); }

  footer { text-align: center; padding: 32px; color: var(--muted); font-size: 12px; }
</style>
</head>
<body>

<header>
  <div>
    <div class="logo">J.A.R.V.<span>I</span>.S</div>
    <div class="subtitle">Painel de Gerenciamento de Provedores AI</div>
  </div>
</header>

<main>
  <!-- Barra de status -->
  <div class="status-bar">
    <div class="status-dot" id="statusDot"></div>
    <div>
      <div class="status-label">Provedor ativo</div>
      <div class="status-value" id="activeProvider">Carregando...</div>
    </div>
    <div style="margin-left:auto; display:flex; gap:10px; align-items:center;">
      <span class="badge" id="enabledCount">— ativos</span>
      <span style="font-size:12px;color:var(--muted);" id="lastUpdate"></span>
    </div>
  </div>

  <div class="section-title">Provedores — arraste para reordenar</div>

  <!-- Lista de provedores -->
  <div class="providers" id="providerList"></div>

  <!-- Modelos OpenRouter -->
  <div class="model-section">
    <h3>Modelo OpenRouter (Nvidia / Gratuitos)</h3>
    <p style="font-size:12px;color:var(--muted);margin-bottom:14px;">
      Selecione o modelo padrão. Modelos com <span style="color:var(--green)">FREE</span> não consomem créditos.
    </p>
    <div class="model-grid" id="modelGrid"></div>
  </div>

  <!-- Chat de teste -->
  <div class="test-section">
    <h3>Testar provedor ativo</h3>
    <div class="test-row">
      <input class="test-input" id="testInput" placeholder="Digite uma mensagem de teste..." />
      <button class="btn" id="testBtn" onclick="testChat()">Enviar</button>
    </div>
    <div class="test-response" id="testResponse"></div>
  </div>
</main>

<footer>Jarvis AI &nbsp;•&nbsp; Multi-provider Router &nbsp;•&nbsp; <span id="footerTime"></span></footer>

<div class="toast" id="toast"></div>

<script>
const ICONS = { gemini:'🔵', claude:'🟣', openai:'🟢', openrouter:'🟠' };
const COLORS = { gemini:'#4285F4', claude:'#9b59b6', openai:'#10a37f', openrouter:'#ff6b35' };
let providers = [];
let selectedModel = '';

async function loadStatus() {
  const r = await fetch('/api/status');
  const data = await r.json();
  providers = data.providers;
  renderProviders(providers);
  document.getElementById('activeProvider').textContent = data.active_provider || 'Nenhum';
  document.getElementById('enabledCount').textContent = data.enabled_count + ' ativos';
  document.getElementById('lastUpdate').textContent = 'Atualizado ' + new Date().toLocaleTimeString('pt-BR');
}

function renderProviders(list) {
  const el = document.getElementById('providerList');
  el.innerHTML = '';
  list.forEach((p, i) => {
    const isActive = document.getElementById('activeProvider')?.textContent === p.id;
    const card = document.createElement('div');
    card.className = 'provider-card' +
      (isActive ? ' active-provider' : '') +
      (!p.enabled ? ' disabled' : '') +
      (p.suspended ? ' suspended' : '');
    card.draggable = true;
    card.dataset.id = p.id;
    card.dataset.idx = i;

    const configBadge = p.configured
      ? `<span class="meta-item"><span class="dot dot-green"></span>API Key OK</span>`
      : `<span class="meta-item"><span class="dot dot-red"></span>Sem API Key</span>`;
    const suspendBadge = p.suspended
      ? `<span class="meta-item"><span class="dot dot-yellow"></span>Suspenso (cota)</span>` : '';
    const callsBadge = `<span class="meta-item">📊 ${p.total_calls} chamadas</span>`;
    const lastBadge = p.last_used
      ? `<span class="meta-item">🕒 ${new Date(p.last_used).toLocaleTimeString('pt-BR')}</span>` : '';

    card.innerHTML = `
      <span class="drag-handle">⠿</span>
      <div class="priority-badge">${i+1}</div>
      <div class="provider-icon">${ICONS[p.id]||'🤖'}</div>
      <div class="provider-info">
        <div class="provider-name">${p.name}</div>
        <div class="provider-meta">${configBadge}${suspendBadge}${callsBadge}${lastBadge}</div>
      </div>
      <label class="toggle">
        <input type="checkbox" ${p.enabled?'checked':''} onchange="toggleProvider('${p.id}', this.checked)">
        <span class="slider"></span>
      </label>
    `;
    setupDrag(card);
    el.appendChild(card);
  });
}

async function toggleProvider(id, enabled) {
  await fetch(`/api/providers/${id}/toggle`, {
    method: 'POST',
    headers: {'Content-Type':'application/json'},
    body: JSON.stringify({enabled})
  });
  showToast(enabled ? `✅ ${id} habilitado` : `⛔ ${id} desabilitado`);
  loadStatus();
}

// ── Drag and drop para reordenar ──
let dragSrc = null;
function setupDrag(card) {
  card.addEventListener('dragstart', e => {
    dragSrc = card;
    e.dataTransfer.effectAllowed = 'move';
    card.style.opacity = '.4';
  });
  card.addEventListener('dragend', () => { card.style.opacity = ''; });
  card.addEventListener('dragover', e => { e.preventDefault(); card.classList.add('drag-over'); });
  card.addEventListener('dragleave', () => card.classList.remove('drag-over'));
  card.addEventListener('drop', async e => {
    e.preventDefault();
    card.classList.remove('drag-over');
    if (dragSrc === card) return;
    const list = document.getElementById('providerList');
    const cards = [...list.querySelectorAll('.provider-card')];
    const fromIdx = cards.indexOf(dragSrc);
    const toIdx = cards.indexOf(card);
    const newOrder = cards.map(c => c.dataset.id);
    newOrder.splice(toIdx, 0, newOrder.splice(fromIdx, 1)[0]);
    await fetch('/api/providers/reorder', {
      method: 'POST',
      headers: {'Content-Type':'application/json'},
      body: JSON.stringify({order: newOrder})
    });
    showToast('Ordem salva!');
    loadStatus();
  });
}

// ── Modelos OpenRouter ──
async function loadModels() {
  const r = await fetch('/api/openrouter/models');
  const data = await r.json();
  selectedModel = data.current;
  const grid = document.getElementById('modelGrid');
  grid.innerHTML = '';
  data.models.forEach(m => {
    const chip = document.createElement('div');
    chip.className = 'model-chip' + (m === selectedModel ? ' selected' : '');
    const isFree = m.includes(':free');
    chip.innerHTML = `<span>🧠</span><span style="flex:1;word-break:break-all;">${m.replace(':free','')}</span>${isFree?'<span class="free-tag">FREE</span>':''}`;
    chip.onclick = () => selectModel(m, chip);
    grid.appendChild(chip);
  });
}

async function selectModel(model, chip) {
  await fetch('/api/openrouter/model', {
    method: 'POST',
    headers: {'Content-Type':'application/json'},
    body: JSON.stringify({model})
  });
  document.querySelectorAll('.model-chip').forEach(c => c.classList.remove('selected'));
  chip.classList.add('selected');
  selectedModel = model;
  showToast('Modelo selecionado: ' + model);
}

// ── Chat de teste ──
async function testChat() {
  const input = document.getElementById('testInput');
  const btn = document.getElementById('testBtn');
  const resp = document.getElementById('testResponse');
  if (!input.value.trim()) return;
  btn.disabled = true;
  btn.textContent = 'Enviando...';
  resp.className = 'test-response visible';
  resp.innerHTML = '<div class="response-meta">Aguardando resposta...</div>';
  try {
    const r = await fetch('/api/test', {
      method: 'POST',
      headers: {'Content-Type':'application/json'},
      body: JSON.stringify({message: input.value})
    });
    const data = await r.json();
    if (data.success) {
      resp.innerHTML = `<div class="response-meta">Provedor: <strong>${data.provider}</strong> &nbsp;|&nbsp; Modelo: <strong>${data.model}</strong> &nbsp;|&nbsp; ⏱ ${data.latency_ms}ms</div>${data.text}`;
    } else {
      resp.innerHTML = `<div class="response-meta" style="color:var(--red)">Erro: ${data.error}</div>`;
    }
  } catch(e) {
    resp.innerHTML = `<div class="response-meta" style="color:var(--red)">Erro de conexão: ${e}</div>`;
  }
  btn.disabled = false;
  btn.textContent = 'Enviar';
}

document.getElementById('testInput').addEventListener('keydown', e => {
  if (e.key === 'Enter') testChat();
});

// ── Toast ──
function showToast(msg) {
  const t = document.getElementById('toast');
  t.textContent = msg;
  t.classList.add('show');
  setTimeout(() => t.classList.remove('show'), 2500);
}

// ── Footer clock ──
function updateClock() {
  document.getElementById('footerTime').textContent = new Date().toLocaleString('pt-BR');
}
setInterval(updateClock, 1000); updateClock();

// ── Init ──
loadStatus();
loadModels();
setInterval(loadStatus, 15000);  // auto-refresh a cada 15s
</script>
</body>
</html>"""


# ─────────────────────────────────────────────
# Rotas da API
# ─────────────────────────────────────────────

@app.route("/")
def index():
    return Response(PANEL_HTML, content_type="text/html; charset=utf-8")


@app.route("/api/status")
def api_status():
    router = get_router()
    providers = router.get_status()
    enabled = [p for p in providers if p["enabled"]]
    return jsonify({
        "providers": providers,
        "active_provider": router.get_active_provider(),
        "enabled_count": len(enabled),
        "timestamp": datetime.now().isoformat(),
    })


@app.route("/api/providers/<provider_id>/toggle", methods=["POST"])
def toggle_provider(provider_id):
    data = request.get_json(force=True)
    enabled = bool(data.get("enabled", True))
    router = get_router()
    router.set_enabled(provider_id, enabled)
    return jsonify({"ok": True, "provider": provider_id, "enabled": enabled})


@app.route("/api/providers/reorder", methods=["POST"])
def reorder_providers():
    data = request.get_json(force=True)
    order = data.get("order", [])
    router = get_router()
    router.reorder(order)
    return jsonify({"ok": True, "order": order})


@app.route("/api/openrouter/models")
def list_openrouter_models():
    current = os.getenv("OPENROUTER_MODEL", OPENROUTER_FREE_MODELS[0])
    return jsonify({"models": OPENROUTER_FREE_MODELS, "current": current})


@app.route("/api/openrouter/model", methods=["POST"])
def set_openrouter_model():
    data = request.get_json(force=True)
    model = data.get("model", "")
    if model:
        os.environ["OPENROUTER_MODEL"] = model
        # persiste no .env local
        _write_env("OPENROUTER_MODEL", model)
    return jsonify({"ok": True, "model": model})


@app.route("/api/test", methods=["POST"])
def test_chat():
    data = request.get_json(force=True)
    message = data.get("message", "Olá!")
    router = get_router()
    resp = router.chat(message)
    return jsonify({
        "success": resp.success,
        "text": resp.text,
        "provider": resp.provider_used,
        "model": resp.model_used,
        "latency_ms": resp.latency_ms,
        "error": resp.error,
    })


def _write_env(key: str, value: str):
    """Atualiza ou adiciona variável no arquivo .env sem apagar as outras."""
    env_path = ".env"
    lines = []
    found = False
    if os.path.exists(env_path):
        with open(env_path) as f:
            lines = f.readlines()
        for i, line in enumerate(lines):
            if line.startswith(f"{key}="):
                lines[i] = f"{key}={value}\n"
                found = True
                break
    if not found:
        lines.append(f"{key}={value}\n")
    with open(env_path, "w") as f:
        f.writelines(lines)


# ─────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────

def main():
    import logging
    logging.basicConfig(level=logging.INFO)
    port = int(os.getenv("PANEL_PORT", 5000))
    print(f"Jarvis Web Panel rodando em http://localhost:{port}/")
    print("Pressione Ctrl+C para parar.")
    app.run(host="0.0.0.0", port=port, debug=False)


if __name__ == "__main__":
    main()
