"""
Secondary source-grounding evaluator for the document assistant.

This module implements a claim-level verification layer. It evaluates:

1. Faithfulness / factual consistency: whether each factual claim in the
   generated answer is supported by the source document.
2. Coverage / completeness: whether the answer omits relevant source facts
   required by the task.

The evaluator is used as a post-generation guardrail. It does not generate
new technical content and does not assess legal patentability.

Applied to P1 to gate support_level and to surface missing facts.
P2 uses deterministic excerpt verification for quoted evidence, but its
verdict reasoning may still be LLM-assisted. Therefore, this evaluator is
also applied to P2 when stricter verification is required.
P3 ranking already produces verbatim excerpts, so this layer is optional there.
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


# ---------------------------------------------------------------------------
# Type aliases — kept as-is for backwards compatibility with callers that
# import these names directly.
# ---------------------------------------------------------------------------

FaithfulnessVerdict = Literal["explicit", "inferred", "unsupported"]
CoverageVerdict = Literal["complete", "partial", "missing_critical"]


@dataclass
class FaithfulnessResult:
    # Core evaluation verdicts
    faithfulness: FaithfulnessVerdict   # factual consistency of the answer
    coverage: CoverageVerdict           # completeness relative to the source

    # Reasoning strings for display / logging
    faithfulness_reasoning: str = ""
    coverage_reasoning: str = ""
    missing_facts: list[str] = field(default_factory=list)

    # Evaluator failure flag — True when the LLM judge itself could not run
    # (connection error, timeout, bad JSON).  Must be distinguished from a
    # genuine "unsupported" verdict about the answer content.
    check_failed: bool = False

    # Evaluation metadata — useful for academic reporting and audit trails
    evaluator_name: str = "llm_faithfulness_coverage_judge"
    evaluation_method: str = "claim_level_source_grounding"


# ---------------------------------------------------------------------------
# Evaluator prompts
# ---------------------------------------------------------------------------

_SYSTEM = (
    "You are a source-grounding evaluator for a patent document assistant. "
    "Your role is to verify whether a generated answer is factually consistent "
    "with the provided source and whether it covers all relevant source facts. "
    "Output valid JSON only. No markdown, no explanation."
)

_USER = """You are evaluating an answer produced by a patent document assistant.
Your evaluation must be source-grounded and claim-level.

[SOURCE]
{source}
[/SOURCE]

[ANSWER]
{answer}
[/ANSWER]

[QUESTION CONTEXT]
{question_context}
[/QUESTION CONTEXT]

Step 1 — Decompose the answer into factual claims.
A factual claim is any statement about a component, mechanism, problem, cause, effect, or proposed solution.

Step 2 — Faithfulness / factual consistency.
For each factual claim, decide whether it is:
- directly supported by the source,
- reasonably inferable from the source (all supporting facts are present, but require connecting),
- unsupported or contradicted by the source.

Overall faithfulness verdict:
- "explicit": all factual claims are directly supported by the source.
- "inferred": all factual claims are supported, but at least one requires connecting multiple source statements.
- "unsupported": at least one factual claim is not supported or contradicts the source.

Step 3 — Coverage / completeness.
Determine whether the answer includes all source facts relevant to the question context.

Overall coverage verdict:
- "complete": all relevant source facts are covered.
- "partial": only minor secondary facts are missing.
- "missing_critical": at least one important problem, mechanism, consequence, or solution detail is missing.

Return JSON:
{{
  "faithfulness": "explicit" or "inferred" or "unsupported",
  "coverage": "complete" or "partial" or "missing_critical",
  "faithfulness_reasoning": "short explanation of support status across the factual claims",
  "coverage_reasoning": "short explanation of completeness status",
  "missing_facts": ["short description of each relevant source fact absent from the answer"]
}}

Rules:
- Use ONLY [SOURCE]. Do not use outside knowledge.
- Do not evaluate legal patentability.
- Do not add technical facts not present in the source.
- Treat terminology differences as acceptable only if the meaning is unchanged.
- A fact is "missing" only if it is relevant to the question context AND absent from the answer in any form.
- Keep reasoning concise — one short sentence per field."""


# ---------------------------------------------------------------------------
# Public evaluation interface
# ---------------------------------------------------------------------------

def check(
    source: str,
    answer: str,
    question_context: str = "core technical problem and proposed solution",
) -> FaithfulnessResult:
    """Run the claim-level source-grounding evaluation in a single LLM call.

    Returns a FaithfulnessResult carrying factual consistency and completeness
    verdicts, reasoning, and metadata.

    On evaluator failure (LLM error, empty input), check_failed=True is set
    so callers can distinguish an evaluator failure from a genuine
    "unsupported" verdict about the answer content.
    """
    if not source or not source.strip():
        return FaithfulnessResult(
            faithfulness="unsupported",
            coverage="missing_critical",
            faithfulness_reasoning="Empty source text — evaluation aborted.",
            coverage_reasoning="Empty source text — evaluation aborted.",
            check_failed=True,
        )
    if not answer or not answer.strip():
        return FaithfulnessResult(
            faithfulness="unsupported",
            coverage="missing_critical",
            faithfulness_reasoning="Empty answer — evaluation aborted.",
            coverage_reasoning="Empty answer — evaluation aborted.",
            check_failed=True,
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
            faithfulness_reasoning="Evaluator LLM call failed — could not complete verification.",
            coverage_reasoning="Evaluator LLM call failed — could not complete verification.",
            check_failed=True,
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


# ---------------------------------------------------------------------------
# Backwards-compatible thin wrapper
# ---------------------------------------------------------------------------

def check_faithfulness(source: str, answer: str) -> tuple[FaithfulnessVerdict, str]:
    """Factual-consistency-only convenience wrapper.

    Returns (verdict, reasoning). Prefer check() to also obtain coverage
    and evaluation metadata.
    """
    result = check(source, answer)
    return (result.faithfulness, result.faithfulness_reasoning)
