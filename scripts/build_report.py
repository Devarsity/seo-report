#!/usr/bin/env python3
"""
build_report.py — Render an agency-grade, self-contained HTML SEO audit report.

Takes the measured audit JSON (audit.py) plus an "insights" JSON the model writes
(the judgement layer) and produces one standalone, visualization-heavy HTML
report in the style of a professional client deliverable:

  - navy sidebar with glyph navigation + audit subject
  - gradient hero with scope pills and a print / save-PDF button
  - numbered section kickers (01 · ... , 02 · ...)
  - executive summary: stat cards with accent bars, a "top signals" list,
    an audit-scope card and an interpretation caveat
  - Lighthouse scorecard: conic-gradient rings + comparison bars + interpretation
  - Core Web Vitals: metric cards with meters, thresholds and definitions,
    a field pass-criteria flow, a remediation sequence and an evidence caveat
  - SEO checklist: searchable/filterable table with recorded status + the user's
    solution + an SEO interpretation
  - Failed-check deep dives: per-item cards with "what it means", the workbook
    solution, an honest evaluation of it, and a recommended SEO resolution
  - other findings that need context
  - link audit: stat cards, error-mix bars, a triage workflow, and searchable
    broken-link and redirect registers
  - action roadmap: Now / Next horizons + an acceptance-criteria table
  - evidence gallery: embedded Lighthouse + annotated page screenshots
  - method, definitions and limitations

Everything is inlined (images become data URIs, CSS/JS are embedded) so the
single .html opens offline and prints cleanly. The report keeps a strict
evidence-vs-recommendation separation and never invents data for missing inputs.

Running with only --data works; the richer the insights file, the richer the
report. See references/insights-schema.md for the full schema.

Usage:
    python build_report.py --data audit.json --insights insights.json -o report.html
"""

import argparse
import base64
import datetime as dt
import html
import json
import mimetypes
import os


# ---------------------------------------------------------------------------
# Basics
# ---------------------------------------------------------------------------
def esc(s):
    return html.escape(str(s if s is not None else ""))


def jdump(obj):
    """JSON for embedding in a <script>; safe for </script> injection."""
    return json.dumps(obj).replace("</", "<\\/")


def band_of(v, good=80, warn=50):
    if v is None:
        return "neutral"
    return "good" if v >= good else ("warn" if v >= warn else "bad")


# Lighthouse colour bands: green 90-100, orange 50-89, red 0-49
def lh_band(v):
    if v is None:
        return "neutral"
    return "good" if v >= 90 else ("warn" if v >= 50 else "bad")


BAND_FILL = {"good": "#16a34a", "warn": "#f59e0b", "bad": "#dc4444", "neutral": "#94a3b8"}
BAND_RING = {"good": "#16a34a", "warn": "#f59e0b", "bad": "#dc4444", "neutral": "#94a3b8"}


def data_uri(path):
    if not path or not os.path.exists(path):
        return None
    if os.path.getsize(path) > 14 * 1024 * 1024:
        return None
    mime = mimetypes.guess_type(path)[0] or "image/png"
    with open(path, "rb") as f:
        return f"data:{mime};base64," + base64.b64encode(f.read()).decode()


STATUS_NORM = {"pass": "pass", "passed": "pass", "ok": "pass", "yes": "pass", "good": "pass",
               "pass (1)": "pass", "positive": "pass",
               "fail": "fail", "failed": "fail", "no": "fail", "error": "fail",
               "warn": "warn", "warning": "warn", "review": "warn", "partial": "warn",
               "not recorded": "other", "n/a": "other", "": "other"}


def norm_status(s):
    key = str(s).strip().lower()
    if key in STATUS_NORM:
        return STATUS_NORM[key]
    if "fail" in key:
        return "fail"
    if "pass" in key:
        return "pass"
    if any(w in key for w in ("warn", "review", "improve", "partial")):
        return "warn"
    return "other"


STATUS_BADGE = {"pass": ("b-pass", "Pass"), "fail": ("b-fail", "Fail"),
                "warn": ("b-check", "Review"), "other": ("b-info", "Note")}
IMPACT_CLASS = {"high": "", "medium": "med", "low": "low", "p1": "", "p2": "med", "p3": "low"}


