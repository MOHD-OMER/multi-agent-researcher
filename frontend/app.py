"""
NEXUS — Multi-Agent Research Assistant
Complete single-page UI redesign.
"""
import os, sys, time, threading, tempfile
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent))

import gradio as gr
from dotenv import load_dotenv
load_dotenv()

from utils.history             import (save_report, load_all, delete_report,
                                        format_history_for_display, HISTORY_COLUMNS)
from utils.credibility         import score_sources, render_credibility_html
from utils.factcheck_dashboard import render_factcheck_dashboard
from utils.mindmap             import generate_mindmap
from utils.comparison          import run_parallel_research, generate_comparison_report


# ─── Core helpers ─────────────────────────────────────────────────────────────

def run_pipeline(topic, depth, cb=None):
    from graph.workflow import run_research
    return run_research(topic=topic,
                        depth=depth.lower().replace(" research", ""),
                        progress_callback=cb)

def make_pdf(md, topic):
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import inch
        from reportlab.lib import colors
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, HRFlowable
        from reportlab.lib.enums import TA_JUSTIFY
        import re
        tmp = tempfile.NamedTemporaryFile(
            suffix=".pdf", prefix=f"nexus_{topic[:16].replace(' ','_')}_", delete=False)
        doc = SimpleDocTemplate(tmp.name, pagesize=A4,
            rightMargin=.75*inch, leftMargin=.75*inch,
            topMargin=1*inch, bottomMargin=.75*inch)
        ss = getSampleStyleSheet()
        T  = ParagraphStyle('T',  parent=ss['Heading1'], fontSize=20,
               textColor=colors.HexColor('#0a0a0f'), spaceAfter=14)
        H2 = ParagraphStyle('H2', parent=ss['Heading2'], fontSize=13,
               textColor=colors.HexColor('#0d1f3c'), spaceAfter=8, spaceBefore=12)
        BD = ParagraphStyle('BD', parent=ss['Normal'], fontSize=10,
               leading=16, textColor=colors.HexColor('#1a1a2e'),
               spaceAfter=6, alignment=TA_JUSTIFY)
        MT = ParagraphStyle('MT', parent=ss['Normal'], fontSize=8,
               textColor=colors.HexColor('#666'), spaceAfter=4)
        story = [
            Paragraph("NEXUS Research Report", T),
            Paragraph(f"Generated: {datetime.now().strftime('%d %b %Y · %H:%M')}", MT),
            HRFlowable(width="100%", thickness=2, color=colors.HexColor('#6c63ff')),
            Spacer(1, .15*inch),
        ]
        for line in md.split('\n'):
            line = line.strip()
            if not line: story.append(Spacer(1, .04*inch)); continue
            lc = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', line)
            lc = re.sub(r'\*\*([^*]+)\*\*', r'<b>\1</b>', lc)
            lc = lc.replace('&', '&amp;')
            if   line.startswith('# '):         story.append(Paragraph(line[2:], T))
            elif line.startswith('## '):        story.append(Paragraph(line[3:], H2))
            elif line.startswith(('- ','* ')): story.append(Paragraph(f"• {lc[2:]}", BD))
            elif line.startswith('|') or line.startswith('---'): continue
            else:
                try: story.append(Paragraph(lc, BD))
                except: pass
        doc.build(story)
        return tmp.name
    except Exception as e:
        print(f"PDF: {e}")
        tmp = tempfile.NamedTemporaryFile(suffix=".txt", delete=False)
        tmp.write(md.encode('utf-8', errors='replace')); tmp.close()
        return tmp.name

ICONS = {"researcher":"⬡","writer":"⬢","fact_checker":"⬣",
         "editor":"◆","workflow":"▷","system":"▪"}


# ─── CSS ──────────────────────────────────────────────────────────────────────

