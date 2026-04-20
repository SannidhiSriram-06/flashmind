import json
import os

_MODEL = "llama-3.1-8b-instant"
MIN_TEXT_LENGTH = 200
# Groq's llama-3.1-8b-instant has a ~6000-token context; cap input to avoid truncation
_MAX_INPUT_CHARS = 4000

_SYSTEM_PROMPT = (
    "You are an expert teacher creating flashcards. "
    "Generate exactly 10 flashcards from the provided text. "
    "Each card must have a clear question on the front and a concise answer on the back. "
    "Cover key concepts, definitions, relationships, and important facts. "
    'Return ONLY valid JSON in this format: [{"front": "question here", "back": "answer here"}, ...] '
    "No markdown, no explanation, just the JSON array."
)

_STRICT_SYSTEM_PROMPT = (
    "You are a JSON generator. Output ONLY a valid JSON array of exactly 10 objects. "
    'Each object must have exactly two keys: "front" and "back", both strings. '
    "No markdown fences, no prose, no trailing text — raw JSON only."
)

_FALLBACK_SYSTEM_PROMPT = (
    "Respond with a JSON array only. "
    "Start your response with [ and end with ]. "
    "No text before or after the array. No markdown code fences. "
    'Each element must be {"front": "...", "back": "..."}. Exactly 10 elements.'
)


def _get_client():
    """Lazy-init Groq client so missing API key only raises at call-time."""
    from groq import Groq
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        raise RuntimeError(
            "GROQ_API_KEY is not set. Add it to your .env file or environment variables."
        )
    return Groq(api_key=api_key)


def _validate_cards(cards: object) -> list[dict]:
    """Validate that parsed JSON has the expected [{front, back}, ...] structure."""
    if not isinstance(cards, list):
        raise json.JSONDecodeError("Expected a JSON array", "", 0)
    validated = []
    for card in cards:
        if not isinstance(card, dict):
            raise json.JSONDecodeError("Each card must be a JSON object", "", 0)
        if "front" not in card or "back" not in card:
            raise json.JSONDecodeError("Each card must have 'front' and 'back' keys", "", 0)
        validated.append({
            "front": str(card["front"]).strip(),
            "back":  str(card["back"]).strip(),
        })
    if not validated:
        raise json.JSONDecodeError("Card list is empty", "", 0)
    return validated


def _call_groq(system: str, user: str) -> str:
    response = _get_client().chat.completions.create(
        model=_MODEL,
        messages=[
            {"role": "system", "content": system},
            {"role": "user",   "content": user},
        ],
        temperature=0.7,
    )
    return response.choices[0].message.content.strip()


def generate_flashcards(chunks: list[str], topic_hint: str = "") -> list[dict]:
    """Generate 10 flashcards from a list of text chunks via Groq.

    Raises:
        ValueError:   if the combined text is too short to be meaningful.
        RuntimeError: if all three LLM attempts fail to produce valid JSON.
    """
    combined = "\n\n".join(chunks)

    if len(combined.strip()) < MIN_TEXT_LENGTH:
        raise ValueError("PDF too short to generate meaningful flashcards")

    # Truncate to avoid exceeding model context window
    combined = combined[:_MAX_INPUT_CHARS]

    if topic_hint:
        combined = f"Topic: {topic_hint}\n\n{combined}"

    # Attempt 1 — standard prompt
    raw = _call_groq(_SYSTEM_PROMPT, combined)
    try:
        return _validate_cards(json.loads(raw))
    except (json.JSONDecodeError, ValueError):
        pass

    # Attempt 2 — stricter prompt
    raw = _call_groq(
        _STRICT_SYSTEM_PROMPT,
        f"Convert this content into 10 flashcard JSON objects:\n\n{combined}",
    )
    try:
        return _validate_cards(json.loads(raw))
    except (json.JSONDecodeError, ValueError):
        pass

    # Attempt 3 — fallback prompt
    raw = _call_groq(_FALLBACK_SYSTEM_PROMPT, combined)
    try:
        return _validate_cards(json.loads(raw))
    except (json.JSONDecodeError, ValueError) as e:
        raise RuntimeError(
            "Flashcard generation failed: the AI did not return valid JSON after 3 attempts. "
            "Try uploading a different PDF."
        ) from e
