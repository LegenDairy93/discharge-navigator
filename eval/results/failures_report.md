# Failure Analysis Report

**Model:** MedGemma 4B IT Q4_K_M (2.5 GB)
**Eval:** 50 notes from MTSamples (CC0)
**Result:** 46/50 parsed successfully (92%), **4 failures**

---

## Failure Modes

| Mode | Count | Root Cause |
|------|-------|------------|
| Token limit truncation | 3 | Model output exceeded 4096 tokens, JSON was incomplete |
| Missing required field | 1 | Model omitted `missing_info` key from output |

---

## Individual Failures

### note_003 — Cardiology (4986 chars)
- **Mode:** Token truncation
- **What happened:** Complex cardiac case (atrial fibrillation, stroke, coronary artery disease, carotid stenosis). Model generated too many evidence_spans per diagnosis, exceeding the 4096-token output limit. JSON was cut mid-object.
- **Safety gate:** Pydantic validation rejected the incomplete JSON before any downstream use.

### note_012 — Radiology/Trauma (3510 chars)
- **Mode:** Token truncation
- **What happened:** Massive trauma note with extensive fracture descriptions. Model attempted to extract 10+ evidence spans per diagnosis, exceeding token budget. JSON truncated mid-span.
- **Safety gate:** Pydantic validation rejected the incomplete JSON.

### note_035 — Pediatrics/URI (1359 chars)
- **Mode:** Missing required field
- **What happened:** Short upper respiratory infection note. Model produced valid JSON with correct diagnoses, medications, and followups, but omitted the `missing_info` key entirely.
- **Safety gate:** Pydantic schema validation caught the missing field. Output was rejected.

### note_046 — Oncology/Lymphoma (4087 chars)
- **Mode:** Token truncation
- **What happened:** Verbose lymphoma staging note. Model duplicated evidence spans (same span cited 4+ times across diagnoses), exhausting the token budget. JSON truncated.
- **Safety gate:** Pydantic validation rejected the incomplete JSON.

---

## Why These Failures Are Safe

1. **Schema validation gate** — Every output passes through Pydantic before reaching any consumer. Missing fields or malformed JSON are rejected immediately.
2. **3-attempt retry** — System retries with temperature escalation and stricter prompt variant before declaring failure.
3. **Failure logging** — Raw model output is stored in `failures.jsonl` for post-hoc analysis.
4. **Clinician-in-the-loop** — No extracted data is ever auto-applied. The original clinical note remains available.
5. **Graceful degradation** — When extraction fails, the system surfaces the original note rather than presenting partial/incorrect data.

---

## Design Principle

> **Fail safely, not silently.** Every failure is caught by schema validation before reaching the clinician. The system degrades gracefully: if structured extraction fails, the original note remains available. No hallucinated data can bypass the validation gate.