CSS = """
@import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@300;400;500;600;700&family=Outfit:wght@400;600;700;800;900&family=DM+Mono:ital,wght@0,300;0,400;0,500;1,300&display=swap');

:root {
  --bg:      #06060f;
  --bg2:     #0c0c1a;
  --bg3:     #121224;
  --card:    #0e0e1e;
  --card2:   #141430;
  --border:  #1e1e3a;
  --border2: #28285a;
  --muted:   #32325a;
  --dim:     #50507a;
  --subtle:  #38386a;
  --body:    #a8a8cc;
  --body2:   #7070a0;
  --body3:   #404070;
  --violet:  #7c6fff;
  --vlight:  #a89aff;
  --cyan:    #22d3ee;
  --clight:  #7ff0ff;
  --green:   #10d9a0;
  --glight:  #6fffd4;
  --amber:   #f59e0b;
  --alight:  #fcd34d;
  --rose:    #f43f5e;
  --white:   #eeeeff;
  --pure:    #ffffff;
}

*, *::before, *::after { box-sizing: border-box; }

/* ── BASE ── */
.gradio-container {
  font-family: 'Space Grotesk', sans-serif !important;
  background: var(--bg) !important;
  color: var(--body) !important;
  min-height: 100vh;
}
body { background: var(--bg) !important; }

/* scrollbar */
::-webkit-scrollbar { width: 4px; height: 4px; }
::-webkit-scrollbar-track { background: transparent; }
::-webkit-scrollbar-thumb { background: var(--muted); border-radius: 4px; }
::-webkit-scrollbar-thumb:hover { background: var(--violet); }

/* ── HEADER ── */
.nx-header {
  padding: 48px 48px 40px;
  position: relative;
  overflow: hidden;
  border-bottom: 1px solid var(--border);
}

/* animated gradient line at top */
.nx-header::before {
  content: '';
  position: absolute;
  top: 0; left: 0; right: 0; height: 3px;
  background: linear-gradient(90deg,
    var(--violet) 0%, var(--cyan) 35%,
    var(--green)  65%, var(--violet) 100%);
  background-size: 200% 100%;
  animation: shimmer 4s linear infinite;
}
@keyframes shimmer { 0%{background-position:0% 0%} 100%{background-position:200% 0%} }

/* grid: left text | right pipeline */
.nx-hgrid {
  display: grid;
  grid-template-columns: 1fr 280px;
  gap: 48px;
  align-items: center;
  max-width: 1400px;
}

/* eyebrow */
.nx-eye {
  display: flex; align-items: center; gap: 10px;
  margin-bottom: 20px;
}
.nx-live {
  width: 7px; height: 7px; border-radius: 50%;
  background: var(--green);
  box-shadow: 0 0 12px var(--green);
  animation: pulse 2.5s ease-in-out infinite;
}
@keyframes pulse { 0%,100%{opacity:1;transform:scale(1)} 50%{opacity:.4;transform:scale(.85)} }

.nx-chip {
  font-family: 'DM Mono', monospace;
  font-size: 10px; font-weight: 500;
  letter-spacing: .22em; text-transform: uppercase;
  color: var(--vlight);
  padding: 4px 11px; border-radius: 3px;
  background: rgba(124,111,255,.1);
  border: 1px solid rgba(124,111,255,.3);
}
.nx-ver {
  font-family: 'DM Mono', monospace;
  font-size: 10px; color: var(--body3);
  letter-spacing: .12em;
}

/* big title */
.nx-left { display: flex; flex-direction: column; justify-content: center; }
.nx-big {
  font-family: 'Outfit', sans-serif;
  font-size: 68px; font-weight: 900;
  letter-spacing: -.04em; line-height: .88;
  margin-bottom: 20px;
}
.nx-big-plain {
  color: var(--white);
  font-family: 'Outfit', sans-serif;
  font-size: 68px; font-weight: 900;
  letter-spacing: -.04em;
}
.nx-big-grad {
  font-family: 'Outfit', sans-serif;
  font-size: 68px; font-weight: 900;
  letter-spacing: -.04em;
  background: linear-gradient(135deg, var(--violet) 0%, var(--cyan) 50%, var(--green) 100%);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
}
.nx-pipe-icon {
  font-family: 'Outfit', sans-serif;
  font-size: 11px; font-weight: 800;
  opacity: .5; min-width: 20px;
}
.nx-tagline {
  font-family: 'Space Grotesk', sans-serif;
  font-size: 15px; color: var(--dim);
  line-height: 1.6; max-width: 460px;
  font-weight: 400;
}

/* pipeline sidebar */
.nx-pipe-stack {
  display: flex; flex-direction: column; gap: 6px;
}
.nx-pipe-row {
  display: flex; align-items: center; gap: 12px;
  padding: 10px 14px;
  background: var(--card);
  border: 1px solid var(--border);
  border-left: 3px solid;
  border-radius: 0 6px 6px 0;
  font-family: 'DM Mono', monospace;
  font-size: 11px; font-weight: 400;
  transition: background .2s;
}
.nx-pipe-row:hover { background: var(--card2); }
.pr1 { border-left-color: var(--violet); color: var(--vlight); }
.pr2 { border-left-color: var(--cyan);   color: var(--clight); }
.pr3 { border-left-color: var(--amber);  color: var(--alight); }
.pr4 { border-left-color: var(--green);  color: var(--glight); }
.nx-pipe-name { flex: 1; }
.nx-pipe-tag {
  font-size: 9px; padding: 2px 7px;
  border: 1px solid currentColor;
  border-radius: 2px; opacity: .6;
  letter-spacing: .04em;
}

/* ── TAB NAV ── */
.tab-nav {
  border-bottom: 1px solid var(--border) !important;
  padding: 0 48px !important;
  background: var(--bg) !important;
  gap: 0 !important;
}
.tab-nav button {
  font-family: 'Space Grotesk', sans-serif !important;
  font-size: 12px !important;
  letter-spacing: .08em !important;
  text-transform: none !important;
  font-weight: 500 !important;
  color: var(--body3) !important;
  background: transparent !important;
  border: none !important;
  border-bottom: 2px solid transparent !important;
  padding: 16px 22px !important;
  border-radius: 0 !important;
  transition: color .2s, border-color .2s !important;
}
.tab-nav button:hover { color: var(--body2) !important; }
.tab-nav button.selected {
  color: var(--vlight) !important;
  border-bottom-color: var(--violet) !important;
}
.tabitem {
  background: var(--bg) !important;
  border: none !important;
  padding: 40px 48px !important;
}

/* ── CARDS ── */
.nx-card {
  background: var(--card);
  border: 1px solid var(--border);
  border-radius: 10px;
  padding: 24px;
  position: relative;
}
.nx-card::before {
  content: '';
  position: absolute;
  top: 0; left: 24px;
  width: 48px; height: 2px;
  background: linear-gradient(90deg, var(--violet), var(--cyan));
  border-radius: 0 0 2px 2px;
}
.nx-card-title {
  font-family: 'DM Mono', monospace;
  font-size: 9px; font-weight: 500;
  letter-spacing: .28em; text-transform: uppercase;
  color: var(--body3); margin-bottom: 20px;
  display: flex; align-items: center; gap: 10px;
}
.nx-card-title::after {
  content: ''; flex: 1; height: 1px; background: var(--border);
}

/* ── INPUTS ── */
.nx-card label > span,
.nx-card .label-wrap span {
  font-family: 'DM Mono', monospace !important;
  font-size: 9px !important;
  letter-spacing: .2em !important;
  text-transform: uppercase !important;
  color: var(--body3) !important;
  font-weight: 400 !important;
}
.nx-card input,
.nx-card textarea,
.nx-card select {
  background: var(--bg2) !important;
  border: 1px solid var(--border) !important;
  border-radius: 6px !important;
  color: var(--body) !important;
  font-family: 'Space Grotesk', sans-serif !important;
  font-size: 13px !important;
  font-weight: 400 !important;
  transition: border-color .2s, box-shadow .2s !important;
  padding: 11px 14px !important;
}
.nx-card input:focus,
.nx-card textarea:focus {
  border-color: var(--violet) !important;
  box-shadow: 0 0 0 3px rgba(124,111,255,.12) !important;
  color: var(--white) !important;
  outline: none !important;
}
.nx-card textarea::placeholder { color: var(--body3) !important; }
.nx-card .prose, .nx-card p { color: var(--body3) !important; font-size: 11px !important; }

/* ── LAUNCH BTN ── */
.nx-go button {
  width: 100% !important;
  background: linear-gradient(135deg, var(--violet) 0%, #5248e8 100%) !important;
  color: #fff !important;
  border: none !important;
  border-radius: 7px !important;
  padding: 15px 24px !important;
  font-family: 'Outfit', sans-serif !important;
  font-size: 14px !important;
  font-weight: 700 !important;
  letter-spacing: .08em !important;
  text-transform: uppercase !important;
  cursor: pointer !important;
  transition: all .25s !important;
  position: relative !important;
  overflow: hidden !important;
}
.nx-go button::after {
  content: '';
  position: absolute; inset: 0;
  background: linear-gradient(135deg, transparent 40%, rgba(255,255,255,.08));
}
.nx-go button:hover {
  transform: translateY(-2px) !important;
  box-shadow: 0 12px 40px rgba(124,111,255,.45) !important;
}
.nx-go button:active { transform: translateY(0px) !important; }

/* ── SECONDARY BTNS ── */
.nx-act button {
  background: transparent !important;
  border: 1px solid var(--border2) !important;
  border-radius: 6px !important;
  color: var(--dim) !important;
  font-family: 'DM Mono', monospace !important;
  font-size: 10px !important;
  letter-spacing: .1em !important;
  text-transform: uppercase !important;
  padding: 9px 18px !important;
  transition: all .2s !important;
}
.nx-act button:hover {
  border-color: var(--violet) !important;
  color: var(--vlight) !important;
  background: rgba(124,111,255,.07) !important;
}
.nx-del button {
  background: transparent !important;
  border: 1px solid rgba(244,63,94,.25) !important;
  border-radius: 6px !important;
  color: var(--rose) !important;
  font-family: 'DM Mono', monospace !important;
  font-size: 10px !important;
  letter-spacing: .1em !important;
  padding: 9px 18px !important;
  transition: all .2s !important;
}
.nx-del button:hover { border-color: var(--rose) !important; }

.nx-cgo button {
  width: 100% !important;
  background: linear-gradient(135deg,
    rgba(34,211,238,.85) 0%, rgba(16,217,160,.85) 100%) !important;
  color: var(--bg) !important;
  border: none !important;
  border-radius: 7px !important;
  padding: 14px !important;
  font-family: 'Outfit', sans-serif !important;
  font-size: 13px !important;
  font-weight: 700 !important;
  letter-spacing: .07em !important;
  text-transform: uppercase !important;
  transition: all .25s !important;
}
.nx-cgo button:hover {
  transform: translateY(-2px) !important;
  box-shadow: 0 10px 36px rgba(34,211,238,.35) !important;
}

/* ── TERMINAL ── */
.nx-terminal {
  background: #050510;
  border: 1px solid var(--border);
  border-radius: 10px;
  overflow: hidden;
  box-shadow: 0 20px 60px rgba(0,0,0,.5);
}
.nx-term-bar {
  display: flex; align-items: center; gap: 8px;
  padding: 12px 16px;
  background: var(--bg3);
  border-bottom: 1px solid var(--border);
}
.tb-r { width:11px;height:11px;border-radius:50%;background:#ff5f57;box-shadow:0 0 0 1px #e0443e66; }
.tb-y { width:11px;height:11px;border-radius:50%;background:#ffbd2e;box-shadow:0 0 0 1px #e09f0066; }
.tb-g { width:11px;height:11px;border-radius:50%;background:#28c840;box-shadow:0 0 0 1px #1aaa2c66; }
.tb-sep { flex:1; }
.tb-label {
  font-family: 'DM Mono', monospace;
  font-size: 10px; color: var(--body3);
  letter-spacing: .15em; text-transform: uppercase;
}

#nx-log textarea, #nx-clog textarea {
  background: #050510 !important;
  border: none !important;
  border-radius: 0 !important;
  font-family: 'DM Mono', monospace !important;
  font-size: 12px !important;
  color: #4ade80 !important;
  line-height: 1.9 !important;
  padding: 20px 20px !important;
  letter-spacing: .02em !important;
}

/* ── SECTION DIVIDER ── */
.nx-section {
  display: flex; align-items: center; gap: 14px;
  margin: 44px 0 20px;
}
.nx-section-line-l {
  width: 24px; height: 2px;
  background: linear-gradient(90deg, var(--violet), var(--cyan));
  border-radius: 2px; flex-shrink: 0;
}
.nx-section-label {
  font-family: 'DM Mono', monospace;
  font-size: 9px; font-weight: 500;
  letter-spacing: .3em; text-transform: uppercase;
  color: var(--body3); white-space: nowrap;
}
.nx-section-line-r {
  flex: 1; height: 1px; background: var(--border);
}

/* ── REPORT ── */
.nx-report-box {
  background: var(--card);
  border: 1px solid var(--border);
  border-radius: 10px;
  padding: 40px 44px;
}

#nx-report {
  color: var(--body2) !important;
  font-family: 'Space Grotesk', sans-serif !important;
  font-size: 15px !important;
  line-height: 1.9 !important;
}
#nx-report h1 {
  font-family: 'Outfit', sans-serif !important;
  font-size: 30px !important; font-weight: 900 !important;
  color: var(--white) !important;
  letter-spacing: -.03em !important;
  margin-bottom: 28px !important;
  padding-bottom: 18px !important;
  border-bottom: 1px solid var(--border) !important;
}
#nx-report h2 {
  font-family: 'Outfit', sans-serif !important;
  font-size: 18px !important; font-weight: 700 !important;
  color: var(--vlight) !important;
  margin: 32px 0 12px !important;
  display: flex !important; align-items: center !important; gap: 10px !important;
}
#nx-report h2::before {
  content: '';
  display: inline-block; width: 3px; height: 18px;
  background: linear-gradient(180deg, var(--violet), var(--cyan));
  border-radius: 2px; flex-shrink: 0;
}
#nx-report h3 {
  font-size: 15px !important; font-weight: 600 !important;
  color: var(--body) !important; margin: 20px 0 8px !important;
}
#nx-report p { margin-bottom: 14px !important; }
#nx-report strong { color: var(--white) !important; font-weight: 600 !important; }
#nx-report em { color: var(--clight) !important; font-style: italic !important; }
#nx-report a { color: var(--vlight) !important; text-decoration: none !important; border-bottom: 1px solid rgba(168,154,255,.3) !important; transition: border-color .2s !important; }
#nx-report a:hover { border-bottom-color: var(--vlight) !important; }
#nx-report ul, #nx-report ol { padding-left: 22px !important; margin: 10px 0 !important; }
#nx-report li { margin: 5px 0 !important; color: var(--body2) !important; }
#nx-report blockquote {
  border-left: 3px solid var(--violet) !important;
  padding: 14px 20px !important;
  background: var(--bg2) !important;
  border-radius: 0 8px 8px 0 !important;
  margin: 20px 0 !important; color: var(--dim) !important;
  font-style: italic !important;
}
#nx-report table {
  border-collapse: collapse !important; width: 100% !important;
  font-size: 13px !important; margin: 20px 0 !important;
  font-family: 'DM Mono', monospace !important;
}
#nx-report th {
  background: var(--bg3) !important; color: var(--vlight) !important;
  padding: 10px 16px !important; border: 1px solid var(--border) !important;
  font-weight: 500 !important; letter-spacing: .04em !important; text-align: left !important;
}
#nx-report td {
  border: 1px solid var(--border) !important;
  padding: 9px 16px !important; color: var(--body2) !important;
}
#nx-report tr:hover td { background: var(--card2) !important; }
#nx-report code {
  background: var(--bg3) !important; padding: 2px 8px !important;
  border-radius: 4px !important;
  font-family: 'DM Mono', monospace !important;
  font-size: 12px !important; color: var(--amber) !important;
}
#nx-report hr {
  border: none !important;
  border-top: 1px solid var(--border) !important;
  margin: 28px 0 !important;
}

/* comparison + individual */
#nx-crep, #nx-tr1, #nx-tr2, #nx-tr3 {
  color: var(--body2) !important;
  font-family: 'Space Grotesk', sans-serif !important;
  font-size: 14px !important; line-height: 1.85 !important;
}
#nx-crep h1, #nx-tr1 h1, #nx-tr2 h1, #nx-tr3 h1 {
  font-family: 'Outfit', sans-serif !important;
  font-size: 24px !important; font-weight: 800 !important;
  color: var(--white) !important; margin-bottom: 20px !important;
}
#nx-crep h2, #nx-tr1 h2, #nx-tr2 h2, #nx-tr3 h2 {
  font-family: 'Outfit', sans-serif !important;
  font-size: 16px !important; font-weight: 700 !important;
  color: var(--clight) !important; margin: 20px 0 8px !important;
}

/* ── SIDEBAR STEPS ── */
.nx-steps { margin-top: 20px; padding-top: 18px; border-top: 1px solid var(--border); }
.nx-step {
  display: flex; align-items: flex-start; gap: 14px;
  padding: 11px 0; border-bottom: 1px solid var(--border);
}
.nx-step:last-of-type { border-bottom: none; }
.nx-snum {
  font-family: 'Outfit', sans-serif;
  font-size: 11px; font-weight: 900; color: var(--violet);
  width: 20px; flex-shrink: 0; padding-top: 1px;
}
.nx-sname {
  font-family: 'Space Grotesk', sans-serif;
  font-size: 13px; font-weight: 600; color: var(--body);
  margin-bottom: 2px;
}
.nx-sdesc { font-size: 11px; color: var(--body3); line-height: 1.5; }

.nx-stats {
  display: grid; grid-template-columns: repeat(4,1fr);
  gap: 1px; background: var(--border);
  border: 1px solid var(--border); border-radius: 8px;
  overflow: hidden; margin-top: 18px;
}
.nx-stat {
  background: var(--bg2); padding: 12px 6px; text-align: center;
}
.nx-stat-v {
  font-family: 'Outfit', sans-serif;
  font-size: 22px; font-weight: 900; color: var(--vlight); display: block;
}
.nx-stat-k {
  font-family: 'DM Mono', monospace;
  font-size: 8px; letter-spacing: .16em; text-transform: uppercase;
  color: var(--body3); display: block; margin-top: 3px;
}

/* ── HISTORY TABLE ── */
.nx-tbl table {
  font-family: 'DM Mono', monospace !important;
  font-size: 11px !important;
  border-collapse: collapse !important; width: 100% !important;
}
.nx-tbl th {
  background: var(--bg3) !important; color: var(--vlight) !important;
  padding: 10px 16px !important; border: 1px solid var(--border) !important;
  font-weight: 500 !important; letter-spacing: .06em !important; text-align: left !important;
}
.nx-tbl td {
  border: 1px solid var(--border) !important;
  padding: 8px 16px !important; color: var(--body2) !important;
}
.nx-tbl tr:hover td { background: var(--card2) !important; }

/* ── EXAMPLES ── */
.nx-ex {
  font-family: 'DM Mono', monospace;
  font-size: 9px; letter-spacing: .22em; text-transform: uppercase;
  color: var(--body3); margin: 32px 0 12px;
  display: flex; align-items: center; gap: 10px;
}
.nx-ex::after { content: ''; flex: 1; height: 1px; background: var(--border); }

footer { display: none !important; }
.gradio-container .prose { color: var(--body2) !important; }
"""


