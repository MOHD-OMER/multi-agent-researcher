"""
Editor Agent — Senior Editor
Reviews fact-check results, fixes disputed claims, polishes report.
"""
import os
import json
from langchain_groq import ChatGroq
from langchain_core.messages import HumanMessage, SystemMessage


EDITOR_SYSTEM_PROMPT = """You are a Senior Editor at a prestigious research publication.

Your responsibilities:
1. Incorporate fact-check corrections into the report
2. Remove or qualify any DISPUTED claims
3. Polish prose for clarity, flow, and professionalism
4. Ensure consistent citation format
5. Add a fact-check summary section

You maintain the original structure while improving accuracy and quality.
Never add new information — only work with what's provided.
"""


def get_llm():
    return ChatGroq(
        api_key=os.getenv("GROQ_API_KEY"),
        model="llama-3.3-70b-versatile",
        temperature=0.3,
        max_tokens=5000,
    )


def format_fact_check_summary(fact_check_results: list) -> str:
    """Format the fact check results into a markdown summary section."""
    
    if not fact_check_results:
        return ""
    
    lines = ["\n## Fact-Check Report\n"]
    lines.append("| Claim | Verdict | Confidence | Notes |\n")
    lines.append("|-------|---------|------------|-------|\n")
    
    verdict_emoji = {
        "VERIFIED": "✅ VERIFIED",
        "UNVERIFIED": "⚠️ UNVERIFIED",
        "DISPUTED": "❌ DISPUTED",
    }
    
    for r in fact_check_results:
        claim = r.get("claim", "")[:60] + "..." if len(r.get("claim", "")) > 60 else r.get("claim", "")
        verdict = verdict_emoji.get(r.get("verdict", "UNVERIFIED"), r.get("verdict", ""))
        confidence = f"{int(r.get('confidence', 0.5) * 100)}%"
        explanation = r.get("explanation", "")[:80]
        
        # Escape pipe characters in table
        claim = claim.replace("|", "\\|")
        explanation = explanation.replace("|", "\\|")
        
        lines.append(f"| {claim} | {verdict} | {confidence} | {explanation} |\n")
    
    return "".join(lines)


def editor_agent(state: dict) -> dict:
    """
    Editor agent that reviews fact-check results and produces a final clean report.
    
    Args:
        state: Current workflow state
    
    Returns:
        Updated state with final_report
    """
    draft_report = state.get("draft_report", "")
    fact_check_results = state.get("fact_check_results", [])
    topic = state["topic"]
    
    progress_callback = state.get("_progress_callback")
    if progress_callback:
        progress_callback("editor", "✏️ Reviewing and polishing report...")
    
    if not draft_report:
        return {**state, "final_report": "No report to edit."}
    
    llm = get_llm()
    
    # Format corrections
    corrections_text = ""
    disputed_claims = []
    
    for r in fact_check_results:
        verdict = r.get("verdict", "")
        claim = r.get("claim", "")
        explanation = r.get("explanation", "")
        correction = r.get("correction")
        
        if verdict == "DISPUTED":
            disputed_claims.append(r)
            corrections_text += f"\n❌ DISPUTED: \"{claim}\"\n   Explanation: {explanation}\n"
            if correction:
                corrections_text += f"   Correction: {correction}\n"
        elif verdict == "UNVERIFIED":
            corrections_text += f"\n⚠️ UNVERIFIED: \"{claim}\"\n   Note: {explanation}\n"
    
    if progress_callback:
        if disputed_claims:
            progress_callback("editor", f"🔧 Fixing {len(disputed_claims)} disputed claims...")
        else:
            progress_callback("editor", "✅ No disputed claims found. Polishing prose...")
    
    edit_prompt = f"""You are editing a research report on "{topic}".

ORIGINAL DRAFT:
{draft_report}

FACT-CHECK FINDINGS:
{corrections_text if corrections_text else "All claims verified or no issues found."}

YOUR TASKS:
1. If there are DISPUTED claims: Remove or correct them in the text
2. For UNVERIFIED claims: Add a qualifying phrase like "reportedly" or "according to some sources"
3. Polish the prose — improve flow, eliminate redundancy, strengthen transitions
4. Ensure all section headers are properly formatted as ## headers
5. Keep the report between 500-900 words (excluding references and fact-check table)
6. Do NOT change the core structure or add new factual claims

Return the complete, polished report in Markdown. Start with the title (#) and include all original sections."""
    
    messages = [
        SystemMessage(content=EDITOR_SYSTEM_PROMPT),
        HumanMessage(content=edit_prompt)
    ]
    
    try:
        response = llm.invoke(messages)
        polished_report = response.content.strip()
        
        # Ensure title
        if not polished_report.startswith("#"):
            polished_report = f"# Research Report: {topic}\n\n" + polished_report
        
        # Append fact-check summary table
        fact_check_summary = format_fact_check_summary(fact_check_results)
        
        # Append workflow metadata
        sources = state.get("sources", [])
        metadata = f"""

---
*Report generated by Multi-Agent Research Assistant*  
*Agents: Researcher → Writer → Fact Checker → Editor*  
*Sources analyzed: {len(sources)} | Claims verified: {len(fact_check_results)}*
"""
        
        final_report = polished_report + fact_check_summary + metadata
        
        if progress_callback:
            word_count = len(final_report.split())
            progress_callback("editor", f"✅ Final report ready ({word_count} words, {len(sources)} sources)")
        
        return {
            **state,
            "final_report": final_report,
        }
    
    except Exception as e:
        print(f"[Editor] Error: {e}")
        fact_check_summary = format_fact_check_summary(fact_check_results)
        return {
            **state,
            "final_report": draft_report + fact_check_summary,
        }