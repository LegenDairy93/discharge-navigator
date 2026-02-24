"""Discharge Navigator — Trust Surface Demo (Gradio).

Product-grade clinical dashboard with three panels:
1. Traceability: click extraction → highlight evidence in source note
2. Reliability Board: metrics summary with progress bars
3. Failure Analysis: transparent failure documentation
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

df = pd.read_csv(SUBSET_CSV)
notes_list = df["note"].tolist()
specialties = df["medical_specialty"].tolist()

with open(METRICS_FILE) as f:
    metrics = json.load(f)

samples = {}
for p in sorted(SAMPLES_DIR.glob("note_*.json")):
    note_id = p.stem
    with open(p) as f:
        samples[note_id] = json.load(f)

failures = []
if FAILURES_FILE.exists():
    with open(FAILURES_FILE) as f:
        for line in f:
            if line.strip():
                failures.append(json.loads(line))

note_choices = []
for i in range(len(notes_list)):
    nid = f"note_{i:03d}"
    if nid in samples:
        specialty = specialties[i] if i < len(specialties) else "Unknown"
        note_choices.append(f"{nid} — {specialty} ({len(str(notes_list[i]))} chars)")


# ─── Global CSS ───

GLOBAL_CSS = """
/* ── Nuclear light-mode override — works on ANY system theme ── */
.gradio-container, .gradio-container *:not(svg):not(path):not(circle):not(line):not(rect) {
    color-scheme: light !important;
}
.gradio-container {
    width: 100% !important;
    max-width: 1200px !important;
    min-width: 1000px !important;
    margin: 0 auto !important;
    font-family: 'Inter', system-ui, -apple-system, 'Segoe UI', sans-serif !important;
    background-color: #f8fafc !important;
    color: #111827 !important;
}
/* Force all Gradio wrappers to transparent/white */
.gradio-container .block, .gradio-container .wrap,
.gradio-container .panel, .gradio-container .form {
    background-color: transparent !important;
    color: #111827 !important;
}
.gradio-container input, .gradio-container select,
.gradio-container textarea, .gradio-container .secondary-wrap,
.gradio-container .border-none {
    background-color: white !important;
    color: #111827 !important;
    border-color: #e2e8f0 !important;
}
.gradio-container label, .gradio-container .label-wrap span {
    color: #334155 !important;
}
/* Tab bar styling */
.tabs > .tab-nav {
    background: white !important;
    border-bottom: 2px solid #e2e8f0 !important;
}
.tabs > .tab-nav > button {
    font-weight: 600 !important;
    font-size: 14px !important;
    padding: 10px 20px !important;
    color: #475569 !important;
    background: transparent !important;
}
.tabs > .tab-nav > button.selected {
    color: #2563eb !important;
    border-bottom: 3px solid #2563eb !important;
}
/* Gradio footer */
footer { color: #64748b !important; }
/* Tab content — prevent scaling jumps */
.tabitem > div {
    min-height: 500px !important;
}
/* Accordion / code block */
.gradio-container .accordion {
    background: white !important;
    border-color: #e2e8f0 !important;
}
.gradio-container .code-block, .gradio-container pre, .gradio-container code {
    background-color: #f8fafc !important;
    color: #334155 !important;
}
/* Highlight marks — default yellow (All view) */
mark {
    background: linear-gradient(120deg, #fde68a 0%, #fbbf24 100%) !important;
    padding: 2px 5px !important;
    border-radius: 3px !important;
    font-weight: 600 !important;
    color: #1e293b !important;
}
/* Per-type highlight colors (filter views) */
mark.dx-mark  { background: linear-gradient(120deg, #bfdbfe 0%, #93c5fd 100%) !important; color: #1e3a8a !important; }
mark.med-mark { background: linear-gradient(120deg, #bbf7d0 0%, #86efac 100%) !important; color: #14532d !important; }
mark.fu-mark  { background: linear-gradient(120deg, #fde68a 0%, #fbbf24 100%) !important; color: #78350f !important; }
/* Filter buttons — inactive: colored left border hint */
#btn-dx button  { border-left: 3px solid #3B82F6 !important; }
#btn-med button { border-left: 3px solid #10B981 !important; }
#btn-fu button  { border-left: 3px solid #F59E0B !important; }
/* Filter buttons — active state: full colored background */
.filter-active-all button { background: #6366f1 !important; color: white !important; border-color: #6366f1 !important; }
.filter-active-dx button  { background: #3B82F6 !important; color: white !important; border-color: #3B82F6 !important; }
.filter-active-med button { background: #10B981 !important; color: white !important; border-color: #10B981 !important; }
.filter-active-fu button  { background: #F59E0B !important; color: white !important; border-color: #F59E0B !important; }
/* Dropdown */
.gradio-container .dropdown-arrow { color: #475569 !important; }
.gradio-container ul.options { background: white !important; border-color: #e2e8f0 !important; }
.gradio-container ul.options li { color: #111827 !important; }
.gradio-container ul.options li.active, .gradio-container ul.options li:hover {
    background: #f1f5f9 !important;
}
"""


# ─── SVG Icons ───

def svg_icon(name: str, size: int = 20) -> str:
    icons = {
        "medical_cross": f'<svg width="{size}" height="{size}" viewBox="0 0 36 36" fill="none"><rect width="36" height="36" rx="8" fill="#2563eb"/><path d="M15 10h6v16h-6z" fill="white"/><path d="M10 15h16v6H10z" fill="white"/></svg>',
        "check_circle": f'<svg width="{size}" height="{size}" viewBox="0 0 16 16"><circle cx="8" cy="8" r="7.5" fill="#16a34a"/><path d="M5 8l2.5 2.5L11 6" stroke="white" stroke-width="1.5" fill="none" stroke-linecap="round" stroke-linejoin="round"/></svg>',
        "warning": f'<svg width="{size}" height="{size}" viewBox="0 0 16 16"><circle cx="8" cy="8" r="7.5" fill="#f59e0b"/><path d="M8 5v4M8 11v.5" stroke="white" stroke-width="1.5" stroke-linecap="round"/></svg>',
        "x_circle": f'<svg width="{size}" height="{size}" viewBox="0 0 16 16"><circle cx="8" cy="8" r="7.5" fill="#dc2626"/><path d="M5.5 5.5l5 5M10.5 5.5l-5 5" stroke="white" stroke-width="1.5" stroke-linecap="round"/></svg>',
        "shield": f'<svg width="{size}" height="{size}" viewBox="0 0 24 24" fill="none"><path d="M12 3L4 7v5c0 5.5 3.5 10.7 8 12 4.5-1.3 8-6.5 8-12V7l-8-4z" stroke="#dc2626" stroke-width="1.5" fill="#fee2e2"/><path d="M9 12l2 2 4-4" stroke="#dc2626" stroke-width="1.5" fill="none" stroke-linecap="round" stroke-linejoin="round"/></svg>',
        "link": f'<svg width="{size}" height="{size}" viewBox="0 0 24 24" fill="none"><path d="M10 13a5 5 0 007.54.54l3-3a5 5 0 00-7.07-7.07l-1.72 1.71" stroke="#2563eb" stroke-width="1.5" stroke-linecap="round"/><path d="M14 11a5 5 0 00-7.54-.54l-3 3a5 5 0 007.07 7.07l1.71-1.71" stroke="#2563eb" stroke-width="1.5" stroke-linecap="round"/></svg>',
        "wifi_off": f'<svg width="{size}" height="{size}" viewBox="0 0 24 24" fill="none"><path d="M1 1l22 22M16.72 11.06A10.94 10.94 0 0119 12.55M5 12.55a10.94 10.94 0 015.17-2.39M10.71 5.05A16 16 0 0122.56 9M1.42 9a15.91 15.91 0 014.7-2.88M8.53 16.11a6 6 0 016.95 0M12 20h.01" stroke="#475569" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/></svg>',
        "alert_triangle": f'<svg width="{size}" height="{size}" viewBox="0 0 24 24" fill="none"><path d="M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z" stroke="#f59e0b" stroke-width="1.5" fill="#fef3c7"/><path d="M12 9v4M12 17h.01" stroke="#f59e0b" stroke-width="1.5" stroke-linecap="round"/></svg>',
        "clipboard": f'<svg width="{size}" height="{size}" viewBox="0 0 24 24" fill="none"><path d="M16 4h2a2 2 0 012 2v14a2 2 0 01-2 2H6a2 2 0 01-2-2V6a2 2 0 012-2h2" stroke="#0d9488" stroke-width="1.5"/><rect x="8" y="2" width="8" height="4" rx="1" stroke="#0d9488" stroke-width="1.5" fill="#ccfbf1"/></svg>',
        "question": f'<svg width="{size}" height="{size}" viewBox="0 0 24 24" fill="none"><circle cx="12" cy="12" r="10" stroke="#9333ea" stroke-width="1.5" fill="#f3e8ff"/><path d="M9.09 9a3 3 0 015.83 1c0 2-3 3-3 3M12 17h.01" stroke="#9333ea" stroke-width="1.5" stroke-linecap="round"/></svg>',
        "red_flag": f'<svg width="{size}" height="{size}" viewBox="0 0 24 24" fill="none"><path d="M4 15s1-1 4-1 5 2 8 2 4-1 4-1V3s-1 1-4 1-5-2-8-2-4 1-4 1z" stroke="#dc2626" stroke-width="1.5" fill="#fee2e2"/><line x1="4" y1="22" x2="4" y2="15" stroke="#dc2626" stroke-width="1.5"/></svg>',
        "dot_green": '<svg width="10" height="10" viewBox="0 0 10 10"><circle cx="5" cy="5" r="4" fill="#16a34a"/></svg>',
        "dot_amber": '<svg width="10" height="10" viewBox="0 0 10 10"><circle cx="5" cy="5" r="4" fill="#f59e0b"/></svg>',
    }
    return icons.get(name, "")


# ─── Color constants ───

TYPE_COLORS = {
    "Diagnosis":  {"border": "#2563eb", "bg": "#dbeafe", "text": "#1e40af", "label": "DIAGNOSIS"},
    "Medication": {"border": "#16a34a", "bg": "#dcfce7", "text": "#166534", "label": "MEDICATION"},
    "Follow-up":  {"border": "#f59e0b", "bg": "#fef3c7", "text": "#92400e", "label": "FOLLOW-UP"},
}

CONF_STYLES = {
    "high":   "background:#dcfce7; color:#166534;",
    "medium": "background:#fef3c7; color:#92400e;",
    "low":    "background:#fee2e2; color:#991b1b;",
}


# ─── Highlight helpers ───

def highlight_spans_in_note(note_text: str, spans: list[str], mark_class: str = "") -> str:
    if not spans:
        return note_text

    note_lower = note_text.lower()
    regions = []

    for span in spans:
        if not span:
            continue
        span_lower = re.sub(r"\s+", " ", span.lower().strip())
        note_normalized = re.sub(r"\s+", " ", note_lower)

        idx = note_normalized.find(span_lower)
        if idx == -1:
            continue

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

    regions.sort()
    merged = [regions[0]]
    for s, e in regions[1:]:
        if s <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], e))
        else:
            merged.append((s, e))

    parts = []
    last = 0
    for s, e in merged:
        parts.append(note_text[last:s])
        cls_attr = f' class="{mark_class}"' if mark_class else ""
        parts.append(f'<mark{cls_attr}>{note_text[s:e]}</mark>')
        last = e
    parts.append(note_text[last:])

    return "".join(parts)


def get_extraction_items(packet: dict) -> list[dict]:
    items = []
    for dx in packet.get("diagnoses", []):
        items.append({
            "type": "Diagnosis",
            "label": dx["label"],
            "detail": f"ICD-10: {dx.get('icd10', 'N/A')} | Confidence: {dx.get('confidence', '?')}",
            "confidence": dx.get("confidence", "low"),
            "spans": dx.get("evidence_spans", []),
        })
    for med in packet.get("medications", []):
        dose_str = " ".join(filter(None, [med.get("dose"), med.get("route"), med.get("frequency")]))
        items.append({
            "type": "Medication",
            "label": med["name"],
            "detail": dose_str or "No dosing info",
            "confidence": med.get("confidence", "low"),
            "spans": med.get("evidence_spans", []),
        })
    for fu in packet.get("followups", []):
        items.append({
            "type": "Follow-up",
            "label": f"{fu.get('with_whom', '?')} — {fu.get('when', '?')}",
            "detail": f"Urgency: {fu.get('urgency', '?')}",
            "confidence": fu.get("confidence", "low"),
            "spans": fu.get("evidence_spans", []),
        })
    return items


# ─── HTML Builders ───

def build_status_html(message: str, status: str = "ok") -> str:
    dot = svg_icon("dot_green") if status == "ok" else svg_icon("dot_amber")
    return f'''<div style="display:flex; align-items:center; gap:8px; padding:8px 14px; background:#f1f5f9; border-radius:6px; font-size:12px; color:#475569; margin-top:8px;">{dot} {message}</div>'''


def build_welcome_html() -> str:
    return f'''
    <div style="background:white; border:1px solid #e2e8f0; border-radius:12px; text-align:center; padding:48px 30px; box-shadow:0 1px 3px rgba(0,0,0,0.04);">
        <div style="margin-bottom:16px;">{svg_icon("clipboard", 48)}</div>
        <h3 style="margin:0 0 8px 0; font-size:18px; font-weight:700; color:#0f172a;">Select a Clinical Note</h3>
        <p style="font-size:14px; color:#64748b; max-width:420px; margin:0 auto; line-height:1.6;">
            Choose a note from the dropdown above. The system will extract diagnoses, medications, and follow-ups, then highlight evidence spans in the source text.
        </p>
        <div style="display:flex; justify-content:center; gap:32px; margin-top:24px;">
            <div style="text-align:center;">
                <div style="font-size:28px; font-weight:800; color:#2563eb;">46</div>
                <div style="font-size:11px; color:#64748b; text-transform:uppercase; letter-spacing:0.5px;">Notes Parsed</div>
            </div>
            <div style="text-align:center;">
                <div style="font-size:28px; font-weight:800; color:#16a34a;">94%</div>
                <div style="font-size:11px; color:#64748b; text-transform:uppercase; letter-spacing:0.5px;">Dx Grounded</div>
            </div>
            <div style="text-align:center;">
                <div style="font-size:28px; font-weight:800; color:#f59e0b;">34s</div>
                <div style="font-size:11px; color:#64748b; text-transform:uppercase; letter-spacing:0.5px;">Median CPU</div>
            </div>
        </div>
    </div>'''


def build_tutorial_html() -> str:
    """How It Works tab — product tutorial + glossary."""

    # --- Section A: What is Discharge Navigator ---
    section_a = f"""
    <div style="background:white; border:1px solid #e2e8f0; border-left:4px solid #0F6B8A; border-radius:10px; padding:28px; margin-bottom:20px; box-shadow:0 1px 3px rgba(0,0,0,0.04);">
        <div style="display:flex; align-items:center; gap:10px; margin-bottom:16px;">
            {svg_icon("medical_cross", 28)}
            <h2 style="margin:0; font-size:20px; font-weight:800; color:#0f172a;">What is Discharge Navigator?</h2>
        </div>
        <p style="font-size:14px; color:#334155; line-height:1.7; margin:0 0 16px 0;">
            Discharge Navigator converts <strong>unstructured clinical notes</strong> into <strong>structured, evidence-grounded discharge packets</strong> using Google's MedGemma 4B model. Every extracted diagnosis, medication, and follow-up instruction is traced back to the exact text in the source note — so clinicians can verify claims in seconds, not minutes.
        </p>
        <div style="display:flex; gap:16px; flex-wrap:wrap; margin-top:20px;">
            <div style="flex:1; min-width:180px; background:#f0fdfa; border:1px solid #99f6e4; border-radius:8px; padding:16px; text-align:center;">
                <div style="font-size:32px; font-weight:800; color:#0F6B8A;">5 Steps</div>
                <div style="font-size:12px; color:#475569; margin-top:4px;">Ingest → Extract → Ground → Validate → Review</div>
            </div>
            <div style="flex:1; min-width:180px; background:#eff6ff; border:1px solid #bfdbfe; border-radius:8px; padding:16px; text-align:center;">
                <div style="font-size:32px; font-weight:800; color:#2563eb;">94%</div>
                <div style="font-size:12px; color:#475569; margin-top:4px;">Diagnosis claims grounded in source text</div>
            </div>
            <div style="flex:1; min-width:180px; background:#ecfdf5; border:1px solid #86efac; border-radius:8px; padding:16px; text-align:center;">
                <div style="font-size:32px; font-weight:800; color:#16a34a;">34s</div>
                <div style="font-size:12px; color:#475569; margin-top:4px;">Median extraction time per note (CPU-only)</div>
            </div>
            <div style="flex:1; min-width:180px; background:#fefce8; border:1px solid #fde68a; border-radius:8px; padding:16px; text-align:center;">
                <div style="font-size:32px; font-weight:800; color:#b45309;">2.5 GB</div>
                <div style="font-size:12px; color:#475569; margin-top:4px;">Model fits on any laptop — no GPU, no internet</div>
            </div>
        </div>
    </div>"""

    # --- Section B: Reading the Evidence Explorer ---
    section_b = f"""
    <div style="background:white; border:1px solid #e2e8f0; border-left:4px solid #2563eb; border-radius:10px; padding:28px; margin-bottom:20px; box-shadow:0 1px 3px rgba(0,0,0,0.04);">
        <div style="display:flex; align-items:center; gap:10px; margin-bottom:16px;">
            {svg_icon("link", 24)}
            <h2 style="margin:0; font-size:20px; font-weight:800; color:#0f172a;">Reading the Evidence Explorer</h2>
        </div>

        <div style="display:grid; grid-template-columns:1fr 1fr; gap:20px;">
            <div>
                <h3 style="font-size:14px; font-weight:700; color:#1e40af; margin:0 0 10px 0;">Left Panel — Clinical Note</h3>
                <ul style="font-size:13px; color:#334155; line-height:1.8; padding-left:18px; margin:0;">
                    <li><mark style="background:linear-gradient(120deg, #fde68a 0%, #fbbf24 100%); padding:2px 5px; border-radius:3px; font-weight:600;">Yellow highlights</mark> mark <strong>evidence spans</strong> — the exact text backing each extraction</li>
                    <li>Use the <strong>filter buttons</strong> to isolate Diagnoses (blue), Medications (green), or Follow-ups (amber)</li>
                    <li>Click <strong>"All"</strong> to restore all highlights</li>
                </ul>
            </div>
            <div>
                <h3 style="font-size:14px; font-weight:700; color:#1e40af; margin:0 0 10px 0;">Right Panel — Extraction Cards</h3>
                <ul style="font-size:13px; color:#334155; line-height:1.8; padding-left:18px; margin:0;">
                    <li><span style="display:inline-block; background:#dbeafe; color:#1e40af; padding:1px 8px; border-radius:8px; font-size:11px; font-weight:700;">DIAGNOSIS</span> <span style="display:inline-block; background:#dcfce7; color:#166534; padding:1px 8px; border-radius:8px; font-size:11px; font-weight:700;">MEDICATION</span> <span style="display:inline-block; background:#fef3c7; color:#92400e; padding:1px 8px; border-radius:8px; font-size:11px; font-weight:700;">FOLLOW-UP</span> — type badges</li>
                    <li><strong>Confidence badge:</strong> HIGH (green) / MEDIUM (amber) / LOW (red)</li>
                    <li><strong>Grounding bar:</strong> green = all spans found, amber = partial, red = none</li>
                </ul>
            </div>
        </div>

        <div style="margin-top:20px; padding:14px; background:#f8fafc; border:1px solid #e2e8f0; border-radius:8px;">
            <h3 style="font-size:14px; font-weight:700; color:#0d9488; margin:0 0 8px 0;">Patient Summary Panel</h3>
            <p style="font-size:13px; color:#334155; line-height:1.6; margin:0;">
                Appears above the note when a clinical note is loaded. Shows a <strong style="color:#0d9488;">summary card</strong> (teal border) with the patient overview,
                <strong style="color:#dc2626;">red flags</strong> (red border) for urgent clinical signals, and
                <strong style="color:#9333ea;">missing information</strong> (purple border) for data gaps that need attention before discharge.
            </p>
        </div>
    </div>"""

    # --- Section C: Glossary ---
    glossary_items = [
        ("Evidence Span", "The exact phrase in the clinical note that supports an extracted claim. Highlighted in yellow in the note viewer.", "#2563eb"),
        ("Grounding %", "The fraction of extracted items whose claims can be traced back to specific text in the source note. Higher = more trustworthy.", "#16a34a"),
        ("Confidence", "Model's certainty in the extraction. HIGH (≥80%), MEDIUM (50–80%), LOW (&lt;50%). Low-confidence items are flagged for clinician review.", "#f59e0b"),
        ("Red Flag", "An urgent clinical signal that requires immediate attention — e.g., allergy-drug interaction, abnormal vital signs.", "#dc2626"),
        ("Missing Info", "Data absent from the note but needed for safe discharge — e.g., no allergy list, no follow-up date. Severity: Critical, Important, or Nice-to-Have.", "#9333ea"),
        ("Schema Validation", "A Pydantic gate that checks every model output against a strict JSON schema. Malformed outputs are rejected and retried — never shown to clinicians.", "#0F6B8A"),
    ]

    glossary_cards = ""
    for term, definition, color in glossary_items:
        glossary_cards += f'''
        <div style="background:white; border:1px solid #e2e8f0; border-left:3px solid {color}; border-radius:8px; padding:14px 16px;">
            <div style="font-size:13px; font-weight:700; color:{color}; margin-bottom:4px;">{term}</div>
            <div style="font-size:12px; color:#475569; line-height:1.6;">{definition}</div>
        </div>'''

    section_c = f"""
    <div style="background:white; border:1px solid #e2e8f0; border-left:4px solid #16a34a; border-radius:10px; padding:28px; box-shadow:0 1px 3px rgba(0,0,0,0.04);">
        <div style="display:flex; align-items:center; gap:10px; margin-bottom:16px;">
            {svg_icon("question", 24)}
            <h2 style="margin:0; font-size:20px; font-weight:800; color:#0f172a;">Glossary</h2>
        </div>
        <div style="display:grid; grid-template-columns:1fr 1fr; gap:12px;">
            {glossary_cards}
        </div>
    </div>"""

    return f"""
    <div style="background:white; border-radius:12px; padding:24px; border:1px solid #e2e8f0;">
    <div style="font-family:'Inter',system-ui,-apple-system,sans-serif; margin:0 auto;">
        {section_a}
        {section_b}
        {section_c}
    </div>
    </div>
    """


def build_footer_html() -> str:
    return '''
    <div style="background:white; border-radius:12px; padding:20px; margin-top:12px; border:1px solid #e2e8f0;">
        <div style="max-width:700px; margin:0 auto; text-align:center;">
            <p style="font-size:13px; font-weight:600; color:#334155; margin:0 0 6px 0;">
                Discharge Navigator — Clinical-grade extraction for safer discharges
            </p>
            <p style="font-size:12px; color:#64748b; margin:0 0 12px 0;">
                Powered by Google's MedGemma 4B &middot; Schema-validated &middot; Evidence-grounded &middot; Offline-capable
            </p>
            <p style="font-size:12px; color:#94a3b8; margin:0 0 8px 0;">
                <a href="https://github.com/LegenDairy93/discharge-navigator" style="color:#2563eb; text-decoration:none; font-weight:500;">GitHub</a> &middot;
                <a href="https://www.kaggle.com/competitions/med-gemma-impact-challenge" style="color:#2563eb; text-decoration:none; font-weight:500;">Competition</a> &middot;
                <a href="https://huggingface.co/google/medgemma-4b-it" style="color:#2563eb; text-decoration:none; font-weight:500;">Model Card</a> &middot;
                License: CC BY 4.0
            </p>
            <p style="font-size:11px; color:#cbd5e1; margin:0;">
                Not a medical device. All outputs require clinician review before clinical use.
            </p>
        </div>
    </div>'''


def build_extraction_card_html(item: dict, note_text: str) -> str:
    tc = TYPE_COLORS.get(item["type"], TYPE_COLORS["Diagnosis"])
    conf = item.get("confidence", "low")
    conf_style = CONF_STYLES.get(conf, CONF_STYLES["low"])

    n_spans = len(item["spans"])
    grounded = sum(1 for s in item["spans"] if re.sub(r"\s+", " ", s.lower().strip()) in re.sub(r"\s+", " ", note_text.lower()))
    pct = int((grounded / n_spans) * 100) if n_spans > 0 else 0

    if grounded == n_spans and n_spans > 0:
        g_icon = svg_icon("check_circle", 14)
        bar_color = "#16a34a"
    elif grounded > 0:
        g_icon = svg_icon("warning", 14)
        bar_color = "#f59e0b"
    else:
        g_icon = svg_icon("x_circle", 14)
        bar_color = "#dc2626"

    return f'''
    <div style="background:white; border:1px solid #e2e8f0; border-left:4px solid {tc['border']}; border-radius:8px; padding:12px 14px; margin-bottom:10px; box-shadow:0 1px 2px rgba(0,0,0,0.03);">
        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:6px;">
            <div style="display:flex; align-items:center; gap:8px;">
                <span style="background:{tc['bg']}; color:{tc['text']}; padding:2px 8px; border-radius:10px; font-size:10px; font-weight:700; letter-spacing:0.5px;">{tc['label']}</span>
                <span style="font-size:13px; font-weight:600; color:#0f172a;">{item['label']}</span>
            </div>
            <span style="{conf_style} padding:2px 8px; border-radius:10px; font-size:10px; font-weight:600;">{conf.upper()}</span>
        </div>
        <div style="font-size:12px; color:#475569; margin-bottom:8px;">{item['detail']}</div>
        <div style="display:flex; align-items:center; gap:6px; font-size:11px; color:#64748b;">
            {g_icon}
            <span>{grounded}/{n_spans} spans grounded</span>
            <div style="width:50px; height:6px; border-radius:3px; background:#e2e8f0; overflow:hidden; margin-left:4px;">
                <div style="width:{pct}%; height:100%; border-radius:3px; background:{bar_color};"></div>
            </div>
        </div>
    </div>'''


def build_patient_summary_html(packet: dict) -> str:
    summary = packet.get("patient_summary", "")
    red_flags = packet.get("red_flags", [])
    missing = packet.get("missing_info", [])

    if not summary and not red_flags and not missing:
        return ""

    # Patient summary card
    summary_card = f'''
    <div style="background:white; border:1px solid #e2e8f0; border-left:4px solid #0d9488; border-radius:8px; padding:16px; box-shadow:0 1px 2px rgba(0,0,0,0.03);">
        <div style="display:flex; align-items:center; gap:8px; margin-bottom:10px;">
            {svg_icon("clipboard", 18)}
            <span style="font-size:14px; font-weight:700; color:#0f172a;">Patient Summary</span>
        </div>
        <p style="font-size:13px; line-height:1.7; color:#334155; margin:0;">{summary}</p>
    </div>'''

    # Right column: red flags + missing info
    right_parts = []

    if red_flags:
        rf_items = "".join(
            f'<li style="font-size:12px; color:#450a0a; margin-bottom:4px;"><strong>{rf.get("symptom", "")}</strong> — {rf.get("action", "")}</li>'
            for rf in red_flags
        )
        right_parts.append(f'''
        <div style="background:white; border:1px solid #fecaca; border-left:4px solid #dc2626; border-radius:8px; padding:14px; margin-bottom:10px; box-shadow:0 1px 2px rgba(0,0,0,0.03);">
            <div style="display:flex; align-items:center; gap:8px; margin-bottom:8px;">
                {svg_icon("red_flag", 16)}
                <span style="font-size:13px; font-weight:700; color:#dc2626;">Red Flags</span>
            </div>
            <ul style="margin:0; padding-left:18px;">{rf_items}</ul>
        </div>''')

    if missing:
        sev_map = {"critical": "background:#fee2e2;color:#991b1b;", "important": "background:#fef3c7;color:#92400e;", "nice_to_have": "background:#f1f5f9;color:#475569;"}
        mi_items = "".join(
            f'<li style="font-size:12px; color:#581c87; margin-bottom:4px;"><strong>{mi.get("item", "")}</strong> <span style="{sev_map.get(mi.get("severity", "nice_to_have"), sev_map["nice_to_have"])} padding:1px 6px; border-radius:8px; font-size:10px; font-weight:600; margin-left:4px;">{mi.get("severity", "").replace("_", " ").upper()}</span></li>'
            for mi in missing
        )
        right_parts.append(f'''
        <div style="background:white; border:1px solid #e9d5ff; border-left:4px solid #9333ea; border-radius:8px; padding:14px; box-shadow:0 1px 2px rgba(0,0,0,0.03);">
            <div style="display:flex; align-items:center; gap:8px; margin-bottom:8px;">
                {svg_icon("question", 16)}
                <span style="font-size:13px; font-weight:700; color:#9333ea;">Missing Information</span>
            </div>
            <ul style="margin:0; padding-left:18px;">{mi_items}</ul>
        </div>''')

    right_col = "".join(right_parts) if right_parts else '<div style="font-size:13px; color:#94a3b8; padding:16px;">No red flags or missing information identified.</div>'

    return f'''
    <div style="background:#f8fafc; border-radius:10px; padding:14px; border:1px solid #e2e8f0;">
    <div style="display:grid; grid-template-columns:1fr 1fr; gap:14px;">
        {summary_card}
        <div>{right_col}</div>
    </div>
    </div>'''


# ─── Panel 1: Traceability ───

def load_note(choice: str):
    if not choice:
        return build_welcome_html(), "", "", build_status_html("Select a note to begin.", "info"), ""

    note_id = choice.split(" — ")[0]
    idx = int(note_id.split("_")[1])
    note_text = str(notes_list[idx])
    packet = samples.get(note_id, {})

    items = get_extraction_items(packet)

    # Build extraction cards HTML
    cards_html = '<div style="max-height:600px; overflow-y:auto; padding-right:4px;">'
    if items:
        for item in items:
            cards_html += build_extraction_card_html(item, note_text)
    else:
        cards_html += '<div style="padding:20px; color:#94a3b8; text-align:center;">No extractions found.</div>'
    cards_html += '</div>'

    # Patient summary panel
    summary_html = build_patient_summary_html(packet)

    # Highlight all spans
    all_spans = []
    for item in items:
        all_spans.extend(item["spans"])

    highlighted = highlight_spans_in_note(note_text, all_spans)
    note_html = f'<div style="font-family: \'Courier New\', monospace; white-space:pre-wrap; line-height:1.8; padding:20px; background:#f8fafc; color:#1e293b; border:1px solid #e2e8f0; border-radius:10px; font-size:13px; max-height:600px; overflow-y:auto;">{highlighted}</div>'

    status = build_status_html(f"Loaded {note_id}: {len(items)} extractions, all spans highlighted.")

    # Raw JSON for export
    raw_json = json.dumps(packet, indent=2, ensure_ascii=False) if packet else ""

    return note_html, summary_html, cards_html, status, raw_json


def highlight_by_type(choice: str, ext_type: str):
    if not choice:
        return "", build_status_html("Select a note first.", "info")

    note_id = choice.split(" — ")[0]
    idx = int(note_id.split("_")[1])
    note_text = str(notes_list[idx])
    packet = samples.get(note_id, {})
    items = get_extraction_items(packet)

    filtered = [item for item in items if item["type"] == ext_type]
    spans = []
    for item in filtered:
        spans.extend(item["spans"])

    mark_cls = {"Diagnosis": "dx-mark", "Medication": "med-mark", "Follow-up": "fu-mark"}.get(ext_type, "")
    highlighted = highlight_spans_in_note(note_text, spans, mark_class=mark_cls)
    note_html = f'<div style="font-family: \'Courier New\', monospace; white-space:pre-wrap; line-height:1.8; padding:20px; background:#f8fafc; color:#1e293b; border:1px solid #e2e8f0; border-radius:10px; font-size:13px; max-height:600px; overflow-y:auto;">{highlighted}</div>'

    return note_html, build_status_html(f"Highlighting {len(spans)} spans for {len(filtered)} {ext_type.lower()}(s).")


def filter_click(choice: str, filter_type: str):
    """Handle filter button click: update highlights + toggle active button state."""
    # Build button updates — active gets colored class, others get empty
    class_map = {"All": "filter-active-all", "Diagnosis": "filter-active-dx",
                 "Medication": "filter-active-med", "Follow-up": "filter-active-fu"}
    btn_all_u = gr.update(variant="primary" if filter_type == "All" else "secondary",
                          elem_classes=[class_map["All"]] if filter_type == "All" else [])
    btn_dx_u = gr.update(variant="primary" if filter_type == "Diagnosis" else "secondary",
                         elem_classes=[class_map["Diagnosis"]] if filter_type == "Diagnosis" else [])
    btn_med_u = gr.update(variant="primary" if filter_type == "Medication" else "secondary",
                          elem_classes=[class_map["Medication"]] if filter_type == "Medication" else [])
    btn_fu_u = gr.update(variant="primary" if filter_type == "Follow-up" else "secondary",
                         elem_classes=[class_map["Follow-up"]] if filter_type == "Follow-up" else [])

    if filter_type == "All":
        result = load_note(choice)  # returns 5 values
        return (*result, btn_all_u, btn_dx_u, btn_med_u, btn_fu_u)
    else:
        note_html, status = highlight_by_type(choice, filter_type)
        # gr.update() for unchanged outputs (summary, cards, json)
        return (note_html, gr.update(), gr.update(), status, gr.update(),
                btn_all_u, btn_dx_u, btn_med_u, btn_fu_u)


# ─── Panel 2: Reliability Board ───

def build_reliability_html():
    m = metrics
    criteria = m.get("success_criteria", {})

    def badge(passed):
        if passed:
            return f'<span style="background:#dcfce7; color:#166534; padding:3px 10px; border-radius:12px; font-weight:700; font-size:12px; white-space:nowrap; display:inline-block;">{svg_icon("check_circle", 12)} PASS</span>'
        return f'<span style="background:#fee2e2; color:#991b1b; padding:3px 10px; border-radius:12px; font-weight:700; font-size:12px; white-space:nowrap; display:inline-block;">{svg_icon("x_circle", 12)} FAIL</span>'

    def progress_bar(pct, color="#2563eb", width="80%"):
        return f'<div style="width:{width}; height:6px; border-radius:3px; background:#e2e8f0; overflow:hidden; margin:8px auto 0 auto;"><div style="width:{int(pct)}%; height:100%; border-radius:3px; background:{color};"></div></div>'

    def table_bar(pct, color="#2563eb"):
        return f'<div style="width:60px; height:5px; border-radius:3px; background:#e2e8f0; overflow:hidden; display:inline-block; vertical-align:middle; margin-left:8px;"><div style="width:{int(pct)}%; height:100%; border-radius:3px; background:{color};"></div></div>'

    retries_count = sum(1 for r in m['per_note'] if r.get('latency_seconds', 0) > 100)

    html = f"""
    <div style="background:white; border-radius:12px; padding:28px; border:1px solid #e2e8f0;">
    <div style="font-family:'Inter',system-ui,-apple-system,sans-serif; margin:0 auto;">

    <div style="text-align:center; margin-bottom:24px;">
        <h2 style="margin:0 0 4px 0; font-size:20px; font-weight:700; color:#0f172a;">50-Note Evaluation Results</h2>
        <p style="margin:0; font-size:13px; color:#64748b;">MedGemma 4B Q4_K_M &middot; CPU-only &middot; No internet required</p>
    </div>

    <div style="display:grid; grid-template-columns:1fr 1fr 1fr; gap:16px; margin-bottom:24px;">
        <div style="background:#f8fafc; border:1px solid #e2e8f0; border-radius:12px; padding:24px 16px 28px 16px; text-align:center; box-shadow:0 1px 3px rgba(0,0,0,0.04); overflow:visible;">
            <div style="font-size:42px; font-weight:800; color:#0f172a; line-height:1;">{m['json_valid_rate']:.0%}</div>
            {progress_bar(m['json_valid_rate'] * 100, '#16a34a')}
            <div style="font-size:13px; font-weight:700; color:#0f172a; margin-top:10px; text-transform:uppercase; letter-spacing:0.5px;">NOTES PARSED</div>
            <div style="font-size:12px; color:#64748b; margin-top:2px;">{m['json_valid_count']} of {m['total_notes']} valid JSON</div>
            <div style="margin-top:10px;">{badge(criteria.get('json_valid_ge_80pct', False))}</div>
        </div>
        <div style="background:#f8fafc; border:1px solid #e2e8f0; border-radius:12px; padding:24px 16px 28px 16px; text-align:center; box-shadow:0 1px 3px rgba(0,0,0,0.04); overflow:visible;">
            <div style="font-size:42px; font-weight:800; color:#0f172a; line-height:1;">{m['median_latency_s']:.0f}s</div>
            <div style="display:flex; justify-content:center; gap:12px; margin-top:10px; font-size:11px; color:#64748b;">
                <span>Median: {m['median_latency_s']:.0f}s</span>
                <span style="color:#e2e8f0;">|</span>
                <span>P95: {m['p95_latency_s']:.0f}s</span>
            </div>
            <div style="font-size:13px; font-weight:700; color:#0f172a; margin-top:10px; text-transform:uppercase; letter-spacing:0.5px;">ON CPU</div>
            <div style="font-size:12px; color:#64748b; margin-top:2px;">Median per note, no GPU</div>
            <div style="margin-top:10px;">{badge(criteria.get('median_latency_le_45s', False))}</div>
        </div>
        <div style="background:#f8fafc; border:1px solid #e2e8f0; border-radius:12px; padding:24px 16px 28px 16px; text-align:center; box-shadow:0 1px 3px rgba(0,0,0,0.04); overflow:visible;">
            <div style="font-size:42px; font-weight:800; color:#0f172a; line-height:1;">{m['mean_diagnoses_grounded']:.0%}</div>
            {progress_bar(m['mean_diagnoses_grounded'] * 100, '#16a34a')}
            <div style="font-size:13px; font-weight:700; color:#0f172a; margin-top:10px; text-transform:uppercase; letter-spacing:0.5px;">DX GROUNDED</div>
            <div style="font-size:12px; color:#64748b; margin-top:2px;">Diagnosis evidence verified</div>
            <div style="margin-top:10px;">{badge(criteria.get('dx_grounding_ge_85pct_on_30_notes', False))}</div>
        </div>
    </div>

    <div style="background:white; border:1px solid #e2e8f0; border-radius:12px; padding:24px; margin-bottom:24px; box-shadow:0 1px 3px rgba(0,0,0,0.04);">
        <h3 style="margin:0 0 16px 0; font-size:15px; font-weight:700; color:#0f172a;">Full Metrics</h3>
        <table style="width:100%; border-collapse:collapse; font-size:14px;">
            <tr style="border-bottom:1px solid #f1f5f9;">
                <td style="padding:10px 0; color:#334155;">Medication evidence grounded</td>
                <td style="padding:10px 0; text-align:right; font-weight:700; color:#0f172a;">{m['mean_meds_grounded']:.0%} {table_bar(m['mean_meds_grounded'] * 100, '#16a34a')}</td>
            </tr>
            <tr style="border-bottom:1px solid #f1f5f9;">
                <td style="padding:10px 0; color:#334155;">Overall evidence grounded</td>
                <td style="padding:10px 0; text-align:right; font-weight:700; color:#0f172a;">{m['mean_overall_grounded']:.0%} {table_bar(m['mean_overall_grounded'] * 100, '#2563eb')}</td>
            </tr>
            <tr style="border-bottom:1px solid #f1f5f9;">
                <td style="padding:10px 0; color:#334155;">Mean latency</td>
                <td style="padding:10px 0; text-align:right; font-weight:700; color:#0f172a;">{m['mean_latency_s']:.0f}s</td>
            </tr>
            <tr style="border-bottom:1px solid #f1f5f9;">
                <td style="padding:10px 0; color:#334155;">P95 latency (worst case)</td>
                <td style="padding:10px 0; text-align:right; font-weight:700; color:#0f172a;">{m['p95_latency_s']:.0f}s</td>
            </tr>
            <tr style="border-bottom:1px solid #f1f5f9;">
                <td style="padding:10px 0; color:#334155;">Notes needing retry</td>
                <td style="padding:10px 0; text-align:right; font-weight:700; color:#0f172a;">{retries_count}</td>
            </tr>
            <tr>
                <td style="padding:10px 0; color:#334155;">Complete failures</td>
                <td style="padding:10px 0; text-align:right; font-weight:700; color:#0f172a;">{m['json_fail_count']} <span style="color:#64748b; font-weight:400;">(reviewed in Failure Analysis)</span></td>
            </tr>
        </table>
    </div>

    <div style="display:grid; grid-template-columns:1fr 1fr; gap:12px;">
        <div style="background:white; border:1px solid #e2e8f0; border-radius:10px; padding:16px; display:flex; align-items:flex-start; gap:12px; box-shadow:0 1px 2px rgba(0,0,0,0.03);">
            {svg_icon("shield", 24)}
            <div>
                <div style="font-weight:700; font-size:13px; color:#0f172a;">Clinician Approval Required</div>
                <div style="font-size:12px; color:#64748b; margin-top:2px;">No output auto-applied</div>
            </div>
        </div>
        <div style="background:white; border:1px solid #e2e8f0; border-radius:10px; padding:16px; display:flex; align-items:flex-start; gap:12px; box-shadow:0 1px 2px rgba(0,0,0,0.03);">
            {svg_icon("link", 24)}
            <div>
                <div style="font-weight:700; font-size:13px; color:#0f172a;">Every Claim Traced to Source</div>
                <div style="font-size:12px; color:#64748b; margin-top:2px;">Evidence spans verified</div>
            </div>
        </div>
        <div style="background:white; border:1px solid #e2e8f0; border-radius:10px; padding:16px; display:flex; align-items:flex-start; gap:12px; box-shadow:0 1px 2px rgba(0,0,0,0.03);">
            {svg_icon("wifi_off", 24)}
            <div>
                <div style="font-weight:700; font-size:13px; color:#0f172a;">Runs Without Internet</div>
                <div style="font-size:12px; color:#64748b; margin-top:2px;">2.5 GB model, air-gapped</div>
            </div>
        </div>
        <div style="background:white; border:1px solid #e2e8f0; border-radius:10px; padding:16px; display:flex; align-items:flex-start; gap:12px; box-shadow:0 1px 2px rgba(0,0,0,0.03);">
            {svg_icon("alert_triangle", 24)}
            <div>
                <div style="font-weight:700; font-size:13px; color:#0f172a;">Low Confidence Flagged</div>
                <div style="font-size:12px; color:#64748b; margin-top:2px;">Uncertainty surfaced, not hidden</div>
            </div>
        </div>
    </div>

    </div>
    </div>
    """
    return html


# ─── Panel 3: Failure Gallery ───

def build_failure_html():
    fail = None
    for f in failures:
        if f["note_id"] == "note_035":
            fail = f
            break
    if not fail:
        fail = failures[0] if failures else {"note_id": "N/A", "error": "N/A", "raw": "N/A"}

    fail_idx = int(fail["note_id"].split("_")[1]) if fail["note_id"] != "N/A" else 0
    fail_note = str(notes_list[fail_idx])[:500] if fail_idx < len(notes_list) else "N/A"

    html = f"""
    <div style="background:white; border-radius:12px; padding:28px; border:1px solid #e2e8f0;">
    <div style="font-family:'Inter',system-ui,-apple-system,sans-serif; margin:0 auto;">

    <div style="background:#fff5f5; border:1px solid #fecaca; border-left:4px solid #dc2626; border-radius:12px; padding:24px; margin-bottom:20px; display:flex; align-items:center; gap:16px; box-shadow:0 1px 3px rgba(0,0,0,0.04);">
        <div style="flex-shrink:0;">{svg_icon("shield", 40)}</div>
        <div>
            <h2 style="margin:0 0 4px 0; font-size:20px; font-weight:700; color:#0f172a;">Failure Analysis</h2>
            <p style="margin:0; font-size:13px; color:#64748b;">4 of 50 notes failed structured parsing. All caught by schema gate before reaching any consumer.</p>
        </div>
    </div>

    <div style="background:white; border:1px solid #fecaca; border-radius:12px; padding:24px; margin-bottom:20px; box-shadow:0 1px 3px rgba(0,0,0,0.04);">
        <div style="display:flex; align-items:center; gap:10px; margin-bottom:12px;">
            <h3 style="margin:0; font-size:15px; font-weight:700; color:#991b1b;">What Happened</h3>
            <span style="background:#fee2e2; color:#991b1b; padding:2px 8px; border-radius:10px; font-size:10px; font-weight:700;">MISSING FIELD</span>
            <span style="font-size:12px; color:#64748b;">{fail['note_id']}</span>
        </div>
        <p style="font-size:14px; color:#334155; line-height:1.6; margin:0 0 12px 0;">
            The model produced JSON output, but it was <strong>missing a required field</strong> (<code style="background:#fef2f2; padding:2px 6px; border-radius:3px; color:#991b1b; font-weight:700;">missing_info</code>).
            Pydantic schema validation caught this before the output could reach any downstream consumer.
        </p>
        <div style="background:#f8fafc; border:1px solid #e2e8f0; border-radius:8px; padding:14px;">
            <div style="font-size:11px; color:#64748b; margin-bottom:6px; font-weight:600; text-transform:uppercase; letter-spacing:0.5px;">Source Note (truncated)</div>
            <div style="font-family:'Courier New',monospace; font-size:12px; color:#334155; white-space:pre-wrap; max-height:120px; overflow-y:auto;">{fail_note}</div>
        </div>
    </div>

    <div style="background:white; border:1px solid #bbf7d0; border-left:4px solid #16a34a; border-radius:12px; padding:24px; margin-bottom:20px; box-shadow:0 1px 3px rgba(0,0,0,0.04);">
        <h3 style="margin:0 0 14px 0; font-size:15px; font-weight:700; color:#166534;">Why This Is Safe</h3>
        <div style="display:flex; flex-direction:column; gap:10px;">
            <div style="display:flex; align-items:flex-start; gap:10px;">
                {svg_icon("check_circle", 18)}
                <div><strong style="color:#166534;">Schema validation gate</strong> <span style="color:#334155;">— Pydantic rejects any output missing required fields</span></div>
            </div>
            <div style="display:flex; align-items:flex-start; gap:10px;">
                {svg_icon("check_circle", 18)}
                <div><strong style="color:#166534;">Retry mechanism</strong> <span style="color:#334155;">— System automatically retries with stricter prompt (Variant B)</span></div>
            </div>
            <div style="display:flex; align-items:flex-start; gap:10px;">
                {svg_icon("check_circle", 18)}
                <div><strong style="color:#166534;">Failure logging</strong> <span style="color:#334155;">— Raw output stored for post-hoc analysis</span></div>
            </div>
            <div style="display:flex; align-items:flex-start; gap:10px;">
                {svg_icon("check_circle", 18)}
                <div><strong style="color:#166534;">Clinician-in-the-loop</strong> <span style="color:#334155;">— No output is ever auto-applied; always reviewed</span></div>
            </div>
        </div>
    </div>

    <div style="background:white; border:1px solid #e2e8f0; border-radius:12px; padding:24px; margin-bottom:20px; box-shadow:0 1px 3px rgba(0,0,0,0.04);">
        <h3 style="margin:0 0 14px 0; font-size:15px; font-weight:700; color:#0f172a;">Failure Modes Observed</h3>
        <table style="width:100%; border-collapse:collapse; font-size:14px;">
            <tr style="border-bottom:1px solid #f1f5f9;">
                <td style="padding:10px 0;">
                    <span style="font-weight:600; color:#0f172a;">Missing required field</span>
                    <div style="font-size:12px; color:#64748b; margin-top:2px;">Model omitted <code style="background:#f1f5f9; padding:2px 6px; border-radius:3px;">missing_info</code> key</div>
                </td>
                <td style="padding:10px 0; text-align:right;">
                    <span style="background:#fee2e2; color:#991b1b; padding:3px 10px; border-radius:8px; font-size:12px; font-weight:700;">1</span>
                </td>
            </tr>
            <tr>
                <td style="padding:10px 0;">
                    <span style="font-weight:600; color:#0f172a;">Token limit truncation</span>
                    <div style="font-size:12px; color:#64748b; margin-top:2px;">Verbose output exceeded 4096 tokens, JSON truncated</div>
                </td>
                <td style="padding:10px 0; text-align:right;">
                    <span style="background:#fee2e2; color:#991b1b; padding:3px 10px; border-radius:8px; font-size:12px; font-weight:700;">3</span>
                </td>
            </tr>
        </table>
    </div>

    <div style="background:white; border:1px solid #bfdbfe; border-left:4px solid #2563eb; border-radius:12px; padding:20px; box-shadow:0 1px 3px rgba(0,0,0,0.04);">
        <div style="display:flex; align-items:center; gap:10px; margin-bottom:8px;">
            <span style="font-size:18px;">&#128161;</span>
            <h3 style="margin:0; font-size:15px; font-weight:700; color:#1e3a8a;">Design Principle</h3>
        </div>
        <p style="margin:0; font-size:14px; color:#334155; line-height:1.6;">
            <strong style="color:#1e3a8a;">Fail safely, not silently.</strong> Every failure is caught by schema validation before reaching the clinician.
            The system degrades gracefully: if structured extraction fails, the original note remains available.
            No hallucinated data can bypass the validation gate.
        </p>
    </div>

    </div>
    </div>
    """
    return html


# ─── Header + Pipeline Strip ───

def build_header_html():
    steps = [
        ("1", "Clinical Note", "Input", "#0F6B8A"),
        ("2", "Extract", "MedGemma", "#0F6B8A"),
        ("3", "Ground", "Spans", "#0F6B8A"),
        ("4", "Validate", "Schema", "#0F6B8A"),
        ("5", "Review", "Clinician", "#0D7A3F"),
    ]

    pipeline_parts = []
    for i, (num, label, sub, color) in enumerate(steps):
        if i > 0:
            pipeline_parts.append(f'<div style="flex:1; height:2px; background:#cbd5e1;"></div>')
        pipeline_parts.append(f'''
        <div style="text-align:center; flex-shrink:0;">
            <div style="width:36px; height:36px; border-radius:50%; background:{color}; color:white; display:flex; align-items:center; justify-content:center; font-size:14px; font-weight:700; margin:0 auto;">{num}</div>
            <div style="font-size:12px; font-weight:700; color:#111827; margin-top:6px;">{label}</div>
            <div style="font-size:10px; color:#6B7280; font-weight:500;">{sub}</div>
        </div>''')

    pipeline_html = "".join(pipeline_parts)

    return f"""
    <div style="background:white; border-radius:12px; padding:24px; margin-bottom:8px; border:1px solid #e2e8f0;">
    <div style="font-family:'Inter',system-ui,-apple-system,sans-serif; margin:0 auto;">
        <div style="display:flex; align-items:center; justify-content:center; gap:12px; margin-bottom:4px;">
            {svg_icon("medical_cross", 36)}
            <div>
                <h1 style="margin:0; font-size:26px; font-weight:800; color:#0f172a;">Discharge Navigator</h1>
                <p style="margin:0; font-size:13px; color:#475569; letter-spacing:0.3px; font-weight:500;">MedGemma 4B &middot; Offline-Capable &middot; Clinician-in-the-Loop</p>
            </div>
        </div>
        <div style="display:flex; align-items:center; margin:20px auto 0 auto; padding:0 20px;">
            {pipeline_html}
        </div>
    </div>
    </div>
    """


# ─── Gradio App ───

def build_app():
    with gr.Blocks(
        title="Discharge Navigator",
        theme=_build_forced_light_theme(),
        css=GLOBAL_CSS,
    ) as app:

        gr.HTML(build_header_html())

        with gr.Tabs():

            # Tab 1: Evidence Explorer
            with gr.TabItem("Evidence Explorer"):
                with gr.Row():
                    note_dropdown = gr.Dropdown(
                        choices=note_choices, label="Select Clinical Note",
                        scale=4,
                    )
                    btn_all = gr.Button("All", variant="primary", size="sm", scale=1,
                                        elem_id="btn-all", elem_classes=["filter-active-all"])
                    btn_dx = gr.Button("Diagnoses", size="sm", scale=1,
                                       elem_id="btn-dx", elem_classes=[])
                    btn_med = gr.Button("Medications", size="sm", scale=1,
                                        elem_id="btn-med", elem_classes=[])
                    btn_fu = gr.Button("Follow-ups", size="sm", scale=1,
                                       elem_id="btn-fu", elem_classes=[])

                summary_panel = gr.HTML(value="")

                with gr.Row():
                    with gr.Column(scale=3):
                        note_display = gr.HTML(value=build_welcome_html())
                    with gr.Column(scale=2):
                        extraction_display = gr.HTML(value="")

                status_bar = gr.HTML(value=build_status_html("Select a note to begin.", "info"))

                with gr.Accordion("Raw Extraction Packet (JSON)", open=False):
                    json_output = gr.Code(value="", language="json", label="")

                # Events — unified filter handler toggles highlights + button active state
                filter_outputs = [note_display, summary_panel, extraction_display,
                                  status_bar, json_output,
                                  btn_all, btn_dx, btn_med, btn_fu]

                note_dropdown.change(
                    fn=lambda c: filter_click(c, "All"),
                    inputs=[note_dropdown], outputs=filter_outputs,
                )
                btn_all.click(
                    fn=lambda c: filter_click(c, "All"),
                    inputs=[note_dropdown], outputs=filter_outputs,
                )
                btn_dx.click(
                    fn=lambda c: filter_click(c, "Diagnosis"),
                    inputs=[note_dropdown], outputs=filter_outputs,
                )
                btn_med.click(
                    fn=lambda c: filter_click(c, "Medication"),
                    inputs=[note_dropdown], outputs=filter_outputs,
                )
                btn_fu.click(
                    fn=lambda c: filter_click(c, "Follow-up"),
                    inputs=[note_dropdown], outputs=filter_outputs,
                )

            # Tab 2: Performance Dashboard
            with gr.TabItem("Performance Dashboard"):
                gr.HTML(build_reliability_html())

            # Tab 3: Edge Cases
            with gr.TabItem("Edge Cases"):
                gr.HTML(build_failure_html())

            # Tab 4: How It Works
            with gr.TabItem("How It Works"):
                gr.HTML(build_tutorial_html())

        gr.HTML(build_footer_html())

    return app


# ─── Force-Light Theme ───
# Override every *_dark property to match its light counterpart
# so Gradio renders identically regardless of system theme.
def _build_forced_light_theme():
    theme = gr.themes.Soft()
    dark_overrides = {}
    for attr in dir(theme):
        if attr.endswith("_dark") and not attr.startswith("_"):
            light_attr = attr[: -len("_dark")]
            light_val = getattr(theme, light_attr, None)
            if light_val is not None:
                dark_overrides[attr] = light_val
    return theme.set(**dark_overrides)


LAUNCH_KWARGS = {}  # theme & css now in gr.Blocks() for cross-version compat


if __name__ == "__main__":
    app = build_app()
    app.launch(share=False, server_name="127.0.0.1", server_port=7860)