# ─── Research pipeline ─────────────────────────────────────────────────────────

def do_research(topic, depth):
    """
    Yields 6 values on each iteration:
        progress_log, report_out, act_row (gr.update), fc_out, cred_out, map_img
    The PDF download (pdf_dl) is populated separately via pdf_btn.click.
    """
    if not topic.strip():
        yield (
            "  ERROR: topic cannot be empty", "",
            gr.update(visible=False), "", "", None,
        )
        return

    log, res = [], {"state": None, "done": False, "error": None}
    dk = "quick" if "quick" in depth.lower() else "deep"

    def cb(agent, msg):
        icon = ICONS.get(agent, "▷")
        ts   = datetime.now().strftime("%H:%M:%S")
        log.append(f"  {ts}  {icon}  {agent.upper():<14}  {msg}")

    def _run():
        try:    res["state"] = run_pipeline(topic, dk, cb)
        except Exception as e: res["error"] = str(e)
        finally: res["done"] = True

    threading.Thread(target=_run, daemon=True).start()

    prev = 0
    while not res["done"]:
        if len(log) > prev:
            prev = len(log)
            yield (
                "\n".join(log), "",
                gr.update(visible=False), "", "", None,
            )
        time.sleep(0.4)

    log_txt = "\n".join(log)
    if res["error"]:
        yield (
            log_txt + f"\n\n  ERROR: {res['error']}", "",
            gr.update(visible=False), "", "", None,
        )
        return

    state   = res["state"]
    report  = state.get("final_report", "")
    sources = state.get("sources", [])
    fc_res  = state.get("fact_check_results", [])
    themes  = state.get("key_themes", [])

    try:
        save_report(topic=topic, depth=dk, final_report=report,
                    sources=sources, fact_check_results=fc_res,
                    iteration_count=state.get("iteration_count", 0))
    except Exception as e:
        print(f"History save: {e}")

    fc_html   = render_factcheck_dashboard(fc_res, topic)
    cred_html = render_credibility_html(score_sources(topic, sources))
    map_path  = generate_mindmap(topic, themes, sources, fc_res)

    yield (
        log_txt, report,
        gr.update(visible=True),
        fc_html, cred_html,
        map_path,   # gr.Image accepts a filepath string or None directly
    )


