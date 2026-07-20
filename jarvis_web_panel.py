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
    --bg:#0a0a1a; --card:#12122a; --border:#1e1e4a;
    --accent:#6c63ff; --accent2:#00d4ff; --text:#e0e0ff;
    --muted:#7070a0; --green:#00e676; --red:#ff5252; --yellow:#ffea00;
  }
  *{box-sizing:border-box;margin:0;padding:0;}
  body{background:var(--bg);color:var(--text);font-family:'Segoe UI',sans-serif;min-height:100vh;}
  header{background:linear-gradient(135deg,#1a1a3e,#0d0d2b);border-bottom:1px solid var(--border);padding:18px 32px;display:flex;align-items:center;gap:16px;}
  .logo{font-size:28px;font-weight:800;letter-spacing:2px;color:var(--accent2);}
  .logo span{color:var(--accent);}
  .subtitle{font-size:13px;color:var(--muted);margin-top:2px;}
  main{max-width:940px;margin:32px auto;padding:0 20px;}

  /* ── Hero: IA Ativa ── */
  .hero{
    background:linear-gradient(135deg,#14143a,#0d0d28);
    border:1px solid var(--accent2);border-radius:16px;
    padding:24px 28px;margin-bottom:28px;
    display:flex;align-items:center;gap:20px;flex-wrap:wrap;
  }
  .hero-icon{font-size:52px;line-height:1;}
  .hero-info{flex:1;}
  .hero-label{font-size:11px;color:var(--muted);text-transform:uppercase;letter-spacing:1px;margin-bottom:4px;}
  .hero-name{font-size:26px;font-weight:800;color:var(--accent2);letter-spacing:1px;}
  .hero-mode{display:inline-block;margin-top:6px;font-size:12px;padding:3px 12px;border-radius:20px;border:1px solid;}
  .hero-mode.auto{border-color:var(--green);color:var(--green);}
  .hero-mode.fixed{border-color:var(--yellow);color:var(--yellow);}
  .hero-actions{display:flex;gap:10px;align-items:center;flex-wrap:wrap;}
  .btn-auto{background:transparent;border:1px solid var(--muted);color:var(--muted);border-radius:8px;padding:8px 16px;font-size:13px;cursor:pointer;transition:.2s;}
  .btn-auto:hover{border-color:var(--accent2);color:var(--accent2);}
  @keyframes pulse{0%,100%{opacity:1}50%{opacity:.4}}
  .live-dot{width:8px;height:8px;border-radius:50%;background:var(--green);animation:pulse 2s infinite;display:inline-block;margin-right:6px;}

  /* ── Info bar ── */
  .info-bar{
    background:var(--card);border:1px solid var(--border);border-radius:12px;
    padding:14px 22px;margin-bottom:24px;
    display:flex;align-items:center;gap:20px;flex-wrap:wrap;font-size:13px;
  }
  .badge{font-size:11px;padding:3px 10px;border-radius:20px;background:rgba(108,99,255,.2);color:var(--accent);border:1px solid var(--accent);}

  /* ── Provider cards ── */
  .section-title{font-size:13px;color:var(--muted);text-transform:uppercase;letter-spacing:1px;margin-bottom:12px;}
  .providers{display:grid;gap:12px;}
  .provider-card{
    background:var(--card);border:1px solid var(--border);border-radius:14px;
    padding:18px 22px;display:flex;align-items:center;gap:16px;
    transition:border-color .2s,transform .15s,box-shadow .2s;cursor:grab;
  }
  .provider-card:hover{border-color:var(--accent);transform:translateY(-1px);}
  .provider-card.is-active{border-color:var(--accent2);box-shadow:0 0 16px rgba(0,212,255,.2);}
  .provider-card.is-force{border-color:var(--yellow);box-shadow:0 0 14px rgba(255,234,0,.15);}
  .provider-card.disabled{opacity:.45;}
  .provider-card.suspended{border-left:3px solid var(--yellow);}

  .drag-handle{color:var(--muted);font-size:16px;cursor:grab;user-select:none;}
  .priority-num{
    min-width:26px;height:26px;border-radius:7px;
    background:rgba(108,99,255,.15);color:var(--accent);
    font-size:12px;font-weight:700;display:flex;align-items:center;justify-content:center;
  }
  .p-icon{font-size:26px;flex-shrink:0;}
  .p-info{flex:1;min-width:0;}
  .p-name{font-size:15px;font-weight:600;display:flex;align-items:center;gap:8px;}
  .active-chip{
    font-size:10px;padding:2px 8px;border-radius:12px;font-weight:700;
    background:rgba(0,212,255,.15);color:var(--accent2);border:1px solid var(--accent2);
  }
  .force-chip{
    font-size:10px;padding:2px 8px;border-radius:12px;font-weight:700;
    background:rgba(255,234,0,.12);color:var(--yellow);border:1px solid var(--yellow);
  }
  .p-meta{font-size:11px;color:var(--muted);margin-top:4px;display:flex;gap:10px;flex-wrap:wrap;}
  .meta-item{display:flex;align-items:center;gap:3px;}
  .dot{width:6px;height:6px;border-radius:50%;}
  .dot-green{background:var(--green);}
  .dot-red{background:var(--red);}
  .dot-yellow{background:var(--yellow);}

  /* Botão Ativar */
  .btn-activate{
    background:transparent;border:1px solid var(--accent);color:var(--accent);
    border-radius:8px;padding:7px 14px;font-size:12px;font-weight:600;
    cursor:pointer;transition:.2s;white-space:nowrap;flex-shrink:0;
  }
  .btn-activate:hover{background:var(--accent);color:#fff;}
  .btn-activate.is-active-btn{background:rgba(0,212,255,.1);border-color:var(--accent2);color:var(--accent2);cursor:default;}

  /* Toggle */
  .toggle{position:relative;width:44px;height:24px;flex-shrink:0;}
  .toggle input{opacity:0;width:0;height:0;}
  .slider{position:absolute;inset:0;background:#333;border-radius:24px;transition:.3s;cursor:pointer;}
  .slider:before{content:'';position:absolute;width:18px;height:18px;left:3px;bottom:3px;background:#fff;border-radius:50%;transition:.3s;}
  input:checked+.slider{background:var(--accent);}
  input:checked+.slider:before{transform:translateX(20px);}

  /* Model section */
  .model-section{background:var(--card);border:1px solid var(--border);border-radius:14px;padding:20px 24px;margin-top:24px;}
  .model-section h3{font-size:14px;margin-bottom:12px;color:var(--accent2);}
  .model-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(260px,1fr));gap:8px;}
  .model-chip{
    background:rgba(108,99,255,.08);border:1px solid var(--border);border-radius:8px;
    padding:8px 12px;font-size:12px;cursor:pointer;transition:border-color .2s;
    display:flex;align-items:center;gap:8px;
  }
  .model-chip:hover,.model-chip.selected{border-color:var(--accent);color:var(--accent2);}
  .free-tag{font-size:10px;padding:1px 6px;border-radius:4px;background:rgba(0,230,118,.15);color:var(--green);}

  /* Test section */
  .test-section{background:var(--card);border:1px solid var(--border);border-radius:14px;padding:20px 24px;margin-top:16px;}
  .test-section h3{font-size:14px;margin-bottom:12px;color:var(--accent2);}
  .test-row{display:flex;gap:10px;}
  .test-input{flex:1;background:#0d0d20;border:1px solid var(--border);border-radius:8px;color:var(--text);padding:10px 14px;font-size:14px;outline:none;}
  .test-input:focus{border-color:var(--accent);}
  .btn{background:var(--accent);color:#fff;border:none;border-radius:8px;padding:10px 20px;font-size:14px;font-weight:600;cursor:pointer;transition:opacity .2s;}
  .btn:hover{opacity:.85;}
  .btn:disabled{opacity:.4;cursor:not-allowed;}
  .test-response{margin-top:12px;background:#0d0d20;border:1px solid var(--border);border-radius:8px;padding:14px;font-size:13px;line-height:1.6;min-height:60px;white-space:pre-wrap;display:none;}
  .test-response.visible{display:block;}
  .response-meta{font-size:11px;color:var(--muted);margin-bottom:8px;}

  /* Toast */
  .toast{position:fixed;bottom:24px;right:24px;background:#1a1a3e;border:1px solid var(--accent);color:var(--text);padding:12px 20px;border-radius:10px;font-size:13px;opacity:0;transform:translateY(10px);transition:.3s;z-index:999;pointer-events:none;}
  .toast.show{opacity:1;transform:translateY(0);}

  .provider-card.drag-over{border-color:var(--accent2);background:rgba(0,212,255,.04);}
  footer{text-align:center;padding:32px;color:var(--muted);font-size:12px;}
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

  <!-- IA ATIVA — hero card -->
  <div class="hero" id="heroCard">
    <div class="hero-icon" id="heroIcon">🤖</div>
    <div class="hero-info">
      <div class="hero-label"><span class="live-dot"></span>IA Ativa agora</div>
      <div class="hero-name" id="heroName">Carregando...</div>
      <div class="hero-mode auto" id="heroMode">Modo: Automático</div>
    </div>
    <div class="hero-actions">
      <button class="btn-auto" id="btnAuto" onclick="setAuto()" style="display:none;">
        ↺ Voltar ao automático
      </button>
    </div>
  </div>

  <!-- Info bar -->
  <div class="info-bar">
    <span><span class="badge" id="enabledCount">— ativos</span></span>
    <span style="color:var(--muted);">Fallback automático quando cota esgotar</span>
    <span style="margin-left:auto;font-size:12px;color:var(--muted);" id="lastUpdate"></span>
  </div>

  <div class="section-title">Provedores — clique em Ativar para fixar, arraste para reordenar</div>
  <div class="providers" id="providerList"></div>

  <!-- Modelos OpenRouter -->
  <div class="model-section">
    <h3>Modelo OpenRouter (Nvidia / Gratuitos)</h3>
    <p style="font-size:12px;color:var(--muted);margin-bottom:12px;">
      Selecione o modelo padrão. <span style="color:var(--green)">FREE</span> = sem custo.
    </p>
    <div class="model-grid" id="modelGrid"></div>
  </div>

  <!-- Chat de teste -->
  <div class="test-section">
    <h3>Testar IA ativa</h3>
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
const ICONS  = {gemini:'🔵',claude:'🟣',openai:'🟢',openrouter:'🟠'};
const NAMES  = {gemini:'Gemini',claude:'Claude',openai:'ChatGPT',openrouter:'OpenRouter'};
let providers = [];
let forceActive = null;
let selectedModel = '';

async function loadStatus() {
  const r = await fetch('/api/status');
  const data = await r.json();
  providers = data.providers;
  forceActive = data.force_active_id;
  renderHero(data);
  renderProviders(providers);
  document.getElementById('enabledCount').textContent = data.enabled_count + ' ativos';
  document.getElementById('lastUpdate').textContent = 'Atualizado ' + new Date().toLocaleTimeString('pt-BR');
}

function renderHero(data) {
  const active = data.active_provider;
  const isForce = !!data.force_active_id;
  const icon = ICONS[active] || '🤖';
  const name = providers.find(p => p.id === active)?.name || active || 'Nenhum';

  document.getElementById('heroIcon').textContent = icon;
  document.getElementById('heroName').textContent = name || 'Nenhum configurado';

  const modeEl = document.getElementById('heroMode');
  if (isForce) {
    modeEl.textContent = 'Modo: Fixado manualmente';
    modeEl.className = 'hero-mode fixed';
    document.getElementById('btnAuto').style.display = '';
  } else {
    modeEl.textContent = 'Modo: Automático (por prioridade)';
    modeEl.className = 'hero-mode auto';
    document.getElementById('btnAuto').style.display = 'none';
  }
}

function renderProviders(list) {
  const el = document.getElementById('providerList');
  el.innerHTML = '';
  list.forEach((p, i) => {
    const card = document.createElement('div');
    const isActive = p.is_active;
    const isForce  = p.is_force_active;
    card.className = 'provider-card'
      + (isForce  ? ' is-force'  : isActive ? ' is-active' : '')
      + (!p.enabled ? ' disabled' : '')
      + (p.suspended ? ' suspended' : '');
    card.draggable = true;
    card.dataset.id = p.id;

    const configBadge = p.configured
      ? `<span class="meta-item"><span class="dot dot-green"></span>API Key OK</span>`
      : `<span class="meta-item"><span class="dot dot-red"></span>Sem API Key — configure ${p.key_env} no .env</span>`;
    const suspBadge = p.suspended
      ? `<span class="meta-item"><span class="dot dot-yellow"></span>Suspenso por cota</span>` : '';
    const callsBadge = `<span class="meta-item">📊 ${p.total_calls} chamadas</span>`;
    const lastBadge  = p.last_used
      ? `<span class="meta-item">🕒 ${new Date(p.last_used).toLocaleTimeString('pt-BR')}</span>` : '';

    const activeChip = isForce
      ? `<span class="force-chip">★ FIXADO</span>`
      : isActive ? `<span class="active-chip">✓ ATIVO</span>` : '';

    const btnLabel  = isActive ? 'Usando' : 'Ativar';
    const btnClass  = isActive ? 'btn-activate is-active-btn' : 'btn-activate';
    const btnDisabled = isActive ? 'disabled' : '';

    card.innerHTML = `
      <span class="drag-handle">⠿</span>
      <div class="priority-num">${i+1}</div>
      <div class="p-icon">${ICONS[p.id]||'🤖'}</div>
      <div class="p-info">
        <div class="p-name">${p.name} ${activeChip}</div>
        <div class="p-meta">${configBadge}${suspBadge}${callsBadge}${lastBadge}</div>
      </div>
      <button class="${btnClass}" ${btnDisabled} onclick="activateProvider('${p.id}')">${btnLabel}</button>
      <label class="toggle" title="${p.enabled?'Desabilitar':'Habilitar'}">
        <input type="checkbox" ${p.enabled?'checked':''} onchange="toggleProvider('${p.id}',this.checked)">
        <span class="slider"></span>
      </label>
    `;
    setupDrag(card);
    el.appendChild(card);
  });
}

async function activateProvider(id) {
  await fetch('/api/providers/active', {
    method:'POST',
    headers:{'Content-Type':'application/json'},
    body: JSON.stringify({provider_id: id})
  });
  showToast('✅ ' + (NAMES[id]||id) + ' fixado como IA ativa');
  loadStatus();
}

async function setAuto() {
  await fetch('/api/providers/active', {
    method:'POST',
    headers:{'Content-Type':'application/json'},
    body: JSON.stringify({provider_id: 'auto'})
  });
  showToast('↺ Modo automático restaurado');
  loadStatus();
}

async function toggleProvider(id, enabled) {
  await fetch(`/api/providers/${id}/toggle`, {
    method:'POST', headers:{'Content-Type':'application/json'},
    body: JSON.stringify({enabled})
  });
  showToast(enabled ? `✅ ${id} habilitado` : `⛔ ${id} desabilitado`);
  loadStatus();
}

// ── Drag & drop ──
let dragSrc = null;
function setupDrag(card) {
  card.addEventListener('dragstart', e => { dragSrc=card; e.dataTransfer.effectAllowed='move'; card.style.opacity='.4'; });
  card.addEventListener('dragend',   () => { card.style.opacity=''; });
  card.addEventListener('dragover',  e => { e.preventDefault(); card.classList.add('drag-over'); });
  card.addEventListener('dragleave', () => card.classList.remove('drag-over'));
  card.addEventListener('drop', async e => {
    e.preventDefault(); card.classList.remove('drag-over');
    if (dragSrc===card) return;
    const cards = [...document.querySelectorAll('.provider-card')];
    const order = cards.map(c => c.dataset.id);
    const fi = cards.indexOf(dragSrc), ti = cards.indexOf(card);
    order.splice(ti, 0, order.splice(fi, 1)[0]);
    await fetch('/api/providers/reorder',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({order})});
    showToast('Ordem salva!');
    loadStatus();
  });
}

// ── OpenRouter models ──
async function loadModels() {
  const r = await fetch('/api/openrouter/models');
  const data = await r.json();
  selectedModel = data.current;
  const grid = document.getElementById('modelGrid');
  grid.innerHTML = '';
  data.models.forEach(m => {
    const chip = document.createElement('div');
    chip.className = 'model-chip' + (m===selectedModel?' selected':'');
    const isFree = m.includes(':free');
    chip.innerHTML = `<span>🧠</span><span style="flex:1;word-break:break-all">${m.replace(':free','')}</span>${isFree?'<span class="free-tag">FREE</span>':''}`;
    chip.onclick = () => selectModel(m, chip);
    grid.appendChild(chip);
  });
}

async function selectModel(model, chip) {
  await fetch('/api/openrouter/model',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({model})});
  document.querySelectorAll('.model-chip').forEach(c=>c.classList.remove('selected'));
  chip.classList.add('selected');
  selectedModel = model;
  showToast('Modelo: ' + model);
}

// ── Chat de teste ──
async function testChat() {
  const input = document.getElementById('testInput');
  const btn   = document.getElementById('testBtn');
  const resp  = document.getElementById('testResponse');
  if (!input.value.trim()) return;
  btn.disabled=true; btn.textContent='Enviando...';
  resp.className='test-response visible';
  resp.innerHTML='<div class="response-meta">Aguardando resposta...</div>';
  try {
    const r = await fetch('/api/test',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({message:input.value})});
    const data = await r.json();
    if (data.success) {
      resp.innerHTML=`<div class="response-meta">Provedor: <strong>${data.provider}</strong> &nbsp;|&nbsp; Modelo: <strong>${data.model}</strong> &nbsp;|&nbsp; ⏱ ${data.latency_ms}ms</div>${data.text}`;
    } else {
      resp.innerHTML=`<div class="response-meta" style="color:var(--red)">Erro: ${data.error}</div>`;
    }
  } catch(e) {
    resp.innerHTML=`<div class="response-meta" style="color:var(--red)">Erro de conexão: ${e}</div>`;
  }
  btn.disabled=false; btn.textContent='Enviar';
}
document.getElementById('testInput').addEventListener('keydown', e => { if(e.key==='Enter') testChat(); });

// ── Toast ──
function showToast(msg) {
  const t=document.getElementById('toast');
  t.textContent=msg; t.classList.add('show');
  setTimeout(()=>t.classList.remove('show'),2500);
}

// ── Clock ──
setInterval(()=>{ document.getElementById('footerTime').textContent=new Date().toLocaleString('pt-BR'); },1000);
document.getElementById('footerTime').textContent=new Date().toLocaleString('pt-BR');

// ── Init ──
loadStatus();
loadModels();
setInterval(loadStatus, 15000);
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
        "force_active_id": router.force_active_id,
        "enabled_count": len(enabled),
        "timestamp": datetime.now().isoformat(),
    })


@app.route("/api/providers/active", methods=["POST"])
def set_active_provider():
    data = request.get_json(force=True)
    provider_id = data.get("provider_id", "auto")
    router = get_router()
    router.set_active_provider(provider_id)
    return jsonify({"ok": True, "active": router.get_active_provider(), "force": router.force_active_id})


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
