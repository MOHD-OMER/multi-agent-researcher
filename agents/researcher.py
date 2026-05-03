"""
Researcher Agent — Senior Research Analyst
Finds 5-7 relevant sources using web search and ArXiv.
"""
import os
import json
from langchain_groq import ChatGroq
from langchain_core.messages import HumanMessage, SystemMessage

from tools.web_search import web_search
from tools.arxiv_search import arxiv_search


RESEARCHER_SYSTEM_PROMPT = """You are a Senior Research Analyst with expertise in synthesizing information from multiple sources.

Your job is to research a given topic thoroughly and extract the most relevant, credible information.

When given a topic, you will:
1. Identify the key aspects and sub-topics to investigate
2. Analyze all provided search results
3. Extract the most important facts, figures, and insights
4. Organize sources by relevance and credibility

Always output structured JSON. Be precise and comprehensive.
"""


def get_llm():
    return ChatGroq(
        api_key=os.getenv("GROQ_API_KEY"),
        model="llama-3.3-70b-versatile",
        temperature=0.2,
        max_tokens=4096,
    )


def researcher_agent(state: dict, depth: str = "quick") -> dict:
    """
    Researcher agent that finds sources and extracts key information.
    
    Args:
        state: Current workflow state
        depth: "quick" (5 sources) or "deep" (7+ sources)
    
    Returns:
        Updated state with sources list
    """
    topic = state["topic"]
    existing_sources = state.get("sources", [])
    iteration = state.get("iteration_count", 0)
    
    num_web = 5 if depth == "quick" else 7
    num_arxiv = 2 if depth == "quick" else 4
    
    progress_callback = state.get("_progress_callback")
    if progress_callback:
        progress_callback("researcher", f"🔍 Searching web for: {topic}")
    
    # Web search
    web_results = web_search(
        query=f"{topic} latest developments research",
        max_results=num_web,
        search_depth="advanced"
    )
    
    # Additional targeted search
    web_results2 = web_search(
        query=f"{topic} key findings analysis 2024 2025",
        max_results=3,
        search_depth="basic"
    )
    
    if progress_callback:
        progress_callback("researcher", f"📚 Searching ArXiv for academic papers...")
    
    # ArXiv search
    arxiv_results = arxiv_search(query=topic, max_results=num_arxiv)
    
    # Combine all raw results
    all_raw = web_results + web_results2 + [
        {
            "title": r["title"],
            "url": r["url"],
            "content": f"Authors: {', '.join(r['authors'])}. Published: {r['published']}. {r['summary']}",
            "score": 0.9,
            "source": "arxiv"
        }
        for r in arxiv_results
    ]
    
    if progress_callback:
        progress_callback("researcher", f"🧠 Synthesizing {len(all_raw)} sources with LLM...")
    
    # Use LLM to synthesize and extract key points
    llm = get_llm()
    
    results_text = json.dumps(all_raw[:12], indent=2)
    
    synthesis_prompt = f"""You are a Senior Research Analyst. Analyze these search results about "{topic}" and synthesize the most valuable sources.

SEARCH RESULTS:
{results_text}

Select the 5-7 MOST RELEVANT and CREDIBLE sources. For each source, extract:
- A clear title
- The URL
- 3-5 specific key points or facts from the content
- Why this source is relevant

Return ONLY valid JSON in this exact format:
{{
  "sources": [
    {{
      "title": "Source title",
      "url": "https://...",
      "key_points": ["point 1", "point 2", "point 3"],
      "relevance": "Why this source matters for the topic",
      "source_type": "web|arxiv|news"
    }}
  ],
  "research_summary": "2-3 sentence overview of what was found",
  "key_themes": ["theme1", "theme2", "theme3"]
}}"""
    
    messages = [
        SystemMessage(content=RESEARCHER_SYSTEM_PROMPT),
        HumanMessage(content=synthesis_prompt)
    ]
    
    try:
        response = llm.invoke(messages)
        content = response.content.strip()
        
        # Extract JSON
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0].strip()
        elif "```" in content:
            content = content.split("```")[1].split("```")[0].strip()
        
        parsed = json.loads(content)
        new_sources = parsed.get("sources", [])
        
        # Add metadata
        for s in new_sources:
            s["iteration"] = iteration + 1
        
        # Merge with existing sources (avoid duplicates)
        existing_urls = {s.get("url", "") for s in existing_sources}
        merged_sources = existing_sources + [s for s in new_sources if s.get("url", "") not in existing_urls]
        
        if progress_callback:
            progress_callback("researcher", f"✅ Found {len(new_sources)} quality sources. Total: {len(merged_sources)}")
        
        return {
            **state,
            "sources": merged_sources,
            "research_summary": parsed.get("research_summary", ""),
            "key_themes": parsed.get("key_themes", []),
            "iteration_count": iteration + 1,
        }
    
    except (json.JSONDecodeError, Exception) as e:
        print(f"[Researcher] LLM synthesis error: {e}")
        # Fallback: use raw results directly
        fallback_sources = []
        for r in all_raw[:7]:
            fallback_sources.append({
                "title": r.get("title", "Unknown"),
                "url": r.get("url", ""),
                "key_points": [r.get("content", "")[:200]],
                "relevance": "Retrieved from search",
                "source_type": r.get("source", "web"),
                "iteration": iteration + 1,
            })
        
        return {
            **state,
            "sources": existing_sources + fallback_sources,
            "iteration_count": iteration + 1,
        }