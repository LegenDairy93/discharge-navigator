"""Discharge Navigator — Ollama inference pipeline (Day 2: retry A/B, length gate)."""
import requests
from src.schemas import DischargePacket
from src.prompts import (
    SYSTEM_PROMPT, USER_PROMPT_TEMPLATE,
    SYSTEM_PROMPT_STRICT, USER_PROMPT_STRICT,
)

OLLAMA_URL = "http://localhost:11434"
DEFAULT_MODEL = "williamljx/medgemma-4b-it-Q4_K_M-GGUF:latest"
MAX_NOTE_CHARS = 6000


def check_ollama(url: str = OLLAMA_URL) -> list[str]:
    """Verify Ollama is running and return list of available models."""
    try:
        r = requests.get(f"{url}/api/tags", timeout=5)
        r.raise_for_status()
        return [m['name'] for m in r.json().get('models', [])]
    except Exception as e:
        print(f"Ollama not reachable: {e}")
        return []


def select_model(available: list[str]) -> str:
    """Pick best available model: medgemma > gemma > anything."""
    for m in available:
        if 'medgemma' in m.lower():
            return m
    for m in available:
        if 'gemma' in m.lower():
            return m
    return available[0] if available else DEFAULT_MODEL


def truncate_note(note: str, max_chars: int = MAX_NOTE_CHARS) -> tuple[str, bool]:
    """Truncate long notes: keep first 2000 + last (max-2000) chars.

    Returns (note, was_truncated).
    """
    if len(note) <= max_chars:
        return note, False
    head = note[:2000]
    tail = note[-(max_chars - 2000):]
    return head + "\n\n[...TRUNCATED FOR EDGE INFERENCE...]\n\n" + tail, True


def ollama_chat(
    model: str,
    system: str,
    user: str,
    temperature: float = 0.1,
    url: str = OLLAMA_URL,
) -> str:
    """Call Ollama chat API, return raw text response."""
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "options": {"temperature": temperature, "num_predict": 4096},
        "stream": False,
        "format": "json",
    }
    r = requests.post(f"{url}/api/chat", json=payload, timeout=300)
    r.raise_for_status()
    return r.json()["message"]["content"]


def _clean_raw(raw: str) -> str:
    """Strip markdown fences from raw model output."""
    raw = raw.strip()
    if raw.startswith('```'):
        raw = raw.split('\n', 1)[1]
        raw = raw.rsplit('```', 1)[0]
    return raw


def generate_packet(
    note: str,
    model: str = DEFAULT_MODEL,
    temperature: float = 0.0,
    url: str = OLLAMA_URL,
    retries: int = 2,
    return_raw: bool = False,
) -> "DischargePacket | tuple[DischargePacket, str] | tuple[None, str]":
    """Raw clinical note -> validated DischargePacket.

    Retry strategy:
      - Attempt 1: Variant A (contract prompt), temp=0.0
      - Attempt 2: Variant A, temp=0.1
      - Attempt 3: Variant B (strict/fallback prompt), temp=0.0

    If return_raw=True, returns (packet_or_None, raw_output).
    """
    note_input, was_truncated = truncate_note(note)

    last_err = None
    last_raw = ""

    for attempt in range(1 + retries):
        # Pick prompt variant
        if attempt <= 1:
            sys_prompt = SYSTEM_PROMPT
            usr_template = USER_PROMPT_TEMPLATE
        else:
            sys_prompt = SYSTEM_PROMPT_STRICT
            usr_template = USER_PROMPT_STRICT

        temp = temperature + (attempt * 0.1) if attempt <= 1 else 0.0
        user_prompt = usr_template.format(note=note_input)

        try:
            raw = ollama_chat(model=model, system=sys_prompt, user=user_prompt,
                              temperature=temp, url=url)
        except Exception as e:
            last_err = e
            last_raw = f"HTTP_ERROR: {e}"
            if attempt < retries:
                print(f"  Attempt {attempt+1} HTTP error, retrying...")
            continue

        last_raw = raw
        raw_clean = _clean_raw(raw)

        try:
            packet = DischargePacket.model_validate_json(raw_clean)
            # Add truncation note if applicable
            if was_truncated:
                packet.notes.append(
                    "Input truncated for edge inference; clinician should verify completeness."
                )
            if return_raw:
                return packet, last_raw
            return packet
        except Exception as e:
            last_err = e
            if attempt < retries:
                variant = "A" if attempt <= 0 else "B"
                print(f"  Attempt {attempt+1} parse failed ({e.__class__.__name__}), "
                      f"switching to variant {variant}...")

    if return_raw:
        return None, last_raw
    raise last_err


def generate_packet_hf(
    note: str,
    model=None,
    tokenizer=None,
    temperature: float = 0.0,
    retries: int = 2,
    return_raw: bool = False,
) -> "DischargePacket | tuple[DischargePacket, str] | tuple[None, str]":
    """HuggingFace backend version of generate_packet().

    Same retry strategy, same schema validation, same truncation.
    Uses hf_chat() instead of ollama_chat().
    """
    from src.hf_backend import hf_chat

    note_input, was_truncated = truncate_note(note)

    last_err = None
    last_raw = ""

    for attempt in range(1 + retries):
        if attempt <= 1:
            sys_prompt = SYSTEM_PROMPT
            usr_template = USER_PROMPT_TEMPLATE
        else:
            sys_prompt = SYSTEM_PROMPT_STRICT
            usr_template = USER_PROMPT_STRICT

        temp = temperature + (attempt * 0.1) if attempt <= 1 else 0.0
        user_prompt = usr_template.format(note=note_input)

        try:
            raw = hf_chat(model=model, tokenizer=tokenizer,
                          system=sys_prompt, user=user_prompt,
                          temperature=temp)
        except Exception as e:
            last_err = e
            last_raw = f"HF_ERROR: {type(e).__name__}: {e}"
            import traceback; traceback.print_exc()
            if attempt < retries:
                print(f"  Attempt {attempt+1} HF error, retrying...")
            continue

        last_raw = raw
        raw_clean = _clean_raw(raw)

        try:
            packet = DischargePacket.model_validate_json(raw_clean)
            if was_truncated:
                packet.notes.append(
                    "Input truncated for edge inference; clinician should verify completeness."
                )
            if return_raw:
                return packet, last_raw
            return packet
        except Exception as e:
            last_err = e
            if attempt < retries:
                variant = "A" if attempt <= 0 else "B"
                print(f"  Attempt {attempt+1} parse failed ({e.__class__.__name__}), "
                      f"switching to variant {variant}...")

    if return_raw:
        return None, last_raw
    raise last_err
