"""Render an 8.5x11 print flyer PDF for a Doss & Spaulding rental listing.

Layout: "Bold grid"
  - Top 38% of page is a full-bleed hero photo
  - Dark bottom gradient on the hero for readability
  - "HOME FOR RENT" (first word gold) + address overlaid on the hero
  - Gold/black price bar immediately under the hero
  - Content block: "Property Features" (left) + 2x2 photo grid (right)
  - "About Home" section spans full width below the grid
  - Black footer with logo + contact row

All photos are used at most once: photo[0] is the hero, photos[1:5] fill
the 2x2 grid. If the listing has fewer than 5 photos, the grid truncates
rather than repeating a photo.
"""
from __future__ import annotations

import os
from typing import List
from PIL import Image, ImageDraw

from layout import (
    BLACK, GOLD, OFFWHITE, TEXT_DARK, TEXT_GREY, WHITE,
    PHONE, EMAIL, WEBSITE, OFFICE, TAGLINE,
    LOGO_STACKED, LOGO_MARK_DARK, ASSETS_DIR,
    build_headline, condense_description, select_feature_bullets,
    draw_text_justified, draw_wrapped, fit_cover, font,
    globe_icon, gold_check_icon, phone_icon, pin_icon, qr_code_with_logo,
    rounded_image, svg_to_pil, vertical_gradient, wrap_text,
)
from scraper import Listing, download_photo


# 300 DPI 8.5x11 in
FLYER_W = 2550
FLYER_H = 3300

MARGIN = 110
HERO_H = 1280
PRICE_BAR_H = 165
FOOTER_H = 370


# ---------------------------------------------------------------------------
# Hero + overlay
# ---------------------------------------------------------------------------

def _recolor_logo_for_dark_bg(logo: Image.Image) -> Image.Image:
    """The stacked logo SVG is black+brown. On dark backgrounds the black disappears;
    repaint the near-black pixels white (and leave the brown alone)."""
    logo = logo.convert("RGBA")
    data = logo.load()
    for y in range(logo.height):
        for x in range(logo.width):
            r, g, b, a = data[x, y]
            if a == 0:
                continue
            if r < 60 and g < 60 and b < 60:
                data[x, y] = (WHITE[0], WHITE[1], WHITE[2], a)
    return logo



def _availability_text(date_available: str | None) -> str:
    """Turn listing.date_available into a short marketing string for the hero pill.
    Empty / 'Immediately' / 'Now'  -> 'AVAILABLE NOW'
    Future date                    -> 'AVAILABLE <DATE>'
    If the scraped value is too long (scraper overcaptured into the description),
    fall back to the generic label.
    """
    if not date_available:
        return "AVAILABLE NOW"
    s = date_available.strip()
    low = s.lower()
    if low in ("immediately", "now", "asap", "today", "immediate") or low.startswith("immediately"):
        return "AVAILABLE NOW"
    if len(s) > 20:
        return "AVAILABLE NOW"
    return f"AVAILABLE {s.upper()}"


def _draw_hero(canvas: Image.Image, hero: Image.Image, listing):
    # Upper-anchored crop keeps the roofline in frame instead of cropping the
    # top of the house when the source is much wider than the hero band.
    resized = fit_cover(hero, FLYER_W, HERO_H, anchor_y="upper")
    canvas.paste(resized, (0, 0))

    # Bottom gradient so overlaid text reads cleanly on any photo
    grad_h = int(HERO_H * 0.55)
    grad = vertical_gradient(FLYER_W, grad_h, top=(0, 0, 0, 0), bottom=(0, 0, 0, 205))
    canvas.alpha_composite(grad, dest=(0, HERO_H - grad_h))

    draw = ImageDraw.Draw(canvas)

    # --- "AVAILABLE ..." gold pill (status) ---
    kick_text = _availability_text(listing.date_available)
    f_kicker = font("bold", 42)
    kw = draw.textbbox((0, 0), kick_text, font=f_kicker)[2]
    kh = f_kicker.size + 30
    kick_pad_x = 36
    kick_x = MARGIN
    kick_y = HERO_H - 560
    draw.rounded_rectangle(
        (kick_x, kick_y, kick_x + kw + kick_pad_x * 2, kick_y + kh + 10),
        radius=kh // 2,
        fill=GOLD + (255,),
    )
    draw.text((kick_x + kick_pad_x, kick_y + 8), kick_text, font=f_kicker, fill=WHITE)

    # --- Giant headline "HOME FOR RENT" ---
    headline = build_headline(listing.building_type)
    first, _, rest = headline.partition(" ")
    rest = " " + rest if rest else ""
    f_head = font("bold", 220)
    first_w = draw.textbbox((0, 0), first, font=f_head)[2]
    rest_w = draw.textbbox((0, 0), rest, font=f_head)[2]
    hl_x = MARGIN
    hl_y = HERO_H - 410
    draw.text((hl_x, hl_y), first, font=f_head, fill=GOLD)
    draw.text((hl_x + first_w, hl_y), rest, font=f_head, fill=WHITE)

    # --- Address ---
    f_addr = font("medium", 78)
    addr_y = hl_y + 240
    draw.text((MARGIN, addr_y), listing.full_address, font=f_addr, fill=WHITE)


