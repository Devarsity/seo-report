---
name: seo-report
description: >-
  Generate a professional, agency-grade, self-contained HTML SEO audit report
  for a website. Use whenever someone wants to analyze, audit, check, score, or
  report on a site's SEO — phrases like "SEO report", "SEO audit", "check my
  site's SEO", "seo report in html", or when they hand over a page/site URL
  (optionally with an Excel SEO checklist and a Lighthouse screenshot) and want
  it evaluated. Produces a visualization-heavy deliverable: sidebar navigation, a
  gradient hero, Lighthouse score rings, Core Web Vitals threshold cards, a
  searchable SEO checklist, per-failure deep-dive cards that evaluate the user's
  own fix and add the correct SEO resolution, a link audit with charts and
  registers, a Now/Next action roadmap, an evidence gallery of embedded
  Lighthouse + annotated page screenshots, and definitions/limitations. Output is
  one standalone HTML file that opens, prints and shares anywhere. Reach for this
  even if they don't say "report" but clearly want their search health assessed.
---

# SEO Report Generator

This skill turns a URL (plus whatever extras the user has — an Excel checklist, a
Lighthouse screenshot) into a single, professional HTML report in the style of a
real agency deliverable. Guiding principles, learned the hard way:

- **Visual first.** The report must *show* results — score rings, threshold
  cards, charts, registers, annotated screenshots — not bury them in paragraphs.
  Text is for framing; the visuals carry the findings.
- **Evidence vs recommendation, kept separate.** State what was measured, then
  what you recommend. Be honest about what wasn't supplied; never fabricate data
  for a missing input.
- **Evaluate, don't rubber-stamp.** When the user provides their own fixes, your
  value is an honest read — confirm good ones, flag weak or risky ones — then give
  the correct, specific SEO resolution.

The work splits cleanly. Bundled scripts do the mechanical, repeatable parts
(fetching and measuring pages, dumping the spreadsheet, capturing screenshots,
rendering the HTML). You do the judgement. You never hand-write HTML — the
builder keeps every report consistent and lets you spend your effort on thinking.

## What the finished report contains

A navy sidebar with glyph navigation + audit subject; a gradient hero with scope
pills and a Print/Save-PDF button; and numbered sections: **Executive summary**
(stat cards + top signals + audit scope + caveat), **Lighthouse scorecard**
(rings + comparison bars + interpretation), **Core Web Vitals** (metric cards
with thresholds + pass-criteria + remediation + caveat), **SEO checklist**
(searchable table), **Failed checks** (deep-dive cards: what it means → workbook
solution → your evaluation → recommended SEO resolution) + other findings,
**Link audit** (stats + error-mix bars + triage + broken/redirect registers),
**Action roadmap** (Now/Next + acceptance criteria), **Evidence gallery**
(embedded Lighthouse + annotated snapshots), and **Definitions, methodology &
limitations**.

## Bundled scripts

- `scripts/audit.py` — fetches the live page (or crawls a few pages), measures
  every on-page/technical signal, checks robots.txt/sitemap, scores it → JSON.
- `scripts/read_xlsx.py` — dumps the user's Excel checklist to JSON so you can
  read it without guessing its layout.
- `scripts/snapshot.py` — captures a *live* page screenshot and outlines on-page
  issues (missing alt, H1 problems) with numbered badges + a legend. Needs Playwright.
- `scripts/annotate_image.py` — draws labelled highlight boxes on *any* image
  (percentage coordinates) to point at where a problem is — e.g. ring the failing
  metric on the supplied Lighthouse screenshot. Needs Pillow.
- `scripts/build_report.py` — renders the final visual HTML from the audit JSON
  plus the `insights.json` you write.

## The flow

### 1. Settle inputs and scope

You need at least **one URL**. Collect whatever else the user has:

- a **page URL** (the specific page audited) and the **site URL** — often both,
- an **Excel SEO checklist** (statuses, and their solutions for failed items),
- a **Lighthouse / PageSpeed screenshot** (for performance + Core Web Vitals),
- any **off-page figures** (backlinks, Domain Rating) they want included.

One choice changes the run, so confirm it unless it's already obvious:

> **Single page, or the whole site?** Single audits only the given URL (fast).
> Whole-site crawls internal links (~15 pages) and adds crawl-wide aggregates.

If they said "my homepage" or gave one article → single. "My site" / "crawl it"
→ site. Ambiguous → ask; it's one line. Everything else is optional — don't
block on it, just note in the report where a section is empty and how to fill it.

### 2. Install dependencies (once)

```bash
pip install --break-system-packages requests beautifulsoup4 lxml openpyxl pillow
python -m playwright install chromium   # only if snapshots are wanted
```

### 3. Run the audit

```bash
python scripts/audit.py "<page-url>" -o audit.json                 # single
python scripts/audit.py "<url>" --mode site --max-pages 15 -o audit.json   # whole site
```

Add `--blog "<blog-url>"` to include a blog page, or `--check-links` to HEAD-check
outbound links (slower). **If the fetch fails** (blocked, timeout, 404), the JSON
carries the error — don't invent findings for a page you couldn't read. Say what
failed; offer a corrected URL if it looks like a typo.

### 4. Read the Excel checklist (if provided)

```bash
python scripts/read_xlsx.py "<checklist.xlsx>" -o workbook.json
```

Read the output. Map the rows into two places in `insights.json`:
- the `checklist` block — every item's status + the user's solution + your SEO
  interpretation (the searchable table), and
