"""Discharge Navigator — Grounding checks for evidence spans."""
import re


def normalize(text: str) -> str:
    """Collapse whitespace and lowercase for fuzzy matching."""
    return re.sub(r"\s+", " ", text.lower().strip())


def span_in_note(span: str, note: str) -> bool:
    """Check if an evidence span is a substring of the note (normalized)."""
    if not span or not note:
        return False
    return normalize(span) in normalize(note)


def grounding_report(packet, note: str) -> dict:
    """Produce a grounding quality report for a DischargePacket.

    Returns dict with:
      - diagnoses_grounded_ratio: float 0-1
      - meds_grounded_ratio: float 0-1
      - followups_grounded_ratio: float 0-1
      - total_spans: int
      - grounded_spans: int
      - ungrounded_examples: list[str] (max 5)
    """
    results = {}
    ungrounded = []

    for field_name, items in [
        ("diagnoses", packet.diagnoses),
        ("meds", packet.medications),
        ("followups", packet.followups),
    ]:
        total = 0
        grounded = 0
        for item in items:
            spans = getattr(item, "evidence_spans", [])
            if not spans:
                # No spans claimed — count as 1 ungrounded
                total += 1
            for span in spans:
                total += 1
                if span_in_note(span, note):
                    grounded += 1
                else:
                    if len(ungrounded) < 5:
                        ungrounded.append(f"[{field_name}] {span[:80]}")

        ratio = grounded / total if total > 0 else 1.0
        results[f"{field_name}_grounded_ratio"] = round(ratio, 3)
        results[f"{field_name}_total_spans"] = total
        results[f"{field_name}_grounded_spans"] = grounded

    # Totals across all fields
    all_total = sum(results[f"{f}_total_spans"] for f in ("diagnoses", "meds", "followups"))
    all_grounded = sum(results[f"{f}_grounded_spans"] for f in ("diagnoses", "meds", "followups"))
    results["total_spans"] = all_total
    results["grounded_spans"] = all_grounded
    results["overall_grounded_ratio"] = round(all_grounded / all_total, 3) if all_total > 0 else 1.0
    results["ungrounded_examples"] = ungrounded

    return results
