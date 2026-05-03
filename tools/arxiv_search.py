"""
ArXiv search tool for academic paper retrieval.
Handles rate limits (HTTP 429) gracefully with retry + fallback.
"""
import arxiv
import time


def arxiv_search(query: str, max_results: int = 5) -> list[dict]:
    """
    Search ArXiv for academic papers. Returns empty list on rate limit.
    """
    for attempt in range(2):
        try:
            client = arxiv.Client(
                page_size=max_results,
                delay_seconds=3.0,
                num_retries=2,
            )
            search = arxiv.Search(
                query=query,
                max_results=max_results,
                sort_by=arxiv.SortCriterion.Relevance,
            )

            results = []
            for paper in client.results(search):
                results.append({
                    "title": paper.title,
                    "authors": [a.name for a in paper.authors[:3]],
                    "summary": (paper.summary[:500] + "..."
                                if len(paper.summary) > 500 else paper.summary),
                    "url": paper.entry_id,
                    "published": (paper.published.strftime("%Y-%m-%d")
                                  if paper.published else "Unknown"),
                    "categories": paper.categories[:3],
                    "source": "arxiv",
                })

            return results

        except Exception as e:
            err = str(e)
            if "429" in err or "rate" in err.lower():
                print(f"[ArxivSearch] Rate limited (attempt {attempt+1}), waiting 8s...")
                time.sleep(8)
            else:
                print(f"[ArxivSearch] Error: {e}")
                return []

    print("[ArxivSearch] Skipping ArXiv — rate limited, using web sources only.")
    return []