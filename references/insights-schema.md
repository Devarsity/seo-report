# `insights.json` schema

This is the judgement layer you write after reading `audit.json`, the Excel
checklist (`workbook.json` from `read_xlsx.py`), and the Lighthouse screenshot.
`build_report.py` merges it with the measured data and renders the agency-grade
HTML. Every field is optional — the builder fills defaults and skips empty
sections — but the report is only as good as what you put here. Write it to the
working directory and pass it with `--insights`.

The report's design goal is a professional client deliverable: evidence first,
recommendations clearly separated, honest about what wasn't measured. Keep that
tone in everything you write here.

## Header / identity

| Field | What it is |
|---|---|
| `site_name` | Full name for the hero + footer (e.g. "Search Engine Journal"). |
| `brand_short` | Short name for the sidebar brand (e.g. "SEJ"). Defaults to a trim of `site_name`. |
| `page_url` | The specific page audited (shown in the audit-scope card). |
| `site_url` | The overall website. |
| `report_date` | `YYYY-MM-DD`; today unless the user says otherwise. |
| `prepared_by` | Optional author credit, shown in the sidebar subject block. |
| `hero` | `{title, subtitle, subject_line, pills:[...]}`. `title` may contain `<br>`. `pills` are the small scope tags on the hero (e.g. "4 Lighthouse categories"). `subject_line` is the one-liner under the brand in the sidebar. |

## `executive_summary`

```json
"executive_summary": {
  "text": "3-5 sentences: overall state + the one or two things that matter most.",
  "stats": [
    {"name": "Lighthouse Performance", "value": 70, "suffix": "/ 100", "note": "Needs improvement · lab score", "band": "warn", "pct": 70},
    {"name": "SEO checklist", "value": 15, "suffix": "/ 19", "note": "Recorded pass statuses", "band": "good", "pct": 85},
    {"name": "Broken-link entries", "value": 10, "note": "Validate context first", "band": "bad", "pct": 30}
  ],
  "top_signals": [
    {"title": "Reduce main-thread blocking", "detail": "TBT is 1,960 ms…", "impact": "High"}
  ],
  "scope_note": "Checklist statuses are operator observations — not all are ranking factors."
}
```

- `stats` → the four headline cards with accent bars. `band` is `good` / `warn` /
  `bad` / `blue` / `neutral`; `pct` sets the accent-bar width (0-100). If you omit
  `stats`, the builder derives a few from the Lighthouse/checklist/link data.
- `top_signals` → the numbered "what matters most" list. `impact` is `High` /
  `Medium` / `Low` (colours the pill).
- `scope_note` → the amber "how to read this" caveat in the audit-scope card.
- `text` can also be given as a bare string at `executive_summary` for a quick report.

## `scores`

`{on_page, content, technical, off_page}` as 0-100. These feed the blended health
score. `audit.py` scores on-page/content; supply `technical` and `off_page`.

## `lighthouse`

```json
"lighthouse": {"available": true, "performance": 70, "accessibility": 88, "best_practices": 73, "seo": 100}
```

The four ring scores, read from the screenshot. Drives the conic-gradient rings
and the comparison bars (green ≥90, orange 50-89, red <50). Add
`sections.lighthouse.commentary` for the interpretation text beside them. Set
`"available": false` with no screenshot — never invent scores.

## `core_web_vitals`

```json
"core_web_vitals": {
  "available": true,
  "note": "Mobile, transcribed from the Lighthouse report. INP field data not supplied.",
  "metrics": [
    {"key": "LCP", "name": "Largest Contentful Paint (LCP)", "value": 1.8, "unit": "s",
     "rating": "good", "badge": "Good · lab value",
     "threshold": "Good ≤ 2.5 s · Needs improvement ≤ 4.0 s", "meter_pct": 45,
     "definition": "Time until the largest visible element renders…"},
    {"key": "INP", "name": "Interaction to Next Paint (INP)", "display": "N/A",
     "rating": "na", "badge": "Field data needed",
     "threshold": "Good ≤ 200 ms · Needs improvement ≤ 500 ms", "meter_pct": 0,
     "definition": "A field metric — collect from CrUX; can't be inferred from lab data."}
  ],
  "pass_criteria": [{"metric": "LCP ≤ 2.5 s", "label": "Loading"}, ...],
  "remediation": ["Use the Lighthouse trace/treemap…", ...],
  "caveat": "Lighthouse lab runs vary with network, device, cache…"
}
```

