"""Provider-neutral LLM adapter — free/open-model provider chain.

Configured chain (backend/.env):  groq -> openrouter -> google -> deterministic
Each provider hosts open-source models on a free tier; keys are placeholders in
.env until you paste your own (free) keys:
  Groq:       https://console.groq.com/keys        (model: openai/gpt-oss-120b)
  OpenRouter: https://openrouter.ai/keys           (free models, e.g. ...:free)
  Google:     https://aistudio.google.com/apikey   (gemini-2.5-flash)

All three expose OpenAI-compatible /chat/completions endpoints, so one shared
HTTP path serves the whole chain. Per-provider circuit breakers skip a provider
for 60s after a failure so batch runs never pay repeated connect latency. If
every provider fails (e.g. keys not yet added), triage fail-closes to the built
in deterministic adapter — the pipeline NEVER blocks or crashes. Local Ollama
remains available via AI_PROVIDER=ollama (no key).
"""
from __future__ import annotations

import json
import re
import time

import httpx

from app.core.config import settings

_TIMEOUT = 30.0
ALLOWED_STATUSES = {"routine", "concerning", "urgent", "uncertain"}
_breaker_until: dict[str, float] = {}
_BREAKER_SECONDS = 60.0


def _is_dummy(value: str) -> bool:
    v = (value or "").strip()
    low = v.lower()
    return (not v) or low.startswith("your_") or ("dummy" in low) or ("replace-me" in low) or ("change-me" in low)


def provider_chain() -> list[str]:
    """Ordered providers to try, honouring AI_PROVIDER as the primary."""
    primary = (settings.AI_PROVIDER or "groq").lower()
    if primary == "groq":
        return ["groq", "openrouter", "google"]
    if primary == "openrouter":
        return ["openrouter", "google"]
    if primary == "google":
        return ["google"]
    if primary == "ollama":
        return ["ollama"]
    return []  # mock


def _provider_config(name: str) -> tuple[str, str, str] | None:
    """(base_url, api_key, model) for a chat provider; None if unconfigured."""
    if name == "groq":
        return (settings.GROQ_BASE_URL, settings.GROQ_API_KEY, settings.GROQ_MODEL)
    if name == "openrouter":
        return (settings.OPENROUTER_BASE_URL, settings.OPENROUTER_API_KEY, settings.OPENROUTER_MODEL)
    if name == "google":
        return (settings.GOOGLE_BASE_URL, settings.GOOGLE_API_KEY, settings.GOOGLE_MODEL)
    return None


def active_provider() -> str:
    """First configured provider in the chain, or 'mock'."""
    for name in provider_chain():
        if name == "ollama":
            return "ollama"
        cfg = _provider_config(name)
        if cfg and not _is_dummy(cfg[1]):
            return name
    return "mock"


def active_model() -> str:
    provider = active_provider()
    if provider == "mock":
        return "deterministic-mock"
    if provider == "ollama":
        return settings.OLLAMA_MODEL
    cfg = _provider_config(provider)
    return cfg[2] if cfg else "unknown"


def provider_status() -> dict:
    """Rich status for the /ai/provider-status endpoint."""
    chain = provider_chain()
    providers_info = []
    for name in chain:
        if name == "ollama":
            info = {"provider": "ollama", "model": settings.OLLAMA_MODEL,
                    "configured": True, "kind": "local"}
            try:
                r = httpx.get(f"{settings.OLLAMA_BASE_URL}/api/tags", timeout=2.0)
                info["reachable"] = r.status_code == 200
            except Exception:
                info["reachable"] = False
        else:
            cfg = _provider_config(name)
            info = {"provider": name, "model": cfg[2] if cfg else "",
                    "configured": bool(cfg and not _is_dummy(cfg[1])), "kind": "free-cloud",
                    "reachable": None}
        if _breaker_until.get(name, 0) > time.monotonic():
            info["circuit"] = "open (cooling down after failure)"
        providers_info.append(info)
    provider = active_provider()
    status = {"provider": provider, "model": active_model(),
              "mode": "free-cloud" if provider in ("groq", "openrouter", "google")
              else ("local" if provider == "ollama" else "mock-offline"),
              "chain": providers_info}
    if provider == "mock":
        status["hint"] = ("No provider key configured — triage uses the built-in deterministic adapter. "
                          "Add your free keys in backend/.env: GROQ_API_KEY (console.groq.com/keys), "
                          "OPENROUTER_API_KEY (openrouter.ai/keys), GOOGLE_API_KEY (aistudio.google.com/apikey).")
    return status


