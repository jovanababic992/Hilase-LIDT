# === Imports ===
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.lib import colors
from PIL import Image
import io, os
from textwrap import wrap
from svglib.svglib import svg2rlg
from reportlab.graphics import renderPDF
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from pathlib import Path
import logging
logging.getLogger("svglib").setLevel(logging.ERROR)


FONT_PATH = Path(__file__).resolve().parents[1] / "assets" / "fonts" / "DejaVuSans.ttf"
pdfmetrics.registerFont(TTFont("DejaVu", str(FONT_PATH)))

# ---------------- Helpers - styling functions ----------------

def _hex_to_rgb(hex_color: str):
    hex_color = hex_color.lstrip("#")
    return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))

def _cover_crop(img, target_w, target_h):
    w, h = img.size
    target_ratio = target_w / target_h
    img_ratio = w / h
    if img_ratio > target_ratio:
        new_w = int(h * target_ratio)
        x_off = (w - new_w) // 2
        box = (x_off, 0, x_off + new_w, h)
    else:
        new_h = int(w / target_ratio)
        y_off = (h - new_h) // 2
        box = (0, y_off, w, y_off + new_h)
    return img.crop(box).resize((target_w, target_h), Image.LANCZOS)

def _make_gradient(w, h, color_left, color_right, alpha):
    c1, c2 = _hex_to_rgb(color_left), _hex_to_rgb(color_right)
    gradient = Image.new("RGBA", (w, h))
    a = int(255 * alpha)
    for x in range(max(w, 1)):
        t = x / (w - 1) if w > 1 else 0
        r = int(c1[0]*(1-t) + c2[0]*t)
        g = int(c1[1]*(1-t) + c2[1]*t)
        b = int(c1[2]*(1-t) + c2[2]*t)
        for y in range(h):
            gradient.putpixel((x, y), (r, g, b, a))
    return gradient

def _pil_to_reader(img):
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return ImageReader(buf)

def _draw_svg(c, svg_path, x_left, baseline_y, target_height_pt):
    drawing = svg2rlg(svg_path)
    # keep background transparent if present
    if hasattr(drawing, "background"):
        drawing.background = None
    scale = target_height_pt / drawing.height
    drawing.width  *= scale
    drawing.height *= scale
    drawing.scale(scale, scale)
    renderPDF.draw(drawing, c, x_left, baseline_y)

def _wrap_text(c, text, font_name, font_size, max_width):
    words = text.split()
    lines = []
    current = []
    for w in words:
        test = (" ".join(current + [w])) if current else w
        if c.stringWidth(test, font_name, font_size) <= max_width:
            current.append(w)
        else:
            if current:
                lines.append(" ".join(current))
            current = [w]
    if current:
        lines.append(" ".join(current))
    return lines


def _draw_header_footer_svg_ombre(
    c, page_w, page_h, *,
    logo_path, sample_name, report_no,
    left_margin=16*mm, right_margin=16*mm, top_margin=16*mm, bottom_margin=16*mm,
    logo_height_pt=35, header_height_pt=35,
    ombre_left="#1B8EAB", ombre_right="#5BB79E", ombre_alpha=0.5,
    header_font="Helvetica", header_font_size=10.5,
    footer_font="Helvetica", footer_font_size=9
):
    # header area
 
    # 
    y_top = page_h
    header_h = int(header_height_pt)
    header_y = y_top - header_h
    header_w = int(page_w)
    header_x = 0
    #header_x = left_margin
    

    # ombre strip (no photo) as header background
    grad = _make_gradient(header_w, header_h, ombre_left, ombre_right, ombre_alpha)
    c.drawImage(_pil_to_reader(grad), header_x, header_y, width=header_w, height=header_h)

    # SVG logo (same as title logo file, but header size)
    if os.path.exists(logo_path):
        logo_baseline_y = header_y + (header_h-logo_height_pt) / 2.0
        _draw_svg(c, logo_path, left_margin, logo_baseline_y, logo_height_pt)

    # right-aligned header text in white
    c.setFillColor(colors.white)
    c.setFont(header_font, header_font_size)
    c.drawRightString(page_w - right_margin, header_y + (header_h - 10.5)/2 + 1, f"LIDT Test – {sample_name}")

    # footer (unchanged)
    c.setFillColor(colors.HexColor("#667085"))
    c.setFont(footer_font, footer_font_size)
    footer_y = bottom_margin - 6
    c.drawString(left_margin, footer_y, f"Report No: {report_no}")
    c.drawRightString(page_w - right_margin, footer_y, f"Page {c.getPageNumber()}")

# --- New simple section drawing function ---
def _draw_overlay_letter(c, letter, x, y, font_size=10):
    c.setFont("Helvetica-Bold", font_size)
    c.setFillColor(colors.HexColor("#111827"))
    # Draw with a slight downward shift so top aligns more naturally
    c.drawString(x, y - font_size, letter)

def _load_image_flatten_white(path):
    im = Image.open(path)
    # If there's an alpha channel (RGBA, LA, or palette with transparency), flatten onto white
    if im.mode in ("RGBA", "LA") or (im.mode == "P" and ("transparency" in im.info)):
        im = im.convert("RGBA")
        white_bg = Image.new("RGBA", im.size, (255, 255, 255, 255))
        white_bg.alpha_composite(im)
        return white_bg.convert("RGB")
    else:
        return im.convert("RGB")
    