# ---------------------------------------------------------------------------
# CSS  (plain string — literal braces, never an f-string)
# ---------------------------------------------------------------------------
CSS = """
:root{--navy:#12243a;--ink:#203047;--muted:#63748a;--line:#dce5ef;--bg:#f3f6fa;
--white:#fff;--blue:#2563eb;--teal:#0f9d91;--green:#16865b;--amber:#c77a08;
--red:#d64545;--purple:#7257d5;--shadow:0 10px 30px rgba(25,48,78,.08)}
*{box-sizing:border-box}html{scroll-behavior:smooth}
body{margin:0;background:var(--bg);color:var(--ink);
font:15px/1.55 Inter,-apple-system,BlinkMacSystemFont,"Segoe UI",Arial,sans-serif}
a{color:#1d5cc6;overflow-wrap:anywhere}
.shell{display:grid;grid-template-columns:250px minmax(0,1fr);min-height:100vh}
.side{background:var(--navy);color:#e9f0fa;padding:28px 18px;position:sticky;top:0;height:100vh;overflow:auto}
.brand{font-weight:800;font-size:16px;letter-spacing:.04em;margin:0 10px 5px}
.brand small{display:block;color:#9eb3cd;font-weight:500;letter-spacing:0;font-size:12px}
.side .label{font-size:10px;text-transform:uppercase;letter-spacing:.15em;color:#8ea4c0;margin:28px 10px 8px}
.side nav a{display:flex;text-decoration:none;color:#d7e3f3;padding:9px 11px;border-radius:9px;margin:2px 0;font-size:13px;gap:9px}
.side nav a:hover{background:#233b57;color:#fff}
.subject{font-size:12px;line-height:1.8;padding:0 10px;color:#b8c9dc}
.subject span{color:#829bb8}
.main{min-width:0}
.topbar{display:flex;justify-content:space-between;align-items:center;padding:18px 34px;background:#fff;border-bottom:1px solid var(--line);font-size:12px;color:var(--muted)}
.topbar strong{color:var(--ink)}
.content{max-width:1500px;margin:auto;padding:28px 34px 60px}
.hero{background:linear-gradient(120deg,#11233a,#1d4970 68%,#176b78);color:white;border-radius:22px;padding:38px 40px;position:relative;overflow:hidden;box-shadow:var(--shadow)}
.hero:after{content:"";position:absolute;width:350px;height:350px;border:1px solid #ffffff20;border-radius:50%;right:-90px;top:-140px;box-shadow:0 0 0 35px #ffffff08,0 0 0 75px #ffffff06}
.eyebrow{text-transform:uppercase;letter-spacing:.16em;font-size:11px;font-weight:800;color:#a9d7f0}
.hero h1{font-size:clamp(27px,3vw,42px);line-height:1.12;margin:12px 0;max-width:850px}
.hero p{color:#d7e7f5;max-width:850px;margin:0 0 20px}
.hero-meta{display:flex;flex-wrap:wrap;gap:8px}
.pill{display:inline-flex;border:1px solid #ffffff3d;background:#ffffff12;border-radius:30px;padding:6px 11px;font-size:12px;color:#fff}
.section{margin-top:32px;scroll-margin-top:20px}
.section-head{display:flex;align-items:end;justify-content:space-between;gap:20px;margin-bottom:16px}
.section-head h2{font-size:24px;margin:0;color:#162c45;letter-spacing:-.03em}
.section-head p{margin:4px 0 0;color:var(--muted);max-width:850px}
.kicker{color:var(--blue);text-transform:uppercase;letter-spacing:.12em;font-weight:800;font-size:10px;margin-bottom:5px}
.grid{display:grid;gap:16px}
.stats{grid-template-columns:repeat(4,minmax(0,1fr))}
.card{background:white;border:1px solid var(--line);border-radius:16px;padding:20px;box-shadow:var(--shadow);min-width:0}
.stat{position:relative;overflow:hidden}
.stat .name{color:var(--muted);font-size:12px;font-weight:700}
.stat .value{font-size:34px;line-height:1.15;font-weight:800;letter-spacing:-.04em;margin:8px 0 4px}
.stat .value small{font-size:15px;color:#718096;font-weight:700}
.stat .note{font-size:12px;color:var(--muted)}
.accent{height:4px;border-radius:8px;margin-top:15px;background:#e8eef5}
.accent span{display:block;height:100%;border-radius:8px}
.two{grid-template-columns:1.1fr .9fr}.three{grid-template-columns:repeat(3,minmax(0,1fr))}
.four{grid-template-columns:repeat(4,minmax(0,1fr))}
.score-row{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:14px}
.score-card{display:flex;align-items:center;gap:14px}
.ring{width:74px;height:74px;flex:0 0 74px;position:relative;display:grid;place-items:center;border-radius:50%;background:conic-gradient(var(--c) calc(var(--score)*1%),#e8edf4 0)}
.ring:before{content:"";position:absolute;inset:7px;background:white;border-radius:50%}
.ring b{z-index:1;font-size:20px}
.score-card strong{display:block;font-size:13px}.score-card small{display:block;color:var(--muted);font-size:11px}
.good{color:var(--green)}.warn{color:var(--amber)}.bad{color:var(--red)}.neutral{color:var(--muted)}
.barlist{display:grid;gap:14px}
.barline{display:grid;grid-template-columns:150px 1fr 52px;align-items:center;gap:12px;font-size:12px}
.track{height:12px;background:#edf2f7;border-radius:20px;overflow:hidden}
.fill{height:100%;border-radius:20px}
.callout{border-left:4px solid var(--blue);background:#eff6ff;padding:14px 16px;border-radius:0 12px 12px 0;color:#23456e;font-size:13px}
.callout.red{border-color:var(--red);background:#fff1f1;color:#7c2d2d}
.callout.amber{border-color:var(--amber);background:#fff8e8;color:#75490c}
.callout.green{border-color:var(--green);background:#edfbf4;color:#175b3d}
.callout ol,.callout ul{margin:6px 0 0;padding-left:18px}
.table-wrap{overflow:auto;border:1px solid var(--line);border-radius:12px;background:#fff}
table{border-collapse:collapse;width:100%;font-size:12px;min-width:720px}
th{background:#f0f4f9;color:#465971;text-align:left;font-size:10px;text-transform:uppercase;letter-spacing:.07em;padding:12px;border-bottom:1px solid var(--line)}
td{padding:11px 12px;border-bottom:1px solid #edf1f6;vertical-align:top}
tr:last-child td{border-bottom:0}tbody tr:hover{background:#f8fbff}
.badge{display:inline-flex;align-items:center;border-radius:30px;padding:3px 8px;font-weight:800;font-size:10px;white-space:nowrap}
.b-pass{background:#e8f8ef;color:#16754c}.b-fail{background:#fff0f0;color:#b82c2c}
.b-check{background:#fff6df;color:#8a5a08}.b-info{background:#edf4ff;color:#245bb3}
.definition{background:#f8fafc;border:1px solid var(--line);border-radius:12px;padding:15px}
.definition strong{display:block;margin-bottom:4px}.definition p{margin:0;color:var(--muted);font-size:12px}
.metric-grid{grid-template-columns:repeat(3,minmax(0,1fr))}
.metric{border:1px solid var(--line);border-radius:14px;padding:17px;background:white}
.metric-top{display:flex;justify-content:space-between;align-items:center;gap:8px}
.metric h3{margin:0;font-size:14px}
.metric .number{font-size:27px;font-weight:800;margin:12px 0 2px}
.metric .threshold{font-size:11px;color:var(--muted)}
.meter{height:8px;background:#edf1f6;border-radius:20px;margin:12px 0;overflow:hidden}
.meter span{display:block;height:100%;border-radius:20px}
.small{font-size:11px;color:var(--muted)}
.priority{display:grid;grid-template-columns:38px 1fr auto;gap:12px;align-items:start;padding:14px 0;border-bottom:1px solid #edf1f6}
.priority:last-child{border:0}
.priority .num{width:32px;height:32px;border-radius:10px;display:grid;place-items:center;font-weight:800;background:#eaf1ff;color:#2557ad}
.priority h3{font-size:14px;margin:0 0 4px}.priority p{font-size:12px;color:var(--muted);margin:0}
.impact{font-size:10px;font-weight:800;border-radius:20px;padding:5px 8px;background:#fff0f0;color:#b82c2c;white-space:nowrap}
.impact.med{background:#fff6df;color:#8a5a08}.impact.low{background:#e8f8ef;color:#16754c}
.image-frame{background:#f8fafc;border:1px solid var(--line);border-radius:14px;padding:12px}
.image-frame img{display:block;max-width:100%;height:auto;margin:auto;border-radius:8px}
.image-frame figcaption{font-size:11px;color:var(--muted);padding:9px 4px 0}
.ev-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:18px}
.ev-card{background:#fff;border:1px solid var(--line);border-radius:16px;overflow:hidden;box-shadow:var(--shadow)}
.ev-card img{display:block;width:100%;height:auto}
.ev-copy{padding:14px 16px}.ev-copy .tag{font-size:10px;font-weight:800;text-transform:uppercase;letter-spacing:.06em;color:var(--blue)}
.ev-copy h3{margin:6px 0 4px;font-size:15px}.ev-copy p{margin:0;font-size:12px;color:var(--muted)}
.ev-badge{display:inline-block;background:var(--red);color:#fff;font-size:10px;font-weight:800;text-transform:uppercase;letter-spacing:.04em;padding:3px 9px;border-radius:7px;margin-bottom:6px}
.search{border:1px solid var(--line);border-radius:9px;padding:10px 12px;background:white;color:var(--ink);font:inherit;font-size:12px;min-width:220px}
.note-box{font-size:12px;color:var(--muted);padding:12px 14px;background:#f8fafc;border-radius:10px}
.code-evidence{margin-top:16px;border-top:1px dashed var(--line);padding-top:14px}
.codewrap{border:1px solid var(--line);border-radius:10px;overflow:hidden;margin:8px 0}
.codewrap.bad{border-color:#f0c4c0}.codewrap.good{border-color:#bfe6cf}
.codelab{font-size:10px;font-weight:800;text-transform:uppercase;letter-spacing:.06em;padding:6px 12px}
.codelab.bad{background:var(--bad-bg);color:#b82c2c}.codelab.good{background:var(--good-bg);color:#16754c}
pre.code{margin:0;padding:12px 14px;background:#0f1b2d;color:#e6edf6;overflow:auto;
  font:12px/1.5 ui-monospace,SFMono-Regular,Menlo,Consolas,monospace}
pre.code code{white-space:pre;background:none;padding:0;color:inherit;font-size:12px}
.codewrap.bad pre.code{border-left:4px solid var(--bad)}.codewrap.good pre.code{border-left:4px solid var(--green)}
.flow{display:grid;grid-template-columns:repeat(4,1fr);gap:10px;align-items:stretch}
.flow div{position:relative;background:#f5f8fc;border:1px solid var(--line);border-radius:12px;padding:14px;text-align:center}
.flow strong{display:block;font-size:13px}.flow span{font-size:11px;color:var(--muted)}
.footer{margin-top:40px;padding:22px 0;border-top:1px solid var(--line);color:var(--muted);font-size:11px;display:flex;justify-content:space-between;gap:20px}
.print{border:0;border-radius:9px;background:#1e5cc4;color:white;padding:10px 14px;font-weight:700;cursor:pointer}
@media(max-width:1050px){.shell{grid-template-columns:210px minmax(0,1fr)}.content{padding:24px}
.stats,.score-row{grid-template-columns:repeat(2,minmax(0,1fr))}.metric-grid{grid-template-columns:repeat(2,minmax(0,1fr))}.two{grid-template-columns:1fr}.ev-grid{grid-template-columns:1fr}}
@media(max-width:700px){.shell{display:block}.side{position:relative;height:auto;padding:15px}
.side nav{display:flex;overflow:auto;gap:4px}.side nav a{white-space:nowrap}.side .label,.subject{display:none}
.topbar{padding:12px 18px}.content{padding:18px 14px 40px}.hero{padding:25px 22px}
.stats,.score-row,.three,.four,.metric-grid{grid-template-columns:1fr 1fr}.section-head{display:block}
.flow{grid-template-columns:1fr 1fr}.barline{grid-template-columns:100px 1fr 42px}.card{padding:15px}.footer{display:block}}
@media print{body{background:#fff;font-size:11px}.shell{display:block}.side{display:none}
.topbar{padding:8px 0}.content{max-width:none;padding:12px}
.hero{background:#17344f!important;-webkit-print-color-adjust:exact;print-color-adjust:exact}
.card{box-shadow:none;break-inside:avoid}.table-wrap{overflow:visible}table{min-width:0;font-size:9px}
.print,.search{display:none}.image-frame,.ev-card,.metric,.priority,.codewrap{break-inside:avoid}
pre.code{background:#f3f6fa!important;color:#17241d!important;-webkit-print-color-adjust:exact;print-color-adjust:exact}
.section-head h2{font-size:18px}}
"""


