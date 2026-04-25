# Doss & Spaulding listing flyer generator

Generates a printable 8.5×11 PDF flyer and a 1080×1080 Instagram PNG for any
active rental listing on `dspropertiesnc.com/greensboro-homes-for-rent`, given
just a street address.

## Requirements

Python 3.10+ and these libraries (`pip install ...`):

- `requests`
- `beautifulsoup4`
- `Pillow`
- `cairosvg` (renders the logo SVG + icons)

System dependencies for cairosvg on Debian/Ubuntu:

```bash
apt-get install libcairo2 libpango-1.0-0 libpangocairo-1.0-0 libgdk-pixbuf2.0-0
```

The generator looks for the Google Poppins fonts at
`/usr/share/fonts/truetype/google-fonts/`. If those aren't installed it falls
back to DejaVu Sans. Install Poppins with
`apt-get install fonts-poppins` or by placing `Poppins-{Bold,Medium,Regular}.ttf`
in that directory.

## Usage

```bash
# Generate both flyer + IG post for an address (fuzzy match supported)
python generate.py "916 Harris St"

# Write into a specific folder
python generate.py "916 Harris" --out-dir ./marketing

# Only one of the two
python generate.py "916 Harris" --flyer-only
python generate.py "916 Harris" --ig-only

# See every active listing the index page exposes
python generate.py --list
```

Default filenames are derived from the address, e.g. `916-harris-st_flyer.pdf`
and `916-harris-st_ig.png`. Override with `--pdf-name` / `--png-name`.

## File layout

- `scraper.py` — Fetches the listing index + detail page and returns a typed
  `Listing` object. Handles fuzzy address matching and photo downloads.
- `layout.py` — Brand constants (colors, fonts, contact info), shared PIL
  helpers (circle crop, rounded panels, icons), and copywriting helpers
  (headline builder, feature bullet picker, description condenser).
- `flyer.py` — Composes the 8.5×11 PDF at 300 DPI.
- `instagram.py` — Composes the 1080×1080 PNG.
- `generate.py` — CLI entry point. Finds the listing, downloads photos once,
  and renders both outputs.
- `assets/` — Stacked logo SVGs used inside the black "tag" at the top of
  each piece.

## How the listing is discovered

`find_listing(query)` pulls the index page, extracts every
`/greensboro-homes-for-rent/<id>/<slug>` link, and scores each slug against
the query using a combination of token containment and `SequenceMatcher`.
The highest-scoring match wins as long as it crosses a minimum threshold —
otherwise an error prints the current slugs so you can see what's on the
site.

## Brand customization

Brand constants are grouped at the top of `layout.py`:

```python
GOLD = (167, 130, 72)   # #a78248
BLACK = (15, 15, 15)
PHONE = "(336) 594-5747"
EMAIL = "info@dspropertiesnc.com"
WEBSITE = "dspropertiesnc.com"
OFFICE = "2601 Oakcrest Ave, Ste F"
TAGLINE = "Find beauty and comfort in your dream home with Doss & Spaulding Properties"
```

Edit there — both outputs will pick up the change on the next render.

The headline switches between "HOME FOR RENT" and "UNIT FOR RENT" based on
`Building Type` from the listing. Single-family → home. Duplex, triplex,
apartment, condo, townhouse, unit, multi → unit. The first word is always
gold, the second half is black. Adjust in `build_headline()` in `layout.py`.

## Feature bullet selection

The list on the left of the "Property Features" block is assembled from:

1. Always: `X bed, Y bath`
2. If present: `<sqft> sqft`
3. Pet policy (e.g. `Cats considered` or `Pet friendly`)
4. Up to 3 top-ranked amenities from the scraped list

Amenity rankings and human-friendly renames live in `_AMENITY_PRIORITY` and
`_AMENITY_RENAME` in `layout.py`. Nudge those dicts to prefer different
amenities.

## Notes on reliability

- The rentvine CDN serves photos at `/small.jpg` and `/large.jpg` variants;
  the scraper always upgrades to `large.jpg` before downloading.
- Qualification / credit-score / income-requirement text is stripped from
  the description before it's rendered — that copy reads poorly on a flyer.
- If a listing has fewer than 4 photos, the hero photo is reused to fill
  the three accent slots.
