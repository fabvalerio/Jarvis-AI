#!/usr/bin/env python3
"""
Jarvis AI Router - Multi-provider com fallback automático.

Suporta: Claude (Anthropic), Gemini (Google), OpenAI (ChatGPT), OpenRouter (Nvidia + modelos grátis).
Quando um provedor atinge cota/limite, cai automaticamente para o próximo habilitado na fila.

Uso:
    router = AIRouter()
    response = router.chat("Qual é a capital do Brasil?")
    print(response.text, response.provider_used)
"""

import os
import json
import time
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

import requests
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

STATE_FILE = Path("jarvis_ai_router_state.json")

# Modelos gratuitos conhecidos do OpenRouter (atualizado jul/2025)
OPENROUTER_FREE_MODELS = [
    "nvidia/llama-3.1-nemotron-70b-instruct:free",
    "meta-llama/llama-3.2-3b-instruct:free",
    "mistralai/mistral-7b-instruct:free",
    "google/gemma-2-9b-it:free",
    "qwen/qwen-2-7b-instruct:free",
    "deepseek/deepseek-r1:free",
    "microsoft/phi-3-mini-128k-instruct:free",
]


@dataclass
class AIResponse:
    text: str
    provider_used: str
    model_used: str
    success: bool
    error: Optional[str] = None
    latency_ms: int = 0


@dataclass
class ProviderState:
    provider_id: str
    enabled: bool = True
    priority: int = 0          # menor = maior prioridade
    quota_reset_at: Optional[str] = None  # ISO datetime
    error_count: int = 0
    total_calls: int = 0
    last_used: Optional[str] = None


# ------------------------------------------------------------------ #
# Provedores individuais
# ------------------------------------------------------------------ #

class BaseProvider(ABC):
    provider_id: str
    display_name: str
    requires_key: str  # nome da variável de ambiente da API key

    @abstractmethod
    def chat(self, message: str, system: str = "") -> AIResponse:
        ...

    def is_configured(self) -> bool:
        return bool(os.getenv(self.requires_key, ""))

    def _quota_error(self, e: Exception) -> bool:
        msg = str(e).lower()
        return any(kw in msg for kw in ["quota", "rate limit", "429", "insufficient_quota",
                                         "resource_exhausted", "too many requests"])


class GeminiProvider(BaseProvider):
    provider_id = "gemini"
    display_name = "Gemini (Google)"
    requires_key = "GEMINI_API_KEY"

    def chat(self, message: str, system: str = "") -> AIResponse:
        t0 = time.time()
        try:
            import google.generativeai as genai
            genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
            model_name = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
            model = genai.GenerativeModel(
                model_name,
                system_instruction=system or "Você é o Jarvis, assistente pessoal de IA.",
            )
            r = model.generate_content(message)
            return AIResponse(
                text=r.text, provider_used=self.provider_id,
                model_used=model_name, success=True,
                latency_ms=int((time.time() - t0) * 1000),
            )
        except Exception as e:
            return AIResponse(text="", provider_used=self.provider_id,
                              model_used="", success=False, error=str(e),
                              latency_ms=int((time.time() - t0) * 1000))


class ClaudeProvider(BaseProvider):
    provider_id = "claude"
    display_name = "Claude (Anthropic)"
    requires_key = "ANTHROPIC_API_KEY"

    def chat(self, message: str, system: str = "") -> AIResponse:
        t0 = time.time()
        try:
            import anthropic
            client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
            model_name = os.getenv("CLAUDE_MODEL", "claude-sonnet-4-6")
            msg = client.messages.create(
                model=model_name,
                max_tokens=2048,
                system=system or "Você é o Jarvis, assistente pessoal de IA.",
                messages=[{"role": "user", "content": message}],
            )
            return AIResponse(
                text=msg.content[0].text, provider_used=self.provider_id,
                model_used=model_name, success=True,
                latency_ms=int((time.time() - t0) * 1000),
            )
        except Exception as e:
            return AIResponse(text="", provider_used=self.provider_id,
                              model_used="", success=False, error=str(e),
                              latency_ms=int((time.time() - t0) * 1000))


class OpenAIProvider(BaseProvider):
    provider_id = "openai"
    display_name = "ChatGPT (OpenAI)"
    requires_key = "OPENAI_API_KEY"

    def chat(self, message: str, system: str = "") -> AIResponse:
        t0 = time.time()
        try:
            import openai as oai
            client = oai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
            model_name = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
            r = client.chat.completions.create(
                model=model_name,
                messages=[
                    {"role": "system", "content": system or "Você é o Jarvis, assistente pessoal de IA."},
                    {"role": "user", "content": message},
                ],
            )
            return AIResponse(
                text=r.choices[0].message.content, provider_used=self.provider_id,
                model_used=model_name, success=True,
                latency_ms=int((time.time() - t0) * 1000),
            )
        except Exception as e:
            return AIResponse(text="", provider_used=self.provider_id,
                              model_used="", success=False, error=str(e),
                              latency_ms=int((time.time() - t0) * 1000))


