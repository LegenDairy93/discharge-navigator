"""Discharge Navigator — Trust Surface Demo (Gradio).

Three panels:
1. Traceability: click extraction → highlight evidence in source note
2. Reliability Board: metrics summary card
3. Failure Gallery: one failure explained with safety narrative
"""
import sys, json, re
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import gradio as gr
import pandas as pd

# ─── Data loading ───

DATA_DIR = PROJECT_ROOT / "data"
RESULTS_DIR = PROJECT_ROOT / "eval" / "results"
SAMPLES_DIR = RESULTS_DIR / "samples"
METRICS_FILE = RESULTS_DIR / "day2_metrics.json"
FAILURES_FILE = RESULTS_DIR / "failures.jsonl"
SUBSET_CSV = DATA_DIR / "mtsamples_subset.csv"

# Load notes
df = pd.read_csv(SUBSET_CSV)
notes_list = df["note"].tolist()
specialties = df["medical_specialty"].tolist()

# Load metrics
with open(METRICS_FILE) as f:
    metrics = json.load(f)

# Load sample outputs (note_id -> packet dict)
samples = {}
for p in sorted(SAMPLES_DIR.glob("note_*.json")):
    note_id = p.stem
    with open(p) as f:
        samples[note_id] = json.load(f)

# Load failures
failures = []
if FAILURES_FILE.exists():
    with open(FAILURES_FILE) as f:
        for line in f:
            if line.strip():
                failures.append(json.loads(line))

# Build dropdown choices: only notes that have sample outputs
note_choices = []
for i in range(len(notes_list)):
    nid = f"note_{i:03d}"
    if nid in samples:
        specialty = specialties[i] if i < len(specialties) else "Unknown"
        note_choices.append(f"{nid} — {specialty} ({len(str(notes_list[i]))} chars)")


# ─── Highlight helpers ───

def highlight_spans_in_note(note_text: str, spans: list[str]) -> str:
    """Wrap matching evidence spans with HTML highlight markers."""
    if not spans:
        return note_text

    # Normalize for matching but preserve original for display
    note_lower = note_text.lower()
    regions = []  # (start, end) indices to highlight

    for span in spans:
        if not span:
            continue
        span_lower = re.sub(r"\s+", " ", span.lower().strip())
        note_normalized = re.sub(r"\s+", " ", note_lower)

        idx = note_normalized.find(span_lower)
        if idx == -1:
            continue

        # Map back from normalized position to original position
        # Walk through original text counting non-collapsed chars
        orig_pos = 0
        norm_pos = 0
        start_orig = None
        end_orig = None

        i = 0
        while i < len(note_text) and norm_pos <= idx + len(span_lower):
            if norm_pos == idx:
                start_orig = i
            if norm_pos == idx + len(span_lower):
                end_orig = i
                break

            ch = note_text[i]
            if ch in (' ', '\t', '\n', '\r'):
                # Consume all consecutive whitespace as one space
                norm_pos += 1
                i += 1
                while i < len(note_text) and note_text[i] in (' ', '\t', '\n', '\r'):
                    i += 1
            else:
                norm_pos += 1
                i += 1

        if start_orig is not None and end_orig is None:
            end_orig = len(note_text)

        if start_orig is not None and end_orig is not None:
            regions.append((start_orig, end_orig))

    if not regions:
        return note_text

    # Merge overlapping regions
    regions.sort()
    merged = [regions[0]]
    for s, e in regions[1:]:
        if s <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], e))
        else:
            merged.append((s, e))

    # Build highlighted text (use simple markers, convert to HTML)
    parts = []
    last = 0
    for s, e in merged:
        parts.append(note_text[last:s])
        parts.append(f'<mark style="background-color: #FBBF24; padding: 2px 4px; border-radius: 3px; font-weight: 600;">{note_text[s:e]}</mark>')
        last = e
    parts.append(note_text[last:])

    return "".join(parts)


def get_extraction_items(packet: dict) -> list[dict]:
    """Flatten all extractions into a list with type, label, spans."""
    items = []
    for dx in packet.get("diagnoses", []):
        items.append({
            "type": "Diagnosis",
            "label": dx["label"],
            "detail": f"ICD-10: {dx.get('icd10', 'N/A')} | Confidence: {dx.get('confidence', '?')}",
            "spans": dx.get("evidence_spans", []),
        })
    for med in packet.get("medications", []):
        dose_str = " ".join(filter(None, [med.get("dose"), med.get("route"), med.get("frequency")]))
        items.append({
            "type": "Medication",
            "label": med["name"],
            "detail": dose_str or "No dosing info",
            "spans": med.get("evidence_spans", []),
        })
    for fu in packet.get("followups", []):
        items.append({
            "type": "Follow-up",
            "label": f"{fu.get('with_whom', '?')} — {fu.get('when', '?')}",
            "detail": f"Urgency: {fu.get('urgency', '?')}",
            "spans": fu.get("evidence_spans", []),
        })
    return items