# ---------------------------------------------------------------------------
# Section builders
# ---------------------------------------------------------------------------
def stat_card(name, value, suffix="", note="", band="neutral", pct=None):
    val = f'{esc(value)}' + (f'<small> {esc(suffix)}</small>' if suffix else "")
    color = {"good": "#16865b", "warn": "#d97706", "bad": "#d64545",
             "blue": "#2563eb", "neutral": "#203047"}.get(band, "#203047")
    accent = ""
    if pct is not None:
        fill = BAND_FILL.get(band, "#3b82f6") if band in BAND_FILL else \
            {"good": "#16a34a", "warn": "#f59e0b", "bad": "#ef4444", "blue": "#3b82f6"}.get(band, "#3b82f6")
        accent = f'<div class="accent"><span style="width:{max(0,min(pct,100))}%;background:{fill}"></span></div>'
    return (f'<div class="card stat"><div class="name">{esc(name)}</div>'
            f'<div class="value" style="color:{color}">{val}</div>'
            f'<div class="note">{esc(note)}</div>{accent}</div>')


def priority_list(items, numbered_from=1):
    out = []
    for i, it in enumerate(items, numbered_from):
        imp = str(it.get("impact", "")).lower()
        cls = IMPACT_CLASS.get(imp, "med")
        label = it.get("impact", "")
        numbg = ('style="background:#fff0f0;color:#b82c2c"'
                 if cls == "" and i == numbered_from else "")
        badge = f'<span class="impact {cls}">{esc(label)}</span>' if label else ""
        out.append(
            f'<div class="priority"><div class="num" {numbg}>{i}</div>'
            f'<div><h3>{esc(it.get("title",""))}</h3>'
            f'<p>{esc(it.get("detail",""))}</p></div>{badge}</div>')
    return "".join(out)


def ring_card(score, label, sub):
    b = lh_band(score)
    disp = esc(score) if score is not None else "—"
    return (f'<div class="score-card"><div class="ring" style="--score:{score or 0};'
            f'--c:{BAND_RING[b]}"><b>{disp}</b></div>'
            f'<div><strong>{esc(label)}</strong><small>{esc(sub)}</small></div></div>')


def bar(label, value, maxv=100):
    b = lh_band(value) if maxv == 100 else band_of(value)
    pct = 0 if value is None else max(0, min(100, 100 * value / maxv))
    return (f'<div class="barline"><span>{esc(label)}</span><div class="track">'
            f'<div class="fill" style="width:{pct:.0f}%;background:{BAND_FILL[b]}"></div></div>'
            f'<b>{esc(value) if value is not None else "—"}</b></div>')


