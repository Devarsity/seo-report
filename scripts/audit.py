#!/usr/bin/env python3
"""
audit.py — Collect on-page / technical SEO signals from a live site.

Fetches one page (single mode) or crawls a handful of same-domain pages
(site mode), parses the HTML, checks robots.txt and sitemap.xml, runs a set
of deterministic SEO checks with severities, computes per-category and overall
scores, and writes everything to a compact JSON file.

This script does the mechanical, repeatable part of an audit so the model can
spend its attention on judgement (writing the summary, prioritising fixes,
reading the Lighthouse screenshot). It is intentionally dependency-light and
honours standard proxy / CA environment variables (HTTPS_PROXY,
REQUESTS_CA_BUNDLE), so it runs the same inside a sandbox or on a normal box.

Usage:
    python audit.py https://example.com -o data.json
    python audit.py https://example.com --blog https://example.com/blog -o data.json
    python audit.py https://example.com --mode site --max-pages 20 -o data.json
    python audit.py https://example.com --check-links -o data.json   # slower

Only --mode site crawls; the default (single) audits just the given URL(s).
"""

import argparse
import json
import re
import sys
import time
from collections import Counter
from urllib.parse import urljoin, urlparse, urldefrag

try:
    import requests
except ImportError:
    sys.exit("Missing dependency. Install with:\n"
             "  pip install --break-system-packages requests beautifulsoup4 lxml")

try:
    from bs4 import BeautifulSoup
except ImportError:
    sys.exit("Missing dependency. Install with:\n"
             "  pip install --break-system-packages requests beautifulsoup4 lxml")

UA = ("Mozilla/5.0 (compatible; SEOReportBot/1.0; "
      "+https://example.com/bot) AppleWebKit/537.36")
HEADERS = {"User-Agent": UA, "Accept": "text/html,application/xhtml+xml"}
TIMEOUT = 20

# ----------------------------------------------------------------------------
# Thresholds — the commonly cited "good" ranges. Kept here so they're easy to
# see and adjust rather than buried in the logic.
# ----------------------------------------------------------------------------
TITLE_MIN, TITLE_MAX = 30, 60           # characters
DESC_MIN, DESC_MAX = 70, 160            # characters
THIN_CONTENT_WORDS = 300                # below this, a page reads as thin


def fetch(url, session, allow_redirects=True):
    """Return (response, error). response is None on failure."""
    try:
        t0 = time.time()
        r = session.get(url, headers=HEADERS, timeout=TIMEOUT,
                         allow_redirects=allow_redirects)
        r._elapsed_ms = int((time.time() - t0) * 1000)
        return r, None
    except requests.RequestException as e:
        return None, str(e)


def text_of(el):
    return el.get_text(" ", strip=True) if el else ""


