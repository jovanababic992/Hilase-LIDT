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
def _draw_overlay_letter(c, letter, x, y, font_size=10, color="white"):
    """
    Draw just a bold letter (no background badge).
    (x, y) is the top-left anchor inside the image.
    color: 'white' or 'black'
    """
    if color not in ("white", "black"):
        color = "white"  # fallback
    c.setFont("Helvetica-Bold", font_size)
    c.setFillColor(colors.HexColor("#FFFFFF" if color == "white" else "#111827"))
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
    figure_number=None
):
    """
    Adds optional transparency flatten flag:
      images_spec['flatten_alpha_to_white'] = True/False (default False)
    If True: transparent pixels become white; if False: current behavior (transparent -> black).
    """
    if not images_spec:
        return start_y, False

    if images_spec.get("layout") == "template1":
        items = images_spec.get("items") or []
        if not items:
            return start_y, False

        img_path = items[0].get("path")
        if not img_path or (not isinstance(img_path, bytes) and not os.path.exists(img_path)):
            return start_y, False

        caption_user = images_spec.get("caption", "").strip()
        overlay_color = images_spec.get("overlay_color", "white")
        width_pct = max(0.1, min(width_pct, 1.0))

        # Figure caption
        if figure_number is not None:
            caption_final = f"Figure {figure_number}: {caption_user}" if caption_user else f"Figure {figure_number}"
        else:
            caption_final = caption_user

        left_x = left_margin_mm * mm
        right_x = page_w - right_margin_mm * mm
        usable_w = right_x - left_x

        img_w = usable_w * width_pct
        img_x = left_x + (usable_w - img_w) / 2

        caption_h = 12 if caption_final else 0
        bottom_limit = margins["bottom_mm"] * mm + min_bottom_gap_pt

        min_img_h = 80
        needed_min = min_img_h + caption_h + 16
        if start_y - needed_min < bottom_limit:
            c.showPage()
            start_y = on_new_page(c)

        available_h_for_image = start_y - (bottom_limit + caption_h + 16)
        if available_h_for_image < 40:
            available_h_for_image = 40

        # Choose loading strategy based on flag
        flatten_flag = images_spec.get("flatten_alpha_to_white", False)

        try:
            if flatten_flag:
                pil = _load_image_flatten_white(img_path)
            else:
                pil = Image.open(img_path).convert("RGB")

            w0, h0 = pil.size
            scale = img_w / w0
            img_h = h0 * scale
            if img_h > available_h_for_image:
                scale = available_h_for_image / h0
                img_h = available_h_for_image
                img_w = w0 * scale
                img_x = left_x + (usable_w - img_w) / 2

            fitted = _cover_crop(pil, int(img_w), int(img_h))
            reader = _pil_to_reader(fitted)
        except Exception:
            return start_y, False

        c.drawImage(reader, img_x, start_y - img_h, width=img_w, height=img_h)

        # _draw_overlay_letter(
        #     c,
        #     "a",
        #     img_x + 6,
        #     start_y - 6,
        #     font_size=10,
        #     color="white" if overlay_color == "white" else "black"
        # )

        y = start_y - img_h - 8

        if caption_final:
            c.setFillColor(colors.HexColor("#111827"))
            caption_font = "Helvetica-Oblique"
            caption_size = 10
            line_spacing = 12

            usable_w2 = (page_w - right_margin_mm * mm) - (left_margin_mm * mm)

            # wrap caption into multiple lines
            lines = _wrap_text(c, caption_final, caption_font, caption_size, usable_w2)

            c.setFont(caption_font, caption_size)
            current_y = y - line_spacing

            if len(lines) == 1:
                # ---- single line → center ----
                line = lines[0]
                text_w = c.stringWidth(line, caption_font, caption_size)
                caption_x = left_x + (usable_w2 - text_w) / 2
                c.drawString(caption_x, current_y, line)
                current_y -= line_spacing
            else:
                # ---- multiple lines → left align ----
                caption_x = left_x
                for line in lines:
                    c.drawString(caption_x, current_y, line)
                    current_y -= line_spacing

            # extra gap after caption
            y = current_y - 35





            return y, True



    # ------------------------------------------------------------
    # TEMPLATE 2: 2x2 grid (a b / c d)
    # ------------------------------------------------------------
    if images_spec.get("layout") == "template2":
        items = images_spec.get("items") or []
        if len(items) < 4:
            return start_y, False  # need exactly 4 images
        overlay_color = images_spec.get("overlay_color", "white")
        flatten_flag = images_spec.get("flatten_alpha_to_white", False)
        width_pct_local = max(0.1, min(images_spec.get("width_pct", width_pct), 1.0))

        caption_user = images_spec.get("caption", "").strip()
        if figure_number is not None:
            caption_final = f"Figure {figure_number}: {caption_user}" if caption_user else f"Figure {figure_number}"
        else:
            caption_final = caption_user
        caption_h = 12 if caption_final else 0

        left_x = left_margin_mm * mm
        right_x = page_w - right_margin_mm * mm
        usable_w = right_x - left_x

        grid_w = usable_w * width_pct_local
        grid_x = left_x + (usable_w - grid_w) / 2

        gap = 8  # horizontal & vertical gap
        cell_w = (grid_w - gap) / 2
        cell_h = cell_w 

        # Load images and compute a common height so the grid is nice and even
        # ==== NEW: load each image and stretch to exact cell size (no cropping, no borders) ====
        readers = []
        for i in range(4):
            p = items[i].get("path")
            if not p or not os.path.exists(p):
                return start_y, False
            try:
                pil = _load_image_flatten_white(p) if flatten_flag else Image.open(p).convert("RGB")
            except Exception:
                return start_y, False

            # Stretch directly to the grid cell dimensions (may slightly distort)
            # resized = pil.resize((int(cell_w), int(cell_h)), Image.LANCZOS)
            # readers.append(_pil_to_reader(resized))
            fitted = _cover_crop(pil, int(cell_w), int(cell_h))
            readers.append(_pil_to_reader(fitted))

      

        # Both rows have the same height now
        row1_h = cell_h
        row2_h = cell_h
        needed = row1_h + gap + row2_h + 8 + caption_h + 16  # total vertical space



        bottom_limit = margins["bottom_mm"] * mm + min_bottom_gap_pt

        if start_y - needed < bottom_limit:
            c.showPage()
            start_y = on_new_page(c)

        # Draw row 1 (a, b)
        x_a = grid_x
        x_b = grid_x + cell_w + gap
        y_top = start_y
        c.drawImage(readers[0], x_a, y_top - cell_h, width=cell_w, height=cell_h)
        c.drawImage(readers[1], x_b, y_top - cell_h, width=cell_w, height=cell_h)

        _draw_overlay_letter(c, "a", x_a + 6, y_top - 6,
                             font_size=10,
                             color="white" if overlay_color == "white" else "black")
        _draw_overlay_letter(c, "b", x_b + 6, y_top - 6,
                             font_size=10,
                             color="white" if overlay_color == "white" else "black")

        # Row 2 (c, d)
        y_row2_top = y_top - row1_h - gap
        c.drawImage(readers[2], x_a, y_row2_top - cell_h, width=cell_w, height=cell_h)
        c.drawImage(readers[3], x_b, y_row2_top - cell_h, width=cell_w, height=cell_h)

        _draw_overlay_letter(c, "c", x_a + 6, y_row2_top - 6,
                             font_size=10,
                             color="white" if overlay_color == "white" else "black")
        _draw_overlay_letter(c, "d", x_b + 6, y_row2_top - 6,
                             font_size=10,
                             color="white" if overlay_color == "white" else "black")

        y_after = y_row2_top - cell_h - 8

        # Centered caption (optional)
        if caption_final:
            c.setFillColor(colors.HexColor("#111827"))
            caption_font = "Helvetica-Oblique"
            caption_size = 10
            line_spacing = 12

            # wrap caption into multiple lines (use full usable_w)
            lines = _wrap_text(c, caption_final, caption_font, caption_size, usable_w)

            c.setFont(caption_font, caption_size)
            current_y = y_after - line_spacing

            if len(lines) == 1:
                # ---- single line → center ----
                line = lines[0]
                text_w = c.stringWidth(line, caption_font, caption_size)
                caption_x = left_x + (usable_w - text_w) / 2
                c.drawString(caption_x, current_y, line)
                current_y -= line_spacing
            else:
                # ---- multiple lines → left align ----
                caption_x = left_x
                for line in lines:
                    c.drawString(caption_x, current_y, line)
                    current_y -= line_spacing

            # extra gap after caption
            y_after = current_y - 35

        return y_after, True
    
    # ------------------------------------------------------------
    # TEMPLATE 3: 1/3 + 2/3 top, full-width bottom (a | b / c)
    # ------------------------------------------------------------
    if images_spec.get("layout") == "template3":
        items = images_spec.get("items") or []
        if len(items) < 3:
            return start_y, False  # need exactly 3 images

        overlay_color = images_spec.get("overlay_color", "white")
        flatten_flag = images_spec.get("flatten_alpha_to_white", False)
        width_pct_local = max(0.1, min(images_spec.get("width_pct", width_pct), 1.0))

        caption_user = images_spec.get("caption", "").strip()
        if figure_number is not None:
            caption_final = f"Figure {figure_number}: {caption_user}" if caption_user else f"Figure {figure_number}"
        else:
            caption_final = caption_user
        caption_h = 12 if caption_final else 0

        # --- Geometry ---
        left_x = left_margin_mm * mm
        right_x = page_w - right_margin_mm * mm
        usable_w = right_x - left_x

        grid_w = usable_w * width_pct_local
        grid_x = left_x + (usable_w - grid_w) / 2

        gap = 8

        w_a = (grid_w - gap) * (1/3)
        w_b = (grid_w - gap) * (2/3)

        h_top = w_a  # square
        h_bottom = h_top #* 0.6

        needed = h_top + gap + h_bottom + 8 + caption_h + 16
        bottom_limit = margins["bottom_mm"] * mm + min_bottom_gap_pt

        if start_y - needed < bottom_limit:
            c.showPage()
            start_y = on_new_page(c)

        # --- Load images ---
        readers = []
        for i in range(3):
            p = items[i].get("path")
            if not p or not os.path.exists(p):
                return start_y, False
            try:
                pil = _load_image_flatten_white(p) if flatten_flag else Image.open(p).convert("RGB")
                if i == 0:
                    fitted = _cover_crop(pil, int(w_a), int(h_top))
                elif i == 1:
                    fitted = _cover_crop(pil, int(w_b), int(h_top))
                else:
                    fitted = _cover_crop(pil, int(grid_w), int(h_bottom))
                readers.append(_pil_to_reader(fitted))
            except Exception:
                return start_y, False

        # --- Draw top row ---
        x_a = grid_x
        x_b = grid_x + w_a + gap
        y_top = start_y

        c.drawImage(readers[0], x_a, y_top - h_top, width=w_a, height=h_top)
        c.drawImage(readers[1], x_b, y_top - h_top, width=w_b, height=h_top)

        _draw_overlay_letter(c, "a", x_a + 6, y_top - 6,
                             font_size=10,
                             color="white" if overlay_color == "white" else "black")
        _draw_overlay_letter(c, "b", x_b + 6, y_top - 6,
                             font_size=10,
                             color="white" if overlay_color == "white" else "black")

        # --- Draw bottom image ---
        y_bottom_top = y_top - h_top - gap
        c.drawImage(readers[2], grid_x, y_bottom_top - h_bottom,
                    width=grid_w, height=h_bottom)

        _draw_overlay_letter(c, "c", grid_x + 6, y_bottom_top - 6,
                             font_size=10,
                             color="white" if overlay_color == "white" else "black")

        y_after = y_bottom_top - h_bottom - 12

        # --- Caption ---
        if caption_final:
            c.setFillColor(colors.HexColor("#111827"))
            caption_font = "Helvetica-Oblique"
            caption_size = 10
            line_spacing = 12

            lines = _wrap_text(c, caption_final, caption_font, caption_size, usable_w)
            c.setFont(caption_font, caption_size)

            current_y = y_after - line_spacing
            if len(lines) == 1:
                text_w = c.stringWidth(lines[0], caption_font, caption_size)
                c.drawString(left_x + (usable_w - text_w) / 2, current_y, lines[0])
                current_y -= line_spacing
            else:
                for line in lines:
                    c.drawString(left_x, current_y, line)
                    current_y -= line_spacing

            y_after = current_y - 35

        return y_after, True

    # ------------------------------------------------------------
    # FUTURE TEMPLATES (placeholders – do nothing yet)
    # ------------------------------------------------------------
    # if layout == "template2":
    #     # Two side-by-side images (a, b)
    #     return start_y
    #
    # if layout == "template3":
    #     # Tall-left (a tall image + two stacked)
    #     return start_y
    #
    # if layout == "template4":
    #     # Tall-right (mirror)
    #     return start_y
    #
    # if layout == "template5":
    #     # Quad 2x2 (a, b, c, d)
    #     return start_y
    #
    # if layout == "template6":
    #     # Big-top + two bottom
    #     return start_y

    # Unknown layout name
    return start_y


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

        # Ensure space for header + one item; otherwise page-break first
        header_h = title_font_size + title_to_rule_gap + rule_height_pt + rule_to_items_gap
        if y - (header_h + line_spacing) < bottom_limit:
            c.showPage()
            y = on_new_page(c)

        # Title
        c.setFillColor(colors.HexColor("#00afee"))
        c.setFillColor(colors.HexColor("#00afee"))
        c.setFont(title_font, title_font_size)
        c.drawString(left_x, y, f"{idx}. {title}")

        # Rule
        rule_y = y - title_to_rule_gap
        c.setFillColor(colors.HexColor("#00afee"))
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
            if drawn:
                fig_counter += 1

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
    if os.path.exists(context["logo_title"]):
        logo_target_h = 48  
        logo_x = 16 * mm
        logo_y = banner_y + banner_h - 30 * mm  # baseline
        _draw_svg(c, context["logo_title"], logo_x, logo_y, logo_target_h)

    # --- Title ( "{title} {sample}")
    font_name, font_size = "Helvetica-Bold", 28
    c.setFillColor(colors.white)
    title_txt = f"{context['title']}"
    max_width = PAGE_W - 80 * mm
    approx_char_w = font_size * 0.45
    wrap_width = max(1, int(max_width / approx_char_w))
    lines = wrap(title_txt, width=wrap_width)

    start_y = banner_y + 35*mm + (len(lines) - 1) * 6
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
        c.setFillColor(colors.HexColor("#00afee"))
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
    header_h_pt = 45
    logo_h_pt = 25

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
