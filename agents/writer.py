"""
Writer Agent — Technical Report Writer
Generates structured 500-800 word reports from research sources.
"""
import os
import json
from langchain_groq import ChatGroq
from langchain_core.messages import HumanMessage, SystemMessage


WRITER_SYSTEM_PROMPT = """You are a Technical Report Writer specializing in creating clear, well-structured research reports.

You write for an educated professional audience. Your reports are:
- Factually grounded (citing only what sources say)
- Well-organized with clear sections
- Analytically insightful, not just descriptive
- Written in professional but accessible language

You NEVER fabricate information. Every claim must trace back to the provided sources.
"""


def get_llm():
    return ChatGroq(
        api_key=os.getenv("GROQ_API_KEY"),
        model="llama-3.3-70b-versatile",
        temperature=0.4,
        max_tokens=4096,
    )


def writer_agent(state: dict) -> dict:
    """
    Writer agent that generates a structured markdown report from research sources.
    
    Args:
        state: Current workflow state with sources
    
    Returns:
        Updated state with draft_report
    """
    topic = state["topic"]
    sources = state.get("sources", [])
    research_summary = state.get("research_summary", "")
    key_themes = state.get("key_themes", [])
    
    progress_callback = state.get("_progress_callback")
    if progress_callback:
        progress_callback("writer", f"✍️ Drafting structured report on: {topic}")
    
    if not sources:
        return {
            **state,
            "draft_report": f"# {topic}\n\nInsufficient research data to generate report.",
        }
    
    llm = get_llm()
    
    # Format sources for the prompt
    sources_text = ""
    for i, s in enumerate(sources, 1):
        key_pts = "\n".join(f"  - {pt}" for pt in s.get("key_points", []))
        sources_text += f"""
Source {i}: {s.get('title', 'Unknown')}
URL: {s.get('url', 'N/A')}
Key Points:
{key_pts}
Relevance: {s.get('relevance', '')}
"""
    
    themes_text = ", ".join(key_themes) if key_themes else "to be determined from sources"
    
    writing_prompt = f"""Write a comprehensive research report on: "{topic}"

RESEARCH SUMMARY:
{research_summary}

KEY THEMES IDENTIFIED:
{themes_text}

SOURCES (use these as your evidence base):
{sources_text}

Write a 500-800 word report in Markdown with EXACTLY these sections:

## Executive Summary
(2-3 sentences capturing the most important finding)

## Background
(Context and why this topic matters — 80-100 words)

## Key Findings
(The 3-5 most significant findings from research, each with a brief explanation — 200-250 words)

## Analysis
(Synthesize the findings, identify patterns, implications — 150-200 words)

## Conclusion
(What this means going forward, open questions — 80-100 words)

## References
(List all sources with their URLs as markdown links)

IMPORTANT RULES:
- Reference sources inline like [Source Title](URL) when stating key facts
- Do NOT fabricate statistics or claims not found in the sources
- Write in a professional, analytical tone
- Use bullet points sparingly — prefer flowing prose
- The report title should be: # [Your Title: Descriptive subtitle]"""
    
    messages = [
        SystemMessage(content=WRITER_SYSTEM_PROMPT),
        HumanMessage(content=writing_prompt)
    ]
    
    if progress_callback:
        progress_callback("writer", "📝 Generating report sections...")
    
    try:
        response = llm.invoke(messages)
        draft = response.content.strip()
        
        # Ensure it starts with a title
        if not draft.startswith("#"):
            draft = f"# Research Report: {topic}\n\n" + draft
        
        if progress_callback:
            word_count = len(draft.split())
            progress_callback("writer", f"✅ Report drafted ({word_count} words)")
        
        return {
            **state,
            "draft_report": draft,
        }
    
    except Exception as e:
        print(f"[Writer] Error: {e}")
        fallback = f"# Research Report: {topic}\n\n"
        fallback += "## Executive Summary\nResearch compilation complete.\n\n"
        fallback += "## Key Findings\n"
        for s in sources[:5]:
            fallback += f"### {s.get('title', 'Source')}\n"
            for pt in s.get("key_points", [])[:3]:
                fallback += f"- {pt}\n"
            fallback += "\n"
        
        return {**state, "draft_report": fallback}