class OpenRouterProvider(BaseProvider):
    """OpenRouter: acesso a centenas de modelos (incluindo Nvidia e grátis)."""
    provider_id = "openrouter"
    display_name = "OpenRouter (Nvidia / Grátis)"
    requires_key = "OPENROUTER_API_KEY"
    BASE_URL = "https://openrouter.ai/api/v1/chat/completions"

    def chat(self, message: str, system: str = "") -> AIResponse:
        t0 = time.time()
        model_name = os.getenv("OPENROUTER_MODEL", OPENROUTER_FREE_MODELS[0])
        try:
            headers = {
                "Authorization": f"Bearer {os.getenv('OPENROUTER_API_KEY', '')}",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://github.com/fabvalerio/Jarvis-AI",
                "X-Title": "Jarvis AI",
            }
            payload = {
                "model": model_name,
                "messages": [
                    {"role": "system", "content": system or "Você é o Jarvis, assistente pessoal de IA."},
                    {"role": "user", "content": message},
                ],
            }
            r = requests.post(self.BASE_URL, headers=headers, json=payload, timeout=60)
            r.raise_for_status()
            data = r.json()
            text = data["choices"][0]["message"]["content"]
            return AIResponse(
                text=text, provider_used=self.provider_id,
                model_used=model_name, success=True,
                latency_ms=int((time.time() - t0) * 1000),
            )
        except Exception as e:
            return AIResponse(text="", provider_used=self.provider_id,
                              model_used=model_name, success=False, error=str(e),
                              latency_ms=int((time.time() - t0) * 1000))


# ------------------------------------------------------------------ #
# Router principal
# ------------------------------------------------------------------ #

ALL_PROVIDERS: list[BaseProvider] = [
    GeminiProvider(),
    ClaudeProvider(),
    OpenAIProvider(),
    OpenRouterProvider(),
]

PROVIDER_MAP = {p.provider_id: p for p in ALL_PROVIDERS}


