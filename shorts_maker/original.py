"""Grounded, local-only Original Content script proposal via Ollama."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from typing import Literal
from urllib.error import URLError
from urllib.request import ProxyHandler, Request, build_opener

from pydantic import BaseModel, Field, ValidationError, model_validator

from .models import TranscriptSegment
from .utils import PipelineError

OLLAMA_BASE = "http://127.0.0.1:11434"


@dataclass(frozen=True)
class EvidenceReference:
    segment_id: int
    source_id: str
    source_start: float
    source_end: float
    supporting_text: str


class ClaimProposal(BaseModel):
    text: str = Field(min_length=8, max_length=600)
    evidence_ids: list[int] = Field(default_factory=list)
    requires_external_verification: bool = False

    @model_validator(mode="after")
    def has_support_or_flag(self):
        if not self.evidence_ids and not self.requires_external_verification:
            raise ValueError("A fact claim needs source evidence or an external-verification flag.")
        return self


class ScriptProposal(BaseModel):
    title: str = Field(min_length=4, max_length=160)
    hook: str = Field(min_length=8, max_length=800)
    context: str = Field(min_length=8, max_length=1200)
    source_evidence: str = Field(min_length=8, max_length=1200)
    original_analysis: str = Field(min_length=20, max_length=2400)
    conclusion: str = Field(min_length=8, max_length=800)
    claims: list[ClaimProposal] = Field(min_length=1, max_length=12)


@dataclass(frozen=True)
class GroundedClaim:
    text: str
    evidence: tuple[EvidenceReference, ...]
    requires_external_verification: bool


@dataclass(frozen=True)
class OriginalDraft:
    source_id: str
    language: Literal["hu", "en"]
    style: str
    model: str
    proposal: ScriptProposal
    claims: tuple[GroundedClaim, ...]
    status: str = "AWAITING_SCRIPT_APPROVAL"

    def to_dict(self) -> dict:
        data = asdict(self)
        data["proposal"] = self.proposal.model_dump()
        return data


def evidence_for_range(
    segments: list[TranscriptSegment], source_id: str, start: float, end: float, limit: int = 18
) -> list[EvidenceReference]:
    selected = [s for s in segments if s.end > start and s.start < end and s.text.strip()]
    if len(selected) > limit:
        # Keep an ordered overview across the topic, not just its opening.
        selected = [selected[round(i * (len(selected) - 1) / (limit - 1))] for i in range(limit)]
    return [
        EvidenceReference(i, source_id, segment.start, segment.end, segment.text.strip())
        for i, segment in enumerate(selected, 1)
    ]


def _local_json(path: str, payload: dict | None = None, timeout: int = 30) -> dict:
    opener = build_opener(ProxyHandler({}))
    request = Request(
        OLLAMA_BASE + path,
        data=json.dumps(payload).encode("utf-8") if payload is not None else None,
        headers={"Content-Type": "application/json"},
        method="POST" if payload is not None else "GET",
    )
    try:
        with opener.open(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except (URLError, TimeoutError, ValueError) as exc:
        raise PipelineError(f"A helyi Ollama szolgáltatás nem érhető el vagy hibás választ adott: {exc}") from exc


def installed_ollama_models() -> list[str]:
    data = _local_json("/api/tags", timeout=3)
    return [str(item["name"]) for item in data.get("models", []) if item.get("name")]


def generate_original_draft(
    evidence: list[EvidenceReference], *, model: str, language: Literal["hu", "en"], style: str
) -> OriginalDraft:
    if not evidence:
        raise PipelineError("A témához nem tartozik idézhető forrásszakasz.")
    if not model.strip():
        raise PipelineError("Válassz helyben telepített Ollama modellt.")
    if language not in {"hu", "en"}:
        raise PipelineError("A forgatókönyv nyelve magyar vagy angol lehet.")
    source_id = evidence[0].source_id
    if any(item.source_id != source_id for item in evidence):
        raise PipelineError("Egy forgatókönyv-javaslat csak egy forrás bizonyítékait használhatja.")
    evidence_map = {item.segment_id: item for item in evidence}
    source_lines = "\n".join(
        f"[{item.segment_id}] {item.source_start:.2f}-{item.source_end:.2f}s: {item.supporting_text[:450]}"
        for item in evidence
    )
    prompt = (
        "Create a genuinely original short-video script based only on the cited source excerpts below. "
        "Separate source claims from your own commentary. Give a strong hook, context, evidence, "
        "new analysis (comparison, critique, or explanation), and conclusion. Do not merely paraphrase "
        "the source. Every factual claim must cite evidence_ids from the provided brackets; if a claim "
        "requires outside knowledge, set requires_external_verification=true and do not present it as certain. "
        "Never invent quotes or citations. A human will review every claim. "
        f"Write in {'Hungarian' if language == 'hu' else 'English'} with a {style} tone.\n\n"
        f"SOURCE EXCERPTS:\n{source_lines}"
    )
    result = _local_json(
        "/api/chat",
        {
            "model": model.strip(),
            "messages": [{"role": "user", "content": prompt}],
            "stream": False,
            "format": ScriptProposal.model_json_schema(),
            "options": {"temperature": 0.25},
        },
        timeout=180,
    )
    try:
        proposal = ScriptProposal.model_validate_json(result["message"]["content"])
        claims = []
        for claim in proposal.claims:
            unknown = set(claim.evidence_ids) - evidence_map.keys()
            if unknown:
                raise PipelineError(f"A modell nem létező forrásszakaszra hivatkozott: {sorted(unknown)}")
            claims.append(GroundedClaim(
                claim.text,
                tuple(evidence_map[index] for index in claim.evidence_ids),
                claim.requires_external_verification,
            ))
    except (KeyError, TypeError, ValidationError) as exc:
        raise PipelineError(f"Az LLM válasza nem felelt meg a forgatókönyv-sémának: {exc}") from exc
    return OriginalDraft(source_id, language, style, model.strip(), proposal, tuple(claims))