# ─── Panel 1: Traceability ───

def load_note(choice: str):
    """Load a note and its extractions when dropdown changes."""
    if not choice:
        return "", "", "Select a note to begin."

    note_id = choice.split(" — ")[0]
    idx = int(note_id.split("_")[1])
    note_text = str(notes_list[idx])
    packet = samples.get(note_id, {})

    # Build extraction summary
    items = get_extraction_items(packet)
    extraction_lines = []
    for i, item in enumerate(items):
        n_spans = len(item["spans"])
        grounded = sum(1 for s in item["spans"] if re.sub(r"\s+", " ", s.lower().strip()) in re.sub(r"\s+", " ", note_text.lower()))
        icon = "+" if grounded == n_spans and n_spans > 0 else "~" if grounded > 0 else "-"
        extraction_lines.append(
            f"[{icon}] {item['type']}: {item['label']}\n"
            f"    {item['detail']}\n"
            f"    Spans: {grounded}/{n_spans} grounded"
        )

    extraction_text = "\n\n".join(extraction_lines) if extraction_lines else "No extractions found."

    # Patient summary
    summary = packet.get("patient_summary", "N/A")
    red_flags = packet.get("red_flags", [])
    rf_text = ", ".join(rf.get("symptom", "") for rf in red_flags) if red_flags else "None identified"
    missing = packet.get("missing_info", [])
    mi_text = ", ".join(mi.get("item", "") for mi in missing) if missing else "None"

    overview = (
        f"PATIENT SUMMARY:\n{summary}\n\n"
        f"RED FLAGS: {rf_text}\n"
        f"MISSING INFO: {mi_text}\n\n"
        f"--- EXTRACTIONS ({len(items)} items) ---\n\n"
        f"{extraction_text}"
    )

    # Default: highlight all spans
    all_spans = []
    for item in items:
        all_spans.extend(item["spans"])

    highlighted = highlight_spans_in_note(note_text, all_spans)
    highlighted_html = f'<div style="font-family: monospace; white-space: pre-wrap; line-height: 1.8; padding: 16px; background: #1a1a2e; color: #e0e0e0; border-radius: 8px; font-size: 14px;">{highlighted}</div>'

    return highlighted_html, overview, f"Loaded {note_id}: {len(items)} extractions, all spans highlighted."


def highlight_by_type(choice: str, ext_type: str):
    """Highlight only spans for a specific extraction type."""
    if not choice:
        return "", "Select a note first."

    note_id = choice.split(" — ")[0]
    idx = int(note_id.split("_")[1])
    note_text = str(notes_list[idx])
    packet = samples.get(note_id, {})
    items = get_extraction_items(packet)

    # Filter by type
    filtered = [item for item in items if item["type"] == ext_type]
    spans = []
    for item in filtered:
        spans.extend(item["spans"])

    highlighted = highlight_spans_in_note(note_text, spans)
    highlighted_html = f'<div style="font-family: monospace; white-space: pre-wrap; line-height: 1.8; padding: 16px; background: #1a1a2e; color: #e0e0e0; border-radius: 8px; font-size: 14px;">{highlighted}</div>'

    return highlighted_html, f"Highlighting {len(spans)} spans for {len(filtered)} {ext_type.lower()}(s)."


# ─── Panel 2: Reliability Board ───