def analyse_page(url, resp, soup):
    """Pull the on-page signals out of one parsed page."""
    p = {"url": url, "final_url": resp.url, "status_code": resp.status_code,
         "fetch_ms": getattr(resp, "_elapsed_ms", None),
         "html_bytes": len(resp.content)}

    # Grab JSON-LD strings up front: the word-count step below strips <script>
    # tags out of the soup, so reading them afterwards would find nothing.
    ld_scripts = [s.string for s in soup.find_all("script", type="application/ld+json")]

    # Title
    title_el = soup.find("title")
    title = text_of(title_el)
    p["title"] = title
    p["title_length"] = len(title)

    # Meta description + robots
    desc = ""
    meta_robots = ""
    for m in soup.find_all("meta"):
        name = (m.get("name") or "").lower()
        if name == "description":
            desc = (m.get("content") or "").strip()
        elif name == "robots":
            meta_robots = (m.get("content") or "").strip().lower()
    p["meta_description"] = desc
    p["meta_description_length"] = len(desc)
    p["meta_robots"] = meta_robots
    p["x_robots_tag"] = resp.headers.get("X-Robots-Tag", "")

    # Canonical, lang, viewport, charset
    canonical = soup.find("link", rel=lambda v: v and "canonical" in v)
    p["canonical"] = canonical.get("href", "") if canonical else ""
    html_tag = soup.find("html")
    p["lang"] = (html_tag.get("lang") if html_tag else "") or ""
    p["has_viewport"] = bool(soup.find("meta", attrs={"name": "viewport"}))
    charset_meta = soup.find("meta", charset=True)
    p["charset"] = charset_meta.get("charset") if charset_meta else ""

    # Heading outline
    headings = []
    for lvl in range(1, 7):
        for h in soup.find_all(f"h{lvl}"):
            headings.append({"level": lvl, "text": text_of(h)[:120]})
    p["headings"] = headings[:60]
    p["h1_count"] = sum(1 for h in headings if h["level"] == 1)
    p["h1_text"] = [h["text"] for h in headings if h["level"] == 1][:5]

    # Visible word count (drop script/style/noscript)
    body = soup.find("body")
    for junk in soup(["script", "style", "noscript"]):
        junk.extract()
    visible = text_of(body if body else soup)
    words = re.findall(r"\b\w+\b", visible)
    p["word_count"] = len(words)

    # Images / alt coverage
    imgs = soup.find_all("img")
    missing_alt = [i.get("src", "") for i in imgs
                   if not (i.get("alt") or "").strip()]
    p["images_total"] = len(imgs)
    p["images_missing_alt"] = len(missing_alt)
    p["images_missing_alt_samples"] = [s for s in missing_alt if s][:10]

    # Links
    host = urlparse(resp.url).netloc
    internal, external, nofollow = 0, 0, 0
    link_targets = []
    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        if href.startswith(("#", "mailto:", "tel:", "javascript:")):
            continue
        absolute = urljoin(resp.url, href)
        netloc = urlparse(absolute).netloc
        if netloc == host:
            internal += 1
        else:
            external += 1
        rel = " ".join(a.get("rel", [])).lower()
        if "nofollow" in rel:
            nofollow += 1
        link_targets.append(absolute)
    p["links_internal"] = internal
    p["links_external"] = external
    p["links_nofollow"] = nofollow
    p["_link_targets"] = link_targets  # used by the crawler; stripped later

    # Social cards
    og = {m.get("property", ""): m.get("content", "")
          for m in soup.find_all("meta", property=re.compile(r"^og:"))}
    tw = {m.get("name", ""): m.get("content", "")
          for m in soup.find_all("meta", attrs={"name": re.compile(r"^twitter:")})}
    p["og_title"] = bool(og.get("og:title"))
    p["og_description"] = bool(og.get("og:description"))
    p["og_image"] = bool(og.get("og:image"))
    p["twitter_card"] = bool(tw.get("twitter:card"))

    # Structured data (JSON-LD @type values)
    ld_types = []
    for s in ld_scripts:
        try:
            data = json.loads(s or "")
        except (json.JSONDecodeError, TypeError):
            continue
        for node in (data if isinstance(data, list) else [data]):
            if isinstance(node, dict):
                t = node.get("@type")
                if isinstance(t, list):
                    ld_types.extend(t)
                elif t:
                    ld_types.append(t)
    p["structured_data_types"] = ld_types

    # hreflang + favicon
    p["hreflang_count"] = len(soup.find_all("link", rel="alternate",
                                            hreflang=True))
    p["has_favicon"] = bool(soup.find("link", rel=lambda v: v and "icon" in v))

    # Transport signals
    p["https"] = resp.url.startswith("https://")
    p["gzip"] = "gzip" in resp.headers.get("Content-Encoding", "").lower() or \
                "br" in resp.headers.get("Content-Encoding", "").lower()
    p["hsts"] = bool(resp.headers.get("Strict-Transport-Security"))
    return p


