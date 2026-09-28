import json
import logging
import os
import re

from dotenv import load_dotenv

load_dotenv()
log = logging.getLogger(__name__)


class AIServiceError(Exception):
    pass


def configured_provider():
    """Return the configured provider when it has a usable API key."""
    provider = os.getenv("AI_PROVIDER", "groq").strip().lower()
    if provider not in {"groq", "gemini"}:
        provider = "groq"
    if provider == "gemini" and os.getenv("GEMINI_API_KEY", "").strip():
        return "gemini"
    if provider == "groq" and os.getenv("GROQ_API_KEY", "").strip():
        return "groq"
    if os.getenv("GROQ_API_KEY", "").strip():
        return "groq"
    if os.getenv("GEMINI_API_KEY", "").strip():
        return "gemini"
    return provider


def available_providers():
    return {
        "groq": bool(os.getenv("GROQ_API_KEY", "").strip()),
        "gemini": bool(os.getenv("GEMINI_API_KEY", "").strip()),
    }


def generate_text(prompt, provider=None):
    if os.getenv("MOCK_AI", "false").lower() == "true":
        raise AIServiceError("Mock mode enabled")
    provider = (provider or configured_provider()).strip().lower()
    keys = {"groq": os.getenv("GROQ_API_KEY", "").strip(), "gemini": os.getenv("GEMINI_API_KEY", "").strip()}
    if provider not in keys:
        raise AIServiceError("Choose a supported AI model.")
    key = keys[provider]
    if not key:
        raise AIServiceError(f"Add a {provider.title()} API key to use this model.")
    try:
        system_prompt = "You are PocketSmart AI, a budget planning assistant. Return only valid JSON without markdown."
        if provider == "gemini":
            from google import genai

            client = genai.Client(api_key=key, http_options={"timeout": 45000})
            response = client.models.generate_content(
                model=os.getenv("GEMINI_MODEL", "gemini-3.8-flash"),
                contents=f"{system_prompt}\n\n{prompt}",
                config={"response_mime_type": "application/json", "temperature": 0.4},
            )
            return response.text or ""

        from groq import Groq

        client = Groq(api_key=key, timeout=45, max_retries=2)
        response = client.chat.completions.create(
            model=os.getenv("GROQ_MODEL", "openai/gpt-oss-120b"),
            messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
            temperature=0.4,
        )
        return response.choices[0].message.content or ""
    except Exception as exc:
        log.exception("%s request failed", provider.title())
        status_code = getattr(exc, "status_code", getattr(exc, "code", None))
        if provider == "gemini" and (status_code == 503 or "503 unavailable" in str(exc).lower()):
            raise AIServiceError("Gemini is temporarily busy. Try again in a little while or use Change model to switch to Groq.") from exc
        if "connection" in str(exc).lower():
            raise AIServiceError(f"Could not connect to {provider.title()}. Check your network connection and try again.") from exc
        raise AIServiceError("PocketSmart AI couldn't generate recommendations right now. Please try again.") from exc


def generate_structured_response(prompt, provider=None):
    raw = generate_text(prompt, provider)
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        match = re.search(r"\{[\s\S]*\}", raw)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                pass
        log.error("AI provider returned malformed JSON")
        raise AIServiceError("PocketSmart AI returned an unusable plan. Please try again.")