# ─── Comparison ───────────────────────────────────────────────────────────────

def do_comparison(t1, t2, t3, depth):
    topics = [t for t in [t1, t2, t3] if t.strip()]
    if len(topics) < 2:
        yield "  ERROR: need at least 2 topics", "", "", "", ""
        return

    log, res = [], {"states": None, "comp": "", "done": False, "error": None}
    dk = "quick" if "quick" in depth.lower() else "deep"

    def cb(agent, msg):
        icon = ICONS.get(agent, "▷")
        ts   = datetime.now().strftime("%H:%M:%S")
        log.append(f"  {ts}  {icon}  {agent.upper():<14}  {msg}")

    def _run():
        try:
            states = run_parallel_research(topics, dk, cb)
            comp   = generate_comparison_report(states, topics, cb)
            res["states"] = states
            res["comp"]   = comp
        except Exception as e: res["error"] = str(e)
        finally: res["done"] = True

    threading.Thread(target=_run, daemon=True).start()

    prev = 0
    while not res["done"]:
        if len(log) > prev:
            prev = len(log)
            yield "\n".join(log), "", "", "", ""
        time.sleep(0.4)

    log_txt = "\n".join(log)
    if res.get("error"):
        yield log_txt + f"\n\n  ERROR: {res['error']}", "", "", "", ""
        return

    states  = res["states"] or []
    reports = [s.get("final_report", "") for s in states]
    while len(reports) < 3: reports.append("")

    yield log_txt, reports[0], reports[1], reports[2], res["comp"]


