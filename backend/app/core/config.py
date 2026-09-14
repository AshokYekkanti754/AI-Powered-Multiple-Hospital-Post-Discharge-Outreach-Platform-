"""
Application configuration.
Loaded exclusively from environment variables (.env in dev, real env vars in prod).
No secrets are ever hardcoded here.

External / third-party keys are OPTIONAL placeholders: when left as
"change-me-..." / "sk-dummy-..." the platform runs fully offline with its
deterministic mock AI + simulated voice pipeline. Fill them in later to
enable real providers without code changes. See docs/EXTERNAL_KEYS.md.
"""
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

# Resolve backend/.env relative to this file so `uvicorn app.main:app
# --app-dir backend` AND `pytest` from the repo root both load the same file.
_BACKEND_DIR = Path(__file__).resolve().parents[2]
_ENV_FILE = str(_BACKEND_DIR / ".env")


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=_ENV_FILE, extra="ignore")

    DATABASE_URL: str = "postgresql://user:password@localhost:5432/outreach_platform"
    JWT_SECRET_KEY: str = "change-me-to-a-long-random-string"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 480
    ENVIRONMENT: str = "development"
    REDIS_URL: str = "redis://localhost:6379/0"
    FRONTEND_URL: str = "http://localhost:3000"

    # --- AI / LLM providers: free/open-model fallback chain ---
    # Chain (in order): groq -> openrouter -> google -> deterministic mock (fail-closed).
    # All three are free-tier providers hosting open-source models.
    #   Groq:      free key at https://console.groq.com/keys
    #   OpenRouter: free key at https://openrouter.ai/keys (free models w/ :free suffix)
    #   Google:    free key at https://aistudio.google.com/apikey
    # Local Ollama remains supported: set AI_PROVIDER=ollama (no key needed).
    AI_PROVIDER: str = "groq"  # groq | openrouter | google | ollama | mock
    GROQ_API_KEY: str = "your_groq_api_key"
    GROQ_MODEL: str = "openai/gpt-oss-120b"
    GROQ_BASE_URL: str = "https://api.groq.com/openai/v1"
    OPENROUTER_API_KEY: str = "your_openrouter_api_key"
    OPENROUTER_MODEL: str = "openrouter/free"
    OPENROUTER_BASE_URL: str = "https://openrouter.ai/api/v1"
    GOOGLE_API_KEY: str = "your_google_api_key"
    GOOGLE_MODEL: str = "gemini-2.5-flash"
    GOOGLE_BASE_URL: str = "https://generativelanguage.googleapis.com/v1beta/openai"
    

    # --- Voice / telephony provider (optional, simulated when dummy) ---
    VOICE_PROVIDER: str = "simulated"  # simulated | twilio | elevenlabs | telnyx
    TWILIO_ACCOUNT_SID: str = "AC-dummy-replace-me"
    TWILIO_AUTH_TOKEN: str = "dummy-replace-me"
    TWILIO_PHONE_NUMBER: str = "+10000000000"
    ELEVENLABS_API_KEY: str = "eleven-dummy-replace-me"
    ELEVENLABS_VOICE_ID: str = "dummy-voice-id"
    TELNYX_API_KEY: str = "telnyx-dummy-replace-me"

    # --- Notifications (optional) ---
    SMTP_HOST: str = "localhost"
    SMTP_PORT: int = 1025
    SMTP_USERNAME: str = "dummy-replace-me"
    SMTP_PASSWORD: str = "dummy-replace-me"
    SMS_PROVIDER_API_KEY: str = "sms-dummy-replace-me"


settings = Settings()