- the `failed_checks` block — one deep-dive card per failed/notable item, with
  "what it means", the workbook solution, **your honest evaluation of it**, a
  recommended **SEO resolution** (ordered mitigation steps), and — whenever the
  problem is code-level — a `code` block showing the **offending code and the
  corrected version** (rendered as highlighted before/after snippets). Add
  `code` for anything expressible in markup/config: missing alt, unlabeled
  inputs, untitled iframes, missing width/height, non-descriptive anchors, a
  broken robots.txt line, a missing canonical, a meta/schema snippet, etc.

If a sheet holds links/redirects and statuses (often Sheet 3), map it into the
`link_audit` block (`broken` and `redirects`). The failed-checks deep dives are
usually what the user cares about most — see the schema reference for the exact
shape of each field.

### 5. Read the Lighthouse screenshot (if provided)

Look at the image and pull out the four ring scores (Performance, Accessibility,
Best Practices, SEO) and the metrics (LCP, FCP, TBT, CLS, Speed Index, INP). Note
whether it's mobile or desktop. Fill the `lighthouse` block (ring scores) **and**
the `core_web_vitals` block (numeric values + ratings) — the report plots the
vitals against Google's thresholds, so give numbers, not strings. No screenshot
→ set both `"available": false`; never fabricate performance data.

### 6. Capture annotated snapshots

The user wants the report to *show* problems on the page. For the audited page —
and any other page with notable issues (e.g. the one missing alt text) — capture
an annotated screenshot:

```bash
python scripts/snapshot.py "<page-url>" -o snap_page.jpg --mode desktop
```

It outlines issues and prints what it flagged. Add each image to the
`screenshots` block with a caption and `annotated: true`. **If Playwright isn't
available or the capture fails** (it prints `PLAYWRIGHT_MISSING` / `SNAPSHOT_FAILED`),
that's fine — embed any screenshots the user supplied instead, and note that live
snapshots weren't captured. Also add the Lighthouse screenshot to `screenshots`
with `kind: "lighthouse"` so it's embedded in the performance section.

**Highlight the problem inside the supplied image.** The user wants to *see*
where each problem is. For the Lighthouse/PageSpeed screenshot (which you can't
re-capture), ring the failing items with `annotate_image.py` — read the box
coordinates off the image as percentages and label each one:

```bash
python scripts/annotate_image.py lighthouse.png -o lh_annotated.png --boxes '[
  {"x":33,"y":7.3,"w":13,"h":3.4,"label":"Performance 28 — poor","color":"red"},
  {"x":51,"y":12.9,"w":13,"h":1.9,"label":"LCP 6.7s — poor","color":"red"}
]'
```

Embed the annotated copy with `annotated: true`. This is the "highlight the image
where the problem is" part — use it on the Lighthouse screenshot and on any
supplied page capture.

### 7. Write `insights.json`

This is where your judgement goes. Read `audit.json` and `workbook.json` first,
then write the file. The full annotated schema and worked examples are in
`references/insights-schema.md` — **read it** before writing, since the blocks
(`executive_summary` stats/top-signals, `core_web_vitals` numeric metrics,
`failed_checks` deep dives, `link_audit` registers, `roadmap` Now/Next +
acceptance) each have specific shapes the builder depends on.

Aim to fill every block you have evidence for — the report's strength is its
depth. Supply `scores` for `technical` and `off_page` yourself (the script only
scores on-page/content). Keep commentary tight — the visuals do the talking.

### 8. Build the report

```bash
python scripts/build_report.py --data audit.json --insights insights.json -o seo-report.html
```

It prints the blended health score and file size, and writes one standalone HTML
file with everything described in "What the finished report contains" above —
sidebar nav, hero, Lighthouse rings, CWV cards, searchable checklist, failed-check
deep dives, link registers, roadmap, evidence gallery and definitions. Section
numbers and the sidebar adjust automatically to whichever blocks you supplied.
Everything is inlined (images base64-embedded) — no network, no dependencies —
and it prints cleanly via the Print/Save-PDF button.

### 9. Deliver

Hand over `seo-report.html`. Give a one or two sentence headline — the single
most important finding — not a recap of every section; the report is detailed on
purpose and speaks for itself.

## What makes a good report here

- **Visual first.** Lean on the rings, cards, charts and registers. If you're
  writing a long paragraph, the substance probably belongs in a stat, a checklist
  row, a failed-check card or a roadmap item instead.
- **Evaluate, don't rubber-stamp.** For each of the user's own fixes, give an
  honest read — confirm good ones, flag weak or risky ones ("too broad", "verify
  first") — then the concrete SEO resolution. Agreeing with everything helps no one.
- **Specific and grounded.** Every recommendation ties to a real finding and says
  what to change and why. "Compress the hero to pull LCP under 2.5s" beats
  "improve performance".
- **Honest about scope.** On-page/technical is measured directly. Performance is
  whatever Lighthouse run they gave you; Core Web Vitals field metrics (INP
  especially) usually aren't in a lab screenshot — say "field data needed" rather
  than inventing a number. Off-page and checklist data are supplied, not
  re-tested. SEO is probabilistic; the limitations section says so — keep that
  framing in your own words too.
- **Self-contained.** The builder inlines everything and adds only a tiny filter
  script. Never add external fonts, scripts or CDN links — the point is one file
  that works offline.
