"""Discharge Navigator — Pydantic schemas with LLM output coercion."""
from pydantic import BaseModel, Field, field_validator
from typing import List, Optional, Literal


# ─── Coercion helpers (LLMs return messy types) ───

def _coerce_str(v, default="unspecified"):
    if v is None:
        return default
    return str(v)

def _coerce_list(v):
    if v is None:
        return []
    if isinstance(v, str):
        return [v] if v and v.lower() not in ("n/a", "none", "") else []
    return v

def _coerce_confidence(v):
    if v in ("low", "medium", "high"):
        return v
    return "low"

def _coerce_urgency(v):
    if v in ("routine", "soon", "urgent"):
        return v
    return "routine"

def _coerce_severity(v):
    if v in ("nice_to_have", "important", "critical"):
        return v
    return "nice_to_have"


MAX_SPANS_PER_ITEM = 5
MAX_WORDS_PER_SPAN = 20

def _cap_evidence_spans(v):
    """Coerce to list, then cap span count and word length (token budget defense)."""
    spans = _coerce_list(v)
    capped = []
    for s in spans[:MAX_SPANS_PER_ITEM]:
        words = str(s).split()
        capped.append(" ".join(words[:MAX_WORDS_PER_SPAN]))
    return capped


# ─── Schema classes ───

class CandidateICD(BaseModel):
    """A diagnosis extracted from the note with candidate ICD code."""
    label: str = Field(..., description="Diagnosis label as written in note")
    icd10: Optional[str] = Field(None, description="Candidate ICD-10 code for review")
    confidence: Literal["low", "medium", "high"] = Field("low")
    evidence_spans: List[str] = Field(default_factory=list)

    @field_validator("label", mode="before")
    @classmethod
    def fix_label(cls, v): return _coerce_str(v)
    @field_validator("confidence", mode="before")
    @classmethod
    def fix_conf(cls, v): return _coerce_confidence(v)
    @field_validator("evidence_spans", mode="before")
    @classmethod
    def cap_spans(cls, v): return _cap_evidence_spans(v)


class Medication(BaseModel):
    """A medication extracted with dosing details."""
    name: str
    dose: Optional[str] = None
    route: Optional[str] = None
    frequency: Optional[str] = None
    duration: Optional[str] = None
    warnings: List[str] = Field(default_factory=list)
    confidence: Literal["low", "medium", "high"] = "medium"
    evidence_spans: List[str] = Field(default_factory=list)

    @field_validator("name", mode="before")
    @classmethod
    def fix_name(cls, v): return _coerce_str(v)
    @field_validator("confidence", mode="before")
    @classmethod
    def fix_conf(cls, v): return _coerce_confidence(v)
    @field_validator("warnings", mode="before")
    @classmethod
    def coerce_warnings(cls, v): return _coerce_list(v)
    @field_validator("evidence_spans", mode="before")
    @classmethod
    def cap_spans(cls, v): return _cap_evidence_spans(v)


class FollowUp(BaseModel):
    """A follow-up appointment or action required."""
    with_whom: str = "unspecified"
    when: str = "unspecified"
    why: Optional[str] = None
    urgency: Literal["routine", "soon", "urgent"] = "routine"
    confidence: Literal["low", "medium", "high"] = "medium"
    evidence_spans: List[str] = Field(default_factory=list)

    @field_validator("with_whom", "when", mode="before")
    @classmethod
    def fix_str(cls, v): return _coerce_str(v)
    @field_validator("confidence", mode="before")
    @classmethod
    def fix_conf(cls, v): return _coerce_confidence(v)
    @field_validator("urgency", mode="before")
    @classmethod
    def fix_urg(cls, v): return _coerce_urgency(v)
    @field_validator("evidence_spans", mode="before")
    @classmethod
    def cap_spans(cls, v): return _cap_evidence_spans(v)


class RedFlag(BaseModel):
    """A warning symptom — return immediately if this occurs."""
    symptom: str = "unspecified"
    action: str = "unspecified"
    confidence: Literal["low", "medium", "high"] = "medium"

    @field_validator("symptom", "action", mode="before")
    @classmethod
    def fix_str(cls, v): return _coerce_str(v)
    @field_validator("confidence", mode="before")
    @classmethod
    def fix_conf(cls, v): return _coerce_confidence(v)


class MissingInfoItem(BaseModel):
    """Something expected but absent from the note."""
    item: str = "unspecified"
    why_required: str = "unspecified"
    severity: Literal["nice_to_have", "important", "critical"] = "nice_to_have"

    @field_validator("item", "why_required", mode="before")
    @classmethod
    def fix_str(cls, v): return _coerce_str(v)
    @field_validator("severity", mode="before")
    @classmethod
    def fix_sev(cls, v): return _coerce_severity(v)


class DischargePacket(BaseModel):
    """Complete structured discharge document."""
    diagnoses: List[CandidateICD]
    medications: List[Medication]
    followups: List[FollowUp]
    red_flags: List[RedFlag]
    patient_summary: str = Field(..., description="Plain language summary at 8th grade reading level")
    missing_info: List[MissingInfoItem]
    notes: List[str] = Field(default_factory=list)

    @field_validator("notes", mode="before")
    @classmethod
    def coerce_notes(cls, v): return _coerce_list(v)