# ---------------------------------------------------------------------------
# Price bar
# ---------------------------------------------------------------------------

def _draw_price_bar(canvas: Image.Image, listing, y0: int):
    draw = ImageDraw.Draw(canvas)
    # Black bar with a gold left segment
    draw.rectangle((0, y0, FLYER_W, y0 + PRICE_BAR_H), fill=BLACK)
    gold_w = int(FLYER_W * 0.42)
    draw.rectangle((0, y0, gold_w, y0 + PRICE_BAR_H), fill=GOLD)

    # Rent price
    rent = (listing.rent or "").replace(".00", "").replace("$", "$")
    if not rent.startswith("$"):
        rent = "$" + rent.lstrip("$") if rent else ""
    rent_text = f"{rent}/mo" if rent else "FOR RENT"
    f_rent = font("bold", 92)
    rent_w = draw.textbbox((0, 0), rent_text, font=f_rent)[2]
    rx = (gold_w - rent_w) // 2
    ry = y0 + (PRICE_BAR_H - f_rent.size) // 2 - 4
    draw.text((rx, ry), rent_text, font=f_rent, fill=WHITE)

    # Quick facts on the black side
    facts = []
    if listing.beds:
        try:
            b = int(float(listing.beds)); facts.append(f"{b} bed")
        except Exception:
            facts.append(f"{listing.beds} bed")
    if listing.baths:
        try:
            ba = int(float(listing.baths))
            if float(listing.baths) == ba:
                facts.append(f"{ba} bath")
            else:
                facts.append(f"{listing.baths} bath")
        except Exception:
            facts.append(f"{listing.baths} bath")
    if listing.sqft:
        facts.append(f"{listing.sqft} sqft")
    if listing.pets and listing.pets.lower().startswith("y"):
        facts.append("pets OK")
    facts_text = "   ·   ".join(facts)
    f_facts = font("medium", 60)
    if facts_text:
        fw = draw.textbbox((0, 0), facts_text, font=f_facts)[2]
        fx = gold_w + (FLYER_W - gold_w - fw) // 2
        fy = y0 + (PRICE_BAR_H - f_facts.size) // 2 - 4
        draw.text((fx, fy), facts_text, font=f_facts, fill=WHITE)


# ---------------------------------------------------------------------------
# Two-column content block (features left, 2x2 photo grid right)
# ---------------------------------------------------------------------------

def _draw_features_column(canvas: Image.Image, x: int, y: int, width: int, bullets: List[str]):
    draw = ImageDraw.Draw(canvas)
    f_eyebrow = font("bold", 34)
    f_head = font("bold", 72)
    f_body = font("medium", 44)

    draw.text((x, y), "PROPERTY", font=f_eyebrow, fill=GOLD)
    draw.text((x, y + 50), "FEATURES", font=f_head, fill=TEXT_DARK)

    # Thin gold rule under the header
    rule_y = y + 50 + f_head.size + 24
    draw.rectangle((x, rule_y, x + 140, rule_y + 6), fill=GOLD)

    y_cursor = rule_y + 46
    check = gold_check_icon(56)

    for b in bullets:
        canvas.alpha_composite(check, dest=(x, y_cursor - 4))
        draw.text((x + 90, y_cursor + 4), b, font=f_body, fill=TEXT_DARK)
        y_cursor += 92

    return y_cursor


def _draw_photo_grid(canvas: Image.Image, photos: List[Image.Image],
                     x: int, y: int, tile_w: int, tile_h: int, gap: int):
    """2x2 grid of tiles (any aspect). `photos` is used once per slot."""
    slots = [(x, y), (x + tile_w + gap, y),
             (x, y + tile_h + gap), (x + tile_w + gap, y + tile_h + gap)]
    for i, slot in enumerate(slots):
        if i >= len(photos):
            break
        tile = rounded_image(photos[i], tile_w, tile_h, radius=28, stroke=0)
        canvas.alpha_composite(tile, dest=slot)


