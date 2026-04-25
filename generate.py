"""One-shot CLI: given an address, produce a printable PDF flyer and a
1080x1080 Instagram PNG for the matching Doss & Spaulding rental listing.

Usage:
    python generate.py "916 Harris St"
    python generate.py "916 Harris" --out-dir ./marketing
    python generate.py "916 Harris" --pdf-name flyer.pdf --png-name ig.png
    python generate.py "916 Harris" --flyer-only
    python generate.py "916 Harris" --ig-only
    python generate.py --list        # list all active listings

All outputs default to the working directory, filenames derived from the
address slug, e.g. `916-harris-st_flyer.pdf`.
"""
from __future__ import annotations

import argparse
import os
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from typing import List

from scraper import Listing, download_photo, fetch_index, find_listing
from flyer import render_flyer_image, save_pdf
from instagram import render_instagram_image


def _slug(s: str) -> str:
    s = s.lower()
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    return s or "listing"


def _fetch_photos(listing: Listing, n: int = 5, indices: list[int] | None = None):
    """Download photos in parallel. If `indices` is given, pull those specific
    photos (hero first, then grid slots). Otherwise pull the first n."""
    if not listing.photos:
        raise RuntimeError(f"No photos found for {listing.full_address}")
    if indices:
        try:
            urls = [listing.photos[i] for i in indices[:n]]
        except IndexError:
            raise RuntimeError(
                f"photo indices {indices} exceed {len(listing.photos)} available photos"
            )
    else:
        urls = listing.photos[:n] if len(listing.photos) >= n else (listing.photos * n)[:n]
    with ThreadPoolExecutor(max_workers=min(4, len(urls))) as ex:
        return list(ex.map(download_photo, urls))


def _print_summary(listing: Listing) -> None:
    print("Matched listing:")
    print(f"  Address:   {listing.full_address}")
    print(f"  URL:       {listing.url}")
    rent = f"{listing.rent}/mo" if listing.rent else "—"
    size = f"{listing.beds}bed/{listing.baths}bath"
    if listing.sqft:
        size += f" · {listing.sqft} sqft"
    print(f"  Size/rent: {size} · {rent}")
    if listing.building_type:
        print(f"  Type:      {listing.building_type}")
    print(f"  Photos:    {len(listing.photos)} available")


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("query", nargs="?", help="Street address or partial match (e.g. '916 Harris St')")
    p.add_argument("--list", action="store_true", help="List all current active listings and exit")
    p.add_argument("--out-dir", default=".", help="Output directory (default: current dir)")
    p.add_argument("--pdf-name", help="Override the flyer PDF filename")
    p.add_argument("--png-name", help="Override the Instagram PNG filename")
    p.add_argument("--flyer-only", action="store_true", help="Only generate the 8.5x11 PDF")
    p.add_argument("--ig-only", action="store_true", help="Only generate the 1080x1080 PNG")
    p.add_argument("--photos", help="Comma-separated photo indices: hero,tile1,tile2,tile3,tile4 (e.g. 0,6,9,12,14)")
    p.add_argument("--unit", help="Override/force unit number (e.g. 305, B). Auto-detected from slug if omitted.")
    p.add_argument("--add-features", help="Comma-separated bullets to add (e.g. 'Accepts Section 8,Elevator')")
    p.add_argument("--remove-features", help="Comma-separated bullets to remove (exact match, case-insensitive)")
    p.add_argument("--quiet", action="store_true", help="Suppress progress output")
    args = p.parse_args(argv)

    if args.list:
        entries = fetch_index()
        print(f"Found {len(entries)} active listing(s):")
        for e in entries:
            print(f"  - {e['slug']}")
            print(f"      {e['url']}")
        return 0

    if not args.query:
        p.error("query address is required unless --list is used")
        return 2

    os.makedirs(args.out_dir, exist_ok=True)

    log = (lambda *a, **kw: None) if args.quiet else print

    t0 = time.time()
    log(f"Searching for: {args.query!r}")
    listing = find_listing(args.query)
    if args.unit:
        listing.unit = args.unit
    if args.add_features:
        listing._add_features = [s.strip() for s in args.add_features.split(",") if s.strip()]
    if args.remove_features:
        listing._remove_features = [s.strip() for s in args.remove_features.split(",") if s.strip()]
    if not args.quiet:
        _print_summary(listing)

    log("\nDownloading photos...")
    photo_indices = None
    if args.photos:
        photo_indices = [int(x.strip()) for x in args.photos.split(",") if x.strip()]
    photos = _fetch_photos(listing, n=5, indices=photo_indices)

    base = _slug(listing.address)
    pdf_path = os.path.join(args.out_dir, args.pdf_name or f"{base}_flyer.pdf")
    png_path = os.path.join(args.out_dir, args.png_name or f"{base}_ig.png")

    outputs: List[str] = []
    if not args.ig_only:
        log(f"Rendering flyer -> {pdf_path}")
        img = render_flyer_image(listing, photos)
        save_pdf(img, pdf_path)
        outputs.append(pdf_path)
    if not args.flyer_only:
        log(f"Rendering Instagram -> {png_path}")
        img = render_instagram_image(listing, photos)
        img.convert("RGB").save(png_path, "PNG", optimize=True)
        outputs.append(png_path)

    log(f"\nDone in {time.time() - t0:.1f}s. Wrote:")
    for o in outputs:
        log(f"  {o}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
