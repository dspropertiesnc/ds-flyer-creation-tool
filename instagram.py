"""Render a 1080x1080 Instagram square PNG in the "Bold grid" style used by
the printable flyer. Vertical stack:

  - Hero photo (50%) with dark bottom gradient overlay
    · AVAILABLE NOW gold pill
    · "HOME FOR RENT" (first word gold) + address
  - Gold/black price bar
  - Features column (left) + 2x2 landscape photo grid (right)
  - Black footer with horizontal logo, inverted QR code, contact stack

Photo indices mirror the flyer: photos[0] hero, photos[1:5] grid tiles.
"""
from __future__ import annotations

import os
from typing import List
from PIL import Image, ImageDraw

from layout import (
    BLACK, GOLD, TEXT_DARK, TEXT_GREY, WHITE,
    PHONE, EMAIL, WEBSITE, TAGLINE,
    LOGO_STACKED, LOGO_MARK_DARK, ASSETS_DIR,
    build_headline, condense_description, select_feature_bullets,
    fit_cover, font, globe_icon, gold_check_icon, phone_icon,
    qr_code_with_logo, rounded_image, svg_to_pil, vertical_gradient,
)
from scraper import Listing, download_photo
from flyer import _availability_text, _mail_icon, _recolor_logo_for_dark_bg


IG = 1080

MARGIN = 40
HERO_H = 540
PRICE_BAR_H = 78
FOOTER_H = 190


# ---------------------------------------------------------------------------
# Sections
# ---------------------------------------------------------------------------

def _draw_hero(canvas: Image.Image, hero: Image.Image, listing):
    # Upper-anchored crop so the house roofline stays visible
    resized = fit_cover(hero, IG, HERO_H, anchor_y="upper")
    canvas.paste(resized, (0, 0))

    # Bottom gradient
    grad_h = int(HERO_H * 0.58)
    grad = vertical_gradient(IG, grad_h, top=(0, 0, 0, 0), bottom=(0, 0, 0, 210))
    canvas.alpha_composite(grad, dest=(0, HERO_H - grad_h))

    draw = ImageDraw.Draw(canvas)

    # AVAILABLE NOW pill
    kick_text = _availability_text(listing.date_available)
    f_kicker = font("bold", 18)
    kw = draw.textbbox((0, 0), kick_text, font=f_kicker)[2]
    kh = f_kicker.size + 12
    kick_pad_x = 16
    kick_x = MARGIN
    kick_y = HERO_H - 240
    draw.rounded_rectangle(
        (kick_x, kick_y, kick_x + kw + kick_pad_x * 2, kick_y + kh + 4),
        radius=kh // 2, fill=GOLD + (255,),
    )
    draw.text((kick_x + kick_pad_x, kick_y + 4), kick_text, font=f_kicker, fill=WHITE)

    # Giant headline
    headline = build_headline(listing.building_type)
    first, _, rest = headline.partition(" ")
    rest = " " + rest if rest else ""
    f_head = font("bold", 92)
    first_w = draw.textbbox((0, 0), first, font=f_head)[2]
    hl_y = HERO_H - 190
    draw.text((MARGIN, hl_y), first, font=f_head, fill=GOLD)
    draw.text((MARGIN + first_w, hl_y), rest, font=f_head, fill=WHITE)

    # Address
    f_addr = font("medium", 32)
    addr_y = hl_y + 102
    draw.text((MARGIN, addr_y), listing.full_address, font=f_addr, fill=WHITE)


