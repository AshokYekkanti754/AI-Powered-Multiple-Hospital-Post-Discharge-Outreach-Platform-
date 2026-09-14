"""Diagnose the live Ollama call: timing, raw output, JSON extraction."""
import sys, time, json
sys.path.insert(0, "backend")
import httpx
from app.core.config import settings
from app.ai.llm_provider import PROMPT_TEMPLATE, _extract_json, _normalize

TRANSCRIPT = "I have chest pain and cannot breathe."
for model in ("llama3.2", "qwen3:4b"):
    t0 = time.time()
    try:
        r = httpx.post(
            f"{settings.OLLAMA_BASE_URL}/api/generate",
            json={"model": model, "prompt": PROMPT_TEMPLATE.format(transcript=TRANSCRIPT),
                  "stream": False, "options": {"temperature": 0}},
            timeout=120,
        )
        dt = time.time() - t0
        print(f"--- {model}: HTTP {r.status_code} in {dt:.1f}s")
        raw = r.json().get("response", "")
        print("RAW:", raw[:300].replace("\n", " | "))
        data = _extract_json(raw)
        print("EXTRACTED:", json.dumps(data) if data else None)
        if data:
            print("NORMALIZED:", _normalize(data, f"ollama/test", model))
    except Exception as exc:
        print(f"--- {model}: ERROR in {time.time()-t0:.1f}s: {type(exc).__name__}: {exc}")