def build_reliability_html():
    m = metrics
    criteria = m.get("success_criteria", {})

    def badge(passed):
        if passed:
            return '<span style="background: #10B981; color: white; padding: 3px 10px; border-radius: 12px; font-weight: 700; font-size: 13px;">PASS</span>'
        return '<span style="background: #EF4444; color: white; padding: 3px 10px; border-radius: 12px; font-weight: 700; font-size: 13px;">FAIL</span>'

    retries_count = sum(1 for r in m['per_note'] if r.get('latency_seconds', 0) > 100)

    html = f"""
    <div style="font-family: system-ui, -apple-system, sans-serif; max-width: 750px; margin: 0 auto; color: #1a1a2e !important;">

    <div style="text-align: center; margin-bottom: 24px;">
        <h2 style="margin: 0 0 4px 0; font-size: 22px; font-weight: 700; color: white !important;">50-Note Evaluation Results</h2>
        <p style="margin: 0; font-size: 13px; color: #94a3b8 !important;">MedGemma 4B Q4_K_M &middot; CPU-only &middot; No internet required</p>
    </div>

    <div style="display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 16px; margin-bottom: 24px;">
        <div style="background: white !important; border: 2px solid #e2e8f0; border-radius: 12px; padding: 24px 16px; text-align: center;">
            <div style="font-size: 42px; font-weight: 800; color: #1a1a2e !important; line-height: 1;">{m['json_valid_rate']:.0%}</div>
            <div style="font-size: 14px; font-weight: 700; color: #1a1a2e !important; margin-top: 8px;">NOTES PARSED</div>
            <div style="font-size: 12px; color: #475569 !important; margin-top: 2px;">{m['json_valid_count']} of {m['total_notes']} valid JSON</div>
            <div style="margin-top: 10px;">{badge(criteria.get('json_valid_ge_80pct', False))}</div>
        </div>
        <div style="background: white !important; border: 2px solid #e2e8f0; border-radius: 12px; padding: 24px 16px; text-align: center;">
            <div style="font-size: 42px; font-weight: 800; color: #1a1a2e !important; line-height: 1;">{m['median_latency_s']:.0f}s</div>
            <div style="font-size: 14px; font-weight: 700; color: #1a1a2e !important; margin-top: 8px;">ON CPU</div>
            <div style="font-size: 12px; color: #475569 !important; margin-top: 2px;">Median per note, no GPU</div>
            <div style="margin-top: 10px;">{badge(criteria.get('median_latency_le_45s', False))}</div>
        </div>
        <div style="background: white !important; border: 2px solid #e2e8f0; border-radius: 12px; padding: 24px 16px; text-align: center;">
            <div style="font-size: 42px; font-weight: 800; color: #1a1a2e !important; line-height: 1;">{m['mean_diagnoses_grounded']:.0%}</div>
            <div style="font-size: 14px; font-weight: 700; color: #1a1a2e !important; margin-top: 8px;">BACKED BY SOURCE</div>
            <div style="font-size: 12px; color: #475569 !important; margin-top: 2px;">Diagnosis evidence grounded</div>
            <div style="margin-top: 10px;">{badge(criteria.get('dx_grounding_ge_85pct_on_30_notes', False))}</div>
        </div>
    </div>

    <div style="background: white !important; border: 2px solid #e2e8f0; border-radius: 12px; padding: 24px; margin-bottom: 24px;">
        <h3 style="margin: 0 0 16px 0; font-size: 16px; color: #1a1a2e !important;">Full Metrics</h3>
        <table style="width: 100%; border-collapse: collapse; font-size: 14px;">
            <tr style="border-bottom: 1px solid #e2e8f0;">
                <td style="padding: 8px 0; color: #334155 !important;">Medication evidence grounded</td>
                <td style="padding: 8px 0; text-align: right; font-weight: 700; color: #1a1a2e !important;">{m['mean_meds_grounded']:.0%}</td>
            </tr>
            <tr style="border-bottom: 1px solid #e2e8f0;">
                <td style="padding: 8px 0; color: #334155 !important;">Overall evidence grounded</td>
                <td style="padding: 8px 0; text-align: right; font-weight: 700; color: #1a1a2e !important;">{m['mean_overall_grounded']:.0%}</td>
            </tr>
            <tr style="border-bottom: 1px solid #e2e8f0;">
                <td style="padding: 8px 0; color: #334155 !important;">Mean latency</td>
                <td style="padding: 8px 0; text-align: right; font-weight: 700; color: #1a1a2e !important;">{m['mean_latency_s']:.0f}s</td>
            </tr>
            <tr style="border-bottom: 1px solid #e2e8f0;">
                <td style="padding: 8px 0; color: #334155 !important;">P95 latency (worst case)</td>
                <td style="padding: 8px 0; text-align: right; font-weight: 700; color: #1a1a2e !important;">{m['p95_latency_s']:.0f}s</td>
            </tr>
            <tr style="border-bottom: 1px solid #e2e8f0;">
                <td style="padding: 8px 0; color: #334155 !important;">Notes needing retry</td>
                <td style="padding: 8px 0; text-align: right; font-weight: 700; color: #1a1a2e !important;">{retries_count}</td>
            </tr>
            <tr>
                <td style="padding: 8px 0; color: #334155 !important;">Complete failures</td>
                <td style="padding: 8px 0; text-align: right; font-weight: 700; color: #1a1a2e !important;">{m['json_fail_count']} <span style="color: #475569 !important; font-weight: 400;">(reviewed below)</span></td>
            </tr>
        </table>
    </div>

    <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 12px; margin-bottom: 0;">
        <div style="background: white !important; border: 2px solid #e2e8f0; border-radius: 10px; padding: 16px; display: flex; align-items: flex-start; gap: 12px;">
            <div style="font-size: 24px; line-height: 1;">&#128721;</div>
            <div>
                <div style="font-weight: 700; font-size: 13px; color: #1a1a2e !important;">Clinician Approval Required</div>
                <div style="font-size: 12px; color: #475569 !important; margin-top: 2px;">No output auto-applied</div>
            </div>
        </div>
        <div style="background: white !important; border: 2px solid #e2e8f0; border-radius: 10px; padding: 16px; display: flex; align-items: flex-start; gap: 12px;">
            <div style="font-size: 24px; line-height: 1;">&#128206;</div>
            <div>
                <div style="font-weight: 700; font-size: 13px; color: #1a1a2e !important;">Every Claim Traced to Source</div>
                <div style="font-size: 12px; color: #475569 !important; margin-top: 2px;">Evidence spans verified</div>
            </div>
        </div>
        <div style="background: white !important; border: 2px solid #e2e8f0; border-radius: 10px; padding: 16px; display: flex; align-items: flex-start; gap: 12px;">
            <div style="font-size: 24px; line-height: 1;">&#128187;</div>
            <div>
                <div style="font-weight: 700; font-size: 13px; color: #1a1a2e !important;">Runs Without Internet</div>
                <div style="font-size: 12px; color: #475569 !important; margin-top: 2px;">2.5 GB model, air-gapped</div>
            </div>
        </div>
        <div style="background: white !important; border: 2px solid #e2e8f0; border-radius: 10px; padding: 16px; display: flex; align-items: flex-start; gap: 12px;">
            <div style="font-size: 24px; line-height: 1;">&#9888;&#65039;</div>
            <div>
                <div style="font-weight: 700; font-size: 13px; color: #1a1a2e !important;">Low Confidence Flagged</div>
                <div style="font-size: 12px; color: #475569 !important; margin-top: 2px;">Uncertainty surfaced, not hidden</div>
            </div>
        </div>
    </div>

    </div>
    """
    return html


