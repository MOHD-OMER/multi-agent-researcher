"""
Source Credibility Scorer
Uses sentence-transformers cosine similarity to score each source's
relevance to the topic, plus heuristic credibility signals.
"""
from __future__ import annotations
import re


# Lazy-load model to avoid slow startup
_model = None

def _get_model():
    global _model
    if _model is None:
        try:
            from sentence_transformers import SentenceTransformer
            _model = SentenceTransformer("all-MiniLM-L6-v2")
        except Exception as e:
            print(f"[Credibility] Could not load model: {e}")
            _model = None
    return _model


# High-credibility domain patterns
CREDIBLE_DOMAINS = [
    r"arxiv\.org", r"nature\.com", r"science\.org", r"pubmed", r"ncbi\.nlm\.nih",
    r"ieee\.org", r"acm\.org", r"springer\.com", r"scholar\.google",
    r"openai\.com", r"deepmind\.com", r"anthropic\.com", r"mit\.edu",
    r"stanford\.edu", r"berkeley\.edu", r"harvard\.edu", r"\.gov",
    r"reuters\.com", r"apnews\.com", r"bbc\.com", r"wired\.com",
]

LOW_CREDIBILITY = [
    r"reddit\.com", r"twitter\.com", r"facebook\.com", r"tiktok\.com",
    r"quora\.com", r"yahoo\.answers",
]


def _domain_score(url: str) -> float:
    """Score 0-1 based on domain credibility."""
    url_lower = url.lower()
    for pat in LOW_CREDIBILITY:
        if re.search(pat, url_lower):
            return 0.2
    for pat in CREDIBLE_DOMAINS:
        if re.search(pat, url_lower):
            return 1.0
    return 0.6  # neutral/unknown


def _content_richness(text: str) -> float:
    """Score based on content length and structure."""
    if not text:
        return 0.0
    words = len(text.split())
    if words > 200:
        return 1.0
    elif words > 80:
        return 0.7
    elif words > 30:
        return 0.4
    return 0.2


def score_sources(topic: str, sources: list) -> list:
    """
    Score each source for relevance + credibility.
    Returns sources list with added 'credibility_score' (0-100) and 'credibility_label'.
    """
    model = _get_model()
    scored = []

    for source in sources:
        url = source.get("url", "")
        content = " ".join(source.get("key_points", []))
        title = source.get("title", "")

        # Domain credibility (40% weight)
        domain_s = _domain_score(url)

        # Content richness (20% weight)
        richness_s = _content_richness(content)

        # Semantic relevance via embeddings (40% weight)
        if model and (content or title):
            try:
                from sentence_transformers import util
                import torch
                topic_emb = model.encode(topic, convert_to_tensor=True)
                src_text = f"{title}. {content}"[:512]
                src_emb = model.encode(src_text, convert_to_tensor=True)
                similarity = float(util.cos_sim(topic_emb, src_emb)[0][0])
                relevance_s = max(0.0, min(1.0, similarity))
            except Exception:
                relevance_s = 0.5
        else:
            relevance_s = 0.5

        # Weighted final score
        raw = (domain_s * 0.4) + (richness_s * 0.2) + (relevance_s * 0.4)
        score = int(raw * 100)

        # Label
        if score >= 80:
            label = "HIGH"
            color = "#34d399"
        elif score >= 55:
            label = "MEDIUM"
            color = "#fbbf24"
        else:
            label = "LOW"
            color = "#f87171"

        s = dict(source)
        s["credibility_score"] = score
        s["credibility_label"] = label
        s["credibility_color"] = color
        scored.append(s)

    # Sort by score descending
    scored.sort(key=lambda x: x["credibility_score"], reverse=True)
    return scored


def render_credibility_html(scored_sources: list) -> str:
    """Render a premium HTML credibility dashboard."""
    if not scored_sources:
        return "<p style='color:#475569;font-family:JetBrains Mono,monospace;font-size:12px;'>No sources to display.</p>"

    rows = ""
    for i, s in enumerate(scored_sources, 1):
        score = s.get("credibility_score", 0)
        label = s.get("credibility_label", "N/A")
        color = s.get("credibility_color", "#94a3b8")
        title = s.get("title", "Unknown Source")[:60]
        url = s.get("url", "#")
        src_type = s.get("source_type", "web").upper()
        bar_width = score

        rows += f"""
        <div style="margin-bottom:12px;padding:14px 16px;background:#0a1628;border:1px solid #0f2744;border-radius:4px;border-left:3px solid {color};">
            <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:8px;">
                <div style="display:flex;align-items:center;gap:10px;">
                    <span style="font-family:'Syne',sans-serif;font-size:10px;font-weight:700;color:#1e3a5f;">#{i:02d}</span>
                    <a href="{url}" target="_blank" style="color:#e2e8f0;font-family:'JetBrains Mono',monospace;font-size:12px;text-decoration:none;font-weight:500;">{title}</a>
                </div>
                <div style="display:flex;align-items:center;gap:8px;flex-shrink:0;">
                    <span style="font-size:9px;letter-spacing:0.1em;color:#334155;background:#0f2744;padding:2px 7px;border-radius:2px;">{src_type}</span>
                    <span style="font-size:10px;letter-spacing:0.08em;font-weight:600;color:{color};font-family:'Syne',sans-serif;">{label}</span>
                    <span style="font-family:'Syne',sans-serif;font-size:16px;font-weight:800;color:{color};min-width:36px;text-align:right;">{score}</span>
                </div>
            </div>
            <div style="height:3px;background:#0f2744;border-radius:2px;overflow:hidden;">
                <div style="height:100%;width:{bar_width}%;background:{color};border-radius:2px;transition:width 0.6s ease;"></div>
            </div>
        </div>"""

    avg = int(sum(s.get("credibility_score", 0) for s in scored_sources) / len(scored_sources))
    high = sum(1 for s in scored_sources if s.get("credibility_label") == "HIGH")
    med  = sum(1 for s in scored_sources if s.get("credibility_label") == "MEDIUM")
    low  = sum(1 for s in scored_sources if s.get("credibility_label") == "LOW")

    return f"""
    <div style="font-family:'JetBrains Mono',monospace;">
        <div style="display:flex;gap:20px;margin-bottom:16px;padding-bottom:12px;border-bottom:1px solid #0f2744;">
            <div style="font-size:10px;color:#1e3a5f;letter-spacing:0.1em;">
                AVG SCORE<br>
                <span style="font-family:'Syne',sans-serif;font-size:22px;font-weight:800;color:#f59e0b;">{avg}</span>
            </div>
            <div style="font-size:10px;color:#1e3a5f;letter-spacing:0.1em;">
                HIGH<br><span style="font-family:'Syne',sans-serif;font-size:22px;font-weight:800;color:#34d399;">{high}</span>
            </div>
            <div style="font-size:10px;color:#1e3a5f;letter-spacing:0.1em;">
                MEDIUM<br><span style="font-family:'Syne',sans-serif;font-size:22px;font-weight:800;color:#fbbf24;">{med}</span>
            </div>
            <div style="font-size:10px;color:#1e3a5f;letter-spacing:0.1em;">
                LOW<br><span style="font-family:'Syne',sans-serif;font-size:22px;font-weight:800;color:#f87171;">{low}</span>
            </div>
        </div>
        {rows}
    </div>"""