def run_checks(page):
    """Turn raw signals into graded checks. Each: id, label, status, severity,
    detail. status in pass|warn|fail; severity in high|medium|low."""
    c = []

    def add(cid, label, status, severity, detail=""):
        c.append({"id": cid, "label": label, "status": status,
                  "severity": severity, "detail": detail})

    # --- On-page / technical ---
    tl = page["title_length"]
    if tl == 0:
        add("title", "Title tag present", "fail", "high", "No <title> tag found.")
    elif tl < TITLE_MIN:
        add("title", "Title length", "warn", "medium",
            f"Title is {tl} chars — short. Aim for {TITLE_MIN}-{TITLE_MAX}.")
    elif tl > TITLE_MAX:
        add("title", "Title length", "warn", "medium",
            f"Title is {tl} chars — may truncate in search. Aim for <= {TITLE_MAX}.")
    else:
        add("title", "Title length", "pass", "medium", f"{tl} chars.")

    dl = page["meta_description_length"]
    if dl == 0:
        add("meta_desc", "Meta description present", "fail", "high",
            "No meta description — search engines will auto-generate the snippet.")
    elif dl < DESC_MIN or dl > DESC_MAX:
        add("meta_desc", "Meta description length", "warn", "medium",
            f"{dl} chars — outside the {DESC_MIN}-{DESC_MAX} sweet spot.")
    else:
        add("meta_desc", "Meta description length", "pass", "medium", f"{dl} chars.")

    if page["h1_count"] == 0:
        add("h1", "Single clear H1", "fail", "high", "No H1 on the page.")
    elif page["h1_count"] > 1:
        add("h1", "Single clear H1", "warn", "low",
            f"{page['h1_count']} H1s — usually one is cleaner.")
    else:
        add("h1", "Single clear H1", "pass", "medium", "Exactly one H1.")

    if not page["canonical"]:
        add("canonical", "Canonical URL", "warn", "medium",
            "No canonical link — add one to prevent duplicate-content dilution.")
    else:
        add("canonical", "Canonical URL", "pass", "low", page["canonical"])

    if "noindex" in page["meta_robots"] or "noindex" in page["x_robots_tag"].lower():
        add("indexable", "Indexable", "fail", "high",
            "Page is set to noindex — it will be kept out of search results.")
    else:
        add("indexable", "Indexable", "pass", "high", "No noindex directive.")

    if not page["https"]:
        add("https", "Served over HTTPS", "fail", "high", "Page is not HTTPS.")
    else:
        add("https", "Served over HTTPS", "pass", "high", "")

    if not page["has_viewport"]:
        add("viewport", "Mobile viewport tag", "fail", "high",
            "No viewport meta — the page won't scale on phones.")
    else:
        add("viewport", "Mobile viewport tag", "pass", "medium", "")

    if not page["lang"]:
        add("lang", "Language declared", "warn", "low",
            "No lang attribute on <html>.")
    else:
        add("lang", "Language declared", "pass", "low", page["lang"])

    # --- Content & keywords ---
    wc = page["word_count"]
    if wc < THIN_CONTENT_WORDS:
        add("content_depth", "Content depth", "warn", "medium",
            f"~{wc} words — thin. Pages under {THIN_CONTENT_WORDS} words often "
            "struggle to rank.")
    else:
        add("content_depth", "Content depth", "pass", "low", f"~{wc} words.")

    if page["images_total"] and page["images_missing_alt"]:
        ratio = page["images_missing_alt"] / page["images_total"]
        status = "fail" if ratio > 0.5 else "warn"
        add("img_alt", "Image alt text", status, "medium",
            f"{page['images_missing_alt']} of {page['images_total']} images "
            "have no alt text.")
    elif page["images_total"]:
        add("img_alt", "Image alt text", "pass", "low",
            "All images have alt text.")

    # --- Social / sharing ---
    if page["og_title"] and page["og_description"] and page["og_image"]:
        add("open_graph", "Open Graph tags", "pass", "low", "")
    else:
        add("open_graph", "Open Graph tags", "warn", "low",
            "Incomplete Open Graph tags — shared links may render poorly.")

    # --- Structured data ---
    if page["structured_data_types"]:
        add("schema", "Structured data", "pass", "low",
            ", ".join(sorted(set(page["structured_data_types"]))))
    else:
        add("schema", "Structured data", "warn", "low",
            "No JSON-LD schema — rich results won't be eligible.")

    return c


