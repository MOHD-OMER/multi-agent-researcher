"""
multi_topic_comparison.py
=========================
Orchestrates parallel multi-topic research pipelines and synthesises
a structured, analyst-grade comparison report.

Architecture
------------
  1. run_parallel_research()  – spawns one thread per topic, collects states
  2. generate_comparison_report() – feeds all states to an LLM and produces
     a Markdown comparison with fixed sections
  3. Helper utilities: _build_report_context, _fallback_report, _topic_label

Usage example
-------------
    from multi_topic_comparison import run_parallel_research, generate_comparison_report

    topics = ["LangGraph", "CrewAI", "AutoGen"]
    states = run_parallel_research(topics, depth="standard", progress_callback=print)
    report = generate_comparison_report(states, topics, progress_callback=print)
    print(report)
"""

from __future__ import annotations

import logging
import os
import threading
from typing import Callable, Optional

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_groq import ChatGroq

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

# ---------------------------------------------------------------------------
# Types
# ---------------------------------------------------------------------------

ProgressCallback = Callable[[str, str], None]   # (agent_name, message) -> None
ResearchState   = dict                            # final state dict from run_research()

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_DEFAULT_MODEL       = "llama-3.3-70b-versatile"
_DEFAULT_TEMPERATURE = 0.3
_DEFAULT_MAX_TOKENS  = 5_000
_MAX_REPORT_CHARS    = 2_500   # characters per individual report fed to comparison LLM
_TOPIC_LABEL_LIMIT   = 30      # max chars used for topic labels in headings


# ---------------------------------------------------------------------------
# LLM factory
# ---------------------------------------------------------------------------

def _get_llm(
    model: str = _DEFAULT_MODEL,
    temperature: float = _DEFAULT_TEMPERATURE,
    max_tokens: int = _DEFAULT_MAX_TOKENS,
) -> ChatGroq:
    """
    Instantiate a ChatGroq client.

    Reads ``GROQ_API_KEY`` from environment.  Raises ``RuntimeError`` if the
    key is absent so failures are caught early rather than deep inside a thread.
    """
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise RuntimeError(
            "GROQ_API_KEY environment variable is not set. "
            "Export it before running the comparison pipeline."
        )
    return ChatGroq(
        api_key=api_key,
        model=model,
        temperature=temperature,
        max_tokens=max_tokens,
    )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _topic_label(topic: str, limit: int = _TOPIC_LABEL_LIMIT) -> str:
    """Return a display-safe, truncated topic label."""
    return topic[:limit].strip()


def _emit(
    callback: Optional[ProgressCallback],
    agent: str,
    message: str,
) -> None:
    """Fire the progress callback if one was provided, and log at DEBUG level."""
    logger.debug("[%s] %s", agent, message)
    if callback:
        callback(agent, message)


def _extract_report(state: ResearchState) -> str:
    """
    Pull the best available report text from a research state dict.

    Preference order: ``final_report`` → ``draft_report`` → fallback string.
    """
    return (
        state.get("final_report")
        or state.get("draft_report")
        or "No report was generated for this topic."
    )


def _build_report_context(
    states: list[ResearchState],
    topics: list[str],
    max_chars: int = _MAX_REPORT_CHARS,
) -> str:
    """
    Concatenate individual research reports into a single context block
    that will be passed to the comparison LLM.

    Each section is prefixed with a numbered header and key metadata
    (source count, fact-check pass rate) to give the LLM useful signal
    beyond raw text.
    """
    sections: list[str] = []

    for idx, (state, topic) in enumerate(zip(states, topics), start=1):
        report_text   = _extract_report(state)[:max_chars]
        sources_count = len(state.get("sources", []))
        fact_checks   = state.get("fact_check_results", [])
        verified      = sum(1 for fc in fact_checks if fc.get("verdict") == "VERIFIED")
        total_fc      = len(fact_checks)

        meta = (
            f"Sources indexed: {sources_count} | "
            f"Claims verified: {verified}/{total_fc}"
        )

        sections.append(
            f"--- REPORT {idx}: {topic} ---\n"
            f"[{meta}]\n\n"
            f"{report_text}"
        )

    return "\n\n".join(sections)