def _draw_price_bar(canvas: Image.Image, listing, y0: int):
    draw = ImageDraw.Draw(canvas)
    draw.rectangle((0, y0, IG, y0 + PRICE_BAR_H), fill=BLACK)
    gold_w = int(IG * 0.42)
    draw.rectangle((0, y0, gold_w, y0 + PRICE_BAR_H), fill=GOLD)

    rent = listing.rent or ""
    rent = rent.replace(".00", "")
    rent_text = f"{rent}/mo" if rent else "FOR RENT"
    f_rent = font("bold", 42)
    rent_w = draw.textbbox((0, 0), rent_text, font=f_rent)[2]
    rx = (gold_w - rent_w) // 2
    ry = y0 + (PRICE_BAR_H - f_rent.size) // 2 - 2
    draw.text((rx, ry), rent_text, font=f_rent, fill=WHITE)

    facts = []
    if listing.beds:
        try:
            facts.append(f"{int(float(listing.beds))} bed")
        except Exception:
            facts.append(f"{listing.beds} bed")
    if listing.baths:
        try:
            ba = float(listing.baths)
            facts.append(f"{int(ba) if ba == int(ba) else ba} bath")
        except Exception:
            facts.append(f"{listing.baths} bath")
    if listing.sqft:
        facts.append(f"{listing.sqft} sqft")
    if listing.pets and listing.pets.lower().startswith("y"):
        facts.append("pets OK")
    facts_text = "  ·  ".join(facts)
    f_facts = font("medium", 28)
    if facts_text:
        fw = draw.textbbox((0, 0), facts_text, font=f_facts)[2]
        fx = gold_w + (IG - gold_w - fw) // 2
        fy = y0 + (PRICE_BAR_H - f_facts.size) // 2 - 2
        draw.text((fx, fy), facts_text, font=f_facts, fill=WHITE)


def _draw_features_column(canvas: Image.Image, x: int, y: int, width: int, bullets: List[str]):
    draw = ImageDraw.Draw(canvas)
    f_eyebrow = font("bold", 15)
    f_head = font("bold", 32)
    f_body = font("medium", 20)

    draw.text((x, y), "PROPERTY", font=f_eyebrow, fill=GOLD)
    draw.text((x, y + 20), "FEATURES", font=f_head, fill=TEXT_DARK)

    rule_y = y + 20 + f_head.size + 8
    draw.rectangle((x, rule_y, x + 60, rule_y + 3), fill=GOLD)

    y_cursor = rule_y + 14
    check = gold_check_icon(26)

    for b in bullets[:4]:
        canvas.alpha_composite(check, dest=(x, y_cursor - 1))
        draw.text((x + 38, y_cursor + 2), b, font=f_body, fill=TEXT_DARK)
        y_cursor += 34

    return y_cursor


def _draw_photo_grid(canvas: Image.Image, photos: List[Image.Image], x: int, y: int,
                     tile_w: int, tile_h: int, gap: int):
    slots = [(x, y), (x + tile_w + gap, y),
             (x, y + tile_h + gap), (x + tile_w + gap, y + tile_h + gap)]
    for i, slot in enumerate(slots):
        if i >= len(photos):
            break
        tile = rounded_image(photos[i], tile_w, tile_h, radius=16, stroke=0)
        canvas.alpha_composite(tile, dest=slot)