def metric_card(m):
    rating = (m.get("rating") or "warn").lower()
    badge_cls, _ = {"good": ("b-pass", ""), "needs-improvement": ("b-check", ""),
                    "poor": ("b-fail", ""), "na": ("b-info", "")}.get(rating, ("b-check", ""))
    badge_txt = m.get("badge") or {"good": "Good", "needs-improvement": "Needs work",
                                    "poor": "High", "na": "Field data needed"}.get(rating, "Review")
    numcol = {"good": "#16865b", "needs-improvement": "#c77a08",
              "poor": "#d64545", "na": "#8a5a08"}.get(rating, "#c77a08")
    fillcol = {"good": "#16a34a", "needs-improvement": "#f59e0b",
               "poor": "#dc4444", "na": "#c77a08"}.get(rating, "#f59e0b")
    value = m.get("value")
    unit = m.get("unit", "")
    vdisp = (f"{value}{(' ' + unit) if unit else ''}" if value is not None else
             m.get("display", "N/A"))
    pct = m.get("meter_pct")
    if pct is None:
        pct = 50 if value is not None else 0
    return (f'<div class="metric"><div class="metric-top"><h3>{esc(m.get("name",""))}</h3>'
            f'<span class="badge {badge_cls}">{esc(badge_txt)}</span></div>'
            f'<div class="number" style="color:{numcol}">{esc(vdisp)}</div>'
            f'<div class="threshold">{esc(m.get("threshold",""))}</div>'
            f'<div class="meter"><span style="width:{max(0,min(pct,100))}%;background:{fillcol}"></span></div>'
            f'<p class="small">{esc(m.get("definition",""))}</p></div>')


def code_block(label, code, kind):
    """A labelled before/after code snippet. kind: 'bad' (problem) or 'good' (fix)."""
    if not code:
        return ""
    return (f'<div class="codewrap {kind}"><div class="codelab {kind}">{esc(label)}</div>'
            f'<pre class="code"><code>{esc(code)}</code></pre></div>')


def code_evidence(fc):
    """Render the problem code + corrected code for a failed check, if supplied.
    Accepts either a `code` object {problem, fix, problem_label, fix_label, note}
    or flat `code_before` / `code_after` strings."""
    c = fc.get("code") or {}
    before = c.get("problem") or fc.get("code_before")
    after = c.get("fix") or fc.get("code_after")
    if not before and not after:
        return ""
    blocks = (code_block(c.get("problem_label", "Problem · current code"), before, "bad") +
              code_block(c.get("fix_label", "Fix · corrected code"), after, "good"))
    note = f'<p class="small" style="margin:8px 0 0">{esc(c.get("note"))}</p>' if c.get("note") else ""
    return (f'<div class="code-evidence"><div class="kicker">Code evidence</div>{blocks}{note}</div>')


def failed_check_card(fc):
    st = norm_status(fc.get("status", "fail"))
    bcls, _ = STATUS_BADGE[st]
    badge_label = fc.get("badge_label") or (
        {"fail": "Fail", "pass": "Pass · confirmed", "warn": "Review"}.get(st, "Review"))
    steps = fc.get("resolution_steps", [])
    steps_html = "".join(f"<li>{esc(s)}</li>" for s in steps)
    resolution = ""
    if steps_html or fc.get("resolution"):
        inner = (f'<ol style="padding-left:18px;margin-bottom:0">{steps_html}</ol>'
                 if steps_html else f'<p style="margin:0">{esc(fc.get("resolution"))}</p>')
        resolution = f'<div class="callout green"><strong>How to fix it — mitigation steps</strong>{inner}</div>'
    left = f'<div class="definition"><strong>What it means</strong><p>{esc(fc.get("what_it_means",""))}</p></div>'
    if fc.get("workbook_solution"):
        left += f'<p style="font-size:13px"><b>Workbook solution:</b> {esc(fc["workbook_solution"])}</p>'
    if fc.get("evaluation"):
        left += f'<p style="font-size:13px"><b>Evaluation:</b> {esc(fc["evaluation"])}</p>'
    code = code_evidence(fc)
    return (f'<article class="card"><div class="section-head"><div>'
            f'<span class="badge {bcls}">{esc(badge_label)}</span>'
            f'<h3 style="margin:8px 0 0">{esc(fc.get("title",""))}</h3></div>'
            f'<span class="impact {IMPACT_CLASS.get(str(fc.get("impact","medium")).lower(),"med")}">'
            f'{esc(fc.get("category",""))}</span></div>'
            f'<div class="grid two"><div>{left}</div>{resolution}</div>{code}</article>')


def checklist_section(cl):
    if not cl or not cl.get("available"):
        return ('<p class="note-box">No checklist spreadsheet was supplied. Attach your '
                'SEO checklist (statuses and your fixes) and each item is reproduced and '
                'interpreted here.</p>')
    items = cl.get("items", [])
    counts = {"pass": 0, "fail": 0, "warn": 0, "other": 0}
    for it in items:
        counts[norm_status(it.get("status"))] += 1
    summ = cl.get("summary") or {}
    p = summ.get("pass", counts["pass"])
    f = summ.get("fail", counts["fail"])
    other = summ.get("other", counts["warn"] + counts["other"])
    stat_cards = (stat_card("Pass / positive", p, note="Recorded positive status", band="good") +
                  stat_card("Failed checks", f, note="Needs evaluation and action", band="bad") +
                  stat_card("Other / reference", other, note="Review or non-binary entries", band="warn"))
    rows = []
    for it in sorted(items, key=lambda x: {"fail": 0, "warn": 1, "pass": 2, "other": 3}[norm_status(x.get("status"))]):
        st = norm_status(it.get("status"))
        bcls, _ = STATUS_BADGE[st]
        rows.append(
            f'<tr data-status="{st}"><td><b>{esc(it.get("item",""))}</b>'
            f'{("<br><span class=small>" + esc(it.get("category","")) + "</span>") if it.get("category") else ""}</td>'
            f'<td><span class="badge {bcls}">{esc(it.get("status","") or "—")}</span></td>'
            f'<td>{esc(it.get("user_solution","") or it.get("notes","") or "—")}</td>'
            f'<td class="muted">{esc(it.get("seo_resolution","") or it.get("evaluation","") or "—")}</td></tr>')
    return (f'<div class="grid three">{stat_cards}</div>'
            f'<div class="card" style="margin-top:16px">'
            f'<div style="display:flex;gap:10px;flex-wrap:wrap;margin-bottom:12px">'
            f'<input class="search" data-filter="#checkBody" placeholder="Search item, status or solution…">'
            f'</div><div class="table-wrap"><table><thead><tr><th>Checklist item</th>'
            f'<th>Recorded status</th><th>Solution / note</th><th>SEO interpretation</th></tr></thead>'
            f'<tbody id="checkBody">{"".join(rows)}</tbody></table></div>'
            f'<div class="note-box" style="margin-top:12px">Checklist rows are reproduced from '
            f'your workbook. A recorded "pass" is not independently re-tested; where no solution '
            f'was provided, the SEO interpretation suggests one.</div></div>')


