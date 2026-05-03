"""
Fact Checker Agent — Critical Fact Verifier
Extracts claims from report and verifies them against web sources.
"""
import os
import json
from langchain_groq import ChatGroq
from langchain_core.messages import HumanMessage, SystemMessage

from tools.web_search import fact_check_search


FACT_CHECKER_SYSTEM_PROMPT = """You are a Critical Fact Verifier. Your job is to identify and verify factual claims.

You are skeptical by nature. You distinguish between:
- VERIFIED: Claim is supported by credible sources
- UNVERIFIED: Claim cannot be confirmed or denied from available evidence  
- DISPUTED: Claim contradicts available evidence

Be precise and evidence-based. Do not mark something DISPUTED without actual contradicting evidence.
Always output structured JSON only.
"""


def get_llm():
    return ChatGroq(
        api_key=os.getenv("GROQ_API_KEY"),
        model="llama-3.3-70b-versatile",
        temperature=0.1,
        max_tokens=4096,
    )


def extract_claims(report: str, llm) -> list[str]:
    """Extract the top 5 verifiable factual claims from the report."""
    
    extraction_prompt = f"""Extract the 5 most important VERIFIABLE FACTUAL CLAIMS from this report.

Focus on:
- Specific statistics or numbers
- Claims about capabilities or performance
- Historical or timeline claims
- Named entities and their attributes
- Comparisons or rankings

Do NOT include:
- Opinions or analysis
- Vague generalizations
- Future predictions

REPORT:
{report[:3000]}

Return ONLY valid JSON:
{{
  "claims": [
    "Claim 1 as a complete, standalone factual statement",
    "Claim 2...",
    "Claim 3...",
    "Claim 4...",
    "Claim 5..."
  ]
}}"""
    
    messages = [
        SystemMessage(content="You extract factual claims from text. Output only JSON."),
        HumanMessage(content=extraction_prompt)
    ]
    
    response = llm.invoke(messages)
    content = response.content.strip()
    
    if "```json" in content:
        content = content.split("```json")[1].split("```")[0].strip()
    elif "```" in content:
        content = content.split("```")[1].split("```")[0].strip()
    
    parsed = json.loads(content)
    return parsed.get("claims", [])


def verify_claim(claim: str, llm) -> dict:
    """Verify a single claim using web search."""
    
    # Search for evidence
    search_result = fact_check_search(claim)
    supporting = search_result.get("supporting_sources", [])
    answer_snippet = search_result.get("answer_snippet", "")
    
    sources_text = ""
    for s in supporting:
        sources_text += f"\nTitle: {s['title']}\nURL: {s['url']}\nExcerpt: {s['content']}\n"
    
    verification_prompt = f"""Verify this factual claim using the provided evidence.

CLAIM: "{claim}"

SEARCH EVIDENCE:
{sources_text if sources_text else "No direct evidence found."}

ANSWER SNIPPET: {answer_snippet}

Analyze and return ONLY valid JSON:
{{
  "claim": "{claim}",
  "verdict": "VERIFIED|UNVERIFIED|DISPUTED",
  "confidence": 0.0-1.0,
  "explanation": "1-2 sentence explanation of the verdict",
  "supporting_url": "URL of main supporting source or null",
  "correction": "If DISPUTED: what the correct information is. Otherwise null."
}}

VERDICT RULES:
- VERIFIED: Strong evidence confirms the claim
- UNVERIFIED: Insufficient evidence either way
- DISPUTED: Evidence clearly contradicts the claim"""
    
    messages = [
        SystemMessage(content=FACT_CHECKER_SYSTEM_PROMPT),
        HumanMessage(content=verification_prompt)
    ]
    
    response = llm.invoke(messages)
    content = response.content.strip()
    
    if "```json" in content:
        content = content.split("```json")[1].split("```")[0].strip()
    elif "```" in content:
        content = content.split("```")[1].split("```")[0].strip()
    
    result = json.loads(content)
    result["claim"] = claim  # ensure claim is always present
    return result


def fact_checker_agent(state: dict) -> dict:
    """
    Fact checker agent that verifies top 5 claims in the draft report.
    
    Args:
        state: Current workflow state with draft_report
    
    Returns:
        Updated state with fact_check_results
    """
    draft_report = state.get("draft_report", "")
    topic = state["topic"]
    
    progress_callback = state.get("_progress_callback")
    if progress_callback:
        progress_callback("fact_checker", "🔬 Extracting factual claims from report...")
    
    if not draft_report:
        return {**state, "fact_check_results": []}
    
    llm = get_llm()
    
    # Extract claims
    try:
        claims = extract_claims(draft_report, llm)
    except Exception as e:
        print(f"[FactChecker] Claim extraction error: {e}")
        claims = []
    
    if not claims:
        return {**state, "fact_check_results": []}
    
    if progress_callback:
        progress_callback("fact_checker", f"🔍 Verifying {len(claims)} factual claims...")
    
    # Verify each claim
    fact_check_results = []
    disputed_count = 0
    
    for i, claim in enumerate(claims[:5], 1):
        if progress_callback:
            progress_callback("fact_checker", f"  Checking claim {i}/{min(len(claims), 5)}: {claim[:60]}...")
        
        try:
            result = verify_claim(claim, llm)
            fact_check_results.append(result)
            
            if result.get("verdict") == "DISPUTED":
                disputed_count += 1
                
        except Exception as e:
            print(f"[FactChecker] Verification error for claim {i}: {e}")
            fact_check_results.append({
                "claim": claim,
                "verdict": "UNVERIFIED",
                "confidence": 0.5,
                "explanation": f"Verification failed: {str(e)[:100]}",
                "supporting_url": None,
                "correction": None,
            })
    
    # Summary
    verified = sum(1 for r in fact_check_results if r.get("verdict") == "VERIFIED")
    unverified = sum(1 for r in fact_check_results if r.get("verdict") == "UNVERIFIED")
    disputed = sum(1 for r in fact_check_results if r.get("verdict") == "DISPUTED")
    
    if progress_callback:
        progress_callback(
            "fact_checker",
            f"✅ Fact check complete: {verified} VERIFIED, {unverified} UNVERIFIED, {disputed} DISPUTED"
        )
    
    return {
        **state,
        "fact_check_results": fact_check_results,
        "disputed_count": disputed_count,
    }