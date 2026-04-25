"""Brand constants and shared imaging helpers (PIL) for the flyer + Instagram renderer."""
from __future__ import annotations

import io
import os
from typing import List, Tuple

import cairosvg
from PIL import Image, ImageDraw, ImageFilter, ImageFont

# ---------------------------------------------------------------------------
# Brand
# ---------------------------------------------------------------------------
GOLD = (167, 130, 72)      # #a78248
BLACK = (15, 15, 15)
WHITE = (255, 255, 255)
OFFWHITE = (250, 250, 250)
TEXT_DARK = (34, 34, 34)
TEXT_GREY = (85, 85, 85)

PHONE = "(336) 594-5747"
EMAIL = "info@dspropertiesnc.com"
WEBSITE = "dspropertiesnc.com"
OFFICE = "2601 Oakcrest Ave, Ste F"
TAGLINE = "Find beauty and comfort in your dream home with Doss & Spaulding Properties"

ASSETS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets")
LOGO_STACKED = os.path.join(ASSETS_DIR, "logo_stacked.svg")
LOGO_MARK_DARK = os.path.join(ASSETS_DIR, "logo_mark_dark.svg")   # house icon only, colors inverted for dark bg

# Fonts — Poppins ships with cairosvg's common font list; fall back to DejaVu.
_BUNDLED_FONTS = os.path.join(ASSETS_DIR, "fonts")