- Each metric is its own card with a meter, threshold line and definition.
  `rating` is `good` / `needs-improvement` / `poor` / `na` (colours the number,
  badge and meter). `meter_pct` sets the fill (0-100) — place the value sensibly
  within its range. Use `value`+`unit` for a number, or `display` for "N/A".
- `pass_criteria`, `remediation` and `caveat` have sensible defaults; override to
  tailor them. Include INP honestly: it's a field metric and usually "N/A" from a
  lab screenshot. TBT is a lab diagnostic, not a Core Web Vital — say so.
- No data → `"available": false`.

## `checklist` (from the user's Excel)

```json
"checklist": {
  "available": true,
  "summary": {"pass": 15, "fail": 3, "other": 1, "total": 19},
  "items": [
    {"category": "On-Page", "item": "Meta description", "status": "Fail",
     "notes": "Missing on services page", "user_solution": "Write a 150-char description",
     "evaluation": "Right fix, length on point.",
     "seo_resolution": "Write a unique 140-155 char description leading with service + city."}
  ]
}
```

Rendered as a searchable table (status badge + the user's solution/note + your
SEO interpretation). `status` is normalised (`pass`/`fail`/`warn`/`other`). The
`seo_resolution` (or `evaluation`) shows in the interpretation column. This is
the data for the checklist *table*; the deep-dive cards for failures come next.

## `failed_checks` (the standout section — deep-dive cards)

```json
"failed_checks": [
  {"title": "1. Images missing alt text", "status": "fail", "badge_label": "Fail · high priority",
   "category": "Accessibility & image SEO", "impact": "high",
   "what_it_means": "Screen readers can't describe an image with no alt attribute…",
   "workbook_solution": "Add alt text to the images.",
   "evaluation": "Right fix — keep the alt descriptive, not keyword-stuffed.",
   "resolution_steps": [
     "Describe what each image shows ('stone paver patio with seating wall').",
     "Leave decorative images with empty alt (alt=\"\").",
     "Re-run the accessibility audit to confirm coverage."
   ],
   "code": {
     "problem_label": "Problem · current markup",
     "problem": "<img src=\"/patio.jpg\">\n<img src=\"/lawn.jpg\">",
     "fix_label": "Fix · corrected markup",
     "fix": "<img src=\"/patio.jpg\" alt=\"Stone paver patio with built-in seating\">\n<img src=\"/lawn.jpg\" alt=\"Freshly mowed lawn with garden border\">",
     "note": "Alt text should describe the image's content and function, not repeat the filename."
   }}
]
```

One card per failed (or notable) checklist item. The left column shows "What it
means" + the workbook solution + your **evaluation** of it; the right column is a
green "How to fix it — mitigation steps" box with ordered `resolution_steps`.
This is where you add expertise: **evaluate the user's fix honestly** — confirm
good ones, flag weak or risky ones ("too broad", "verify first") — then give the
correct, specific resolution. `impact` is `high`/`medium`/`low`. Use
`status: "pass"` with a `badge_label` like "Pass · confirmed" if the user
clarified an item is actually fine.

**Code evidence (`code`)** — whenever a problem is code-level, add a `code`
object so the card shows the offending code and the corrected version as
highlighted before/after blocks (red = problem, green = fix). This is the "show
me the code and how to fix it" part — use it for anything you can express in
markup or config: missing alt, unlabeled `<input>`/`<select>`, untitled
`<iframe>`, missing `width`/`height`, non-descriptive anchors, a broken
`robots.txt` line, a missing canonical, a bad heading order, a meta tag, a schema
snippet, an `.htaccess`/redirect rule, etc. Fields: `problem` and `fix` (the two
snippets), optional `problem_label` / `fix_label` (default "Problem · current
code" / "Fix · corrected code"), and an optional `note`. You may also pass flat
`code_before` / `code_after` strings instead of the object. Keep snippets short
and real — the exact lines to change. For problems that aren't code (page weight,
slow LCP), skip `code` and rely on the mitigation steps.

## `other_findings`

```json
"other_findings": [
  {"title": "SEO score 100 vs checklist failures", "detail": "Not a contradiction: Lighthouse runs a limited set of checks…"}
]
```

Small context cards for findings that need nuance rather than a fix (domain age,
score-vs-reality, a genuine strength, etc.).

## `link_audit`