def _draw_image_template(
    c,
    images_spec,
    start_y,
    page_w,
    page_h,
    margins,
    on_new_page,
    left_margin_mm=16,
    right_margin_mm=16,
    min_bottom_gap_pt=20,
    width_pct=0.8,
    figure_number=None,
    dpi=300
):


    if not images_spec or "layout" not in images_spec:
        return start_y, False

    layout = images_spec["layout"]
    items = images_spec.get("items", [])
    if not items:
        return start_y, False

    # ---------------------------
    # Common setup
    # ---------------------------
    left_x = left_margin_mm * mm
    right_x = page_w - right_margin_mm * mm
    usable_w = right_x - left_x
    FOOTER_SAFE_PT = 22
    bottom_limit = margins["bottom_mm"] * mm + min_bottom_gap_pt + FOOTER_SAFE_PT

    gap = 8
    MIN_SCALE = 0.55
    IMAGE_CAPTION_GAP = 20

    caption_user = images_spec.get("caption", "").strip()
    caption_final = (
        f"Figure {figure_number}: {caption_user}"
        if figure_number and caption_user
        else f"Figure {figure_number}" if figure_number else caption_user
    )
    caption_h = 14 if caption_final else 0

    def new_page():
        nonlocal start_y
        c.showPage()
        start_y = on_new_page(c)

    #  STACK layout (variable number of images, one per row, each with own caption/notes) 
    if layout == "stack":
        item_gap       = 24
        cap_gap        = 10
        note_gap       = 8
        cap_font_size  = 10
        note_font_size = 9
        MIN_IMG_H      = 100
        MAX_PER_PAGE   = 2
        full_page_avail = page_h - (margins["top_mm"] + margins["bottom_mm"]) * mm - 60

        # Filter valid items upfront
        valid_items = [it for it in items if it.get("path") and os.path.exists(it["path"])]
        if not valid_items:
            return start_y, 0

        def _overhead(item):
            cap_h  = (cap_gap  + cap_font_size  + 4) if item.get("caption", "").strip() else 0
            note_h = (note_gap + note_font_size + 3) if item.get("notes",   "").strip() else 0
            return cap_h + note_h + item_gap

        overheads = [_overhead(it) for it in valid_items]
        n         = len(valid_items)
        y         = start_y
        drawn_count = 0
        i           = 0

        while i < n:
            avail = y - bottom_limit

            # --- decide how many images go on this page (1 or 2) ---
            draw_h = None
            batch  = 0

            # try fitting 2
            if i + 1 < n:
                oh2 = overheads[i] + overheads[i + 1]
                h2  = (avail - oh2) / 2
                h2  = min(h2, full_page_avail * 0.40)
                if h2 >= MIN_IMG_H:
                    draw_h = h2
                    batch  = 2

            # try fitting 1
            if batch == 0:
                oh1 = overheads[i]
                h1  = avail - oh1
                h1  = min(h1, full_page_avail * 0.55)
                if h1 >= MIN_IMG_H:
                    draw_h = h1
                    batch  = 1

            # nothing fits — new page
            if batch == 0:
                new_page()
                y = start_y
                continue

            # --- draw the batch at uniform draw_h ---
            for j in range(batch):
                item   = valid_items[i + j]
                path   = item["path"]
                img    = Image.open(path)
                iw, ih = img.size

                dh = draw_h
                dw = dh * (iw / ih)
                if dw > usable_w * width_pct:
                    dw = usable_w * width_pct
                    dh = dw * (ih / iw)

                img_x  = left_x + (usable_w - dw) / 2
                reader = _pil_to_reader(_load_image_flatten_white(path))
                c.drawImage(reader, img_x, y - dh, width=dw, height=dh)
                y -= dh
                drawn_count += 1

                item_caption = item.get("caption", "").strip()
                if item_caption:
                    y -= cap_gap
                    fig_label = f"Figure {(figure_number or 0) + drawn_count - 1}: {item_caption}"
                    c.setFont("Helvetica-Oblique", cap_font_size)
                    c.setFillColor(colors.HexColor("#111827"))
                    cap_lines = _wrap_text(c, fig_label, "Helvetica-Oblique", cap_font_size, usable_w)
                    if len(cap_lines) == 1:
                        tw = c.stringWidth(cap_lines[0], "Helvetica-Oblique", cap_font_size)
                        c.drawString(left_x + (usable_w - tw) / 2, y, cap_lines[0])
                        y -= cap_font_size + 4
                    else:
                        for line in cap_lines:
                            c.drawString(img_x, y, line)
                            y -= cap_font_size + 4

                item_notes = item.get("notes", "").strip()
                if item_notes:
                    y -= note_gap
                    c.setFont("Helvetica-Bold", note_font_size)
                    c.setFillColor(colors.HexColor("#111827"))
                    prefix   = "Comment: "
                    prefix_w = c.stringWidth(prefix, "Helvetica-Bold", note_font_size)
                    c.drawString(img_x, y, prefix)
                    c.setFont("Helvetica", note_font_size)
                    for line in _wrap_text(c, item_notes, "Helvetica", note_font_size, usable_w - prefix_w):
                        c.drawString(img_x + prefix_w, y, line)
                        y -= note_font_size + 3
                        prefix_w = 0

                y -= item_gap

            i += batch

        return y, drawn_count

    blocks = []

    # ---------------------------
    # TEMPLATE 1 — single image (adaptive per image)
    # ---------------------------
    if layout == "template1":
        img_w = usable_w * max(0.1, min(width_pct, 1.0))
        img_x = left_x + (usable_w - img_w) / 2

        max_h = start_y - bottom_limit - caption_h - IMAGE_CAPTION_GAP
        if max_h < 60:
            new_page()
            max_h = start_y - bottom_limit - caption_h - IMAGE_CAPTION_GAP

        blocks.append({
            "path": items[0]["path"],
            "x": img_x,
            "y_top": start_y,
            "w": img_w,
            "h": max_h,
            "fit": "contain",
            "label": None
        })

    # ---------------------------
    # TEMPLATE 2 — 2×2 grid (adaptive per layout)
    # ---------------------------
    elif layout == "template2":
        grid_w = usable_w * width_pct
        cell = (grid_w - gap) / 2
        aspect_ratios = [Image.open(item["path"]).height / Image.open(item["path"]).width for item in items]
        extreme_aspect_ratio = max(aspect_ratios)
        cell_height = cell * extreme_aspect_ratio
        preferred_h = (cell_height * 2) + gap
        available_h = start_y - bottom_limit - caption_h - IMAGE_CAPTION_GAP

        layout_scale = min(1.0, available_h / preferred_h)
        if layout_scale < MIN_SCALE:
            new_page()
            layout_scale = 1.0

        grid_w *= layout_scale
        cell *= layout_scale
        cell_height *= layout_scale

        grid_x = left_x + (usable_w - grid_w) / 2

        labels = ["a", "b", "c", "d"]
        for r in range(2):
            for c_i in range(2):
                i = r * 2 + c_i
                blocks.append({
                    "path": items[i]["path"],
                    "x": grid_x + c_i * (cell + gap),
                    "y_top": start_y - r * (cell_height + gap),
                    "w": cell,
                    "h": cell_height,
                    "fit": "cover",
                    "label": labels[i]
                })

    # ---------------------------
    # TEMPLATE 3 — composite (adaptive per layout)
    # ---------------------------
    elif layout == "template3":
        grid_w = usable_w * width_pct
        w_a = (grid_w - gap) / 3
        w_b = grid_w - gap - w_a
        h = w_a

        preferred_h = h * 2 + gap
        available_h = start_y - bottom_limit - caption_h - IMAGE_CAPTION_GAP

        layout_scale = min(1.0, available_h / preferred_h)
        if layout_scale < MIN_SCALE:
            new_page()
            layout_scale = 1.0

        grid_w *= layout_scale
        w_a *= layout_scale
        w_b *= layout_scale
        h *= layout_scale
        gap *= layout_scale

        grid_x = left_x + (usable_w - grid_w) / 2

        blocks.extend([
            {
                "path": items[0]["path"],
                "x": grid_x,
                "y_top": start_y,
                "w": w_a,
                "h": h,
                "fit": "cover",
                "label": "a"
            },
            {
                "path": items[1]["path"],
                "x": grid_x + w_a + gap,
                "y_top": start_y,
                "w": w_b,
                "h": h,
                "fit": "cover",
                "label": "b"
            },
            {
                "path": items[2]["path"],
                "x": grid_x,
                "y_top": start_y - h - gap,
                "w": grid_w,
                "h": h,
                "fit": "cover",
                "label": "c"
            }
        ])

    else:
        return start_y, False

    # ---------------------------
    # Draw images (no adaptive logic here)
    # ---------------------------
    y_min = start_y

    for b in blocks:
        img = Image.open(b["path"]).convert("RGB")
        px_w = int(b["w"] * dpi / 72)
        px_h = int(b["h"] * dpi / 72)

        if b["fit"] == "cover":
            img = _cover_crop(img, px_w, px_h)
        else:
            w0, h0 = img.size
            scale = px_w / w0
            img = img.resize((px_w, int(h0 * scale)), Image.LANCZOS)

        reader = _pil_to_reader(img)
        draw_w = img.size[0] * 72 / dpi
        draw_h = img.size[1] * 72 / dpi
        x_draw = b["x"] + (b["w"] - draw_w) / 2

        c.drawImage(reader, x_draw, b["y_top"] - draw_h, width=draw_w, height=draw_h)

        if b["label"]:
            _draw_overlay_letter(c, b["label"], b["x"] + 6, b["y_top"] - 6)

        y_min = min(y_min, b["y_top"] - draw_h)

    # ---------------------------
    # Caption
    # ---------------------------
    y = y_min - IMAGE_CAPTION_GAP
    if caption_final:
        c.setFont("Helvetica-Oblique", 10)
        lines = _wrap_text(c, caption_final, "Helvetica-Oblique", 10, usable_w)
        if len(lines) == 1:
            line = lines[0]
            text_w = c.stringWidth(line, "Helvetica-Oblique", 10)
            caption_x = left_x + (usable_w - text_w) / 2
            c.drawString(caption_x, y, line)
            y -= 12 
        else:
            caption_x = left_x
            for line in lines:
                c.drawString(caption_x, y, line)
                y -= 12
        y -= 20

        # for line in _wrap_text(c, caption_final, "Helvetica-Oblique", 10, usable_w):
        #     text_w = c.stringWidth(line, "Helvetica-Oblique", 10)
        #     c.drawString(left_x + (usable_w - text_w) / 2, y, line)
        #     y -= 12
        # y -= 20

    return y, True