# Which checks belong to which report category, for scoring.
CATEGORY_MAP = {
    "on_page": ["title", "meta_desc", "h1", "canonical", "indexable", "https",
                "viewport", "lang", "schema"],
    "content": ["content_depth", "img_alt", "open_graph"],
}
STATUS_SCORE = {"pass": 1.0, "warn": 0.5, "fail": 0.0}
SEVERITY_WEIGHT = {"high": 3, "medium": 2, "low": 1}


def score_category(checks, ids):
    rel = [c for c in checks if c["id"] in ids]
    if not rel:
        return None
    num = sum(STATUS_SCORE[c["status"]] * SEVERITY_WEIGHT[c["severity"]] for c in rel)
    den = sum(SEVERITY_WEIGHT[c["severity"]] for c in rel)
    return round(100 * num / den) if den else None


def fetch_robots_and_sitemap(base, session):
    out = {}
    root = f"{urlparse(base).scheme}://{urlparse(base).netloc}"
    r, _ = fetch(urljoin(root, "/robots.txt"), session)
    if r is not None and r.status_code == 200 and "text" in r.headers.get("Content-Type", ""):
        out["robots_txt_present"] = True
        sm = re.findall(r"(?im)^\s*sitemap:\s*(\S+)", r.text)
        out["robots_sitemaps"] = sm[:10]
        out["robots_has_disallow"] = bool(re.search(r"(?im)^\s*disallow:\s*\S", r.text))
    else:
        out["robots_txt_present"] = False
        out["robots_sitemaps"] = []
    sitemap_url = (out.get("robots_sitemaps") or [None])[0] or urljoin(root, "/sitemap.xml")
    r, _ = fetch(sitemap_url, session)
    if r is not None and r.status_code == 200:
        out["sitemap_present"] = True
        out["sitemap_url"] = sitemap_url
        out["sitemap_url_count"] = len(re.findall(r"<loc>", r.text))
    else:
        out["sitemap_present"] = False
    return out


def crawl(start, session, max_pages):
    """BFS over same-domain internal links starting from `start`."""
    host = urlparse(start).netloc
    seen, queue, pages, broken_internal = set(), [start], [], []
    while queue and len(pages) < max_pages:
        url = urldefrag(queue.pop(0))[0]
        if url in seen:
            continue
        seen.add(url)
        r, err = fetch(url, session)
        if r is None:
            broken_internal.append({"url": url, "status": "error"})
            continue
        if r.status_code >= 400:
            broken_internal.append({"url": url, "status": r.status_code})
            continue
        if "html" not in r.headers.get("Content-Type", "").lower():
            continue
        soup = BeautifulSoup(r.content, "html.parser")
        page = analyse_page(url, r, soup)
        page["checks"] = run_checks(page)
        for target in page.pop("_link_targets", []):
            t = urldefrag(target)[0]
            if urlparse(t).netloc == host and t not in seen and t not in queue:
                queue.append(t)
        pages.append(page)
    return pages, broken_internal


def check_broken_links(pages, session, cap=40):
    """HEAD a sample of outbound targets; record ones that fail."""
    checked, broken = set(), []
    for pg in pages:
        for target in pg.get("_link_targets", [])[:cap]:
            if target in checked or len(checked) >= cap:
                continue
            checked.add(target)
            try:
                r = session.head(target, headers=HEADERS, timeout=10,
                                 allow_redirects=True)
                if r.status_code >= 400:
                    broken.append({"url": target, "status": r.status_code})
            except requests.RequestException:
                broken.append({"url": target, "status": "error"})
    return broken


