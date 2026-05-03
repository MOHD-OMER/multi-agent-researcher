"""
Report History Library
Persists all research runs to a local JSON file.
Provides load, search, delete, and export operations.
"""
import json
import os
import uuid
from datetime import datetime
from pathlib import Path

HISTORY_FILE = Path(__file__).parent.parent / "data" / "history.json"


def _ensure_dir():
    HISTORY_FILE.parent.mkdir(exist_ok=True)
    if not HISTORY_FILE.exists():
        HISTORY_FILE.write_text(json.dumps([]))


def save_report(topic: str, depth: str, final_report: str, sources: list,
                fact_check_results: list, iteration_count: int) -> str:
    """Save a completed research run. Returns the report ID."""
    _ensure_dir()
    records = load_all()

    report_id = str(uuid.uuid4())[:8]
    record = {
        "id": report_id,
        "topic": topic,
        "depth": depth,
        "created_at": datetime.now().isoformat(),
        "word_count": len(final_report.split()),
        "sources_count": len(sources),
        "claims_verified": sum(1 for r in fact_check_results if r.get("verdict") == "VERIFIED"),
        "claims_disputed": sum(1 for r in fact_check_results if r.get("verdict") == "DISPUTED"),
        "claims_unverified": sum(1 for r in fact_check_results if r.get("verdict") == "UNVERIFIED"),
        "iterations": iteration_count,
        "final_report": final_report,
        "sources": sources,
        "fact_check_results": fact_check_results,
    }

    records.insert(0, record)  # newest first
    records = records[:50]     # keep last 50

    HISTORY_FILE.write_text(json.dumps(records, indent=2, ensure_ascii=True), encoding="utf-8")
    return report_id


def load_all() -> list:
    """Load all history records."""
    _ensure_dir()
    try:
        return json.loads(HISTORY_FILE.read_text())
    except Exception:
        return []


def load_report(report_id: str) -> dict | None:
    """Load a specific report by ID."""
    for r in load_all():
        if r["id"] == report_id:
            return r
    return None


def delete_report(report_id: str) -> bool:
    """Delete a report by ID."""
    records = load_all()
    new = [r for r in records if r["id"] != report_id]
    if len(new) == len(records):
        return False
    HISTORY_FILE.write_text(json.dumps(new, indent=2, ensure_ascii=True), encoding="utf-8")
    return True


def search_history(query: str) -> list:
    """Search history by topic keyword."""
    q = query.lower()
    return [r for r in load_all() if q in r["topic"].lower()]


def format_history_for_display(records: list) -> list[list]:
    """Format records for Gradio Dataframe."""
    rows = []
    for r in records:
        dt = datetime.fromisoformat(r["created_at"])
        rows.append([
            r["id"],
            r["topic"][:55] + "..." if len(r["topic"]) > 55 else r["topic"],
            r["depth"].title(),
            dt.strftime("%b %d, %Y %H:%M"),
            str(r["word_count"]),
            str(r["sources_count"]),
            f"V:{r['claims_verified']} U:{r['claims_unverified']} D:{r['claims_disputed']}",
        ])
    return rows


HISTORY_COLUMNS = ["ID", "Topic", "Depth", "Date", "Words", "Sources", "Claims"]