def _build_comparison_prompt(topics: list[str], reports_context: str) -> str:
    """
    Construct the structured comparison prompt sent to the LLM.

    The prompt enforces a fixed Markdown schema so downstream rendering
    (e.g. your Streamlit / Gradio UI) can reliably parse sections.
    """
    topics_numbered = "\n".join(
        f"  {i}. {t}" for i, t in enumerate(topics, start=1)
    )
    vs_label = " vs ".join(_topic_label(t) for t in topics)

    return f"""\
You are a Senior Research Analyst producing a structured comparative report.
Your analysis must be analytical and insight-driven — not merely descriptive.

═══════════════════════════════════════
TOPICS UNDER COMPARISON
═══════════════════════════════════════
{topics_numbered}

═══════════════════════════════════════
INDIVIDUAL RESEARCH REPORTS
═══════════════════════════════════════
{reports_context}

═══════════════════════════════════════
OUTPUT REQUIREMENTS
═══════════════════════════════════════
Produce the following Markdown report **exactly** (preserve all headings):

# Comparative Analysis: {vs_label}

## Overview
2–3 sentences explaining what is being compared and why it matters.

## Side-by-Side Summary
A well-structured Markdown table comparing key attributes across all topics.
Use concise, scannable language in every cell.

## Common Themes
Themes, technologies, challenges, or trends that appear across **all** topics.

## Key Differences
The most significant contrasts between the topics.
Be specific: avoid vague statements like "they differ in scope."

## Unique Insights per Topic
One distinctive, non-obvious finding per topic that the others do not share.
Format as a sub-section per topic.

## Synthesis & Implications
What conclusions emerge only when the topics are viewed *together*?
What does the combined picture reveal that individual reports cannot?

## Recommendation
If a decision-maker had to prioritise **one** topic for further investment or
research, which would you recommend and why? Ground your reasoning in evidence
from the reports above.

Rules:
- Draw real connections and contrasts; do not pad with generic filler.
- Every section must add value beyond what the individual reports already say.
- Keep the total word count between 600 and 1 200 words.
"""


def _fallback_report(states: list[ResearchState], topics: list[str]) -> str:
    """
    Generate a minimal concatenation report used when the LLM call fails.

    This ensures callers always receive a usable string even under error
    conditions, which is important for long-running UI pipelines.
    """
    logger.warning("Using fallback concatenation report (LLM synthesis failed).")
    lines: list[str] = [
        f"# Comparative Research: {' vs '.join(topics)}",
        "",
        "> ⚠️ The AI synthesis step encountered an error. "
        "Individual reports are shown below.",
        "",
    ]
    for state, topic in zip(states, topics):
        excerpt = _extract_report(state)[:1_000]
        lines += [f"## {topic}", excerpt, "", "---", ""]

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def run_single_research(
    topic: str,
    depth: str,
    progress_callback: Optional[ProgressCallback] = None,
) -> ResearchState:
    """
    Execute a single research pipeline for *topic* at the requested *depth*.

    Parameters
    ----------
    topic:
        The research subject (e.g. ``"LangGraph"``).
    depth:
        Pipeline depth passed through to the underlying workflow.
        Typical values: ``"quick"``, ``"standard"``, ``"deep"``.
    progress_callback:
        Optional ``(agent, message)`` callable for real-time UI updates.

    Returns
    -------
    ResearchState
        The final state dictionary produced by ``graph.workflow.run_research``.
    """
    # Lazy import to avoid circular dependency if this module is imported
    # by the workflow package itself.
    from graph.workflow import run_research  # noqa: PLC0415

    logger.info("Starting research pipeline | topic=%r depth=%r", topic, depth)
    return run_research(topic=topic, depth=depth, progress_callback=progress_callback)