def _draw_footer(canvas: Image.Image, listing):
    y0 = IG - FOOTER_H
    draw = ImageDraw.Draw(canvas)
    draw.rectangle((0, y0, IG, IG), fill=BLACK)
    # Thin gold rule
    draw.rectangle((0, y0, IG, y0 + 4), fill=GOLD)

    # Horizontal logo on the left (white + gold)
    logo = svg_to_pil(os.path.join(ASSETS_DIR, "logo_horizontal.svg"), width=320)
    logo = _recolor_logo_for_dark_bg(logo)
    canvas.alpha_composite(logo, dest=(MARGIN, y0 + (FOOTER_H - logo.height) // 2))

    # QR code (inverted) centered-right
    qr_size = 120
    qr_img = qr_code_with_logo(
        listing.url,
        qr_size,
        logo_svg_path=LOGO_MARK_DARK,
        logo_scale=0.26,
        fg_color=WHITE,
        bg_color=BLACK,
        logo_pad_color=BLACK,
    )
    qr_x = IG - MARGIN - 340 - 20 - qr_size
    qr_y = y0 + (FOOTER_H - qr_size) // 2
    canvas.alpha_composite(qr_img, dest=(qr_x, qr_y))

    # Contact items on the far right
    f_item = font("medium", 21)
    icon_size = 30
    items = [
        (globe_icon(icon_size), WEBSITE),
        (phone_icon(icon_size), PHONE),
        (_mail_icon(icon_size), EMAIL),
    ]
    right_pad = 50
    # Right-align the block
    max_tw = max(draw.textbbox((0, 0), t, font=f_item)[2] for _, t in items)
    block_w = icon_size + 12 + max_tw
    col_x = IG - right_pad - block_w
    top_pad = 30
    bottom_pad = 30
    line_h = (FOOTER_H - top_pad - bottom_pad) // 3
    start_y = y0 + top_pad
    for i, (icon, text) in enumerate(items):
        by = start_y + i * line_h
        canvas.alpha_composite(icon, dest=(col_x, by + (line_h - icon_size) // 2))
        draw.text(
            (col_x + icon_size + 12, by + (line_h - f_item.size) // 2 - 2),
            text, font=f_item, fill=WHITE,
        )


# ---------------------------------------------------------------------------
# Top-level
# ---------------------------------------------------------------------------

def render_instagram_image(listing: Listing, photos: List[Image.Image]) -> Image.Image:
    assert len(photos) >= 1, "Need a hero photo"
    canvas = Image.new("RGBA", (IG, IG), WHITE + (255,))

    _draw_hero(canvas, photos[0], listing)
    _draw_price_bar(canvas, listing, HERO_H)

    content_y = HERO_H + PRICE_BAR_H + 22

    # Photo grid on the right
    tile_w = 180
    tile_h = 100   # 3:2 landscape
    grid_gap = 8
    grid_w = tile_w * 2 + grid_gap
    grid_h = tile_h * 2 + grid_gap
    grid_x = IG - MARGIN - grid_w
    grid_photos = photos[1:5]
    _draw_photo_grid(canvas, grid_photos, grid_x, content_y, tile_w, tile_h, grid_gap)

    # Features column on the left
    feat_x = MARGIN
    feat_w = grid_x - MARGIN - 30
    bullets = select_feature_bullets(
        listing.beds, listing.baths, listing.sqft,
        listing.pets, listing.pet_type,
        listing.features, listing.description,
        max_bullets=4, include_stats=False,
        add_bullets=getattr(listing, "_add_features", None),
        remove_bullets=getattr(listing, "_remove_features", None),
    )
    _draw_features_column(canvas, feat_x, content_y, feat_w, bullets)

    _draw_footer(canvas, listing)
    return canvas


def build_instagram_png(listing: Listing, out_path: str,
                        photo_indices: list[int] | None = None) -> str:
    if photo_indices:
        urls = [listing.photos[i] for i in photo_indices[:5]]
    else:
        urls = listing.photos[:5]
    if not urls:
        raise RuntimeError(f"No photos on listing for {listing.full_address}")
    photos = [download_photo(u) for u in urls]
    img = render_instagram_image(listing, photos)
    img.convert("RGB").save(out_path, "PNG", optimize=True)
    return out_path


if __name__ == "__main__":
    import argparse
    from scraper import find_listing
    p = argparse.ArgumentParser()
    p.add_argument("query", nargs="?", default="916 Harris St")
    p.add_argument("out", nargs="?", default=None)
    p.add_argument("--photos", help="Comma-separated photo indices: hero,tile1,tile2,tile3,tile4")
    args = p.parse_args()
    out = args.out or f"{args.query.replace(' ', '_')}_ig.png"
    idx = None
    if args.photos:
        idx = [int(x.strip()) for x in args.photos.split(",") if x.strip()]
    listing = find_listing(args.query)
    path = build_instagram_png(listing, out, photo_indices=idx)
    print(f"Saved {path}")