```json
"link_audit": {
  "available": true,
  "note": "A crawler error doesn't always mean a broken editorial link — verify first.",
  "stats": [
    {"name": "Reported broken", "value": 10, "note": "Workbook label", "band": "bad"},
    {"name": "Reported valid", "value": 710, "note": "Workbook label", "band": "good"}
  ],
  "error_mix": [{"label": "404 Not Found", "count": 4, "band": "warn"}, {"label": "403 Forbidden", "count": 3, "band": "bad"}],
  "broken": [{"code": "404", "status": "Not Found", "url": "https://…", "source": "Article body", "action": "Confirm in browser; repair or redirect."}],
  "redirects": [{"url": "https://a → https://b", "source": "Footer", "recommendation": "Update internal link to final URL."}],
  "triage": [{"step": "1 · Identify", "note": "Internal or external?"}, ...]
}
```

Renders stat cards, an error-mix bar chart, a triage-workflow flow, and
searchable broken-link + redirect registers. Map Sheet 3 (links & status) into
`broken`/`redirects`. `triage` has a sensible default. Keep the honest framing:
third-party 403/429 is often bot protection, not a broken link.

## `roadmap`

```json
"roadmap": {
  "now":  [{"title": "Diagnose TBT", "detail": "Capture a trace…", "impact": "P1"}],
  "next": [{"title": "Improve originality", "detail": "Review matches…", "impact": "P2"}],
  "acceptance": [{"workstream": "Performance", "evidence": "Repeated Lighthouse tests show lower TBT…", "owner": "Frontend"}]
}
```

Two horizon cards (Now · 0-2 days / Next · 1-2 weeks) built from prioritised
tasks, plus an acceptance-criteria table (what success looks like + a suggested
owner). `impact` is `P1`/`P2`/`P3` (or High/Medium/Low).

## `screenshots`

```json
"screenshots": [
  {"path": "lighthouse.png", "kind": "lighthouse", "title": "Snapshot 1 — Lighthouse", "caption": "Performance 70, SEO 100"},
  {"path": "snap_page.jpg", "annotated": true, "title": "Snapshot 2 — Article", "caption": "6 images missing alt text (red)"}
]
```

All go in the evidence gallery as cards. `annotated: true` adds an "Issues
highlighted" badge. `kind: "lighthouse"` tags it as Lighthouse evidence. The
builder base64-embeds each image (self-contained). Include the Lighthouse
screenshot *and* annotated page snapshots from `snapshot.py`.

**Highlighting a problem inside an image** — to point at *where* a problem is
(e.g. ring the failing metric on the Lighthouse screenshot, or a problem area on
a supplied page capture), run `scripts/annotate_image.py` first to draw labelled
boxes, then embed the annotated copy with `annotated: true`:

```bash
python scripts/annotate_image.py lighthouse.png -o lh_annotated.png --boxes '[
  {"x":33,"y":7.3,"w":13,"h":3.4,"label":"Performance 28 — poor","color":"red"},
  {"x":51,"y":12.9,"w":13,"h":1.9,"label":"LCP 6.7s — poor","color":"red"},
  {"x":51,"y":14.4,"w":12,"h":1.9,"label":"CLS 0.473 — poor","color":"red"}
]'
```

Boxes use **percentages** of the image size (`x`,`y` = top-left; `w`,`h` =
width/height, all 0-100), so read the coordinates off the image by eye — no need
to know its pixel size. `color` is `red`/`amber`/`green`/`blue`. Each box gets a
numbered badge and a legend. `snapshot.py` already annotates live page captures;
`annotate_image.py` is for highlighting a problem on any image you *didn't*
capture live, above all the supplied Lighthouse/PageSpeed screenshot.

## `definitions` and `limitations`

```json
"definitions": [{"term": "Google Business Profile", "definition": "Your free local listing…"}],
"limitations": ["On-page signals measured directly…", "Off-page data is supplied, not re-tested…"]
```

The builder includes a default glossary (Lighthouse score, CWV, LCP, INP, CLS,
TBT, robots.txt, canonical, HTTP 403/404) and default limitations; anything here
is appended/overrides. Keep the limitations honest — name what wasn't supplied
and don't fabricate conclusions for it.

## `sections`

`{lighthouse: {commentary}, ...}` — short framing text for a section. Currently
`lighthouse` is used for the scorecard interpretation; others are available for
future use. Keep commentary tight — the visuals carry the weight.