# ─── History helpers ───────────────────────────────────────────────────────────

def refresh_hist():
    recs = load_all()
    rows = format_history_for_display(recs)
    status = (f"  {len(rows)} report(s) saved"
              if rows else "  No reports yet — run your first pipeline!")
    return rows, status


def hist_select(evt: gr.SelectData):
    """Load and display a report when a row is clicked in the history table."""
    try:
        recs   = load_all()
        rec    = recs[evt.index[0]]
        report = rec.get("final_report", "")
        fc     = render_factcheck_dashboard(
                     rec.get("fact_check_results", []), rec.get("topic", ""))
        cred   = render_credibility_html(
                     score_sources(rec.get("topic", ""), rec.get("sources", [])))
        return report, fc, cred
    except Exception as e:
        return f"Error loading report: {e}", "", ""


def hist_delete_selected(evt: gr.SelectData):
    """Delete the selected row, then refresh the table.

    BUG FIX: the original code wired hist_del (a Button) to a function that
    expected gr.SelectData from a .select() event.  A Button.click() passes no
    row information, so the function always crashed with a TypeError.

    Fix: use hist_tbl.select to capture the row index into a gr.State, then
    let the delete button read that state instead.
    """
    try:
        recs = load_all()
        delete_report(recs[evt.index[0]]["id"])
    except Exception:
        pass
    return refresh_hist()