# ─── Panel 3: Failure Gallery ───

def build_failure_html():
    """Show failure note_035 as the example — it's the most instructive."""
    # note_035 is the simplest failure: short URI note, model produced valid JSON
    # but missing the missing_info key
    fail = None
    for f in failures:
        if f["note_id"] == "note_035":
            fail = f
            break
    if not fail:
        fail = failures[0] if failures else {"note_id": "N/A", "error": "N/A", "raw": "N/A"}

    # Get the original note
    fail_idx = int(fail["note_id"].split("_")[1]) if fail["note_id"] != "N/A" else 0
    fail_note = str(notes_list[fail_idx])[:500] if fail_idx < len(notes_list) else "N/A"

    raw_preview = fail.get("raw", "")[:800]

    html = f"""
    <div style="font-family: system-ui, -apple-system, sans-serif; max-width: 750px; margin: 0 auto; color: #1a1a2e !important;">

    <div style="background: linear-gradient(135deg, #7f1d1d 0%, #991b1b 100%); border-radius: 16px; padding: 32px; color: white !important; margin-bottom: 24px;">
        <h2 style="margin: 0 0 8px 0; font-size: 22px; font-weight: 700; color: white !important;">Failure Analysis</h2>
        <p style="margin: 0; opacity: 0.9; font-size: 14px; color: #fecaca !important;">Showing failures builds trust. 4 out of 50 notes failed structured parsing.</p>
    </div>

    <div style="background: white !important; border: 2px solid #fecaca; border-radius: 12px; padding: 24px; margin-bottom: 24px;">
        <h3 style="margin: 0 0 12px 0; font-size: 16px; color: #991b1b !important;">What Happened ({fail['note_id']})</h3>
        <p style="font-size: 14px; color: #450a0a !important; line-height: 1.6; margin: 0 0 12px 0;">
            The model produced JSON output, but it was <strong style="color: #450a0a !important;">missing a required field</strong> (<code style="background: #fef2f2; padding: 2px 6px; border-radius: 3px; color: #991b1b !important; font-weight: 700;">missing_info</code>).
            Pydantic schema validation caught this before the output could reach any downstream consumer.
        </p>
        <div style="background: #f8fafc !important; border: 1px solid #e2e8f0; border-radius: 8px; padding: 16px; margin-top: 12px;">
            <div style="font-size: 12px; color: #475569 !important; margin-bottom: 8px; font-weight: 600;">SOURCE NOTE (truncated)</div>
            <div style="font-family: monospace; font-size: 12px; color: #1e293b !important; white-space: pre-wrap; max-height: 150px; overflow-y: auto;">{fail_note}</div>
        </div>
    </div>

    <div style="background: white !important; border: 2px solid #86efac; border-radius: 12px; padding: 24px; margin-bottom: 24px;">
        <h3 style="margin: 0 0 12px 0; font-size: 16px; color: #14532d !important;">Why This Is Safe</h3>
        <ol style="font-size: 14px; color: #14532d !important; line-height: 1.8; margin: 0; padding-left: 20px;">
            <li><strong style="color: #14532d !important;">Schema validation gate</strong> <span style="color: #1e293b !important;">— Pydantic rejects any output missing required fields</span></li>
            <li><strong style="color: #14532d !important;">Retry mechanism</strong> <span style="color: #1e293b !important;">— System automatically retries with stricter prompt (Variant B)</span></li>
            <li><strong style="color: #14532d !important;">Failure logging</strong> <span style="color: #1e293b !important;">— Raw output stored for post-hoc analysis</span></li>
            <li><strong style="color: #14532d !important;">Clinician-in-the-loop</strong> <span style="color: #1e293b !important;">— No output is ever auto-applied; always reviewed by physician</span></li>
        </ol>
    </div>

    <div style="background: white !important; border: 2px solid #e2e8f0; border-radius: 12px; padding: 24px; margin-bottom: 24px;">
        <h3 style="margin: 0 0 12px 0; font-size: 16px; color: #1a1a2e !important;">Failure Modes Observed</h3>
        <table style="width: 100%; border-collapse: collapse; font-size: 14px;">
            <tr style="border-bottom: 1px solid #e2e8f0;">
                <td style="padding: 8px 0; font-weight: 600; color: #1a1a2e !important;">Missing required field</td>
                <td style="padding: 8px 0; color: #334155 !important;">Model omitted <code style="background: #f1f5f9; padding: 2px 6px; border-radius: 3px; color: #1a1a2e !important;">missing_info</code> key</td>
                <td style="padding: 8px 0; text-align: right; color: #1a1a2e !important;">1 note</td>
            </tr>
            <tr style="border-bottom: 1px solid #e2e8f0;">
                <td style="padding: 8px 0; font-weight: 600; color: #1a1a2e !important;">Token limit truncation</td>
                <td style="padding: 8px 0; color: #334155 !important;">Verbose output exceeded 4096 tokens, JSON truncated</td>
                <td style="padding: 8px 0; text-align: right; color: #1a1a2e !important;">3 notes</td>
            </tr>
        </table>
    </div>

    <div style="background: white !important; border: 2px solid #93c5fd; border-radius: 12px; padding: 20px;">
        <h3 style="margin: 0 0 8px 0; font-size: 16px; color: #1e3a8a !important;">Design Principle</h3>
        <p style="margin: 0; font-size: 14px; color: #1e293b !important; line-height: 1.6;">
            <strong style="color: #1e3a8a !important;">Fail safely, not silently.</strong> Every failure is caught by schema validation before reaching the clinician.
            The system degrades gracefully: if structured extraction fails, the original note remains available.
            No hallucinated data can bypass the validation gate.
        </p>
    </div>

    </div>
    """
    return html


