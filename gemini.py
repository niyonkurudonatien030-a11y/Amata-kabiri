"""Server-side Gemini client using only the standard library (REST API).
The API key stays on the server (environment variable) and is never sent to the browser."""
import base64
import json
import re
import urllib.error
import urllib.request

from flask import current_app

ENDPOINT = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"


class AIError(Exception):
    pass


def configured():
    return bool(current_app.config.get("GEMINI_API_KEY"))


def _parse_json(text):
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text)
    try:
        value = json.loads(text)
    except json.JSONDecodeError:
        raise AIError("The AI returned an answer that could not be read. Please try again.")
    if not isinstance(value, dict):
        raise AIError("Unexpected AI answer format.")
    return value


def generate_json(prompt, image_bytes=None, mime_type=None, user_text=None, timeout=60):
    """Send a prompt (+ optional image / text) to Gemini and return the parsed JSON object."""
    key = current_app.config.get("GEMINI_API_KEY")
    if not key:
        raise AIError("AI is not configured on this server (missing GEMINI_API_KEY).")
    parts = [{"text": prompt}]
    if user_text:
        parts.append({"text": user_text})
    if image_bytes:
        parts.append({"inline_data": {"mime_type": mime_type, "data": base64.b64encode(image_bytes).decode()}})
    body = json.dumps({
        "contents": [{"role": "user", "parts": parts}],
        "generationConfig": {"temperature": 0.1, "responseMimeType": "application/json"},
    }).encode()
    req = urllib.request.Request(
        ENDPOINT.format(model=current_app.config["GEMINI_MODEL"]), data=body,
        headers={"Content-Type": "application/json", "x-goog-api-key": key}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            payload = json.loads(resp.read().decode())
    except urllib.error.HTTPError as exc:
        raise AIError(f"AI service error (HTTP {exc.code}).")
    except (urllib.error.URLError, TimeoutError):
        raise AIError("Could not reach the AI service. Check the internet connection.")
    try:
        text = payload["candidates"][0]["content"]["parts"][0]["text"]
    except (KeyError, IndexError, TypeError):
        raise AIError("The AI did not return an answer (it may have been blocked).")
    return _parse_json(text)