def do_pdf(report_md, topic):
    if not report_md or "will appear here" in report_md:
        return gr.update(visible=False)
    return gr.update(value=make_pdf(report_md, topic), visible=True)


# ─── BUILD UI ─────────────────────────────────────────────────────────────────

with gr.Blocks(
    css=CSS,
    title="NEXUS — Research Intelligence",
    theme=gr.themes.Base(
        primary_hue="violet", neutral_hue="slate",
        font=gr.themes.GoogleFont("Space Grotesk"),
    ),
) as demo:

    topic_state      = gr.State("")
    # Tracks which row the user last clicked in the history table so the
    # delete button can act on the correct record (fixes the SelectData crash).
    selected_row_idx = gr.State(-1)

    # ══════════════════════════════════════════════════════════════════
    # HEADER
    # ══════════════════════════════════════════════════════════════════
    gr.HTML("""
    <div class="nx-header">
      <div class="nx-hgrid">
        <div class="nx-left">
          <div class="nx-eye">
            <div class="nx-live"></div>
            <span class="nx-chip">Multi-Agent System</span>
            <span class="nx-ver">v2.0 &middot; NEXUS</span>
          </div>
          <div class="nx-big">
            <span class="nx-big-plain">Research</span>
          </div>
          <div class="nx-big">  
            <span class="nx-big-grad">Intelligence</span>
          </div>
          <p class="nx-tagline">
            Autonomous 4-agent pipeline. Finds sources, writes structured
            reports, verifies every claim, and self-corrects disputed facts.
          </p>
        </div>
        <div class="nx-pipe-stack">
          <div class="nx-pipe-row pr1">
            <span class="nx-pipe-icon">01</span>
            <span class="nx-pipe-name">Researcher</span>
            <span class="nx-pipe-tag">web + arXiv</span>
          </div>
          <div class="nx-pipe-row pr2">
            <span class="nx-pipe-icon">02</span>
            <span class="nx-pipe-name">Writer</span>
            <span class="nx-pipe-tag">500-800 words</span>
          </div>
          <div class="nx-pipe-row pr3">
            <span class="nx-pipe-icon">03</span>
            <span class="nx-pipe-name">Fact Checker</span>
            <span class="nx-pipe-tag">5 claims</span>
          </div>
          <div class="nx-pipe-row pr4">
            <span class="nx-pipe-icon">04</span>
            <span class="nx-pipe-name">Editor</span>
            <span class="nx-pipe-tag">final output</span>
          </div>
        </div>
      </div>
    </div>
    """)

    # ══════════════════════════════════════════════════════════════════
    # TABS
    # ══════════════════════════════════════════════════════════════════
    with gr.Tabs():

        # ── TAB 1 ── RESEARCH (full single-page) ──────────────────────
        with gr.Tab("⬡  Research"):

            # Input row
            with gr.Row(equal_height=False):
                # Sidebar card
                with gr.Column(scale=0, min_width=300, elem_classes=["nx-card"]):
                    gr.HTML('<div class="nx-card-title">Mission Parameters</div>')
                    topic_in = gr.Textbox(
                        label="Research Topic",
                        placeholder="e.g. Mixture of Experts in LLMs",
                        lines=3, elem_id="topic_in")
                    depth_in = gr.Dropdown(
                        label="Research Depth",
                        choices=["Quick Research", "Deep Research"],
                        value="Quick Research",
                        info="Quick ~2 min  |  Deep ~5 min")
                    with gr.Row(elem_classes=["nx-go"]):
                        go_btn = gr.Button("⬡ Launch Pipeline", size="lg")

                    gr.HTML("""
                    <div class="nx-steps">
                      <div class="nx-step">
                        <div class="nx-snum">01</div>
                        <div>
                          <div class="nx-sname">Researcher</div>
                          <div class="nx-sdesc">Web search + ArXiv &middot; 5&ndash;7 sources synthesised by LLM</div>
                        </div>
                      </div>
                      <div class="nx-step">
                        <div class="nx-snum">02</div>
                        <div>
                          <div class="nx-sname">Writer</div>
                          <div class="nx-sdesc">Structured 500&ndash;800 word report &middot; 5 sections</div>
                        </div>
                      </div>
                      <div class="nx-step">
                        <div class="nx-snum">03</div>
                        <div>
                          <div class="nx-sname">Fact Checker</div>
                          <div class="nx-sdesc">Extracts &amp; verifies top 5 claims via live search</div>
                        </div>
                      </div>
                      <div class="nx-step">
                        <div class="nx-snum">04</div>
                        <div>
                          <div class="nx-sname">Editor</div>
                          <div class="nx-sdesc">Fixes disputes &middot; polishes prose &middot; adds citations</div>
                        </div>
                      </div>
                    </div>
                    <div class="nx-stats">
                      <div class="nx-stat">
                        <span class="nx-stat-v">4</span>
                        <span class="nx-stat-k">Agents</span>
                      </div>
                      <div class="nx-stat">
                        <span class="nx-stat-v">7</span>
                        <span class="nx-stat-k">Sources</span>
                      </div>
                      <div class="nx-stat">
                        <span class="nx-stat-v">5</span>
                        <span class="nx-stat-k">Claims</span>
                      </div>
                      <div class="nx-stat">
                        <span class="nx-stat-v">&le;2</span>
                        <span class="nx-stat-k">Loops</span>
                      </div>
                    </div>
                    """)

                # Terminal
                with gr.Column(scale=1):
                    gr.HTML("""
                    <div class="nx-terminal">
                      <div class="nx-term-bar">
                        <div class="tb-r"></div>
                        <div class="tb-y"></div>
                        <div class="tb-g"></div>
                        <div class="tb-sep"></div>
                        <span class="tb-label">Agent Stream</span>
                      </div>""")
                    progress_log = gr.Textbox(
                        label="", lines=13, max_lines=13,
                        interactive=False, elem_id="nx-log",
                        placeholder=(
                            "  Awaiting pipeline launch...\n\n"
                            "  ⬡  RESEARCHER      web_search · arxiv_search · LLM synthesis\n"
                            "  ⬢  WRITER          5-section structured report generation\n"
                            "  ⬣  FACT_CHECKER    claim extraction · live web verification\n"
                            "  ◆  EDITOR          fix disputes · polish prose · citations"
                        ))
                    gr.HTML("</div>")  # close nx-terminal

            # ── Report ──────────────────────────────────────────────
            gr.HTML("""
            <div class="nx-section">
              <div class="nx-section-line-l"></div>
              <span class="nx-section-label">Generated Report</span>
              <div class="nx-section-line-r"></div>
            </div>""")

            with gr.Column(elem_classes=["nx-report-box"]):
                report_out = gr.Markdown(
                    value="*Your research report will appear here after the pipeline completes...*",
                    elem_id="nx-report")

            # act_row is hidden until the pipeline succeeds
            with gr.Row(visible=False, elem_classes=["nx-act"]) as act_row:
                pdf_btn  = gr.Button("↓  Export PDF",    size="sm")
                copy_btn = gr.Button("⧉  Copy Markdown", size="sm")
            pdf_dl = gr.File(label="", visible=False)

            # ── Fact-Check Dashboard ────────────────────────────────
            gr.HTML("""
            <div class="nx-section">
              <div class="nx-section-line-l"></div>
              <span class="nx-section-label">Fact-Check Dashboard</span>
              <div class="nx-section-line-r"></div>
            </div>""")
            fc_out = gr.HTML(render_factcheck_dashboard([], ""))

            # ── Source Credibility ──────────────────────────────────
            gr.HTML("""
            <div class="nx-section">
              <div class="nx-section-line-l"></div>
              <span class="nx-section-label">Source Credibility Analysis</span>
              <div class="nx-section-line-r"></div>
            </div>""")
            cred_out = gr.HTML(render_credibility_html([]))

            # ── Mind Map ───────────────────────────────────────────
            gr.HTML("""
            <div class="nx-section">
              <div class="nx-section-line-l"></div>
              <span class="nx-section-label">Research Mind Map</span>
              <div class="nx-section-line-r"></div>
            </div>""")
            map_img = gr.Image(
                label="Concept Map", type="filepath",
                show_download_button=True, height=460)

            # ── Examples ───────────────────────────────────────────
            gr.HTML('<div class="nx-ex">Example Topics</div>')
            gr.Examples(examples=[
                ["Mixture of Experts in Large Language Models", "Quick Research"],
                ["AI regulation policies in 2025",              "Deep Research"],
                ["Drug discovery using artificial intelligence", "Quick Research"],
                ["Quantum computing in cryptography",            "Quick Research"],
                ["Autonomous vehicle safety challenges",          "Deep Research"],
            ], inputs=[topic_in, depth_in], label="")

        # ── TAB 2 ── COMPARE ──────────────────────────────────────────
        with gr.Tab("⇄  Compare"):
            gr.HTML("""
            <p style="font-family:'DM Mono',monospace;font-size:11px;
                      color:#404070;padding:4px 0 24px;letter-spacing:.05em;line-height:1.7;">
              Research 2&ndash;3 topics simultaneously across parallel pipelines,
              then get an LLM-synthesised comparison report.
            </p>""")

            with gr.Row():
                with gr.Column(scale=1, elem_classes=["nx-card"]):
                    gr.HTML('<div class="nx-card-title">Topics to Compare</div>')
                    ct1 = gr.Textbox(label="Topic 1  &middot;  required",
                                     placeholder="e.g. GPT-4 architecture")
                    ct2 = gr.Textbox(label="Topic 2  &middot;  required",
                                     placeholder="e.g. Gemini 1.5 architecture")
                    ct3 = gr.Textbox(label="Topic 3  &middot;  optional",
                                     placeholder="e.g. Claude 3 architecture")
                    cd  = gr.Dropdown(label="Depth",
                        choices=["Quick Research", "Deep Research"],
                        value="Quick Research")
                    with gr.Row(elem_classes=["nx-cgo"]):
                        cmp_btn = gr.Button("⇄  Launch Parallel Research", size="lg")

                with gr.Column(scale=2):
                    gr.HTML("""
                    <div class="nx-terminal">
                      <div class="nx-term-bar">
                        <div class="tb-r"></div>
                        <div class="tb-y"></div>
                        <div class="tb-g"></div>
                        <div class="tb-sep"></div>
                        <span class="tb-label">Parallel Streams</span>
                      </div>""")
                    cmp_log = gr.Textbox(
                        label="", lines=11, max_lines=11,
                        interactive=False, elem_id="nx-clog",
                        placeholder="  Parallel agent logs will appear here...")
                    gr.HTML("</div>")

            gr.HTML("""
            <div class="nx-section">
              <div class="nx-section-line-l"></div>
              <span class="nx-section-label">Comparison Report</span>
              <div class="nx-section-line-r"></div>
            </div>""")
            with gr.Column(elem_classes=["nx-report-box"]):
                cmp_rep = gr.Markdown(
                    value="*Run a comparison to see the synthesised analysis...*",
                    elem_id="nx-crep")

            gr.HTML("""
            <div class="nx-section">
              <div class="nx-section-line-l"></div>
              <span class="nx-section-label">Individual Reports</span>
              <div class="nx-section-line-r"></div>
            </div>""")
            with gr.Tabs():
                with gr.Tab("Topic 1"): t1r = gr.Markdown("*Awaiting...*", elem_id="nx-tr1")
                with gr.Tab("Topic 2"): t2r = gr.Markdown("*Awaiting...*", elem_id="nx-tr2")
                with gr.Tab("Topic 3"): t3r = gr.Markdown("*Awaiting...*", elem_id="nx-tr3")

        # ── TAB 3 ── LIBRARY ──────────────────────────────────────────
        with gr.Tab("▦  Library"):
            gr.HTML("""
            <p style="font-family:'DM Mono',monospace;font-size:11px;
                      color:#404070;padding:4px 0 24px;letter-spacing:.05em;line-height:1.7;">
              All pipeline runs are auto-saved. Click any row to reload
              the full report, fact-check dashboard, and credibility analysis.
              Select a row first, then press Delete to remove it.
            </p>""")

            with gr.Row():
                with gr.Column(elem_classes=["nx-act"]):
                    hist_ref = gr.Button("↻  Refresh", size="sm")
                with gr.Column(elem_classes=["nx-del"]):
                    hist_del = gr.Button("✕  Delete Selected", size="sm")

            hist_status = gr.Markdown("  Loading library...")
            hist_tbl    = gr.Dataframe(
                headers=HISTORY_COLUMNS, datatype=["str"] * 7,
                interactive=False, wrap=True, elem_classes=["nx-tbl"])

            gr.HTML("""
            <div class="nx-section">
              <div class="nx-section-line-l"></div>
              <span class="nx-section-label">Selected Report</span>
              <div class="nx-section-line-r"></div>
            </div>""")
            with gr.Column(elem_classes=["nx-report-box"]):
                hist_rep = gr.Markdown(
                    "*Click a row above to view the report.*",
                    elem_id="nx-report")

            gr.HTML("""
            <div class="nx-section">
              <div class="nx-section-line-l"></div>
              <span class="nx-section-label">Fact-Check</span>
              <div class="nx-section-line-r"></div>
            </div>""")
            hist_fc = gr.HTML("")

            gr.HTML("""
            <div class="nx-section">
              <div class="nx-section-line-l"></div>
              <span class="nx-section-label">Credibility</span>
              <div class="nx-section-line-r"></div>
            </div>""")
            hist_cred = gr.HTML("")


    # ── EVENT WIRING ──────────────────────────────────────────────────

    # BUG FIX: do_research now yields 6 outputs, not 7.
    # The pdf_dl file component is populated separately by pdf_btn.click —
    # do_research should not write to it (it has no file path to give mid-stream).
    # act_row visibility is the 3rd yield value; pdf_dl is excluded here.
    go_btn.click(
        fn=lambda t, _d: t,
        inputs=[topic_in, depth_in],
        outputs=[topic_state],
    ).then(
        fn=do_research,
        inputs=[topic_in, depth_in],
        outputs=[progress_log, report_out, act_row, fc_out, cred_out, map_img],
        show_progress="hidden",
    )

    pdf_btn.click(fn=do_pdf, inputs=[report_out, topic_state], outputs=[pdf_dl])

    # BUG FIX: copy_btn used `js=` which in current Gradio must be passed as
    # the `js` parameter on a separate `.click()` call (or via gr.Button's js
    # argument). Using fn=None with js copies the markdown to the clipboard
    # without needing an outputs list — passing report_out as output caused
    # Gradio to attempt a Python-side update that wiped the component.
    copy_btn.click(
        fn=None,
        inputs=[report_out],
        js="(r) => { navigator.clipboard.writeText(r); }",
        outputs=[],
    )

    cmp_btn.click(
        fn=do_comparison,
        inputs=[ct1, ct2, ct3, cd],
        outputs=[cmp_log, t1r, t2r, t3r, cmp_rep],
        show_progress="hidden",
    )

    hist_ref.click(fn=refresh_hist, outputs=[hist_tbl, hist_status])
    demo.load(fn=refresh_hist,      outputs=[hist_tbl, hist_status])

    # BUG FIX: hist_tbl.select captures the clicked row and stores its index,
    # then also loads the report for display.
    def _on_row_select(evt: gr.SelectData):
        report, fc, cred = hist_select(evt)
        return evt.index[0], report, fc, cred

    hist_tbl.select(
        fn=_on_row_select,
        outputs=[selected_row_idx, hist_rep, hist_fc, hist_cred],
    )

    # BUG FIX: the delete button now reads from selected_row_idx (gr.State)
    # instead of trying to receive gr.SelectData from a Button click event,
    # which is impossible and caused a TypeError crash every time.
    def _on_delete_click(row_idx: int):
        if row_idx < 0:
            # Nothing selected yet — just refresh without deleting.
            return refresh_hist()
        try:
            recs = load_all()
            if row_idx < len(recs):
                delete_report(recs[row_idx]["id"])
        except Exception:
            pass
        return refresh_hist()

    hist_del.click(
        fn=_on_delete_click,
        inputs=[selected_row_idx],
        outputs=[hist_tbl, hist_status],
    )


# ─── LAUNCH ───────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    demo.launch(
        server_name="0.0.0.0",
        server_port=int(os.getenv("GRADIO_PORT", 7860)),
        share=False,
        show_error=True,
    )