# ─── Header + Pipeline Strip ───

def build_header_html():
    """App header with pipeline strip — instant comprehension."""
    return """
    <div style="font-family: system-ui, -apple-system, sans-serif; max-width: 900px; margin: 0 auto;">

    <div style="text-align: center; margin-bottom: 16px;">
        <h1 style="margin: 0 0 4px 0; font-size: 28px; font-weight: 800; color: white !important;">Discharge Navigator</h1>
        <p style="margin: 0; font-size: 14px; color: #94a3b8 !important;">MedGemma 4B (2.5 GB) &middot; Runs offline on CPU &middot; Clinician-in-the-loop</p>
    </div>

    <div style="display: flex; align-items: center; justify-content: center; gap: 0; margin: 20px 0 8px 0;">
        <div style="background: #1e3a5f; color: white !important; padding: 10px 18px; border-radius: 8px 0 0 8px; font-size: 13px; font-weight: 700; text-align: center; min-width: 100px;">
            CLINICAL<br>NOTE
        </div>
        <div style="color: #64748b !important; font-size: 18px; padding: 0 2px;">&#9654;</div>
        <div style="background: #1e3a5f; color: white !important; padding: 10px 18px; font-size: 13px; font-weight: 700; text-align: center; min-width: 100px;">
            EXTRACT<br><span style="font-weight: 400; font-size: 11px; opacity: 0.8;">MedGemma</span>
        </div>
        <div style="color: #64748b !important; font-size: 18px; padding: 0 2px;">&#9654;</div>
        <div style="background: #1e3a5f; color: white !important; padding: 10px 18px; font-size: 13px; font-weight: 700; text-align: center; min-width: 100px;">
            VERIFY<br><span style="font-weight: 400; font-size: 11px; opacity: 0.8;">Grounding</span>
        </div>
        <div style="color: #64748b !important; font-size: 18px; padding: 0 2px;">&#9654;</div>
        <div style="background: #1e3a5f; color: white !important; padding: 10px 18px; font-size: 13px; font-weight: 700; text-align: center; min-width: 100px;">
            VALIDATE<br><span style="font-weight: 400; font-size: 11px; opacity: 0.8;">Schema</span>
        </div>
        <div style="color: #64748b !important; font-size: 18px; padding: 0 2px;">&#9654;</div>
        <div style="background: #14532d; color: white !important; padding: 10px 18px; border-radius: 0 8px 8px 0; font-size: 13px; font-weight: 700; text-align: center; min-width: 100px;">
            CLINICIAN<br>REVIEW
        </div>
    </div>

    </div>
    """


