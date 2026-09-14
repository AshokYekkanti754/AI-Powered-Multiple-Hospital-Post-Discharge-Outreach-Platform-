# External API keys & integrations — FREE OPEN-MODEL CHAIN
#
# Configured chain (backend/.env):  groq -> openrouter -> google -> deterministic
# All three are free-tier providers hosting open-source models. If a provider
# fails (bad key, rate limit, outage) the next one takes over automatically;
# if ALL fail, triage fail-closes to the built-in deterministic adapter, so the
# platform ALWAYS works. Per-provider circuit breakers prevent retry storms.
#
# | Priority | Provider | Env vars | Free key from | Default model |
# |---|---|---|---|---|
# | 1 | Groq | GROQ_API_KEY, GROQ_MODEL | https://console.groq.com/keys | openai/gpt-oss-120b |
# | 2 | OpenRouter | OPENROUTER_API_KEY, OPENROUTER_MODEL | https://openrouter.ai/keys | (use a :free model id) |
# | 3 | Google Gemini | GOOGLE_API_KEY, GOOGLE_MODEL | https://aistudio.google.com/apikey | gemini-2.5-flash |
# | — | Ollama (local) | AI_PROVIDER=ollama | none needed | llama3.2 |
# | — | Deterministic mock | automatic | none | built-in fail-closed fallback |
#
# Until you paste real keys, triage runs on the deterministic adapter (fail-closed).
# Voice: VOICE_PROVIDER=simulated (no account needed). Real telephony: Twilio/Telnyx keys.
#
# Single integration points (only files you would ever touch):
# - backend/app/ai/llm_provider.py — chain + OpenAI-compatible calls (already implemented).
# - backend/app/services/voice_provider.py — telephony.
# - backend/.env.example — canonical list.