FONT_CANDIDATES = {
    "bold": [
        os.path.join(_BUNDLED_FONTS, "Poppins-Bold.ttf"),
        "/usr/share/fonts/truetype/google-fonts/Poppins-Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    ],
    "medium": [
        os.path.join(_BUNDLED_FONTS, "Poppins-Medium.ttf"),
        "/usr/share/fonts/truetype/google-fonts/Poppins-Medium.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ],
    "regular": [
        os.path.join(_BUNDLED_FONTS, "Poppins-Regular.ttf"),
        "/usr/share/fonts/truetype/google-fonts/Poppins-Regular.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ],
    "light": [
        "/usr/share/fonts/truetype/google-fonts/Poppins-Light.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ],
}


def _first_existing(paths: List[str]) -> str:
    for p in paths:
        if os.path.exists(p):
            return p
    raise FileNotFoundError(f"No font found among: {paths}")


def font(weight: str, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(_first_existing(FONT_CANDIDATES[weight]), size)


# ---------------------------------------------------------------------------
# Imaging helpers
# ---------------------------------------------------------------------------

def svg_to_pil(path: str, width: int) -> Image.Image:
    """Render an SVG to a transparent RGBA PIL image at the given width."""
    png_bytes = cairosvg.svg2png(url=path, output_width=width)
    return Image.open(io.BytesIO(png_bytes)).convert("RGBA")


def fit_cover(img: Image.Image, target_w: int, target_h: int,
              anchor_y: str = "center") -> Image.Image:
    """Resize + crop so the image fills the target box (like CSS cover).
    `anchor_y` controls vertical crop when the scaled image is taller than target:
    "center" (default), "top" (keep the top), "upper" (keep the upper quarter)."""
    src_ratio = img.width / img.height
    dst_ratio = target_w / target_h
    if src_ratio > dst_ratio:
        new_h = target_h
        new_w = int(round(target_h * src_ratio))
    else:
        new_w = target_w
        new_h = int(round(target_w / src_ratio))
    resized = img.resize((new_w, new_h), Image.LANCZOS)
    left = (new_w - target_w) // 2
    overflow = new_h - target_h
    if anchor_y == "top":
        top = 0
    elif anchor_y == "upper":
        top = max(0, overflow // 4)
    else:
        top = overflow // 2
    return resized.crop((left, top, left + target_w, top + target_h))


def circle_crop(img: Image.Image, diameter: int, ring_width: int = 0, ring_color=BLACK) -> Image.Image:
    """Return an RGBA circular crop of `img`, optionally with an outer ring."""
    square = fit_cover(img, diameter, diameter).convert("RGBA")
    mask = Image.new("L", (diameter, diameter), 0)
    ImageDraw.Draw(mask).ellipse((0, 0, diameter, diameter), fill=255)
    square.putalpha(mask)

    if ring_width <= 0:
        return square

    total = diameter + ring_width * 2
    canvas = Image.new("RGBA", (total, total), (0, 0, 0, 0))
    ImageDraw.Draw(canvas).ellipse((0, 0, total, total), fill=ring_color + (255,))
    canvas.alpha_composite(square, dest=(ring_width, ring_width))
    return canvas


def rounded_panel(w: int, h: int, radius: int, fill=BLACK) -> Image.Image:
    """Rounded-rectangle panel, RGBA, used for the logo 'tag' at the top of the hero."""
    canvas = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(canvas)
    draw.rounded_rectangle((0, 0, w - 1, h - 1), radius=radius, fill=fill + (255,))
    return canvas


def vertical_gradient(w: int, h: int, top=(0, 0, 0, 0), bottom=(0, 0, 0, 180)) -> Image.Image:
    """Vertical gradient panel in RGBA. Used to darken the bottom of a hero photo
    so overlaid text is readable."""
    img = Image.new("RGBA", (w, h), top)
    pixels = img.load()
    for y in range(h):
        t = y / max(1, h - 1)
        r = int(top[0] * (1 - t) + bottom[0] * t)
        g = int(top[1] * (1 - t) + bottom[1] * t)
        b = int(top[2] * (1 - t) + bottom[2] * t)
        a = int(top[3] * (1 - t) + bottom[3] * t)
        for x in range(w):
            pixels[x, y] = (r, g, b, a)
    return img


def rounded_image(img: Image.Image, w: int, h: int, radius: int,
                  stroke: int = 0, stroke_color=(0, 0, 0)) -> Image.Image:
    """Resize+crop `img` to w x h with rounded corners. Optional outline stroke."""
    cover = fit_cover(img, w, h).convert("RGBA")
    mask = Image.new("L", (w, h), 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, w - 1, h - 1), radius=radius, fill=255)
    cover.putalpha(mask)
    if stroke <= 0:
        return cover
    out_w, out_h = w + stroke * 2, h + stroke * 2
    out = Image.new("RGBA", (out_w, out_h), (0, 0, 0, 0))
    ImageDraw.Draw(out).rounded_rectangle(
        (0, 0, out_w - 1, out_h - 1),
        radius=radius + stroke,
        fill=stroke_color + (255,),
    )
    out.alpha_composite(cover, dest=(stroke, stroke))
    return out


def wrap_text(draw: ImageDraw.ImageDraw, text: str, f: ImageFont.FreeTypeFont, max_w: int) -> List[str]:
    words = text.split()
    lines: List[str] = []
    current = ""
    for w in words:
        trial = (current + " " + w).strip()
        bbox = draw.textbbox((0, 0), trial, font=f)
        if bbox[2] - bbox[0] <= max_w:
            current = trial
        else:
            if current:
                lines.append(current)
            current = w
    if current:
        lines.append(current)
    return lines


def draw_wrapped(
    draw: ImageDraw.ImageDraw,
    xy: Tuple[int, int],
    text: str,
    f: ImageFont.FreeTypeFont,
    max_w: int,
    fill=TEXT_DARK,
    line_gap: int = 6,
    align: str = "left",
) -> int:
    """Draw wrapped text starting at xy; return the ending y coordinate."""
    x0, y = xy
    lines = wrap_text(draw, text, f, max_w)
    for line in lines:
        bbox = draw.textbbox((0, 0), line, font=f)
        h = bbox[3] - bbox[1]
        if align == "center":
            w_text = bbox[2] - bbox[0]
            x = x0 + (max_w - w_text) // 2
        elif align == "right":
            w_text = bbox[2] - bbox[0]
            x = x0 + max_w - w_text
        else:
            x = x0
        draw.text((x, y), line, font=f, fill=fill)
        # Use the font's configured line height for consistent spacing
        y += f.size + line_gap
    return y


def draw_text_justified(
    draw: ImageDraw.ImageDraw,
    xy: Tuple[int, int],
    text: str,
    f: ImageFont.FreeTypeFont,
    max_w: int,
    fill=TEXT_DARK,
    line_gap: int = 6,
) -> int:
    """Justified paragraph text. Last line is left-aligned."""
    x0, y = xy
    lines = wrap_text(draw, text, f, max_w)
    for i, line in enumerate(lines):
        words = line.split()
        if i == len(lines) - 1 or len(words) == 1:
            draw.text((x0, y), line, font=f, fill=fill)
        else:
            widths = [draw.textbbox((0, 0), w, font=f)[2] for w in words]
            spaces = len(words) - 1
            total_text = sum(widths)
            gap = (max_w - total_text) / spaces if spaces else 0
            x = x0
            for idx, w in enumerate(words):
                draw.text((x, y), w, font=f, fill=fill)
                x += widths[idx] + gap
        y += f.size + line_gap
    return y


def gold_check_icon(size: int) -> Image.Image:
    """Rounded gold disc with a white checkmark, matching the example flyer bullet."""
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    # Filled gold circle
    draw.ellipse((0, 0, size - 1, size - 1), fill=GOLD + (255,))
    # White check: three points forming a checkmark
    pad = size * 0.26
    pts = [
        (pad, size * 0.55),
        (size * 0.44, size * 0.72),
        (size - pad * 0.85, size * 0.32),
    ]
    draw.line(pts, fill=WHITE, width=max(2, int(size * 0.11)), joint="curve")
    # Round the line caps by drawing small circles at the endpoints
    cap = max(1, int(size * 0.05))
    for x, y in pts:
        draw.ellipse((x - cap, y - cap, x + cap, y + cap), fill=WHITE)
    return img


def globe_icon(size: int, color=WHITE) -> Image.Image:
    hex_color = "#{:02x}{:02x}{:02x}".format(*color)
    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24">
      <g fill="none" stroke="{hex_color}" stroke-width="1.6" stroke-linecap="round">
        <circle cx="12" cy="12" r="9"/>
        <ellipse cx="12" cy="12" rx="4" ry="9"/>
        <line x1="3" y1="12" x2="21" y2="12"/>
        <path d="M5 7.5 Q12 5.2 19 7.5"/>
        <path d="M5 16.5 Q12 18.8 19 16.5"/>
      </g>
    </svg>'''
    png = cairosvg.svg2png(bytestring=svg.encode(), output_width=size * 4, output_height=size * 4)
    return Image.open(io.BytesIO(png)).convert("RGBA").resize((size, size), Image.LANCZOS)


def phone_icon(size: int, color=WHITE) -> Image.Image:
    """Solid 'call' handset silhouette rendered via SVG so the shape is
    crisp at any raster size. Matches the common Material/iOS call icon."""
    hex_color = "#{:02x}{:02x}{:02x}".format(*color)
    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24">
      <path fill="{hex_color}" d="M20.01 15.38c-1.23 0-2.42-.2-3.53-.56a.977.977 0 0 0-1.01.24l-1.57 1.97c-2.83-1.35-5.48-3.9-6.89-6.83l1.95-1.66c.27-.28.35-.67.24-1.02-.37-1.11-.56-2.3-.56-3.53 0-.54-.45-.99-.99-.99H4.19C3.65 3 3 3.24 3 3.99 3 13.28 10.73 21 20.01 21c.71 0 .99-.63.99-1.18v-3.45c0-.54-.45-.99-.99-.99z"/>
    </svg>'''
    png = cairosvg.svg2png(bytestring=svg.encode(), output_width=size * 4, output_height=size * 4)
    img = Image.open(io.BytesIO(png)).convert("RGBA")
    return img.resize((size, size), Image.LANCZOS)


def pin_icon(size: int, color=WHITE) -> Image.Image:
    hex_color = "#{:02x}{:02x}{:02x}".format(*color)
    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24">
      <path fill="{hex_color}" d="M12 2C7.86 2 4.5 5.36 4.5 9.5c0 5.25 6.5 12 7.05 12.55a.65.65 0 0 0 .9 0C13 21.5 19.5 14.75 19.5 9.5 19.5 5.36 16.14 2 12 2zm0 10.3a2.8 2.8 0 1 1 0-5.6 2.8 2.8 0 0 1 0 5.6z"/>
    </svg>'''
    png = cairosvg.svg2png(bytestring=svg.encode(), output_width=size * 4, output_height=size * 4)
    return Image.open(io.BytesIO(png)).convert("RGBA").resize((size, size), Image.LANCZOS)


# ---------------------------------------------------------------------------
# Copywriting helpers
# ---------------------------------------------------------------------------


def qr_code_with_logo(url: str, size: int, logo_svg_path: str | None = None,
                      logo_scale: float = 0.22,
                      fg_color=(0, 0, 0), bg_color=(255, 255, 255, 255),
                      logo_pad_color=None) -> "Image.Image":
    """Return a square RGBA QR code for `url`, optionally with a centered logo.
    Uses H-level error correction so ~30% of modules can be obscured by the logo.

    fg_color: color of the module 'dots' (default black)
    bg_color: background color, can be RGB or RGBA. Pass (0,0,0,0) for transparent.
    logo_pad_color: color of the padding rectangle behind the logo. Defaults to
        the QR background so it blends seamlessly.
    """
    import qrcode
    from qrcode.image.styledpil import StyledPilImage
    from qrcode.image.styles.moduledrawers.pil import RoundedModuleDrawer
    from qrcode.image.styles.colormasks import SolidFillColorMask

    qr = qrcode.QRCode(
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_H,
        box_size=14,
        border=1,
    )
    qr.add_data(url)
    qr.make(fit=True)

    # Normalize bg to RGB for the colormask; alpha handled afterward
    bg_rgb = bg_color[:3]
    qr_img = qr.make_image(
        image_factory=StyledPilImage,
        module_drawer=RoundedModuleDrawer(radius_ratio=0.6),
        color_mask=SolidFillColorMask(front_color=fg_color, back_color=bg_rgb),
    ).convert("RGBA")
    qr_img = qr_img.resize((size, size), Image.LANCZOS)

    # Apply background alpha if requested (fully transparent background)
    if len(bg_color) == 4 and bg_color[3] < 255:
        data = qr_img.load()
        for y in range(qr_img.height):
            for x in range(qr_img.width):
                r, g, b, a = data[x, y]
                # pixels that equal the bg rgb -> transparent
                if (r, g, b) == bg_rgb:
                    data[x, y] = (r, g, b, bg_color[3])

    if logo_svg_path and os.path.exists(logo_svg_path):
        logo_target = int(size * logo_scale)
        logo = svg_to_pil(logo_svg_path, width=logo_target)
        pad = int(logo.width * 0.18)
        bg_w = logo.width + pad * 2
        bg_h = logo.height + pad * 2
        pad_fill = logo_pad_color if logo_pad_color is not None else bg_color
        if len(pad_fill) == 3:
            pad_fill = pad_fill + (255,)
        bg = Image.new("RGBA", (bg_w, bg_h), pad_fill)
        bg.alpha_composite(logo, dest=(pad, pad))
        bx = (size - bg.width) // 2
        by = (size - bg.height) // 2
        qr_img.alpha_composite(bg, dest=(bx, by))

    return qr_img

def build_headline(building_type: str | None) -> str:
    """'HOME FOR RENT' for single-family, 'UNIT FOR RENT' for multi-unit types."""
    if not building_type:
        return "HOME FOR RENT"
    bt = building_type.lower()
    unit_keywords = ["duplex", "triplex", "quad", "apartment", "condo", "townhouse", "unit", "multi"]
    if any(k in bt for k in unit_keywords):
        return "UNIT FOR RENT"
    return "HOME FOR RENT"


# Amenity labels we prefer over the raw scraped label (for marketability)
_AMENITY_RENAME = {
    "washer dryer hookups": "W/D hookups",
    "washer dryer": "Washer/dryer",
    "air conditioning": "AC",
    "central air": "Central AC",
    "double pane windows": "Double-pane windows",
    "window coverings": "Window coverings",
    "electric stove": "Electric stove",
    "natural gas": "Gas heat",
    "electric heat": "Electric heat",
    "stainless appliances": "Stainless appliances",
    "stainless steel appliances": "Stainless appliances",
    "hardwood": "Hardwood floors",
    "tile": "Tile floors",
    "linoleum": "Vinyl floors",
    "carpet": "Carpet",
    "blinds": "Blinds",
    "fenced yard": "Fenced yard",
    "garage": "Garage",
    "dishwasher": "Dishwasher",
    "refrigerator": "Refrigerator",
    "breakfast nook": "Breakfast nook",
    "den": "Den",
    "lawn": "Lawn",
    "landscaping": "Landscaped",
}

# Higher score = more marketable / likely to stand out on a flyer
_AMENITY_PRIORITY = {
    "hardwood": 10,
    "stainless": 10,
    "granite": 10,
    "central air": 9,
    "ac": 8,
    "air conditioning": 8,
    "washer dryer hookups": 7,
    "washer dryer": 8,
    "fenced yard": 8,
    "garage": 8,
    "dishwasher": 7,
    "double pane windows": 6,
    "breakfast nook": 6,
    "den": 6,
    "blinds": 4,
    "window coverings": 4,
    "electric heat": 3,
    "refrigerator": 5,
    "electric stove": 5,
    "oven": 4,
    "lawn": 4,
    "landscaping": 5,
    "linoleum": 3,
    "tile": 6,
    "carpet": 4,
}


# (phrase_regex, bullet_label, priority) — higher priority = more marketable
_DESCRIPTION_HIGHLIGHTS = [
    # --- Top-tier selling points ---
    (r"\b(fully|completely|totally|just)\s+remodel\w*",      "Fully remodeled",          100),
    (r"\brenovat\w*",                                        "Renovated",                 95),
    (r"\bbrand.{0,5}new\s+kitchen",                          "Brand-new kitchen",         90),
    (r"\b(new|updated)\s+kitchen",                           "Updated kitchen",           88),
    (r"\bbrand.{0,5}new\s+bath\w*",                         "Brand-new bathrooms",       90),
    (r"\b(new|updated)\s+bath(?:room)?s?\b",                "Updated bathrooms",         88),
    (r"\bnew\s+(?:hardwood\s+)?floor(?:ing)?\b",           "New flooring",              85),
    (r"\bfresh(?:ly)?\s+paint(?:ed)?\b",                    "Fresh paint",               85),
    # --- Premium finishes ---
    (r"\bgranite\b",                                         "Granite countertops",       80),
    (r"\bquartz\b",                                          "Quartz countertops",        80),
    (r"\bmarble\b",                                          "Marble finishes",           78),
    (r"\bstainless(?:\s+steel)?\s+appliance",               "Stainless appliances",      82),
    (r"\bnew\s+appliance",                                   "New appliances",            80),
    (r"\bnew\s+cabinets?\b",                                "New cabinets",              75),
    (r"\bhardwood\b",                                        "Hardwood floors",           70),
    (r"\b(?:luxury\s+vinyl|lvp)\b",                         "LVP flooring",              65),
    # --- Layout / light ---
    (r"\bopen\s+(?:concept|floor\s*plan|layout)\b",        "Open floor plan",           75),
    (r"\b(?:abundant|tons\s+of|plenty\s+of|lots\s+of)?\s*natural\s+light", "Abundant natural light", 75),
    (r"\bvaulted\s+ceiling",                                 "Vaulted ceilings",          72),
    # --- Rooms / amenities worth calling out ---
    (r"\b(?:primary|master).{0,10}en.?suite\b|\bfull\s+en.?suite\b|\bensuite\b", "Primary ensuite", 78),
    (r"\bwalk.?in\s+closet",                                 "Walk-in closet",            70),
    (r"\bwalk.?in\s+shower",                                 "Walk-in shower",            72),
    (r"\b(?:large|spacious)\s+mudroom\b|\bmud\s*room\b", "Mudroom",                   60),
    (r"\bbonus\s+room\b",                                   "Bonus room",                68),
    (r"\bprivate\s+half\s+bath\b",                         "Private half bath",         65),
    # --- Outdoor ---
    (r"\bfenced\s+(?:back)?\s*yard\b",                     "Fenced yard",               75),
    (r"\bscreened\s+porch\b",                               "Screened porch",            70),
    (r"\bcovered\s+(?:porch|patio|deck)\b",                 "Covered outdoor space",     65),
    (r"\b(?:back|front|wrap.?around)\s+(?:porch|deck|patio)\b", "Outdoor space",          58),
    (r"\bdeck\b",                                            "Deck",                      55),
    (r"\bpatio\b",                                           "Patio",                     55),
    (r"\battached\s+garage\b",                              "Attached garage",           72),
    (r"\bgarage\b",                                          "Garage",                    68),
    (r"\bcarport\b",                                         "Carport",                   55),
    (r"\bcorner\s+lot\b",                                   "Corner lot",                60),
]


def extract_highlights_from_description(description: str, max_count: int = 8) -> List[str]:
    """Pull marketing-worthy phrases out of the listing description, in order of
    priority. Deduplicates overlapping concepts (e.g., 'new kitchen' + 'brand-new
    kitchen' resolve to one bullet)."""
    import re
    if not description:
        return []
    text = description.lower()
    hits = []
    seen = set()
    for pattern, label, priority in _DESCRIPTION_HIGHLIGHTS:
        if re.search(pattern, text, re.I):
            # Bucket by first word so we don't list "New kitchen" and "Updated kitchen" both
            bucket = label.split()[-1].lower()
            if bucket in seen:
                continue
            seen.add(bucket)
            hits.append((priority, label))
    hits.sort(key=lambda t: t[0], reverse=True)
    return [h[1] for h in hits[:max_count]]

def select_feature_bullets(
    beds: str | None,
    baths: str | None,
    sqft: str | None,
    pets: str | None,
    pet_type: str | None,
    amenities: List[str],
    description: str,
    max_bullets: int = 6,
    include_stats: bool = True,
    add_bullets: List[str] | None = None,
    remove_bullets: List[str] | None = None,
) -> List[str]:
    """Build a marketing-ready bullet list blending bed/bath/pets + top amenities.
    When include_stats is False, beds/baths/sqft/pets are skipped entirely (useful when
    the flyer already shows them in a price banner)."""
    bullets: List[str] = []

    if include_stats:
        # 1) Bed/bath always first
        if beds and baths:
            b = int(float(beds)) if beds and beds.replace(".", "").isdigit() else beds
            ba = baths
            try:
                ba = int(float(baths)) if float(baths) == int(float(baths)) else baths
            except Exception:
                pass
            bullets.append(f"{b} bed, {ba} bath")
        elif beds:
            bullets.append(f"{beds} bed")

        # 2) Sqft if we have it
        if sqft:
            bullets.append(f"{sqft} sqft")

        # 3) Pet policy
        if pets:
            p = pets.lower()
            if "yes" in p or "true" in p:
                if pet_type and pet_type.lower() != "none":
                    bullets.append(f"{pet_type.strip()} considered")
                else:
                    bullets.append("Pet friendly")
            elif "no" in p:
                bullets.append("No pets")

    # 4) Description highlights — prefer these, they are the real selling points
    highlights = extract_highlights_from_description(description, max_count=max_bullets + 2)
    for h in highlights:
        if len(bullets) >= max_bullets:
            break
        if h in bullets:
            continue
        bullets.append(h)

    # 5) Fall back to scraped amenities (de-ranked) only if we still need bullets;
    # skip commodity amenities that don't differentiate the listing.
    _SKIP_COMMODITY = {
        "ac", "blinds", "window coverings", "refrigerator",
        "oven", "electric stove", "electric heat", "w/d hookups",
        "dishwasher", "den", "double-pane windows", "vinyl floors",
        "ceiling fan", "gas heat",
    }
    ranked = sorted(
        amenities,
        key=lambda a: _AMENITY_PRIORITY.get(a.lower(), 0),
        reverse=True,
    )
    for amen in ranked:
        if len(bullets) >= max_bullets:
            break
        pretty = _AMENITY_RENAME.get(amen.lower(), amen)
        if pretty in bullets or pretty.lower() in _SKIP_COMMODITY:
            continue
        bullets.append(pretty)

    # Apply per-listing overrides before truncation.
    if remove_bullets:
        remove_lower = {b.strip().lower() for b in remove_bullets}
        bullets = [b for b in bullets if b.strip().lower() not in remove_lower]
    if add_bullets:
        for extra in add_bullets:
            extra = extra.strip()
            if extra and extra not in bullets:
                bullets.append(extra)
    return bullets[:max_bullets]


def condense_description(text: str, target_words: int = 50) -> str:
    import re
    text = re.sub(r"\s+", " ", text).strip()
    # Strip qualification tail (belt-and-suspenders with scraper)
    for pat in [r"\bQualification[s]?[: ].*", r"\bRental Requirements.*", r"\bIncome Requirement.*"]:
        m = re.search(pat, text, re.I | re.S)
        if m:
            text = text[:m.start()].strip()
    words = text.split()
    if len(words) <= target_words:
        return text
    budget = int(target_words * 1.25)
    candidate = " ".join(words[:budget])
    last = list(re.finditer(r"[.!?]", candidate))
    if last:
        cut = last[-1].end()
        if len(candidate[:cut].split()) >= target_words - 6:
            return candidate[:cut].strip()
    return " ".join(words[:target_words]).rstrip(",;:") + "..."