def _draw_lidt_table(c, page_w, left_margin_mm, right_margin_mm, y, lidt_table, sample="", table_number=1):
    left_x   = left_margin_mm * mm
    right_x  = page_w - right_margin_mm * mm
    usable_w = right_x - left_x
    show_50  = lidt_table.get("show_50_pct", True)

    if show_50:
        headers = [
            "Number of\npulses",
            "0% LIDT\n[J/cm\u00b2]",
            "50% LIDT\n[J/cm\u00b2]",
            "First observed\ndamage [J/cm\u00b2]",
        ]
        col_ws   = [usable_w * w for w in [0.22, 0.26, 0.26, 0.26]]
        row_vals = [
            str(lidt_table.get("n_pulses",     "")),
            str(lidt_table.get("lidt_0",       "")),
            str(lidt_table.get("lidt_50",      "")),
            str(lidt_table.get("first_damage", "")),
        ]
    else:
        headers = [
            "Number of\npulses",
            "0% LIDT\n[J/cm\u00b2]",
            "First observed\ndamage [J/cm\u00b2]",
        ]
        col_ws   = [usable_w * w for w in [0.28, 0.36, 0.36]]
        row_vals = [
            str(lidt_table.get("n_pulses",     "")),
            str(lidt_table.get("lidt_0",       "")),
            str(lidt_table.get("first_damage", "")),
        ]

    hdr_h      = 34
    row_h      = 20
    font_size  = 9
    border_col = colors.HexColor("#D1D5DB")

    x = left_x
    for header, col_w in zip(headers, col_ws):
        c.setFillColor(colors.HexColor("#F3F4F6"))
        c.setStrokeColor(border_col)
        c.rect(x, y - hdr_h, col_w, hdr_h, stroke=1, fill=1)
        c.setFillColor(colors.HexColor("#111827"))
        lines   = header.split("\n")
        total_h = len(lines) * (font_size + 2)
        text_y  = y - (hdr_h - total_h) / 2 - font_size
        for line in lines:
            c.setFont("Helvetica-Bold", font_size)
            tw = c.stringWidth(line, "Helvetica-Bold", font_size)
            c.drawString(x + (col_w - tw) / 2, text_y, line)
            text_y -= font_size + 2
        x += col_w
    y -= hdr_h

    x = left_x
    for val, col_w in zip(row_vals, col_ws):
        c.setFillColor(colors.white)
        c.setStrokeColor(border_col)
        c.rect(x, y - row_h, col_w, row_h, stroke=1, fill=1)
        c.setFillColor(colors.HexColor("#111827"))
        c.setFont("Helvetica", font_size)
        tw = c.stringWidth(val, "Helvetica", font_size)
        c.drawString(x + (col_w - tw) / 2, y - row_h / 2 - font_size / 2 + 1, val)
        x += col_w
    y -= row_h

    y -= 20
    caption = f"Table {table_number} - Extrapolated and measured values of LIDT, sample {sample}."
    c.setFont("Helvetica-Oblique", 9)
    c.setFillColor(colors.HexColor("#111827"))
    cap_w = c.stringWidth(caption, "Helvetica-Oblique", 9)
    c.drawString(left_x + (usable_w - cap_w) / 2, y, caption)
    y -= 16

    return y