def site_aggregates(pages):
    titles = Counter(p["title"] for p in pages if p["title"])
    descs = Counter(p["meta_description"] for p in pages if p["meta_description"])
    return {
        "pages_crawled": len(pages),
        "missing_title": sum(1 for p in pages if not p["title"]),
        "missing_meta_desc": sum(1 for p in pages if not p["meta_description"]),
        "missing_h1": sum(1 for p in pages if p["h1_count"] == 0),
        "thin_content": sum(1 for p in pages if p["word_count"] < THIN_CONTENT_WORDS),
        "duplicate_titles": sum(n for n in titles.values() if n > 1),
        "duplicate_meta_desc": sum(n for n in descs.values() if n > 1),
        "noindex_pages": sum(1 for p in pages
                             if "noindex" in p["meta_robots"]),
    }


def main():
    ap = argparse.ArgumentParser(description="Collect on-page SEO signals.")
    ap.add_argument("url", help="Site or page URL to audit")
    ap.add_argument("--blog", help="Optional blog URL to audit too")
    ap.add_argument("--mode", choices=["single", "site"], default="single")
    ap.add_argument("--max-pages", type=int, default=15)
    ap.add_argument("--check-links", action="store_true",
                    help="Also HEAD-check outbound links (slower).")
    ap.add_argument("-o", "--output", default="data.json")
    args = ap.parse_args()

    session = requests.Session()
    result = {"input_url": args.url, "blog_url": args.blog, "mode": args.mode,
              "generated_ms": int(time.time() * 1000), "errors": []}

    if args.mode == "site":
        pages, broken_internal = crawl(args.url, session, args.max_pages)
        if broken_internal:
            result["broken_internal_links"] = broken_internal
        if not pages:
            result["errors"].append(f"Could not crawl {args.url}")
    else:
        pages = []
        for u in [args.url, args.blog]:
            if not u:
                continue
            r, err = fetch(u, session)
            if r is None:
                result["errors"].append(f"{u}: {err}")
                continue
            soup = BeautifulSoup(r.content, "html.parser")
            page = analyse_page(u, r, soup)
            page["checks"] = run_checks(page)
            pages.append(page)

    if args.check_links and pages:
        result["broken_links"] = check_broken_links(pages, session)

    # Strip the internal link lists before serialising.
    for p in pages:
        p.pop("_link_targets", None)

    result["site"] = fetch_robots_and_sitemap(args.url, session)
    if args.mode == "site":
        result["site"].update(site_aggregates(pages))

    # Scores: primary page drives the headline numbers.
    if pages:
        primary = pages[0]
        checks = primary["checks"]
        result["scores"] = {
            "on_page": score_category(checks, CATEGORY_MAP["on_page"]),
            "content": score_category(checks, CATEGORY_MAP["content"]),
        }
        valid = [v for v in result["scores"].values() if v is not None]
        result["scores"]["overall_onpage"] = round(sum(valid) / len(valid)) if valid else None

    result["pages"] = pages
    with open(args.output, "w") as f:
        json.dump(result, f, indent=2)

    # Short human-readable summary to stdout for the model.
    print(f"Audited {len(pages)} page(s), mode={args.mode}.")
    if pages:
        fails = [c for c in pages[0]["checks"] if c["status"] == "fail"]
        warns = [c for c in pages[0]["checks"] if c["status"] == "warn"]
        print(f"Primary page: {len(fails)} failures, {len(warns)} warnings.")
        if result.get("scores"):
            print(f"On-page score: {result['scores'].get('overall_onpage')}/100")
    if result["errors"]:
        print("Errors:", "; ".join(result["errors"]))
    print(f"Wrote {args.output}")


if __name__ == "__main__":
    main()
