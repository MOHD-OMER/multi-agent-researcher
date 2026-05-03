"""
Web search tool using Tavily API.
"""
import os
from typing import Optional
from tavily import TavilyClient


def web_search(query: str, max_results: int = 5, search_depth: str = "advanced") -> list[dict]:
    """
    Search the web using Tavily API.
    
    Args:
        query: Search query string
        max_results: Maximum number of results to return
        search_depth: "basic" or "advanced"
    
    Returns:
        List of dicts with keys: title, url, content, score
    """
    api_key = os.getenv("TAVILY_API_KEY")
    if not api_key:
        raise ValueError("TAVILY_API_KEY environment variable not set")
    
    client = TavilyClient(api_key=api_key)
    
    try:
        response = client.search(
            query=query,
            search_depth=search_depth,
            max_results=max_results,
            include_answer=True,
            include_raw_content=False,
        )
        
        results = []
        for r in response.get("results", []):
            results.append({
                "title": r.get("title", "No Title"),
                "url": r.get("url", ""),
                "content": r.get("content", ""),
                "score": r.get("score", 0.0),
            })
        
        return results
    
    except Exception as e:
        print(f"[WebSearch] Error: {e}")
        return []


def fact_check_search(claim: str) -> dict:
    """
    Targeted search to verify a specific factual claim.
    
    Returns:
        Dict with supporting evidence, contradicting evidence, and verdict
    """
    api_key = os.getenv("TAVILY_API_KEY")
    if not api_key:
        raise ValueError("TAVILY_API_KEY environment variable not set")
    
    client = TavilyClient(api_key=api_key)
    
    try:
        # Search for the claim directly
        support_results = client.search(
            query=f"verify fact: {claim}",
            search_depth="advanced",
            max_results=3,
        )
        
        supporting = []
        for r in support_results.get("results", []):
            supporting.append({
                "title": r.get("title", ""),
                "url": r.get("url", ""),
                "content": r.get("content", "")[:400],
            })
        
        return {
            "claim": claim,
            "supporting_sources": supporting,
            "answer_snippet": support_results.get("answer", ""),
        }
    
    except Exception as e:
        print(f"[FactCheckSearch] Error: {e}")
        return {"claim": claim, "supporting_sources": [], "answer_snippet": ""}