def link_audit_section(la, n):
    if not la or not la.get("available"):
        return ""
    stats = la.get("stats", [])
    stat_html = "".join(stat_card(s.get("name", ""), s.get("value", ""),
                                  note=s.get("note", ""), band=s.get("band", "neutral"))
                        for s in stats)
    # error mix bars
    mix = la.get("error_mix", [])
    maxc = max([m.get("count", 0) for m in mix], default=1) or 1
    mix_html = "".join(
        f'<div class="barline"><span>{esc(m.get("label",""))}</span><div class="track">'
        f'<div class="fill" style="width:{m.get("count",0)/maxc*100:.0f}%;'
        f'background:{BAND_FILL.get(m.get("band","warn"),"#f59e0b")}"></div></div>'
        f'<b>{esc(m.get("count",0))}</b></div>' for m in mix)
    triage = la.get("triage") or [
        {"step": "1 · Identify", "note": "Internal or external?"},
        {"step": "2 · Verify", "note": "Repeat request / browser"},
        {"step": "3 · Classify", "note": "Broken, blocked, transient"},
        {"step": "4 · Fix", "note": "Repair, replace or document"}]
    triage_html = "".join(f'<div><strong>{esc(t["step"])}</strong><span>{esc(t["note"])}</span></div>'
                          for t in triage)
    # broken register
    broken = la.get("broken", [])
    broken_rows = "".join(
        f'<tr><td><b>{esc(b.get("code",""))}</b></td><td>{esc(b.get("status",""))}</td>'
        f'<td class="brk">{esc(b.get("url",""))}</td><td>{esc(b.get("source",""))}</td>'
        f'<td>{esc(b.get("action",""))}</td></tr>' for b in broken)
    broken_block = ""
    if broken:
        broken_block = (
            f'<div class="card" style="margin-top:16px"><div class="section-head"><div>'
            f'<div class="kicker">Broken-link register</div><h3 style="margin:0">'
            f'{len(broken)} reported entries</h3></div>'
            f'<input class="search" data-filter="#brokenBody" placeholder="Filter URLs / code…"></div>'
            f'<div class="table-wrap"><table><thead><tr><th>HTTP</th><th>Response</th>'
            f'<th>Destination / URL</th><th>Found on</th><th>Suggested action</th></tr></thead>'
            f'<tbody id="brokenBody">{broken_rows}</tbody></table></div></div>')
    # redirect register
    reds = la.get("redirects", [])
    red_rows = "".join(
        f'<tr><td>{i+1}</td><td class="brk">{esc(r.get("url",""))}</td>'
        f'<td>{esc(r.get("source",""))}</td><td class="muted">{esc(r.get("recommendation",""))}</td></tr>'
        for i, r in enumerate(reds))
    red_block = ""
    if reds:
        red_block = (
            f'<div class="card" style="margin-top:16px"><div class="section-head"><div>'
            f'<div class="kicker">Redirect register</div><h3 style="margin:0">'
            f'Redirect records</h3></div>'
            f'<input class="search" data-filter="#redirBody" placeholder="Filter redirect URLs…"></div>'
            f'<div class="table-wrap"><table><thead><tr><th>#</th><th>Observed source → destination</th>'
            f'<th>Referring page</th><th>SEO recommendation</th></tr></thead>'
            f'<tbody id="redirBody">{red_rows}</tbody></table></div></div>')
    note = la.get("note", "A crawler error does not automatically mean a user-facing "
                  "editorial link is broken — verify before changing a page.")
    return (f'<section class="section" id="links"><div class="section-head"><div>'
            f'<div class="kicker">{n:02d} · Crawl evidence</div>'
            f'<h2>Link audit: errors, redirects &amp; crawl coverage</h2>'
            f'<p>{esc(note)}</p></div></div>'
            f'<div class="grid four">{stat_html}</div>'
            f'<div class="grid two" style="margin-top:16px">'
            f'<div class="card"><div class="kicker">Error mix</div>'
            f'<h3 style="margin-top:0">Reported HTTP / error responses</h3>'
            f'<div class="barlist">{mix_html or "<p class=small>No error breakdown supplied.</p>"}</div></div>'
            f'<div class="card"><div class="kicker">Triage workflow</div>'
            f'<h3 style="margin-top:0">How to prioritise a link issue</h3>'
            f'<div class="flow">{triage_html}</div></div></div>'
            f'{broken_block}{red_block}</section>')


def roadmap_section(rm, n):
    if not rm:
        return ""
    now = priority_list(rm.get("now", []), 1)
    nxt = priority_list(rm.get("next", []), len(rm.get("now", [])) + 1)
    acc = rm.get("acceptance", [])
    acc_rows = "".join(
        f'<tr><td>{esc(a.get("workstream",""))}</td><td>{esc(a.get("evidence",""))}</td>'
        f'<td>{esc(a.get("owner",""))}</td></tr>' for a in acc)
    acc_block = ""
    if acc_rows:
        acc_block = (
            f'<div class="card" style="margin-top:16px"><h3 style="margin-top:0">'
            f'Acceptance criteria for the next audit</h3><div class="table-wrap"><table>'
            f'<thead><tr><th>Workstream</th><th>Success evidence</th><th>Owner</th></tr></thead>'
            f'<tbody>{acc_rows}</tbody></table></div></div>')
    return (f'<section class="section" id="roadmap"><div class="section-head"><div>'
            f'<div class="kicker">{n:02d} · Delivery plan</div>'
            f'<h2>Recommended SEO action roadmap</h2>'
            f'<p>"Priority" reflects likely value and urgency, not a guaranteed ranking lift.</p>'
            f'</div></div><div class="grid two">'
            f'<div class="card"><h3 style="margin-top:0">Now · 0–2 days</h3>{now or "<p class=small>—</p>"}</div>'
            f'<div class="card"><h3 style="margin-top:0">Next · 1–2 weeks</h3>{nxt or "<p class=small>—</p>"}</div>'
            f'</div>{acc_block}</section>')