URGENT_TERMS = ("chest pain", "cannot breathe", "severe bleeding", "loss of consciousness")
AMBIGUOUS_TERMS = ("unclear", "uncertain", "ambiguous", "possible", "new symptom")

PROMPT_TEMPLATE = (
    "You are a clinical triage assessor for post-discharge patient follow-up calls. "
    "Classify the patient transcript into exactly one status:\n"
    "- urgent: red-flag symptoms needing immediate human attention\n"
    "- concerning: worsening symptoms, needs review\n"
    "- uncertain: ambiguous or unclear information\n"
    "- routine: no issues reported\n"
    "Respond with ONLY a JSON object: {{\"status\": \"...\", \"rationale\": \"...\"}}\n\n"
    "Transcript: {transcript}\n\nJSON:"
)


def _deterministic(transcript: str, agent_name: str) -> dict:
    lowered = (transcript or "").lower()
    if any(t in lowered for t in URGENT_TERMS):
        return {"status": "urgent", "rationale": f"{agent_name}: red-flag phrase detected", "provider": "mock"}
    if any(t in lowered for t in AMBIGUOUS_TERMS):
        return {"status": "uncertain", "rationale": f"{agent_name}: ambiguous language", "provider": "mock"}
    return {"status": "routine", "rationale": f"{agent_name}: no red flags", "provider": "mock"}


def _extract_json(text: str) -> dict | None:
    """Pull the first JSON object out of an LLM response; None if absent/invalid."""
    match = re.search(r"\{.*\}", text or "", flags=re.DOTALL)
    if not match:
        return None
    try:
        data = json.loads(match.group(0))
        return data if isinstance(data, dict) else None
    except (json.JSONDecodeError, ValueError):
        return None


def _normalize(data: dict, provider: str, model: str) -> dict | None:
    status = str(data.get("status", "")).lower().strip()
    if status == "escalated":
        status = "urgent"
    if status not in ALLOWED_STATUSES:
        return None
    return {"status": status, "rationale": str(data.get("rationale", ""))[:300],
            "provider": provider, "model": model}


def _chat_completions(base_url: str, api_key: str, model: str, prompt: str) -> str | None:
    """One OpenAI-compatible chat call; returns assistant text or None."""
    try:
        resp = httpx.post(
            f"{base_url.rstrip('/')}/chat/completions",
            headers={"Authorization": f"Bearer {api_key}",
                     "Content-Type": "application/json"},
            json={"model": model,
                  "messages": [{"role": "user", "content": prompt}],
                  "temperature": 0,
                  "max_tokens": 200},
            timeout=_TIMEOUT,
        )
        resp.raise_for_status()
        body = resp.json()
        choices = body.get("choices") or []
        if not choices:
            return None
        return (choices[0].get("message") or {}).get("content", "") or None
    except Exception:
        return None


def _assess_via(provider: str, transcript: str, agent_name: str) -> dict | None:
    """Assess via one named provider with its circuit breaker; None on failure."""
    if _breaker_until.get(provider, 0) > time.monotonic():
        return None
    text = None
    if provider == "ollama":
        try:
            resp = httpx.post(
                f"{settings.OLLAMA_BASE_URL}/api/generate",
                json={"model": settings.OLLAMA_MODEL,
                      "prompt": PROMPT_TEMPLATE.format(transcript=transcript),
                      "stream": False, "options": {"temperature": 0}},
                timeout=90.0,
            )
            resp.raise_for_status()
            text = resp.json().get("response", "")
        except Exception:
            text = None
        model = settings.OLLAMA_MODEL
    else:
        cfg = _provider_config(provider)
        if cfg is None or _is_dummy(cfg[1]):
            return None  # unconfigured (placeholder key) — skip without HTTP
        base, key, model = cfg
        text = _chat_completions(base, key, model, PROMPT_TEMPLATE.format(transcript=transcript))
    if not text:
        _breaker_until[provider] = time.monotonic() + _BREAKER_SECONDS
        return None
    data = _extract_json(text)
    result = _normalize(data, f"{provider}/{agent_name}", model) if data else None
    if result is None:
        _breaker_until[provider] = time.monotonic() + _BREAKER_SECONDS
    return result


def assess(transcript: str, *, agent_name: str = "assessor") -> dict:
    """Walk the configured provider chain (groq -> openrouter -> google), then
    fail-closed to the deterministic offline assessment."""
    for provider in provider_chain():
        result = _assess_via(provider, transcript, agent_name)
        if result:
            return result
    fallback = _deterministic(transcript, agent_name)
    fallback["fallback_reason"] = "all_providers_unavailable_or_malformed"
    return fallback