def _draw_about(canvas: Image.Image, x: int, y: int, width: int, description: str) -> int:
    draw = ImageDraw.Draw(canvas)
    f_eyebrow = font("bold", 34)
    f_head = font("bold", 72)
    f_body = font("medium", 40)

    draw.text((x, y), "ABOUT", font=f_eyebrow, fill=GOLD)
    draw.text((x, y + 50), "THIS HOME", font=f_head, fill=TEXT_DARK)
    rule_y = y + 50 + f_head.size + 24
    draw.rectangle((x, rule_y, x + 140, rule_y + 6), fill=GOLD)

    body_y = rule_y + 46
    text = condense_description(description, target_words=60)
    end_y = draw_text_justified(draw, (x, body_y), text, f_body, width,
                                fill=TEXT_DARK, line_gap=14)
    return end_y


# ---------------------------------------------------------------------------
# Footer
# ---------------------------------------------------------------------------


def _mail_icon(size: int, color=WHITE) -> Image.Image:
    """Simple envelope icon rendered from inline SVG."""
    import cairosvg, io
    from PIL import Image as _I
    hex_color = "#{:02x}{:02x}{:02x}".format(*color)
    svg = f"""<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24'>
      <path fill='none' stroke='{hex_color}' stroke-width='1.6'
            d='M3 6.5 A1.5 1.5 0 0 1 4.5 5 h15 A1.5 1.5 0 0 1 21 6.5 v11 A1.5 1.5 0 0 1 19.5 19 h-15 A1.5 1.5 0 0 1 3 17.5 z' />
      <path fill='none' stroke='{hex_color}' stroke-width='1.6' stroke-linecap='round'
            d='M4 7 L12 13 L20 7' />
    </svg>"""
    png = cairosvg.svg2png(bytestring=svg.encode(), output_width=size*4, output_height=size*4)
    return _I.open(io.BytesIO(png)).convert("RGBA").resize((size, size), _I.LANCZOS)