def evidence_section(screens, n):
    cards = []
    for s in screens:
        uri = data_uri(s.get("path"))
        if not uri:
            continue
        tag = "Evidence · Annotated page" if s.get("annotated") else (
            "Evidence · Lighthouse" if s.get("kind") == "lighthouse" else "Evidence")
        badge = '<span class="ev-badge">Issues highlighted</span>' if s.get("annotated") else ""
        cards.append(
            f'<article class="ev-card"><img src="{uri}" alt="{esc(s.get("caption",""))}">'
            f'<div class="ev-copy">{badge}<span class="tag">{tag}</span>'
            f'<h3>{esc(s.get("title") or s.get("caption","Screenshot"))}</h3>'
            f'<p>{esc(s.get("caption",""))}</p></div></article>')
    if not cards:
        body = ('<p class="note-box">No screenshots were supplied or captured. Attach the '
                'Lighthouse report screenshot and, where a browser is available, the skill '
                'captures annotated page snapshots with the issues outlined.</p>')
    else:
        body = f'<div class="ev-grid">{"".join(cards)}</div>'
    return (f'<section class="section" id="evidence"><div class="section-head"><div>'
            f'<div class="kicker">{n:02d} · Evidence gallery</div>'
            f'<h2>Visual evidence &amp; page-level snapshots</h2>'
            f'<p>Supplied Lighthouse captures and annotated page snapshots. These document '
            f'what was visible at audit time; they are evidence, not a live re-crawl.</p>'
            f'</div></div>{body}</section>')


DEFAULT_DEFS = [
    ("Lighthouse score", "A weighted lab score for a category. It varies with the run environment and is not a ranking score."),
    ("Core Web Vitals", "Google's user-centred metrics for loading (LCP), interactivity (INP) and visual stability (CLS), assessed on field data at the 75th percentile."),
    ("LCP", "Largest Contentful Paint — when the main content finishes rendering. Good ≤ 2.5s."),
    ("INP", "Interaction to Next Paint — responsiveness to input; a field metric. Good ≤ 200ms."),
    ("CLS", "Cumulative Layout Shift — how much the layout moves while loading. Good ≤ 0.1."),
    ("TBT", "Total Blocking Time sums main-thread blocking beyond 50ms in the lab window. A diagnostic proxy, not a field Core Web Vital."),
    ("robots.txt", "Crawl instructions for compliant bots. It does not guarantee indexing and is not a security control."),
    ("Canonical URL", "A hint identifying the preferred version of similar pages; it should match the intended indexable URL."),
    ("HTTP 403 / 404", "403 Forbidden (often bot protection, not a broken link); 404 Not Found — confirm the URL is genuinely missing before replacing."),
]


def method_section(defs, limits, n):
    terms = list(DEFAULT_DEFS) + [(d.get("term", ""), d.get("definition", "")) for d in (defs or [])]
    cards = "".join(f'<div class="definition"><strong>{esc(t)}</strong><p>{esc(d)}</p></div>'
                    for t, d in terms if t)
    lim = limits or [
        "On-page/technical signals are measured directly; performance is read from the supplied Lighthouse run.",
        "Off-page and checklist data are supplied by the auditor and reproduced, not independently re-tested.",
        "This is an evidence-led interpretation, not a guarantee of rankings. SEO is probabilistic.",
        "No conclusions are fabricated for inputs that were not supplied.",
    ]
    lim_html = "".join(f"<li>{esc(x)}</li>" for x in lim)
    return (f'<section class="section" id="method"><div class="section-head"><div>'
            f'<div class="kicker">{n:02d} · How to interpret this report</div>'
            f'<h2>Definitions, methodology &amp; limitations</h2>'
            f'<p>Use these to separate measurements, crawler observations and recommendations.</p>'
            f'</div></div><div class="grid three">{cards}</div>'
            f'<div class="card" style="margin-top:16px"><h3 style="margin-top:0">'
            f'Evidence sources and limitations</h3>'
            f'<ul style="font-size:13px;color:var(--muted);padding-left:20px">{lim_html}</ul></div></section>')


FILTER_JS = """
document.querySelectorAll('.search[data-filter]').forEach(function(inp){
  inp.addEventListener('input', function(){
    var q = this.value.toLowerCase();
    document.querySelectorAll(this.getAttribute('data-filter')+' tr').forEach(function(tr){
      tr.style.display = tr.textContent.toLowerCase().indexOf(q) > -1 ? '' : 'none';
    });
  });
});
"""


# ---------------------------------------------------------------------------
# Assemble
# ---------------------------------------------------------------------------
def overall_health(data, ins):
    s = dict(data.get("scores") or {})
    s.update({k: v for k, v in (ins.get("scores") or {}).items() if v is not None})
    parts = [v for k, v in s.items()
             if k in ("on_page", "content", "technical", "off_page") and isinstance(v, (int, float))]
    lh = ins.get("lighthouse", {})
    if lh.get("available"):
        for k in ("seo", "performance"):
            if isinstance(lh.get(k), (int, float)):
                parts.append(lh[k])
    return round(sum(parts) / len(parts)) if parts else None