def _draw_ron1_table(c, page_w, left_margin_mm, right_margin_mm, y, spot_results, table_number=1):
    left_x   = left_margin_mm * mm
    right_x  = page_w - right_margin_mm * mm
    usable_w = right_x - left_x
    headers  = ["Spot no.", "Damage fluence [J/cm\u00b2]"]
    col_ws   = [usable_w * 0.25, usable_w * 0.75]
    hdr_h    = 24
    row_h    = 20
    fs       = 9
    bc       = colors.HexColor("#D1D5DB")

    x = left_x
    for header, cw in zip(headers, col_ws):
        c.setFillColor(colors.HexColor("#F3F4F6"))
        c.setStrokeColor(bc)
        c.rect(x, y - hdr_h, cw, hdr_h, stroke=1, fill=1)
        c.setFillColor(colors.HexColor("#111827"))
        c.setFont("Helvetica-Bold", fs)
        tw = c.stringWidth(header, "Helvetica-Bold", fs)
        c.drawString(x + (cw - tw) / 2, y - hdr_h / 2 - fs / 2 + 1, header)
        x += cw
    y -= hdr_h

    for row in spot_results:
        spot_no = str(row.get("spot", ""))
        dmg     = row.get("damage_fluence")
        dmg_str = f"{dmg:.1f}" if dmg is not None else "No damage observed"
        x = left_x
        for val, cw in zip([spot_no, dmg_str], col_ws):
            c.setFillColor(colors.white)
            c.setStrokeColor(bc)
            c.rect(x, y - row_h, cw, row_h, stroke=1, fill=1)
            c.setFillColor(colors.HexColor("#111827"))
            c.setFont("Helvetica", fs)
            tw = c.stringWidth(val, "Helvetica", fs)
            c.drawString(x + (cw - tw) / 2, y - row_h / 2 - fs / 2 + 1, val)
            x += cw
        y -= row_h

    y -= 16
    caption = f"Table {table_number} - R-on-1 damage threshold per tested spot."
    c.setFont("Helvetica-Oblique", 9)
    c.setFillColor(colors.HexColor("#111827"))
    cap_w = c.stringWidth(caption, "Helvetica-Oblique", 9)
    c.drawString(left_x + (usable_w - cap_w) / 2, y, caption)
    y -= 16
    return y