def run_parallel_research(
    topics: list[str],
    depth: str = "quick",
    progress_callback: Optional[ProgressCallback] = None,
) -> list[ResearchState]:
    """
    Run multiple research pipelines concurrently using daemon threads.

    Each topic is processed independently; failures are isolated so one
    broken topic does not abort the others.  Results are returned in the
    **same order** as the input *topics* list.

    Parameters
    ----------
    topics:
        List of research subjects.  Must contain at least one element.
    depth:
        Depth mode forwarded to every individual pipeline.
    progress_callback:
        Optional ``(agent, message)`` callable.  Messages are prefixed with
        a truncated topic label so the UI can distinguish parallel streams.

    Returns
    -------
    list[ResearchState]
        One state dict per topic, order-preserving.

    Raises
    ------
    ValueError
        If *topics* is empty.
    """
    if not topics:
        raise ValueError("topics must contain at least one item.")

    results: list[Optional[ResearchState]] = [None] * len(topics)
    threads: list[threading.Thread] = []

    def _worker(idx: int, topic: str) -> None:
        label = _topic_label(topic, limit=25)

        def _cb(agent: str, msg: str) -> None:
            _emit(progress_callback, agent, f"[{label}] {msg}")

        try:
            _emit(progress_callback, "orchestrator", f"🚀 Launching research for '{label}'")
            results[idx] = run_single_research(topic, depth, _cb)
            _emit(progress_callback, "orchestrator", f"✅ Research complete for '{label}'")
        except Exception as exc:  # noqa: BLE001
            logger.exception("Research pipeline failed for topic=%r", topic)
            _emit(progress_callback, "orchestrator", f"❌ Error for '{label}': {exc}")
            results[idx] = {
                "topic":        topic,
                "final_report": f"Research pipeline failed with error: {exc}",
                "sources":      [],
                "error":        str(exc),
            }

    for i, topic in enumerate(topics):
        thread = threading.Thread(target=_worker, args=(i, topic), daemon=True)
        threads.append(thread)
        thread.start()

    logger.info("Waiting for %d research thread(s) to finish…", len(threads))
    for thread in threads:
        thread.join()

    # At this point every slot must be filled (worker always writes to results[idx]).
    return results  # type: ignore[return-value]


def generate_comparison_report(
    states: list[ResearchState],
    topics: list[str],
    progress_callback: Optional[ProgressCallback] = None,
    model: str = _DEFAULT_MODEL,
    temperature: float = _DEFAULT_TEMPERATURE,
    max_tokens: int = _DEFAULT_MAX_TOKENS,
) -> str:
    """
    Synthesise a structured Markdown comparison report from multiple research states.

    Uses the Groq LLM to produce analyst-grade insights rather than simple
    concatenation.  Falls back to a plain concatenation if the LLM call fails.

    Parameters
    ----------
    states:
        List of research state dicts, one per topic (order-matched to *topics*).
    topics:
        Human-readable topic names corresponding to each state.
    progress_callback:
        Optional ``(agent, message)`` callable for UI progress updates.
    model:
        Groq model identifier.
    temperature:
        Sampling temperature (lower = more deterministic).
    max_tokens:
        Maximum tokens in the LLM response.

    Returns
    -------
    str
        A Markdown string beginning with a level-1 heading.

    Raises
    ------
    ValueError
        If *states* and *topics* have different lengths or are empty.
    """
    if not states or not topics:
        raise ValueError("states and topics must both be non-empty.")
    if len(states) != len(topics):
        raise ValueError(
            f"states and topics length mismatch: {len(states)} vs {len(topics)}."
        )

    _emit(progress_callback, "comparison", "🔀 Building comparison context…")
    reports_context = _build_report_context(states, topics)

    _emit(progress_callback, "comparison", "🤖 Requesting LLM synthesis…")
    prompt = _build_comparison_prompt(topics, reports_context)

    try:
        llm = _get_llm(model=model, temperature=temperature, max_tokens=max_tokens)
        messages = [
            SystemMessage(
                content=(
                    "You are an expert comparative research analyst. "
                    "Produce structured, evidence-based comparisons that go "
                    "beyond surface-level summaries."
                )
            ),
            HumanMessage(content=prompt),
        ]

        logger.info("Invoking LLM for comparison | model=%s topics=%s", model, topics)
        response = llm.invoke(messages)
        report: str = response.content.strip()

        # Guarantee the report starts with a Markdown H1 heading.
        if not report.startswith("#"):
            vs_label = " vs ".join(_topic_label(t) for t in topics)
            report = f"# Comparative Analysis: {vs_label}\n\n{report}"

        word_count = len(report.split())
        _emit(
            progress_callback,
            "comparison",
            f"✅ Comparison report ready — {word_count:,} words",
        )
        logger.info("Comparison report generated | words=%d", word_count)
        return report

    except Exception as exc:  # noqa: BLE001
        logger.exception("LLM comparison synthesis failed.")
        _emit(progress_callback, "comparison", f"⚠️ Synthesis error — using fallback: {exc}")
        return _fallback_report(states, topics)