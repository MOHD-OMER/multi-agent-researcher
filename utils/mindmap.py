"""
Research Mind Map Generator — v5.0
Proper hierarchical radial layout with zero overlaps.
Themes spread wide, sources/facts orbit their parent at safe distances.
"""

import math
import tempfile
import textwrap


# ─── Text wrapper ─────────────────────────────────────────────────────────────

def _wrap(text: str, width: int, max_lines: int = 4) -> str:
    if not text:
        return ""
    lines = textwrap.wrap(text, width=width, max_lines=max_lines, placeholder="…")
    return "\n".join(lines)


# ─── Geometry helpers ─────────────────────────────────────────────────────────

def _polar(cx: float, cy: float, r: float, angle: float):
    return cx + r * math.cos(angle), cy + r * math.sin(angle)


# ─── Main generator ───────────────────────────────────────────────────────────

def generate_mindmap(
    topic: str,
    key_themes: list,
    sources: list,
    fact_check_results: list,
) -> str | None:
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import matplotlib.patches as mpatches
        from matplotlib.patches import FancyBboxPatch

        # ── Palette ───────────────────────────────────────────────────────────
        BG = "#f0f2f8"

        STYLES = {
            "topic":           {"bg": "#0f172a", "border": "#38bdf8", "text": "#f1f5f9", "fs": 15,   "fw": "bold",   "pad": 0.55, "lw": 3.5},
            "theme":           {"bg": "#1e3a5f", "border": "#60a5fa", "text": "#e0f2fe", "fs": 11.5, "fw": "bold",   "pad": 0.40, "lw": 2.5},
            "source":          {"bg": "#ffffff", "border": "#64748b", "text": "#1e293b", "fs": 9.5,  "fw": "normal", "pad": 0.30, "lw": 1.8},
            "fact_verified":   {"bg": "#ecfdf5", "border": "#10b981", "text": "#064e3b", "fs": 9.5,  "fw": "normal", "pad": 0.30, "lw": 2.0},
            "fact_unverified": {"bg": "#fefce8", "border": "#f59e0b", "text": "#78350f", "fs": 9.5,  "fw": "normal", "pad": 0.30, "lw": 2.0},
            "fact_disputed":   {"bg": "#fef2f2", "border": "#ef4444", "text": "#7f1d1d", "fs": 9.5,  "fw": "normal", "pad": 0.30, "lw": 2.0},
        }

        EDGE_STYLES = {
            "topic-theme":  {"color": "#60a5fa", "lw": 2.2, "alpha": 0.9, "style": "-"},
            "theme-source": {"color": "#94a3b8", "lw": 1.4, "alpha": 0.75, "style": "--"},
            "theme-fact":   {"color": "#6ee7b7", "lw": 1.4, "alpha": 0.75, "style": ":"},
        }

        DPI = 180

        # ── Build node/edge lists ─────────────────────────────────────────────
        nodes: list[dict] = []
        edges: list[dict] = []

        # Central topic
        nodes.append({"id": "topic", "label": _wrap(topic, 28, 3), "type": "topic", "x": 0.0, "y": 0.0})

        # Themes: place evenly on a large radius, starting top
        themes = [t.strip() for t in (key_themes or []) if t.strip()][:8]
        n_themes = len(themes)
        R_THEME = 5.5  # big enough to breathe

        theme_angles: dict[str, float] = {}
        for i, label in enumerate(themes):
            angle = (2 * math.pi * i / max(n_themes, 1)) - math.pi / 2
            tx, ty = _polar(0, 0, R_THEME, angle)
            tid = f"theme_{i}"
            nodes.append({"id": tid, "label": _wrap(label, 22, 3), "type": "theme", "x": tx, "y": ty})
            edges.append({"a": "topic", "b": tid, "style": "topic-theme"})
            theme_angles[tid] = angle

        parent_ids = [f"theme_{i}" for i in range(n_themes)] if n_themes else ["topic"]

        # Sources: each theme gets sources fanned out AWAY from center
        sources_clean = sources[:8]
        n_src = len(sources_clean)

        # Assign sources round-robin to themes
        src_assignments: dict[str, list] = {p: [] for p in parent_ids}
        for i, src in enumerate(sources_clean):
            src_assignments[parent_ids[i % len(parent_ids)]].append(src)

        R_SRC = 3.8
        for pid, srcs in src_assignments.items():
            parent = next(n for n in nodes if n["id"] == pid)
            base_angle = theme_angles.get(pid, 0.0)
            # Fan out away from center
            outward = base_angle  # direction pointing away from origin
            n = len(srcs)
            spread = math.radians(50) if n > 1 else 0
            for k, src in enumerate(srcs):
                title = src.get("title", str(src)) if isinstance(src, dict) else str(src)
                fan_angle = outward + (k - (n - 1) / 2) * (spread / max(n - 1, 1))
                sx, sy = _polar(parent["x"], parent["y"], R_SRC, fan_angle)
                sid = f"src_{pid}_{k}"
                nodes.append({"id": sid, "label": _wrap(title, 28, 3), "type": "source", "x": sx, "y": sy})
                edges.append({"a": pid, "b": sid, "style": "theme-source"})

        # Facts: assign round-robin, fan perpendicular-ish to theme direction
        facts_clean = fact_check_results[:10]
        fact_assignments: dict[str, list] = {p: [] for p in parent_ids}
        for j, fc in enumerate(facts_clean):
            fact_assignments[parent_ids[j % len(parent_ids)]].append(fc)

        R_FACT = 3.8
        # perpendicular offset so facts don't overlap with sources
        PERP_OFFSET = math.radians(90)

        for pid, facts in fact_assignments.items():
            parent = next(n for n in nodes if n["id"] == pid)
            base_angle = theme_angles.get(pid, 0.0)
            outward = base_angle + PERP_OFFSET
            n = len(facts)
            spread = math.radians(50) if n > 1 else 0
            for k, fc in enumerate(facts):
                raw = fc.get("verdict", "unverified").strip().lower() if isinstance(fc, dict) else "unverified"
                ntype = f"fact_{raw}" if f"fact_{raw}" in STYLES else "fact_unverified"
                claim = fc.get("claim", str(fc)) if isinstance(fc, dict) else str(fc)
                fan_angle = outward + (k - (n - 1) / 2) * (spread / max(n - 1, 1))
                fx, fy = _polar(parent["x"], parent["y"], R_FACT, fan_angle)
                fid = f"fact_{pid}_{k}"
                nodes.append({"id": fid, "label": _wrap(claim, 30, 3), "type": ntype, "x": fx, "y": fy})
                edges.append({"a": pid, "b": fid, "style": "theme-fact"})

        # ── Figure ────────────────────────────────────────────────────────────
        fig, ax = plt.subplots(figsize=(28, 20), dpi=DPI)
        fig.patch.set_facecolor(BG)
        ax.set_facecolor(BG)
        ax.set_aspect("equal")
        ax.axis("off")

        xs = [n["x"] for n in nodes]
        ys = [n["y"] for n in nodes]
        pad = 5.5
        ax.set_xlim(min(xs) - pad, max(xs) + pad)
        ax.set_ylim(min(ys) - pad, max(ys) + pad)

        id_to_node = {n["id"]: n for n in nodes}

        # ── Draw edges ────────────────────────────────────────────────────────
        for e in edges:
            na, nb = id_to_node.get(e["a"]), id_to_node.get(e["b"])
            if not (na and nb):
                continue
            es = EDGE_STYLES[e["style"]]
            ax.plot(
                [na["x"], nb["x"]], [na["y"], nb["y"]],
                color=es["color"], linewidth=es["lw"], alpha=es["alpha"],
                linestyle=es["style"], zorder=1,
            )

        # ── Draw nodes ────────────────────────────────────────────────────────
        for node in nodes:
            st = STYLES.get(node["type"], STYLES["source"])
            label = node["label"]
            x, y = node["x"], node["y"]

            lines = label.split("\n")
            max_ch = max((len(l) for l in lines), default=8)
            n_lines = len(lines)

            char_w = 0.092 * (st["fs"] / 10)
            line_h = 0.285 * (st["fs"] / 10)
            bw = max_ch * char_w + st["pad"] * 2.8
            bh = n_lines * line_h + st["pad"] * 2.8

            rect = FancyBboxPatch(
                (x - bw / 2, y - bh / 2), bw, bh,
                boxstyle="round,pad=0.12",
                facecolor=st["bg"], edgecolor=st["border"],
                linewidth=st["lw"], zorder=2,
            )
            ax.add_patch(rect)

            ax.text(
                x, y, label,
                ha="center", va="center",
                fontsize=st["fs"], fontweight=st["fw"], color=st["text"],
                fontfamily="DejaVu Sans", linespacing=1.45, zorder=3,
            )

        # ── Legend ────────────────────────────────────────────────────────────
        legend_items = [
            mpatches.Patch(facecolor=STYLES["topic"]["bg"],           edgecolor=STYLES["topic"]["border"],           label="Main Topic"),
            mpatches.Patch(facecolor=STYLES["theme"]["bg"],           edgecolor=STYLES["theme"]["border"],           label="Key Theme"),
            mpatches.Patch(facecolor=STYLES["source"]["bg"],          edgecolor=STYLES["source"]["border"],          label="Source"),
            mpatches.Patch(facecolor=STYLES["fact_verified"]["bg"],   edgecolor=STYLES["fact_verified"]["border"],   label="✓ Verified"),
            mpatches.Patch(facecolor=STYLES["fact_unverified"]["bg"], edgecolor=STYLES["fact_unverified"]["border"], label="? Unverified"),
            mpatches.Patch(facecolor=STYLES["fact_disputed"]["bg"],   edgecolor=STYLES["fact_disputed"]["border"],   label="✗ Disputed"),
        ]
        ax.legend(
            handles=legend_items,
            loc="lower left",
            bbox_to_anchor=(0.01, 0.01),
            bbox_transform=ax.transAxes,
            fontsize=11, facecolor="white", edgecolor="#cbd5e1",
            labelcolor="#1e2937", framealpha=1.0, borderpad=1.2,
        )

        # ── Title ─────────────────────────────────────────────────────────────
        ax.set_title(
            f"Research Mind Map — {_wrap(topic, 80, 2)}",
            fontsize=18, color="#1e2937", pad=34, fontweight="semibold",
        )

        plt.tight_layout(pad=3.0)

        tmp = tempfile.NamedTemporaryFile(suffix=".png", prefix="mindmap_v5_", delete=False)
        plt.savefig(tmp.name, dpi=DPI, bbox_inches="tight", facecolor=BG)
        plt.close(fig)
        return tmp.name

    except Exception as exc:
        import traceback
        print(f"[MindMap] Error: {exc}")
        traceback.print_exc()
        return None