def _draw_raster_lidt_table(c, page_w, left_margin_mm, right_margin_mm, y, raster_lidt_table, table_number=1):
    left_x   = left_margin_mm * mm
    right_x  = page_w - right_margin_mm * mm
    usable_w = right_x - left_x
    headers  = [
        "Number of\npulses",
        "0% LIDT\n[J/cm\u00b2]",
        "5% LIDT\n[J/cm\u00b2]",
        "First observed\ndamage [J/cm\u00b2]",
    ]
    col_ws   = [usable_w * w for w in [0.22, 0.26, 0.26, 0.26]]
    row_vals = [
        str(raster_lidt_table.get("n_pulses",     "")),
        str(raster_lidt_table.get("lidt_0",       "")),
        str(raster_lidt_table.get("lidt_5",       "")),
        str(raster_lidt_table.get("first_damage", "")),
    ]
    hdr_h     = 34
    row_h     = 20
    font_size = 9
    bc        = colors.HexColor("#D1D5DB")

    x = left_x
    for header, col_w in zip(headers, col_ws):
        c.setFillColor(colors.HexColor("#F3F4F6"))
        c.setStrokeColor(bc)
        c.rect(x, y - hdr_h, col_w, hdr_h, stroke=1, fill=1)
        c.setFillColor(colors.HexColor("#111827"))
        lines   = header.split("\n")
        total_h = len(lines) * (font_size + 2)
        text_y  = y - (hdr_h - total_h) / 2 - font_size
        for line in lines:
            c.setFont("Helvetica-Bold", font_size)
            tw = c.stringWidth(line, "Helvetica-Bold", font_size)
            c.drawString(x + (col_w - tw) / 2, text_y, line)
            text_y -= font_size + 2
        x += col_w
    y -= hdr_h

    x = left_x
    for val, col_w in zip(row_vals, col_ws):
        c.setFillColor(colors.white)
        c.setStrokeColor(bc)
        c.rect(x, y - row_h, col_w, row_h, stroke=1, fill=1)
        c.setFillColor(colors.HexColor("#111827"))
        c.setFont("Helvetica", font_size)
        tw = c.stringWidth(val, "Helvetica", font_size)
        c.drawString(x + (col_w - tw) / 2, y - row_h / 2 - font_size / 2 + 1, val)
        x += col_w
    y -= row_h

    y -= 20
    sample  = raster_lidt_table.get("sample", "")
    caption = f"Table {table_number} - Extrapolated and measured values of LIDT, sample {sample}."
    c.setFont("Helvetica-Oblique", 9)
    c.setFillColor(colors.HexColor("#111827"))
    cap_w = c.stringWidth(caption, "Helvetica-Oblique", 9)
    c.drawString(left_x + (usable_w - cap_w) / 2, y, caption)
    y -= 16
    return y

