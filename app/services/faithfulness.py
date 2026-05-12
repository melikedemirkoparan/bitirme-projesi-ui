"""
Shared faithfulness + coverage layer for the document assistant.

Two complementary checks, exposed as one combined call so each pattern pays
only one LLM round-trip:

  - Faithfulness: are all claims in the answer supported by the source?
                  (catches hallucinations and unsupported assertions)
  - Coverage:     does the answer cover all distinct facts from the source
                  that the question asked for?
                  (catches incompleteness and dropped facts)

Used by P1 to gate support_level and to surface missing facts. P2 is fully
deterministic so faithfulness is guaranteed by construction. P3 ranking
already produces verbatim excerpts, so this layer is optional there.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from app.generation import llm_router
from app.generation.llm_client import (
    LLMConnectionError,
    LLMParseError,
    LLMResponseError,
)


FaithfulnessVerdict = Literal["explicit", "inferred", "unsupported"]
CoverageVerdict = Literal["complete", "partial", "missing_critical"]


@dataclass
class FaithfulnessResult:
    faithfulness: FaithfulnessVerdict
    coverage: CoverageVerdict
    faithfulness_reasoning: str = ""
    coverage_reasoning: str = ""
    missing_facts: list[str] = field(default_factory=list)


_SYSTEM = (
    "You are a faithfulness and coverage judge for a patent drafting assistant. "
    "Output valid JSON only. No markdown, no explanation."
)

_USER = """You judge an answer against a source text on TWO independent dimensions.

[SOURCE]
{source}
[/SOURCE]

[ANSWER]
{answer}
[/ANSWER]

[QUESTION CONTEXT]
{question_context}
[/QUESTION CONTEXT]

Dimension 1 — Faithfulness (is everything in the answer supported by the source?):
- "explicit": every factual claim in the answer is directly and clearly stated in the source.
- "inferred": the answer is a reasonable interpretation of the source, but some claims are not directly stated.
- "unsupported": the answer contains a claim not present in the source, contradicts the source, or invents details.

Dimension 2 — Coverage (does the answer cover everything the source provides for the question?):
- "complete": every distinct relevant fact from the source is reflected in the answer.
- "partial": minor secondary details are missing, but the main relevant facts are covered.
- "missing_critical": at least one distinct relevant fact from the source is absent from the answer.

Output JSON:
{{
  "faithfulness": "explicit" or "inferred" or "unsupported",
  "coverage": "complete" or "partial" or "missing_critical",
  "faithfulness_reasoning": "one short sentence: which claims are or are not supported",
  "coverage_reasoning": "one short sentence: what is covered or what is missing",
  "missing_facts": ["short description of each distinct relevant fact from the source not present in the answer"]
}}

Rules:
- Use ONLY [SOURCE]. Do not use outside knowledge.
- Faithfulness and coverage are independent — judge each separately.
- A fact is "missing" only if it is relevant to the question context AND not reflected in the answer in any form.
- Keep missing_facts short — one sentence per item, focused on the missing fact itself."""


def check(
    source: str,
    answer: str,
    question_context: str = "core technical problem and proposed solution",
) -> FaithfulnessResult:
    """Run faithfulness and coverage check in a single LLM call.

    Returns a FaithfulnessResult. On any LLM failure or empty input, returns
    an "unsupported"/"missing_critical" result so callers can fail safe.
    """
    if not source or not source.strip():
        return FaithfulnessResult(
            faithfulness="unsupported",
            coverage="missing_critical",
            faithfulness_reasoning="Empty source text.",
            coverage_reasoning="Empty source text.",
        )
    if not answer or not answer.strip():
        return FaithfulnessResult(
            faithfulness="unsupported",
            coverage="missing_critical",
            faithfulness_reasoning="Empty answer.",
            coverage_reasoning="Empty answer.",
        )

    try:
        raw = llm_router.generate_json(
            user_prompt=_USER.format(
                source=source,
                answer=answer,
                question_context=question_context,
            ),
            system_prompt=_SYSTEM,
            temperature=0.1,
        )
    except (LLMConnectionError, LLMResponseError, LLMParseError):
        return FaithfulnessResult(
            faithfulness="unsupported",
            coverage="missing_critical",
            faithfulness_reasoning="Faithfulness/coverage check could not be completed.",
            coverage_reasoning="Faithfulness/coverage check could not be completed.",
        )

    f_verdict = raw.get("faithfulness", "unsupported")
    if f_verdict not in {"explicit", "inferred", "unsupported"}:
        f_verdict = "unsupported"

    c_verdict = raw.get("coverage", "missing_critical")
    if c_verdict not in {"complete", "partial", "missing_critical"}:
        c_verdict = "missing_critical"

    f_reason = (raw.get("faithfulness_reasoning") or "").strip()[:240]
    c_reason = (raw.get("coverage_reasoning") or "").strip()[:240]

    missing_raw = raw.get("missing_facts", [])
    missing = []
    if isinstance(missing_raw, list):
        for item in missing_raw:
            if isinstance(item, str) and item.strip():
                missing.append(item.strip()[:240])

    return FaithfulnessResult(
        faithfulness=f_verdict,
        coverage=c_verdict,
        faithfulness_reasoning=f_reason,
        coverage_reasoning=c_reason,
        missing_facts=missing,
    )


# Backwards-compatible thin wrapper for callers that only need faithfulness.
def check_faithfulness(source: str, answer: str) -> tuple[FaithfulnessVerdict, str]:
    """Faithfulness-only convenience wrapper.

    Returns (verdict, reasoning). Prefer `check()` to also get coverage.
    """
    result = check(source, answer)
    return (result.faithfulness, result.faithfulness_reasoning)
