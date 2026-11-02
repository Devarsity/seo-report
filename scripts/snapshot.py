#!/usr/bin/env python3
"""
snapshot.py — Capture a screenshot of a page and outline on-page SEO issues.

Produces an annotated image: images missing alt text get a red outline and a
numbered badge, H1 problems get an amber outline, and a legend in the corner
lists what was flagged. This is what makes the report's snapshots *show* the
problems instead of just describing them.

It needs Playwright + Chromium. If that isn't available, the skill falls back to
embedding whatever screenshots the user supplied — so treat a failure here as
"no live snapshot", not a hard error.

Output is a size-optimised JPEG (capped width, quality 82) so it embeds in the
self-contained HTML without blowing the file size.

Usage:
    python snapshot.py "https://example.com" -o snap.jpg
    python snapshot.py "https://example.com" -o snap.jpg --mode mobile
    python snapshot.py "https://example.com" -o snap.jpg --no-annotate   # clean
"""

import argparse
import json
import sys

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    sys.exit("PLAYWRIGHT_MISSING: Install with:\n"
             "  pip install --break-system-packages playwright && python -m playwright install chromium")

try:
    from PIL import Image
except ImportError:
    Image = None

VIEWPORTS = {
    "desktop": {"width": 1280, "height": 900, "scale": 1},
    "mobile": {"width": 390, "height": 844, "scale": 2},
}

# JS injected into the page: outline problem elements, drop numbered badges,
# add a legend, and return the list of flagged issues.
ANNOTATE_JS = r"""
() => {
  const issues = [];
  let n = 0;
  const legendItems = {};
  const mark = (el, color, label) => {
    const r = el.getBoundingClientRect();
    if (r.width < 4 || r.height < 4) return;          // skip invisible
    n++;
    el.style.setProperty('outline', '3px solid ' + color, 'important');
    el.style.setProperty('outline-offset', '1px', 'important');
    const tag = document.createElement('div');
    tag.textContent = n;
    tag.style.cssText = 'position:absolute;z-index:2147483647;background:' + color +
      ';color:#fff;font:700 13px system-ui,sans-serif;min-width:20px;text-align:center;' +
      'padding:2px 7px;border-radius:12px;box-shadow:0 1px 4px rgba(0,0,0,.4);';
    tag.style.left = (window.scrollX + r.left) + 'px';
    tag.style.top  = (window.scrollY + r.top) + 'px';
    document.body.appendChild(tag);
    issues.push({num: n, type: label});
    legendItems[label] = (legendItems[label] || 0) + 1;
  };

  document.querySelectorAll('img').forEach(img => {
    const alt = (img.getAttribute('alt') || '').trim();
    if (!alt) mark(img, '#e11d48', 'Image missing alt text');
  });

  const h1s = document.querySelectorAll('h1');
  if (h1s.length > 1) h1s.forEach(h => mark(h, '#d97706', 'Multiple H1 tags'));

  // Legend box, pinned at the top of the document.
  const labels = Object.keys(legendItems);
  if (labels.length) {
    const box = document.createElement('div');
    box.style.cssText = 'position:absolute;z-index:2147483647;top:10px;left:10px;' +
      'background:rgba(17,24,39,.94);color:#fff;font:600 13px system-ui,sans-serif;' +
      'padding:12px 16px;border-radius:10px;box-shadow:0 2px 12px rgba(0,0,0,.4);max-width:320px;';
    let html = '<div style="font-size:12px;letter-spacing:.08em;text-transform:uppercase;' +
      'opacity:.7;margin-bottom:6px">Flagged issues</div>';
    const colors = {'Image missing alt text':'#e11d48','Multiple H1 tags':'#d97706'};
    labels.forEach(l => {
      html += '<div style="display:flex;align-items:center;gap:8px;margin:3px 0">' +
        '<span style="width:11px;height:11px;border-radius:3px;background:' +
        (colors[l]||'#999') + ';display:inline-block"></span>' + l +
        ' <span style="opacity:.6">×' + legendItems[l] + '</span></div>';
    });
    box.innerHTML = html;
    document.body.appendChild(box);
  }
  return issues;
}
"""


def autoscroll(page):
    """Scroll to the bottom in steps to trigger lazy-loaded images, then back."""
    try:
        page.evaluate("""async () => {
          await new Promise(res => {
            let y = 0; const step = 600;
            const t = setInterval(() => {
              window.scrollTo(0, y); y += step;
              if (y >= document.body.scrollHeight) { clearInterval(t); res(); }
            }, 60);
          });
        }""")
        page.wait_for_timeout(400)
        page.evaluate("window.scrollTo(0, 0)")
        page.wait_for_timeout(200)
    except Exception:
        pass


def optimise(png_path, out_path, max_w=1100):
    if Image is None:
        return png_path  # leave PNG as-is if PIL unavailable
    im = Image.open(png_path).convert("RGB")
    if im.width > max_w:
        im = im.resize((max_w, round(im.height * max_w / im.width)), Image.LANCZOS)
    # Guard against absurdly tall captures bloating the file.
    max_h = 6000
    if im.height > max_h:
        im = im.crop((0, 0, im.width, max_h))
    im.save(out_path, "JPEG", quality=82, optimize=True)
    return out_path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("url")
    ap.add_argument("-o", "--output", default="snapshot.jpg")
    ap.add_argument("--mode", choices=["desktop", "mobile"], default="desktop")
    ap.add_argument("--no-annotate", action="store_true")
    ap.add_argument("--full-page", action="store_true", default=True)
    args = ap.parse_args()

    vp = VIEWPORTS[args.mode]
    issues = []
    tmp_png = args.output + ".tmp.png"
    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(args=["--no-sandbox"])
            ctx = browser.new_context(
                viewport={"width": vp["width"], "height": vp["height"]},
                device_scale_factor=vp["scale"],
                user_agent=("Mozilla/5.0 (compatible; SEOReportBot/1.0)"))
            page = ctx.new_page()
            try:
                page.goto(args.url, wait_until="networkidle", timeout=30000)
            except Exception:
                page.goto(args.url, wait_until="load", timeout=30000)
            autoscroll(page)
            if not args.no_annotate:
                try:
                    issues = page.evaluate(ANNOTATE_JS) or []
                except Exception as e:
                    print(f"annotate step failed: {e}", file=sys.stderr)
            page.screenshot(path=tmp_png, full_page=args.full_page)
            browser.close()
    except Exception as e:
        sys.exit(f"SNAPSHOT_FAILED: {e}")

    final = optimise(tmp_png, args.output)
    try:
        import os
        if final != tmp_png and os.path.exists(tmp_png):
            os.remove(tmp_png)
    except Exception:
        pass

    print(json.dumps({"output": args.output, "mode": args.mode,
                      "issues_flagged": len(issues), "issues": issues}, indent=2))


if __name__ == "__main__":
    main()
