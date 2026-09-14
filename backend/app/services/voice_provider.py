"""Simulated voice/telephony provider (swap for Twilio/ElevenLabs/Telnyx later).

Default VOICE_PROVIDER=simulated works offline with zero keys. When you add
real TWILIO_*/ELEVENLABS_*/TELNYX_* keys, set VOICE_PROVIDER accordingly and
implement place_call() here — no other file needs to change.
"""
from __future__ import annotations

from app.core.config import settings


def _is_dummy(value: str) -> bool:
    v = (value or "").lower()
    return (not v) or ("dummy" in v) or ("replace-me" in v)


def active_voice_provider() -> str:
    provider = (settings.VOICE_PROVIDER or "simulated").lower()
    if provider == "twilio" and (_is_dummy(settings.TWILIO_ACCOUNT_SID) or _is_dummy(settings.TWILIO_AUTH_TOKEN)):
        return "simulated"
    if provider == "elevenlabs" and _is_dummy(settings.ELEVENLABS_API_KEY):
        return "simulated"
    if provider == "telnyx" and _is_dummy(settings.TELNYX_API_KEY):
        return "simulated"
    return provider


def place_call(*, to_phone: str, script: str, from_phone: str | None = None) -> dict:
    """Place (or simulate) an outbound call. Returns a provider receipt dict."""
    provider = active_voice_provider()
    if provider == "simulated":
        return {
            "provider": "simulated",
            "to": to_phone,
            "from": from_phone or settings.TWILIO_PHONE_NUMBER,
            "script_chars": len(script or ""),
            "status": "simulated-connected",
        }
    # Real provider integration point (Twilio/ElevenLabs/Telnyx) goes here.
    return {"provider": provider, "to": to_phone, "status": "queued-external"}