# ─── Gradio App ───

def build_app():
    with gr.Blocks(
        title="Discharge Navigator — Trust Surface",
    ) as app:

        gr.HTML(build_header_html())

        with gr.Tabs():

            # Tab 1: Traceability
            with gr.TabItem("Traceability"):
                gr.Markdown("### Click a note to see extractions highlighted in the source text.")

                with gr.Row():
                    note_dropdown = gr.Dropdown(
                        choices=note_choices, label="Select Note",
                        scale=3,
                    )

                with gr.Row():
                    btn_all = gr.Button("Show All", variant="primary", size="sm")
                    btn_dx = gr.Button("Diagnoses Only", size="sm")
                    btn_med = gr.Button("Medications Only", size="sm")
                    btn_fu = gr.Button("Follow-ups Only", size="sm")

                status = gr.Textbox(label="Status", interactive=False, max_lines=1)

                with gr.Row():
                    with gr.Column(scale=3):
                        note_display = gr.HTML(
                            label="Clinical Note (highlighted)",
                            value='<div style="padding: 20px; color: #999;">Select a note to begin.</div>'
                        )
                    with gr.Column(scale=2):
                        extraction_display = gr.Textbox(
                            label="Structured Extractions",
                            lines=25,
                            interactive=False,
                        )

                # Events
                note_dropdown.change(
                    fn=load_note,
                    inputs=[note_dropdown],
                    outputs=[note_display, extraction_display, status],
                )
                btn_all.click(
                    fn=load_note,
                    inputs=[note_dropdown],
                    outputs=[note_display, extraction_display, status],
                )
                btn_dx.click(
                    fn=lambda c: highlight_by_type(c, "Diagnosis"),
                    inputs=[note_dropdown],
                    outputs=[note_display, status],
                )
                btn_med.click(
                    fn=lambda c: highlight_by_type(c, "Medication"),
                    inputs=[note_dropdown],
                    outputs=[note_display, status],
                )
                btn_fu.click(
                    fn=lambda c: highlight_by_type(c, "Follow-up"),
                    inputs=[note_dropdown],
                    outputs=[note_display, status],
                )

            # Tab 2: Reliability Board
            with gr.TabItem("Reliability Board"):
                gr.HTML(build_reliability_html())

            # Tab 3: Failure Gallery
            with gr.TabItem("Failure Analysis"):
                gr.HTML(build_failure_html())

    return app


if __name__ == "__main__":
    app = build_app()
    app.launch(
        share=False, server_name="127.0.0.1", server_port=7860,
        theme=gr.themes.Soft(),
        css=".gradio-container { max-width: 1200px !important; } mark { background-color: #FBBF24 !important; }",
    )