class AIRouter:
    """
    Gerencia múltiplos provedores de IA com fallback automático.

    - Tenta provedores em ordem de prioridade (menor número = maior prioridade).
    - Se um falha por cota/rate-limit, marca como temporariamente suspenso e tenta o próximo.
    - Estado (habilitado/prioridade/erros) persiste em JSON local.
    - force_active_id: quando definido, usa apenas esse provedor (sem fallback automático).
    """

    QUOTA_SUSPEND_MINUTES = 60  # suspende provedor por 1h após erro de cota

    def __init__(self):
        self.states: dict[str, ProviderState] = {}
        self.force_active_id: Optional[str] = None  # None = modo automático
        self._load_state()

    # ------------------------------------------------------------------ #
    # Estado
    # ------------------------------------------------------------------ #

    def _default_state(self) -> dict:
        return {
            p.provider_id: ProviderState(
                provider_id=p.provider_id,
                enabled=True,
                priority=i,
            )
            for i, p in enumerate(ALL_PROVIDERS)
        }

    def _load_state(self):
        if STATE_FILE.exists():
            try:
                raw = json.loads(STATE_FILE.read_text())
                self.force_active_id = raw.pop("__force_active__", None)
                self.states = {
                    k: ProviderState(**v) for k, v in raw.items()
                }
                for p in ALL_PROVIDERS:
                    if p.provider_id not in self.states:
                        self.states[p.provider_id] = ProviderState(
                            provider_id=p.provider_id,
                            enabled=True,
                            priority=len(self.states),
                        )
                return
            except Exception:
                pass
        self.states = self._default_state()

    def _save_state(self):
        try:
            data = {k: vars(v) for k, v in self.states.items()}
            if self.force_active_id:
                data["__force_active__"] = self.force_active_id
            STATE_FILE.write_text(json.dumps(data, indent=2))
        except Exception as e:
            logger.warning(f"Erro ao salvar estado: {e}")

    # ------------------------------------------------------------------ #
    # Controle de provedores
    # ------------------------------------------------------------------ #

    def set_enabled(self, provider_id: str, enabled: bool):
        if provider_id in self.states:
            self.states[provider_id].enabled = enabled
            self._save_state()

    def set_priority(self, provider_id: str, priority: int):
        if provider_id in self.states:
            self.states[provider_id].priority = priority
            self._save_state()

    def reorder(self, ordered_ids: list[str]):
        """Define ordem de prioridade a partir de lista ordenada."""
        for i, pid in enumerate(ordered_ids):
            if pid in self.states:
                self.states[pid].priority = i
        self._save_state()

    def set_active_provider(self, provider_id: str):
        """Fixa manualmente um provedor. Passa 'auto' para voltar ao modo automático."""
        if provider_id == "auto":
            self.force_active_id = None
        else:
            self.force_active_id = provider_id
        self._save_state()

    def _is_suspended(self, state: ProviderState) -> bool:
        if not state.quota_reset_at:
            return False
        reset_dt = datetime.fromisoformat(state.quota_reset_at)
        return datetime.now() < reset_dt

    def _suspend(self, state: ProviderState):
        reset = datetime.now() + timedelta(minutes=self.QUOTA_SUSPEND_MINUTES)
        state.quota_reset_at = reset.isoformat()
        self._save_state()

    # ------------------------------------------------------------------ #
    # Chamada principal com fallback
    # ------------------------------------------------------------------ #

    def chat(self, message: str, system: str = "") -> AIResponse:
        """
        Envia mensagem ao próximo provedor disponível.
        Se force_active_id estiver definido, usa apenas ele.
        Caso contrário faz fallback automático por prioridade.
        """
        if self.force_active_id:
            forced_state = self.states.get(self.force_active_id)
            forced_provider = PROVIDER_MAP.get(self.force_active_id)
            if forced_state and forced_provider and forced_provider.is_configured():
                t0 = time.time()
                resp = forced_provider.chat(message, system)
                forced_state.total_calls += 1
                forced_state.last_used = datetime.now().isoformat()
                self._save_state()
                return resp
            # Provedor fixado não disponível → cai para automático

        ordered = sorted(
            [s for s in self.states.values() if s.enabled],
            key=lambda s: s.priority,
        )

        last_error = "Nenhum provedor habilitado."
        for state in ordered:
            if self._is_suspended(state):
                logger.info(f"Provedor {state.provider_id} suspenso por cota. Pulando.")
                continue

            provider = PROVIDER_MAP.get(state.provider_id)
            if not provider:
                continue

            if not provider.is_configured():
                logger.info(f"Provedor {state.provider_id} sem API key. Pulando.")
                continue

            logger.info(f"Tentando provedor: {state.provider_id}")
            response = provider.chat(message, system)

            state.total_calls += 1
            state.last_used = datetime.now().isoformat()

            if response.success:
                state.error_count = 0
                self._save_state()
                return response

            last_error = response.error or "Erro desconhecido"
            state.error_count += 1

            # Verifica se é erro de cota → suspende
            if provider._quota_error(Exception(last_error)):
                logger.warning(f"{state.provider_id} atingiu cota. Suspendendo por {self.QUOTA_SUSPEND_MINUTES}min.")
                self._suspend(state)
            else:
                self._save_state()

            logger.warning(f"{state.provider_id} falhou: {last_error}. Tentando próximo.")

        return AIResponse(
            text=f"Todos os provedores falharam. Último erro: {last_error}",
            provider_used="none", model_used="", success=False, error=last_error,
        )

    # ------------------------------------------------------------------ #
    # Status para o painel
    # ------------------------------------------------------------------ #

    def get_status(self) -> list[dict]:
        result = []
        auto_active = self._resolve_auto_active()
        for p in ALL_PROVIDERS:
            state = self.states.get(p.provider_id, ProviderState(provider_id=p.provider_id))
            is_force = self.force_active_id == p.provider_id
            is_active = is_force or (not self.force_active_id and p.provider_id == auto_active)
            result.append({
                "id": p.provider_id,
                "name": p.display_name,
                "enabled": state.enabled,
                "priority": state.priority,
                "configured": p.is_configured(),
                "suspended": self._is_suspended(state),
                "quota_reset_at": state.quota_reset_at,
                "error_count": state.error_count,
                "total_calls": state.total_calls,
                "last_used": state.last_used,
                "key_env": p.requires_key,
                "is_active": is_active,
                "is_force_active": is_force,
            })
        return sorted(result, key=lambda x: x["priority"])

    def _resolve_auto_active(self) -> Optional[str]:
        for state in sorted(self.states.values(), key=lambda s: s.priority):
            if not state.enabled:
                continue
            if self._is_suspended(state):
                continue
            p = PROVIDER_MAP.get(state.provider_id)
            if p and p.is_configured():
                return state.provider_id
        return None

    def get_active_provider(self) -> Optional[str]:
        if self.force_active_id:
            p = PROVIDER_MAP.get(self.force_active_id)
            if p and p.is_configured():
                return self.force_active_id
        return self._resolve_auto_active()


# Instância global (importada pelo web panel e core)
_router: Optional[AIRouter] = None


def get_router() -> AIRouter:
    global _router
    if _router is None:
        _router = AIRouter()
    return _router