def render_sections_split_simple(
    c,
    sections,
    start_y,
    page_w,
    page_h,
    margins,
    on_new_page,
    left_margin_mm=16,
    right_margin_mm=16,
    line_spacing=14,
    min_bottom_gap_pt=20
):

    y = start_y
    bottom_limit = margins["bottom_mm"] * mm + min_bottom_gap_pt

    title_font = "Helvetica-Bold"
    title_font_size = 14
    body_font = "Helvetica"
    body_font_size = 11
    title_to_rule_gap = 8
    rule_height_pt = 0.3
    rule_to_items_gap = 16
    tail_gap = 24

    # Global figure counter (increment only if an image actually draws)
    fig_counter = 0

    for idx, sec in enumerate(sections, start=1):
        title = sec.get("title", f"Section {idx}")
        items = sec.get("items", [])
        left_x = left_margin_mm * mm
        right_x = page_w - right_margin_mm * mm
        rule_width = int(right_x - left_x)

        # Force page break if section requests it (e.g. Annex)
        if sec.get("page_break_before"):
            c.showPage()
            y = on_new_page(c)
        # Ensure space for header + one item; otherwise page-break first
        header_h = title_font_size + title_to_rule_gap + rule_height_pt + rule_to_items_gap
        images_spec = sec.get("images")
        min_content = 150 if (images_spec and images_spec.get("items") and not items) else line_spacing
        if y - (header_h + min_content) < bottom_limit:
            c.showPage()
            y = on_new_page(c)

        # Title
        #0a714e
        # c.setFillColor(colors.HexColor("#00afee"))
        # c.setFillColor(colors.HexColor("#00afee"))

        c.setFillColor(colors.HexColor("#0a714e"))
        c.setFillColor(colors.HexColor("#0a714e"))
        c.setFont(title_font, title_font_size)
        c.drawString(left_x, y, f"{idx}. {title}")

        # Rule
        rule_y = y - title_to_rule_gap
        #0a714e
        #c.setFillColor(colors.HexColor("#00afee"))
        c.setFillColor(colors.HexColor("#0a714e"))
        c.rect(left_x, rule_y, rule_width, rule_height_pt, stroke=0, fill=1)

        # Items start position
        y = rule_y - rule_to_items_gap

        # Body font setup
        c.setFillColor(colors.HexColor("#111827"))
        c.setFont(body_font, body_font_size)

        # Draw items (split across pages as needed)
        for label, value in items:
            if y - line_spacing < bottom_limit:
                c.showPage()
                y = on_new_page(c)
                c.setFillColor(colors.HexColor("#111827"))
                c.setFont(body_font, body_font_size)

            wrapped_label = _wrap_text(c, f"{label}:", "Helvetica-Bold", body_font_size, right_x - left_x)
            label_width = c.stringWidth(wrapped_label[0], "Helvetica-Bold", body_font_size) + 4
            available_width = (right_x - left_x) - (2 * mm + label_width)
            wrapped_value = _wrap_text(c, str(value), body_font, body_font_size, available_width)
            for i in range(max(len(wrapped_label), len(wrapped_value))):
                if i < len(wrapped_label):
                    c.setFont("Helvetica-Bold", body_font_size)
                    c.drawString(left_x + 2 * mm, y, wrapped_label[i])
                if i < len(wrapped_value):
                    x_val = left_x + 2 * mm + c.stringWidth(wrapped_label[0], "Helvetica-Bold", body_font_size) + 4
                    c.setFont(body_font, body_font_size)
                    c.drawString(x_val, y, wrapped_value[i])
                y -= line_spacing


        # Tail gap after items
        y -= tail_gap

        # Optional image template (global figure numbering)
        images_spec = sec.get("images")
        if images_spec:
            prev_y = y
            y, drawn = _draw_image_template(
                c=c,
                images_spec=images_spec,
                start_y=y,
                page_w=page_w,
                page_h=page_h,
                margins=margins,
                on_new_page=on_new_page,
                left_margin_mm=left_margin_mm,
                right_margin_mm=right_margin_mm,
                min_bottom_gap_pt=min_bottom_gap_pt,
                figure_number=fig_counter + 1  # pass next figure number
            )
            
            fig_counter += drawn

        # Optional LIDT table
        lidt_table_data = sec.get("lidt_table")
        if lidt_table_data:
            table_h_needed = 34 + 20 + 30  # header + data row + caption + gap
            if y - table_h_needed < bottom_limit:
                c.showPage()
                y = on_new_page(c)
            y = _draw_lidt_table(
                c             = c,
                page_w        = page_w,
                left_margin_mm  = left_margin_mm,
                right_margin_mm = right_margin_mm,
                y             = y,
                lidt_table    = lidt_table_data,
                sample        = lidt_table_data.get("sample", ""),
                table_number  = lidt_table_data.get("table_number", 1),
            )
        # R-on-1 spot plots
        ron1_spots = sec.get("ron1_spots")
        if ron1_spots:
            y, drawn = _draw_image_template(
                c               = c,
                images_spec     = {"layout": "stack", "items": ron1_spots},
                start_y         = y,
                page_w          = page_w,
                page_h          = page_h,
                margins         = margins,
                on_new_page     = on_new_page,
                left_margin_mm  = left_margin_mm,
                right_margin_mm = right_margin_mm,
                min_bottom_gap_pt = min_bottom_gap_pt,
                figure_number   = fig_counter + 1,
            )
            fig_counter += drawn

        # R-on-1 results table
        ron1_table = sec.get("ron1_table")
        if ron1_table:
            n_rows = len(ron1_table.get("spot_results", []))
            needed = 24 + n_rows * 20 + 32
            if y - needed < bottom_limit:
                c.showPage()
                y = on_new_page(c)
            y = _draw_ron1_table(
                c               = c,
                page_w          = page_w,
                left_margin_mm  = left_margin_mm,
                right_margin_mm = right_margin_mm,
                y               = y,
                spot_results    = ron1_table.get("spot_results", []),
                table_number    = ron1_table.get("table_number", 1),
            )
        # Raster scan LIDT table
        raster_lidt_table = sec.get("raster_lidt_table")
        if raster_lidt_table:
            needed = 34 + 20 + 36
            if y - needed < bottom_limit:
                c.showPage()
                y = on_new_page(c)
            y = _draw_raster_lidt_table(
                c               = c,
                page_w          = page_w,
                left_margin_mm  = left_margin_mm,
                right_margin_mm = right_margin_mm,
                y               = y,
                raster_lidt_table = raster_lidt_table,
                table_number    = raster_lidt_table.get("table_number", 1),
            )
        # Optional notes AFTER images
        notes_text = sec.get("notes")
        if notes_text:
            left_x = left_margin_mm * mm
            right_x = page_w - right_margin_mm * mm
            usable_w = right_x - left_x
            bottom_limit = margins["bottom_mm"] * mm + min_bottom_gap_pt

            note_label_font = "Helvetica-Bold"
            note_label_size = body_font_size
            note_text_font = "Helvetica-Oblique"
            note_text_size = body_font_size

            prefix = "Notes:"
            prefix_w = c.stringWidth(prefix, note_label_font, note_label_size) + 6
            max_line_w = usable_w - prefix_w

            # Wrap note text (italic part)
            c.setFont(note_text_font, note_text_size)
            note_lines = _wrap_text(c, notes_text, note_text_font, note_text_size, max_line_w)

            needed_h = len(note_lines) * line_spacing + 4
            if y - needed_h < bottom_limit:
                c.showPage()
                y = on_new_page(c)
                c.setFillColor(colors.HexColor("#111827"))

            # First line with prefix
            c.setFillColor(colors.HexColor("#111827"))
            c.setFont(note_label_font, note_label_size)
            c.drawString(left_x + 2 * mm, y, prefix)
            c.setFont(note_text_font, note_text_size)
            c.drawString(left_x + 2 * mm + prefix_w, y, note_lines[0])
            y -= line_spacing

            # Remaining lines (italic only)
            for extra in note_lines[1:]:
                if y - line_spacing < bottom_limit:
                    c.showPage()
                    y = on_new_page(c)
                    c.setFillColor(colors.HexColor("#111827"))
                    c.setFont(note_text_font, note_text_size)
                c.drawString(left_x + 2 * mm + prefix_w, y, extra)
                y -= line_spacing

            y -= 12  # small gap after notes

    return y