def _draw_footer(canvas: Image.Image, listing=None):
    y0 = FLYER_H - FOOTER_H
    draw = ImageDraw.Draw(canvas)
    draw.rectangle((0, y0, FLYER_W, FLYER_H), fill=BLACK)
    # Thin gold rule at the very top of the footer
    draw.rectangle((0, y0, FLYER_W, y0 + 8), fill=GOLD)

    f_item = font("medium", 46)
    icon_size = 72

    # Horizontal logo on the left
    logo = svg_to_pil(os.path.join(ASSETS_DIR, "logo_horizontal.svg"), width=790)
    logo = _recolor_logo_for_dark_bg(logo)
    lh = logo.height
    canvas.alpha_composite(logo, dest=(MARGIN, y0 + (FOOTER_H - lh) // 2))

    # Contact items stacked on the right
    items = [
        (globe_icon(icon_size), WEBSITE),
        (phone_icon(icon_size), PHONE),
        (_mail_icon(icon_size), EMAIL),
    ]
    # Give the contact column explicit top/bottom safe padding so the last
    # line (address) never crowds the page trim edge during print.
    bottom_pad = 80
    top_pad = 60
    line_h = (FOOTER_H - top_pad - bottom_pad) // 3
    start_y = y0 + top_pad
    # Compute the widest combined row so we can right-align consistently
    max_block_w = 0
    blocks = []
    for icon, text in items:
        text_w = draw.textbbox((0, 0), text, font=f_item)[2]
        block_w = icon_size + 32 + text_w
        blocks.append((icon, text, block_w))
        max_block_w = max(max_block_w, block_w)
    # --- QR code to the listing URL, placed just to the left of the contact column ---
    # Inverted colors (white dots, black background) to blend into the footer.
    qr_size = 240
    qr_url = listing.url if listing is not None else "https://www.dspropertiesnc.com"
    qr_img = qr_code_with_logo(
        qr_url, qr_size,
        logo_svg_path=LOGO_MARK_DARK,
        logo_scale=0.26,
        fg_color=WHITE,
        bg_color=BLACK,
        logo_pad_color=BLACK,   # seamless blend with the footer
    )
    qr_right_gap = 80
    col_x = FLYER_W - 160 - max_block_w
    qr_x = col_x - qr_right_gap - qr_size
    qr_y = y0 + (FOOTER_H - qr_size) // 2
    canvas.alpha_composite(qr_img, dest=(qr_x, qr_y))
    for i, (icon, text, _) in enumerate(blocks):
        by = start_y + i * line_h
        canvas.alpha_composite(icon, dest=(col_x, by + (line_h - icon_size) // 2))
        draw.text(
            (col_x + icon_size + 32, by + (line_h - f_item.size) // 2 - 4),
            text, font=f_item, fill=WHITE,
        )


# ---------------------------------------------------------------------------
# Top-level render
# ---------------------------------------------------------------------------

def render_flyer_image(listing: Listing, photos: List[Image.Image]) -> Image.Image:
    assert len(photos) >= 1, "Need at least a hero photo"
    canvas = Image.new("RGBA", (FLYER_W, FLYER_H), WHITE + (255,))

    # Hero + overlay
    _draw_hero(canvas, photos[0], listing)

    # Price bar
    price_y = HERO_H
    _draw_price_bar(canvas, listing, price_y)

    # Two-column content area
    content_y = price_y + PRICE_BAR_H + 80
    gap = 80

    # Photo grid on the right (2x2). Landscape tiles match the source 3:2 ratio
    # so the full photo renders with minimal cropping.
    tile_w = 540
    tile_h = 360
    grid_gap = 26
    grid_w = tile_w * 2 + grid_gap
    grid_x = FLYER_W - MARGIN - grid_w
    grid_photos = photos[1:5]                     # 4 photos (no reuse of hero)
    _draw_photo_grid(canvas, grid_photos, grid_x, content_y, tile_w, tile_h, grid_gap)
    grid_bottom = content_y + tile_h * 2 + grid_gap

    # Features on the left
    feat_x = MARGIN
    feat_w = grid_x - MARGIN - gap
    bullets = select_feature_bullets(
        listing.beds, listing.baths, listing.sqft,
        listing.pets, listing.pet_type,
        listing.features, listing.description,
        max_bullets=6,
        include_stats=False,
        add_bullets=getattr(listing, "_add_features", None),
        remove_bullets=getattr(listing, "_remove_features", None),
    )
    feat_bottom = _draw_features_column(canvas, feat_x, content_y, feat_w, bullets)

    # About Home spans full width below whichever column is taller
    about_y = max(feat_bottom, grid_bottom) + 110
    about_w = FLYER_W - MARGIN * 2
    _draw_about(canvas, MARGIN, about_y, about_w, listing.description)

    _draw_footer(canvas, listing=listing)
    return canvas


def save_pdf(img: Image.Image, out_path: str) -> None:
    rgb = Image.new("RGB", img.size, WHITE)
    if img.mode == "RGBA":
        rgb.paste(img, mask=img.split()[3])
    else:
        rgb.paste(img)
    rgb.save(out_path, "PDF", resolution=300.0)


def build_flyer_pdf(listing: Listing, out_path: str,
                    photo_indices: list[int] | None = None) -> str:
    # Photo order: hero first, then 4 for the grid. If caller passes explicit
    # indices, use those; otherwise default to the first five photos.
    if photo_indices:
        try:
            urls = [listing.photos[i] for i in photo_indices[:5]]
        except IndexError:
            raise RuntimeError(
                f"photo_indices {photo_indices} exceeds {len(listing.photos)} "
                f"available photos"
            )
    else:
        urls = listing.photos[:5]
    if not urls:
        raise RuntimeError(f"No photos on listing for {listing.full_address}")
    photos = [download_photo(u) for u in urls]
    img = render_flyer_image(listing, photos)
    save_pdf(img, out_path)
    return out_path


if __name__ == "__main__":
    import argparse
    from scraper import find_listing
    p = argparse.ArgumentParser()
    p.add_argument("query", nargs="?", default="916 Harris St")
    p.add_argument("out", nargs="?", default=None)
    p.add_argument("--photos", help="Comma-separated photo indices: hero,tile1,tile2,tile3,tile4")
    args = p.parse_args()
    out = args.out or f"{args.query.replace(' ', '_')}_flyer.pdf"
    idx = None
    if args.photos:
        idx = [int(x.strip()) for x in args.photos.split(",") if x.strip()]
    listing = find_listing(args.query)
    path = build_flyer_pdf(listing, out, photo_indices=idx)
    print(f"Saved {path}")