# ─── Test ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    path = generate_mindmap(
        topic="Mixture of Experts in Large Language Models",
        key_themes=[
            "Architecture & Routing",
            "Efficiency & Compute",
            "Training Strategies",
            "Notable MoE Models",
            "Multimodal MoE",
        ],
        sources=[
            {"title": "Switch Transformer — Scaling to Trillion Parameters"},
            {"title": "Mixtral 8x7B Technical Report"},
            {"title": "DeepSeek-V2: A Strong, Economical MoE LLM"},
            {"title": "Expert Choice Routing in MoE"},
            {"title": "GShard: Scaling Giant Models with Conditional Computation"},
        ],
        fact_check_results=[
            {"claim": "MoE uses sparse activation — only top-K experts fire per token.", "verdict": "verified"},
            {"claim": "DeepSeek-V2 and Grok-1 are MoE-based LLMs.", "verdict": "verified"},
            {"claim": "Some MoE models have 256 or more expert modules.", "verdict": "verified"},
            {"claim": "MoE always outperforms dense models at every scale.", "verdict": "disputed"},
            {"claim": "Expert routing incurs zero communication overhead.", "verdict": "disputed"},
            {"claim": "Load balancing loss is universally applied in all MoE papers.", "verdict": "unverified"},
        ],
    )
    if path:
        import shutil
        out = "/mnt/user-data/outputs/mindmap_v5.png"
        shutil.copy(path, out)
        print(f"Saved → {out}")
    else:
        print("Generation failed.")