def build(data, ins, out_path):
    pages = data.get("pages", [])
    primary = pages[0] if pages else {}
    lh = ins.get("lighthouse", {})
    cwv = ins.get("core_web_vitals", {})
    exe = ins.get("executive_summary", {})
    if isinstance(exe, str):
        exe = {"text": exe}

    site_name = ins.get("site_name") or data.get("input_url") or "Website"
    page_url = ins.get("page_url") or data.get("input_url") or ""
    site_url = ins.get("site_url") or ""
    report_date = ins.get("report_date") or dt.date.today().isoformat()
    by = ins.get("prepared_by", "")
    hero = ins.get("hero", {})
    hero_title = hero.get("title") or f"{site_name}<br>Technical SEO &amp; Core Web Vitals Report"
    hero_sub = hero.get("subtitle") or (
        "A structured review of the page, Lighthouse diagnostics, the SEO checklist and crawl "
        "evidence. Findings are separated from recommendations so the team can act on what is evidenced.")
    pills = hero.get("pills") or []
    pills_html = "".join(f'<span class="pill">{esc(p)}</span>' for p in pills)

    health = overall_health(data, ins)

    # ---- Section numbering (only count sections that render) ----
    has_links = bool(ins.get("link_audit", {}).get("available"))
    has_roadmap = bool(ins.get("roadmap"))
    n = 1

    def kick(title, extra=""):
        nonlocal n
        k = f'{n:02d} · {title}'
        n += 1
        return k

    # Executive summary is section 01 — compute its kicker before the other
    # sections build (they consume n in source order, ahead of the final doc).
    exec_kicker = kick("At a glance")

    # ---- Executive summary ----
    stats = exe.get("stats") or []
    if not stats:
        # sensible defaults from what we have
        if lh.get("available") and lh.get("performance") is not None:
            stats.append({"name": "Lighthouse Performance", "value": lh["performance"],
                          "suffix": "/ 100", "note": "Lab score", "band": lh_band(lh["performance"]),
                          "pct": lh["performance"]})
        cl = ins.get("checklist", {})
        if cl.get("available"):
            su = cl.get("summary", {})
            tot = su.get("total") or len(cl.get("items", []))
            passed = su.get("pass")
            if passed is not None:
                stats.append({"name": "SEO checklist", "value": passed, "suffix": f"/ {tot}",
                              "note": "Recorded pass statuses", "band": "good",
                              "pct": round(100 * passed / tot) if tot else 0})
        la = ins.get("link_audit", {})
        if la.get("available") and la.get("broken") is not None:
            stats.append({"name": "Broken-link entries", "value": len(la.get("broken", [])),
                          "note": "Validate context first", "band": "bad", "pct": 30})
    stat_html = "".join(stat_card(s.get("name", ""), s.get("value", ""), s.get("suffix", ""),
                                  s.get("note", ""), s.get("band", "neutral"), s.get("pct"))
                        for s in stats) or '<div class="card stat"><div class="note">No headline stats supplied.</div></div>'

    top_signals = priority_list(exe.get("top_signals", []))
    scope_note = exe.get("scope_note") or (
        "Checklist statuses are tool/operator observations — not all are direct ranking factors, "
        "and a Lighthouse SEO score of 100 does not guarantee rankings or complete SEO health.")
    scope_links = ""
    if page_url:
        scope_links += (f'<p style="font-size:13px;margin:0 0 2px">Page under review</p>'
                        f'<a href="{esc(page_url)}" target="_blank" rel="noreferrer">{esc(page_url)} ↗</a>')
    if site_url:
        scope_links += (f'<p style="font-size:13px;margin:14px 0 2px">Website</p>'
                        f'<a href="{esc(site_url)}" target="_blank" rel="noreferrer">{esc(site_url)} ↗</a>')

    exec_html = (
        f'<div class="grid stats">{stat_html}</div>'
        f'<div class="grid two" style="margin-top:16px">'
        f'<div class="card"><div class="kicker">What matters most</div>'
        f'<h3 style="margin:0 0 12px">Top signals</h3>'
        f'{top_signals or "<p class=small>No top signals supplied.</p>"}</div>'
        f'<div class="card"><div class="kicker">Audit scope</div>'
        f'<h3 style="margin-top:0">Pages &amp; evidence reviewed</h3>{scope_links}'
        f'<div class="callout amber" style="margin-top:16px"><strong>How to read this</strong><br>'
        f'{esc(scope_note)}</div></div></div>')

    # ---- Lighthouse scorecard ----
    if lh.get("available"):
        rings = "".join(ring_card(lh.get(k), lab, sub) for k, lab, sub in [
            ("performance", "Performance", "Lab score"),
            ("accessibility", "Accessibility", "Automated subset"),
            ("best_practices", "Best Practices", "Technical review"),
            ("seo", "SEO", "Automated checks")])
        bars = "".join(bar(lab, lh.get(k)) for k, lab in [
            ("performance", "Performance"), ("accessibility", "Accessibility"),
            ("best_practices", "Best Practices"), ("seo", "SEO")])
        interp = ins.get("sections", {}).get("lighthouse", {}).get("commentary") or (
            "Lower scores mark the biggest technical gaps. An SEO score of 100 only means the "
            "automated Lighthouse SEO checks passed — it does not assess keyword usefulness, "
            "originality, internal-link strategy, indexation, backlinks or content expertise.")
        lh_section = (
            f'<section class="section" id="scores"><div class="section-head"><div>'
            f'<div class="kicker">{kick("Lab diagnostics")}</div><h2>Lighthouse scorecard</h2>'
            f'<p>Scores are out of 100. Bands follow Lighthouse: green 90–100, orange 50–89, red 0–49.</p>'
            f'</div></div><div class="card"><div class="score-row">{rings}</div>'
            f'<div style="height:1px;background:var(--line);margin:22px 0"></div>'
            f'<div class="grid two"><div><h3 style="margin-top:0">Relative score comparison</h3>'
            f'<div class="barlist">{bars}</div></div>'
            f'<div><h3 style="margin-top:0">Interpretation</h3>'
            f'<p style="font-size:13px;color:var(--muted)">{esc(interp)}</p></div></div></div></section>')
    else:
        lh_section = (
            f'<section class="section" id="scores"><div class="section-head"><div>'
            f'<div class="kicker">{kick("Lab diagnostics")}</div><h2>Lighthouse scorecard</h2></div></div>'
            f'<p class="note-box">No Lighthouse screenshot was supplied, so lab scores are not shown. '
            f'Run Lighthouse (Chrome DevTools or PageSpeed Insights) and re-run with the screenshot.</p></section>')

    # ---- Core Web Vitals ----
    if cwv.get("available") and cwv.get("metrics"):
        metrics = "".join(metric_card(m) for m in cwv["metrics"])
        pc = cwv.get("pass_criteria") or [
            {"metric": "LCP ≤ 2.5 s", "label": "Loading"},
            {"metric": "INP ≤ 200 ms", "label": "Interactivity"},
            {"metric": "CLS ≤ 0.10", "label": "Visual stability"},
            {"metric": "75th percentile", "label": "Field data"}]
        pc_html = "".join(f'<div><strong>{esc(p["metric"])}</strong><span>{esc(p["label"])}</span></div>'
                          for p in pc)
        rem = cwv.get("remediation") or [
            "Use the Lighthouse trace/treemap to find the largest JS bundles and long tasks.",
            "Delay or remove non-essential third-party scripts; load ads/analytics only when needed.",
            "Split code, defer non-critical JS, and avoid expensive main-thread work.",
            "Optimise critical CSS, fonts and image priority; don't lazy-load the LCP image.",
            "Re-run 3–5 tests under the same device/network profile and compare medians."]
        rem_html = "".join(f"<li>{esc(r)}</li>" for r in rem)
        caveat = cwv.get("caveat") or (
            "Lighthouse lab runs vary with network, device emulation, cache, ads and third-party "
            "services. Treat the values as a diagnostic snapshot, not every user's experience.")
        cwv_note = cwv.get("note", "")
        cwv_section = (
            f'<section class="section" id="vitals"><div class="section-head"><div>'
            f'<div class="kicker">{kick("Speed & user experience")}</div>'
            f'<h2>Core Web Vitals &amp; performance metrics</h2>'
            f'<p>{esc(cwv_note) or "Values transcribed from the supplied Lighthouse report; thresholds follow Google\'s good / needs-improvement ranges."}</p>'
            f'</div></div><div class="grid metric-grid">{metrics}</div>'
            f'<div class="grid two" style="margin-top:16px">'
            f'<div class="card"><div class="kicker">How to read the metrics</div>'
            f'<h3 style="margin-top:0">Field Core Web Vitals pass criteria</h3>'
            f'<div class="flow">{pc_html}</div>'
            f'<p class="small" style="margin-top:14px">A page passes Core Web Vitals when all three '
            f'field metrics meet their "good" thresholds at the 75th percentile.</p></div>'
            f'<div class="card"><div class="kicker">Performance remediation</div>'
            f'<h3 style="margin-top:0">Recommended sequence</h3>'
            f'<ol style="font-size:13px;padding-left:20px">{rem_html}</ol></div></div>'
            f'<div class="callout amber" style="margin-top:16px"><strong>Evidence caveat:</strong> {esc(caveat)}</div></section>')
    else:
        cwv_section = (
            f'<section class="section" id="vitals"><div class="section-head"><div>'
            f'<div class="kicker">{kick("Speed & user experience")}</div>'
            f'<h2>Core Web Vitals &amp; performance metrics</h2></div></div>'
            f'<p class="note-box">No Core Web Vitals were supplied. Pull them from a Lighthouse run '
            f'or the Chrome UX Report and they are plotted here against Google\'s thresholds.</p></section>')

    # ---- Checklist ----
    checklist_html = (
        f'<section class="section" id="checklist"><div class="section-head"><div>'
        f'<div class="kicker">{kick("On-page & technical checks")}</div>'
        f'<h2>SEO checklist results</h2>'
        f'<p>Each recorded item from your workbook, with its status, the solution noted, and an SEO '
        f'interpretation. Search to inspect any item.</p></div></div>{checklist_section(ins.get("checklist", {}))}</section>')

    # ---- Failed checks deep dive ----
    fcs = ins.get("failed_checks", [])
    failed_html = ""
    if fcs:
        cards = "".join(failed_check_card(fc) for fc in fcs)
        other = ins.get("other_findings", [])
        other_html = ""
        if other:
            oc = "".join(f'<div class="card"><h3>{esc(o.get("title",""))}</h3>'
                         f'<p style="font-size:13px;color:var(--muted)">{esc(o.get("detail",""))}</p></div>'
                         for o in other)
            other_html = (f'<div class="section" style="margin-top:22px"><div class="section-head"><div>'
                          f'<div class="kicker">Additional evaluation</div>'
                          f'<h2>Other findings that need context</h2></div></div>'
                          f'<div class="grid two">{oc}</div></div>')
        failed_html = (
            f'<section class="section" id="failures"><div class="section-head"><div>'
            f'<div class="kicker">{kick("Evaluation & fixes")}</div>'
            f'<h2>Failed checks: evaluate the proposed solution, then improve it</h2>'
            f'<p>Each card separates a useful direction from a safe implementation — avoid broad '
            f'robots changes or rewriting content just to satisfy a score.</p></div></div>'
            f'<div class="grid" style="gap:14px">{cards}</div>{other_html}</section>')

    # ---- Link audit ----
    links_html = link_audit_section(ins.get("link_audit", {}), n) if has_links else ""
    if has_links:
        n += 1

    # ---- Roadmap ----
    roadmap_html = roadmap_section(ins.get("roadmap", {}), n) if has_roadmap else ""
    if has_roadmap:
        n += 1

    # ---- Evidence + method ----
    evidence_html = evidence_section(ins.get("screenshots", []), n); n += 1
    method_html = method_section(ins.get("definitions"), ins.get("limitations"), n); n += 1

    # ---- Sidebar nav ----
    nav_items = [("summary", "◈ Executive summary"), ("scores", "◉ Lighthouse scores"),
                 ("vitals", "◷ Core Web Vitals"), ("checklist", "✓ SEO checklist")]
    if fcs:
        nav_items.append(("failures", "⚑ Failed checks & fixes"))
    if has_links:
        nav_items.append(("links", "↗ Link audit"))
    if has_roadmap:
        nav_items.append(("roadmap", "▤ Action roadmap"))
    nav_items += [("evidence", "▧ Evidence gallery"), ("method", "ⓘ Method & definitions")]
    nav_html = "".join(f'<a href="#{i}">{esc(l)}</a>' for i, l in nav_items)

    subject = (f'<div class="subject">{esc(site_name)}<br>'
               f'{esc(hero.get("subject_line","Audited page"))}<br>'
               f'<span>{esc(report_date)}'
               f'{(" · " + esc(by)) if by else ""}</span></div>')

    doc = f"""<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(site_name)} | SEO &amp; Core Web Vitals Audit</title>
<style>{CSS}</style></head><body>
<div class="shell">
<aside class="side">
  <div class="brand">{esc(ins.get("brand_short", site_name[:28]))} <small>SEO &amp; Technical Audit</small></div>
  <div class="label">Report navigation</div>
  <nav>{nav_html}</nav>
  <div class="label">Audit subject</div>
  {subject}
</aside>
<main class="main">
<div class="topbar"><div><strong>{esc(site_name.upper())}</strong> / Technical SEO review</div>
<button class="print" onclick="window.print()">Print / Save PDF</button></div>
<div class="content">

<header class="hero"><div class="eyebrow">Website SEO &amp; performance audit</div>
<h1>{hero_title}</h1><p>{esc(hero_sub)}</p>
<div class="hero-meta">{pills_html}</div></header>

<section class="section" id="summary"><div class="section-head"><div>
<div class="kicker">{exec_kicker}</div><h2>Executive summary</h2>
<p>{esc(exe.get("text",""))}</p></div></div>{exec_html}</section>

{lh_section}
{cwv_section}
{checklist_html}
{failed_html}
{links_html}
{roadmap_html}
{evidence_html}
{method_html}

<footer class="footer">
<div><strong>{esc(site_name)} · SEO &amp; Core Web Vitals audit</strong><br>
Prepared from supplied checklist, crawl export and Lighthouse evidence.</div>
<div>Report generated: {esc(report_date)}<br>Interactive HTML · print-friendly layout</div></footer>

</div></main></div>
<script>{FILTER_JS}</script>
</body></html>"""

    with open(out_path, "w") as f:
        f.write(doc)
    return health


def main():
    ap = argparse.ArgumentParser(description="Render an agency-grade HTML SEO report.")
    ap.add_argument("--data", required=True)
    ap.add_argument("--insights")
    ap.add_argument("-o", "--output", default="seo-report.html")
    args = ap.parse_args()

    with open(args.data) as f:
        data = json.load(f)
    ins = {}
    if args.insights:
        with open(args.insights) as f:
            ins = json.load(f)

    health = build(data, ins, args.output)
    size_kb = round(os.path.getsize(args.output) / 1024)
    print(f"Wrote {args.output} (SEO health: {health}/100, {size_kb} KB)")


if __name__ == "__main__":
    main()
