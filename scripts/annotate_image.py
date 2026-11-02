#!/usr/bin/env python3
"""
annotate_image.py — Draw labelled highlight boxes on any screenshot.

Use it to point at *where* a problem is in an image: ring the failing metric on a
Lighthouse screenshot, or outline a problem area on a page capture. Boxes are
given in percentages of the image size (0-100), so you can read coordinates off
the image at any resolution without knowing its pixel dimensions.

Each box gets a coloured rectangle + a numbered badge; a legend lists what each
number means. The result is a size-optimised image ready to embed in the report
(add it to the `screenshots` block with `annotated: true`).

Boxes are passed as JSON, either inline or from a file:

    python annotate_image.py lighthouse.png -o lh_annot.png --boxes '[
      {"x":46,"y":30,"w":9,"h":6,"label":"LCP 6.7s — poor","color":"red"},
      {"x":46,"y":40,"w":9,"h":6,"label":"CLS 0.473 — poor","color":"red"}
    ]'

    python annotate_image.py page.png -o page_annot.png --boxes-file boxes.json

Box fields: x, y (top-left, % of width/height), w, h (% of width/height),
label (text), color (red|amber|green|blue, default red). label is optional.
"""

import argparse
import json
import sys

try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError:
    sys.exit("Install Pillow:\n  pip install --break-system-packages pillow")

COLORS = {
    "red": (225, 29, 72), "amber": (217, 119, 6), "green": (22, 134, 91),
    "blue": (37, 99, 235), "purple": (114, 87, 213),
}


def load_font(size):
    for path in ("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
                 "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"):
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            continue
    return ImageFont.load_default()


def text_size(draw, text, font):
    box = draw.textbbox((0, 0), text, font=font)
    return box[2] - box[0], box[3] - box[1]


def annotate(img_path, boxes, out_path, max_w=1400):
    im = Image.open(img_path).convert("RGB")
    W, H = im.size
    draw = ImageDraw.Draw(im, "RGBA")
    badge_font = load_font(max(14, W // 70))
    legend_font = load_font(max(13, W // 85))

    line_w = max(3, W // 400)
    legend_rows = []
    for i, b in enumerate(boxes, 1):
        col = COLORS.get(str(b.get("color", "red")).lower(), COLORS["red"])
        x0 = W * float(b.get("x", 0)) / 100
        y0 = H * float(b.get("y", 0)) / 100
        x1 = x0 + W * float(b.get("w", 10)) / 100
        y1 = y0 + H * float(b.get("h", 8)) / 100
        # translucent fill + solid border
        draw.rectangle([x0, y0, x1, y1], fill=col + (38,), outline=col, width=line_w)
        # numbered badge at the top-left corner
        r = max(14, W // 90)
        bx, by = x0, y0
        draw.ellipse([bx - r, by - r, bx + r, by + r], fill=col)
        num = str(i)
        tw, th = text_size(draw, num, badge_font)
        draw.text((bx - tw / 2, by - th / 2 - 1), num, fill=(255, 255, 255), font=badge_font)
        if b.get("label"):
            legend_rows.append((i, col, b["label"]))

    # Legend panel (top-left), only if any labels
    if legend_rows:
        pad = max(12, W // 90)
        gap = max(6, W // 180)
        rows_txt = [f"{i}. {lab}" for i, _, lab in legend_rows]
        tw = max(text_size(draw, t, legend_font)[0] for t in rows_txt)
        row_h = text_size(draw, "Ag", legend_font)[1] + gap
        box_w = tw + pad * 2 + row_h
        box_h = pad * 2 + row_h * len(legend_rows) + text_size(draw, "Ag", legend_font)[1]
        draw.rectangle([pad, pad, pad + box_w, pad + box_h], fill=(17, 24, 39, 235))
        draw.text((pad * 1.6, pad * 1.4), "Flagged issues", fill=(170, 190, 215), font=legend_font)
        y = pad * 1.4 + row_h
        for i, col, lab in legend_rows:
            sw = text_size(draw, "Ag", legend_font)[1]
            draw.rectangle([pad * 1.6, y + 2, pad * 1.6 + sw * 0.8, y + 2 + sw * 0.8], fill=col)
            draw.text((pad * 1.6 + sw, y), f"{i}. {lab}", fill=(240, 244, 248), font=legend_font)
            y += row_h

    if im.width > max_w:
        im = im.resize((max_w, round(im.height * max_w / im.width)), Image.LANCZOS)
    ext = out_path.lower().rsplit(".", 1)[-1]
    if ext in ("jpg", "jpeg"):
        im.save(out_path, "JPEG", quality=85, optimize=True)
    else:
        im.save(out_path, "PNG", optimize=True)
    return im.size


def main():
    ap = argparse.ArgumentParser(description="Draw labelled highlight boxes on an image.")
    ap.add_argument("image")
    ap.add_argument("-o", "--output", required=True)
    ap.add_argument("--boxes", help="Inline JSON array of boxes")
    ap.add_argument("--boxes-file", help="Path to a JSON file with the boxes array")
    args = ap.parse_args()

    if args.boxes_file:
        with open(args.boxes_file) as f:
            boxes = json.load(f)
    elif args.boxes:
        boxes = json.loads(args.boxes)
    else:
        sys.exit("Provide --boxes '<json>' or --boxes-file <path>")

    if not isinstance(boxes, list) or not boxes:
        sys.exit("Boxes must be a non-empty JSON array.")

    size = annotate(args.image, boxes, args.output)
    print(json.dumps({"output": args.output, "size": list(size),
                      "boxes_drawn": len(boxes)}, indent=2))


if __name__ == "__main__":
    main()