# ---------------- callable functions ----------------

def generate_report(context: dict, output_path: str = "report.pdf"):
    """
    Expected context keys (keep your existing names):
      lab_image (str)           # photo
      logo_title (str, SVG)     # white SVG for title page
      logo_inner (str, SVG)     # black SVG for inner pages
      ombre_left (hex), ombre_right (hex), ombre_alpha (0..1)
      fade_alpha_255 (0..255)   # e.g. 160 like notebook
      banner_ratio (float)      # e.g. 0.35
      title (str)               # will be combined with sample (notebook behavior)
      sample (str)
      standard (str)
      prepared_by, approved_by, institute, inst_address
      customer, cust_address, cust_contact
      report_no (str)
      margins: {left_mm,right_mm,top_mm,bottom_mm}
      copyright (optional str)  # if omitted, nothing is drawn at bottom of title page
    """
    PAGE_W, PAGE_H = A4
    c = canvas.Canvas(output_path, pagesize=A4)

    # --- Banner full width over page
    banner_h = int(PAGE_H * context["banner_ratio"])
    banner_w = int(PAGE_W)
    banner_y = PAGE_H - banner_h

    lab = Image.open(context["lab_image"]).convert("RGB")
    banner = _cover_crop(lab, banner_w, banner_h).convert("RGBA")
    
    fade_layer = Image.new("RGBA", banner.size, (255, 255, 255, int(context["fade_alpha_255"])))
    banner = Image.alpha_composite(banner, fade_layer)
    gradient = _make_gradient(
        banner_w, banner_h, context["ombre_left"], context["ombre_right"], float(context["ombre_alpha"])
    )
    banner = Image.alpha_composite(banner, gradient)
    c.drawImage(_pil_to_reader(banner), 0, banner_y, width=banner_w, height=banner_h)

    # --- Title-page SVG logo (white)
    # if os.path.exists(context["logo_title"]):
    #     logo_target_h = 48  
    #     logo_x = 16 * mm
    #     logo_y = banner_y + banner_h - 30 * mm  # baseline
    #     _draw_svg(c, context["logo_title"], logo_x, logo_y, logo_target_h)
    # --- Title-page SVG logo (white, bigger + centered)
    if os.path.exists(context["logo_title"]):
        logo_target_h = 80
        _tmp_svg = svg2rlg(context["logo_title"])
        _logo_scale = logo_target_h / _tmp_svg.height
        _logo_w = _tmp_svg.width * _logo_scale
        logo_x = (PAGE_W - _logo_w) / 2
        logo_y = banner_y + banner_h - 42 * mm
        _draw_svg(c, context["logo_title"], logo_x, logo_y, logo_target_h)

    # --- Title ( "{title} {sample}")
    font_name, font_size = "Helvetica-Bold", 28
    c.setFillColor(colors.white)
    title_txt = f"{context['title']}"
    max_width = PAGE_W - 80 * mm
    approx_char_w = font_size * 0.45
    wrap_width = max(1, int(max_width / approx_char_w))
    lines = wrap(title_txt, width=wrap_width)

    #start_y = banner_y + 35*mm + (len(lines) - 1) * 6
    _logo_base    = banner_y + banner_h - 42 * mm   # same as logo_y above
    _subtitle_top = banner_y + 22 * mm
    _mid          = (_logo_base + _subtitle_top) / 2
    start_y       = _mid + (len(lines) - 1) * font_size * 0.55
    c.setFont(font_name, font_size)
    for i, line in enumerate(lines):
        line_w = c.stringWidth(line, font_name, font_size)
        c.drawString((PAGE_W - line_w)/2, start_y - i*font_size*1.1, line)

    # --- Subtitle (notebook: "According to {standard}")
    c.setFillColor(colors.white)
    c.setFont("Helvetica", 14)
    subtitle = f"According to {context['standard']}"
    sub_w = c.stringWidth(subtitle, "Helvetica-Bold", 14)
    c.drawString((PAGE_W - sub_w)/2, banner_y + 16*mm, subtitle)

    c.setFillColor(colors.white)
    c.setFont("Helvetica", 14)
    subtitle2 = f"No. {context['report_no']}"
    sub2_w = c.stringWidth(subtitle2, "Helvetica-Bold", 14)
    c.drawString((PAGE_W - sub2_w)/2, banner_y + 8*mm, subtitle2)


    page_bottom = context["margins"]["bottom_mm"] * mm
    #y_pos = page_bottom + 90*mm
    current_y = PAGE_H - page_bottom - 90 * mm
    # --- Info blocks (notebook look)
    block_x = 16 * mm
    current_y = banner_y - 25 * mm
    #current_y = banner_y - 20 * mm
    #current_y=y_pos
    line_h = 18
    #current_y = 0


    def _measure_block_height(items, line_h=18, title_gap_mm=8, tail_gap_mm=14):
        lines = 0
        for _, value in items:
            if isinstance(value, (list, tuple)):
                lines += max(1, len(value))
            else:
                lines += max(1, len(_wrap_text(c, str(value), "DejaVu", 12, max_width)))

        body_h = lines * line_h
        title_gap = title_gap_mm * mm
        tail_gap = tail_gap_mm * mm
        return body_h + title_gap + tail_gap


    def _block(title_txt, items, max_width):
        nonlocal current_y

        c.setFont("Helvetica-Bold", 14)
        #c.setFillColor(colors.HexColor("#00afee"))
        c.setFillColor(colors.HexColor("#0a714e"))
        
        c.drawString(block_x, current_y - 2, title_txt)

        y = current_y - 8 * mm
        line_h = 18

        for label, value in items:
            c.setFont("Helvetica-Bold", 12)
            c.setFillColor(colors.HexColor("#111827"))

            label_text = f"{label}:"
            label_x = block_x + 2 * mm
            label_w = c.stringWidth(label_text, "Helvetica-Bold", 12) + 4
            value_x = label_x + label_w

            if isinstance(value, (list, tuple)):
                # draw label once
                if value:
                    c.drawString(label_x, y, label_text)
                    c.setFont("DejaVu", 12)
                    c.drawString(value_x, y, str(value[0]))
                    y -= line_h

                    for v in value[1:]:
                        c.drawString(value_x, y, str(v))
                        y -= line_h
                else:
                    c.drawString(label_x, y, label_text)
                    y -= line_h
            else:
                c.setFont("Helvetica-Bold", 12)
                c.drawString(label_x, y, label_text)
                wrapped_value = _wrap_text(c, str(value), "DejaVu", 12, max_width)
                c.setFont("DejaVu", 12)
                for i, line in enumerate(wrapped_value):
                    if i == 0:
                        c.drawString(value_x, y, line)
                    else:
                        y -= line_h
                        c.drawString(label_x, y, line)
            
                y -= line_h

        current_y = y - 14 * mm   


    # page_bottom = context["margins"]["bottom_mm"] * mm
    # bottom_padding = 25 * mm

    hilase_items = [
        ("Prepared by", context["prepared_by"]),
        ("Approved by", context["approved_by"]),
        ("Institute", context["institute"]),
        ("Address", context["inst_address"]),
    ]

    customer_items = [
        ("Name", context["customer"]),
        ("Sample ID", context["sample"]),
        ("Address", context["cust_address"]),
        ("Contact", context["cust_contact"]),
    ]
    FINAL_BASELINE_Y = banner_y - 180 * mm

    hilase_h = _measure_block_height(hilase_items)
    customer_h = _measure_block_height(customer_items)

    current_y = FINAL_BASELINE_Y + hilase_h + customer_h + 10 * mm

    _block("HiLASE", hilase_items, max_width)
    _block("Customer", customer_items, max_width)





    # --- Optional copyright centered at bottom of title page
    if "copyright" in context and context["copyright"]:
        c.setFont("Helvetica", 9)
        c.setFillColor(colors.HexColor("#667085"))
        c.drawCentredString(PAGE_W/2, 12*mm, context["copyright"])

    # Next page
    c.showPage()
    ##----------------------------------------------------------------------
    ## END OF TITLE PAGE
    ## ----------------------------------------------------------------------


    #------------------------------------------------------------------------
    ## SECOND PAGE
    #------------------------------------------------------------------------

    # --- Second page header/footer using SVG
    m = context["margins"]
    header_h_pt = 55
    logo_h_pt = 40

    _draw_header_footer_svg_ombre(
    c, PAGE_W, PAGE_H,
    logo_path=context["logo_inner"],
    sample_name=context["sample"],
    report_no=context["report_no"],
    left_margin=m["left_mm"] * mm,
    right_margin=m["right_mm"] * mm,
    top_margin=m["top_mm"] * mm,
    bottom_margin=m["bottom_mm"] * mm,
    ombre_left=context["ombre_left"],
    ombre_right=context["ombre_right"],
    ombre_alpha=context["ombre_alpha"],  
    logo_height_pt=logo_h_pt,                   
    header_height_pt=header_h_pt             
)
    content_top_y = PAGE_H - m["top_mm"] * mm - header_h_pt - 6

    def _on_new_page(ca):
        _draw_header_footer_svg_ombre(
            ca, PAGE_W, PAGE_H,
            logo_path=context["logo_inner"],
            sample_name=context["sample"],
            report_no=context["report_no"],
            left_margin=m["left_mm"] * mm,
            right_margin=m["right_mm"] * mm,
            top_margin=m["top_mm"] * mm,
            bottom_margin=m["bottom_mm"] * mm,
            ombre_left=context["ombre_left"],
            ombre_right=context["ombre_right"],
            ombre_alpha=context["ombre_alpha"],
            logo_height_pt=logo_h_pt,
            header_height_pt=header_h_pt
        )
        return PAGE_H - m["top_mm"] * mm - header_h_pt - 6

    sections = context.get("sections", [])
    if sections:
        render_sections_split_simple( 
            c=c, 
            sections=sections, 
            start_y=content_top_y, 
            page_w=PAGE_W, 
            page_h=PAGE_H, 
            margins=m, 
            on_new_page=_on_new_page, 
            left_margin_mm=m["left_mm"], 
            right_margin_mm=m["right_mm"], 
            line_spacing=14, 
            min_bottom_gap_pt=20 )



    # # Example placeholder section
    # c.setFillColor(colors.HexColor("#1B8EAB"))
    # c.setFont("Helvetica-Bold", 14)
    # c.drawString(16*mm, PAGE_H - 16*mm - 16*mm, "1. Report Identification")
    # c.setFillColor(colors.HexColor("#1D722D"))
    # c.rect(16*mm, banner_y - 10*mm, 56, 2, stroke=0, fill=1)

    c.showPage()
    c.save()
