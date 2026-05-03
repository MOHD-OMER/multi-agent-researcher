"""
Interactive Fact-Check Dashboard
Renders a rich visual HTML dashboard from fact_check_results.
"""


def render_factcheck_dashboard(fact_check_results: list, topic: str = "") -> str:
    """Render a premium HTML fact-check dashboard."""

    if not fact_check_results:
        return """
        <div style="font-family:'JetBrains Mono',monospace;color:#475569;
                    padding:40px;text-align:center;background:#070e1a;
                    border:1px solid #0f2744;border-radius:6px;">
            <div style="font-size:32px;margin-bottom:12px;">◇</div>
            <div style="font-size:12px;letter-spacing:0.1em;">NO FACT-CHECK DATA AVAILABLE</div>
            <div style="font-size:11px;color:#334155;margin-top:6px;">Run a research pipeline first</div>
        </div>"""

    verdict_config = {
        "VERIFIED":   {"icon": "✓", "color": "#34d399", "bg": "#0a2a1a", "border": "#22c55e33", "label": "VERIFIED"},
        "UNVERIFIED": {"icon": "?", "color": "#fbbf24", "bg": "#1a160a", "border": "#fbbf2433", "label": "UNVERIFIED"},
        "DISPUTED":   {"icon": "✗", "color": "#f87171", "bg": "#2a0a0a", "border": "#f8717133", "label": "DISPUTED"},
    }

    # Summary stats
    verified   = sum(1 for r in fact_check_results if r.get("verdict") == "VERIFIED")
    unverified = sum(1 for r in fact_check_results if r.get("verdict") == "UNVERIFIED")
    disputed   = sum(1 for r in fact_check_results if r.get("verdict") == "DISPUTED")
    total      = len(fact_check_results)
    accuracy   = int((verified / total) * 100) if total > 0 else 0

    # Accuracy ring (SVG)
    circumference = 2 * 3.14159 * 36
    dash_offset   = circumference * (1 - accuracy / 100)
    ring_color    = "#34d399" if accuracy >= 70 else "#fbbf24" if accuracy >= 40 else "#f87171"

    ring_svg = f"""
    <svg width="90" height="90" viewBox="0 0 90 90">
        <circle cx="45" cy="45" r="36" fill="none" stroke="#0f2744" stroke-width="6"/>
        <circle cx="45" cy="45" r="36" fill="none" stroke="{ring_color}" stroke-width="6"
                stroke-dasharray="{circumference:.1f}"
                stroke-dashoffset="{dash_offset:.1f}"
                stroke-linecap="round"
                transform="rotate(-90 45 45)"/>
        <text x="45" y="46" text-anchor="middle" dominant-baseline="central"
              font-family="'Syne',sans-serif" font-size="18" font-weight="800"
              fill="{ring_color}">{accuracy}%</text>
        <text x="45" y="62" text-anchor="middle" dominant-baseline="central"
              font-family="'JetBrains Mono',monospace" font-size="7"
              fill="#334155">ACCURACY</text>
    </svg>"""

    # Stats bar
    stats_html = f"""
    <div style="display:flex;align-items:center;gap:28px;padding:20px 24px;
                background:#070e1a;border:1px solid #0f2744;border-radius:6px;
                margin-bottom:16px;">
        {ring_svg}
        <div style="display:flex;gap:32px;flex:1;">
            <div style="text-align:center;">
                <div style="font-family:'Syne',sans-serif;font-size:28px;font-weight:800;color:#34d399;">{verified}</div>
                <div style="font-size:9px;letter-spacing:0.15em;color:#1e3a5f;margin-top:2px;">VERIFIED</div>
            </div>
            <div style="text-align:center;">
                <div style="font-family:'Syne',sans-serif;font-size:28px;font-weight:800;color:#fbbf24;">{unverified}</div>
                <div style="font-size:9px;letter-spacing:0.15em;color:#1e3a5f;margin-top:2px;">UNVERIFIED</div>
            </div>
            <div style="text-align:center;">
                <div style="font-family:'Syne',sans-serif;font-size:28px;font-weight:800;color:#f87171;">{disputed}</div>
                <div style="font-size:9px;letter-spacing:0.15em;color:#1e3a5f;margin-top:2px;">DISPUTED</div>
            </div>
            <div style="text-align:center;">
                <div style="font-family:'Syne',sans-serif;font-size:28px;font-weight:800;color:#94a3b8;">{total}</div>
                <div style="font-size:9px;letter-spacing:0.15em;color:#1e3a5f;margin-top:2px;">TOTAL CLAIMS</div>
            </div>
        </div>
        {"<div style='padding:8px 16px;background:#2a0a0a;border:1px solid #f8717133;border-radius:4px;color:#f87171;font-size:10px;letter-spacing:0.1em;font-family:JetBrains Mono,monospace;'>⚠ DISPUTED CLAIMS FOUND</div>" if disputed > 0 else "<div style='padding:8px 16px;background:#0a2a1a;border:1px solid #22c55e33;border-radius:4px;color:#34d399;font-size:10px;letter-spacing:0.1em;font-family:JetBrains Mono,monospace;'>✓ ALL CLEAR</div>"}
    </div>"""

    # Claim cards
    cards_html = ""
    for i, r in enumerate(fact_check_results, 1):
        verdict  = r.get("verdict", "UNVERIFIED")
        cfg      = verdict_config.get(verdict, verdict_config["UNVERIFIED"])
        claim    = r.get("claim", "Unknown claim")
        expl     = r.get("explanation", "")
        corr     = r.get("correction")
        conf     = r.get("confidence", 0.5)
        src_url  = r.get("supporting_url")
        conf_pct = int(conf * 100)

        correction_html = ""
        if corr:
            correction_html = f"""
            <div style="margin-top:10px;padding:10px 12px;background:#0f2744;
                        border-left:2px solid #f59e0b;border-radius:0 3px 3px 0;">
                <div style="font-size:9px;letter-spacing:0.12em;color:#f59e0b;margin-bottom:4px;">CORRECTION</div>
                <div style="font-size:11px;color:#94a3b8;line-height:1.5;">{corr}</div>
            </div>"""

        source_html = ""
        if src_url:
            source_html = f"""
            <a href="{src_url}" target="_blank"
               style="display:inline-block;margin-top:8px;font-size:10px;
                      color:#38bdf8;text-decoration:none;letter-spacing:0.05em;">
                ↗ View Source
            </a>"""

        cards_html += f"""
        <div style="margin-bottom:12px;padding:16px;background:{cfg['bg']};
                    border:1px solid {cfg['border']};border-radius:6px;
                    border-left:3px solid {cfg['color']};">
            <div style="display:flex;align-items:flex-start;justify-content:space-between;gap:12px;">
                <div style="display:flex;align-items:flex-start;gap:12px;flex:1;">
                    <div style="width:24px;height:24px;border-radius:50%;background:{cfg['color']}22;
                                border:1px solid {cfg['color']}66;display:flex;align-items:center;
                                justify-content:center;color:{cfg['color']};font-size:12px;
                                font-weight:700;flex-shrink:0;margin-top:1px;">{cfg['icon']}</div>
                    <div style="flex:1;">
                        <div style="font-size:11px;color:#334155;letter-spacing:0.06em;margin-bottom:6px;">
                            CLAIM #{i:02d}
                        </div>
                        <div style="font-size:12px;color:#e2e8f0;font-family:'JetBrains Mono',monospace;
                                    line-height:1.6;margin-bottom:8px;">"{claim}"</div>
                        <div style="font-size:11px;color:#64748b;line-height:1.5;">{expl}</div>
                        {correction_html}
                        {source_html}
                    </div>
                </div>
                <div style="text-align:right;flex-shrink:0;">
                    <div style="font-family:'Syne',sans-serif;font-size:10px;font-weight:700;
                                letter-spacing:0.1em;color:{cfg['color']};margin-bottom:6px;">{cfg['label']}</div>
                    <div style="font-size:9px;color:#1e3a5f;letter-spacing:0.08em;margin-bottom:4px;">CONFIDENCE</div>
                    <div style="width:60px;height:3px;background:#0f2744;border-radius:2px;margin:0 0 4px auto;">
                        <div style="height:100%;width:{conf_pct}%;background:{cfg['color']};border-radius:2px;"></div>
                    </div>
                    <div style="font-family:'Syne',sans-serif;font-size:13px;font-weight:700;
                                color:{cfg['color']};">{conf_pct}%</div>
                </div>
            </div>
        </div>"""

    topic_line = f"<div style='font-size:10px;color:#1e3a5f;letter-spacing:0.15em;margin-bottom:16px;font-family:JetBrains Mono,monospace;'>TOPIC: {topic[:80]}</div>" if topic else ""

    return f"""
    <div style="font-family:'JetBrains Mono',monospace;background:#020817;padding:4px;">
        {topic_line}
        {stats_html}
        <div style="font-size:10px;letter-spacing:0.2em;color:#1e3a5f;
                    margin-bottom:12px;font-family:'JetBrains Mono',monospace;">
            ◇ CLAIM VERIFICATION DETAILS
        </div>
        {cards_html}
    </div>"""
