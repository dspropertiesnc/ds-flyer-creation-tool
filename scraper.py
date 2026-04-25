"""Fetch and parse Doss & Spaulding rental listings from dspropertiesnc.com."""
from __future__ import annotations

import io
import re
import time
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from typing import List, Optional
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup
from PIL import Image

INDEX_URL = "https://www.dspropertiesnc.com/greensboro-homes-for-rent"

_UNIT_LABELED = re.compile(r"(?:unit|apt|apartment|suite|ste)[-_ ]+([a-z0-9]+)", re.I)
_UNIT_SINGLE_LETTER = re.compile(
    r"(?:\bst|\bave|\brd|\bdr|\bln|\bblvd|\bpl|\bct|\bway|\bpkwy)[-\s]+([a-z])(?=[-\s])",
    re.I,
)

def _extract_unit(slug: str) -> Optional[str]:
    m = _UNIT_LABELED.search(slug)
    if m:
        return m.group(1).upper()
    m = _UNIT_SINGLE_LETTER.search(slug)
    if m:
        return m.group(1).upper()
    return None

BASE = "https://www.dspropertiesnc.com"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0 Safari/537.36"
    )
}


@dataclass
class Listing:
    """A normalized rental listing."""
    address: str                # "916 Harris St"
    city: str                   # "Burlington"
    state: str                  # "NC"
    zip_code: str               # "27217"
    url: str                    # full detail-page URL
    rent: Optional[str] = None  # "$895.00"
    beds: Optional[str] = None  # "1"
    baths: Optional[str] = None  # "1"
    sqft: Optional[str] = None  # "601"
    building_type: Optional[str] = None   # "Single Family" / "Duplex" / etc.
    pets: Optional[str] = None           # "Yes" / "No" / "Cats"
    pet_type: Optional[str] = None
    date_available: Optional[str] = None
    unit: Optional[str] = None
    headline: Optional[str] = None       # Full listing title from schema.org
    description: str = ""                # Full marketing description
    features: List[str] = field(default_factory=list)
    photos: List[str] = field(default_factory=list)   # CDN URLs, hero first

    @property
    def full_address(self) -> str:
        addr = self.address
        if self.unit:
            addr = f"{addr}, Unit {self.unit}"
        return f"{addr}, {self.city}, {self.state} {self.zip_code}"


# ---------------------------------------------------------------------------
# Index page: enumerate all listings (fuzzy match target)
# ---------------------------------------------------------------------------

def fetch_index() -> List[dict]:
    """Return a list of {address, url} for every listing on the index page."""
    resp = requests.get(INDEX_URL, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    out = []
    # Each listing links to /greensboro-homes-for-rent/<id>/<slug>
    seen = set()
    for a in soup.find_all("a", href=True):
        href = a["href"]
        m = re.search(r"/greensboro-homes-for-rent/(\d+)/([a-z0-9-]+)/?$", href)
        if not m:
            continue
        full = urljoin(BASE, href)
        if full in seen:
            continue
        seen.add(full)
        # Derive a human-ish address from the slug for fuzzy matching
        slug = m.group(2).replace("-", " ")
        out.append({"url": full, "slug": slug, "id": m.group(1)})
    return out


# ---------------------------------------------------------------------------
# Detail page: parse a single listing
# ---------------------------------------------------------------------------

_NUM_RE = re.compile(r"[\d.,]+")


def _clean_ws(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()


def _strip_qualification_tail(text: str) -> str:
    """Remove qualification requirements from description."""
    # Cut at 'Qualifications', 'Rental Requirements', 'Qualification Requirements'
    patterns = [
        r"\bQualification[s]?[: ].*",
        r"\bRental Requirements.*",
        r"\bApplication Requirements.*",
        r"\bTo Qualify.*",
        r"\bRequirements:.*",
        r"\bIncome Requirement.*",
        r"\bMinimum (?:Income|Credit).*",
    ]
    cut = len(text)
    for p in patterns:
        m = re.search(p, text, re.I | re.S)
        if m:
            cut = min(cut, m.start())
    return text[:cut].strip()


def _condense(text: str, target_words: int = 50) -> str:
    """Trim description to roughly `target_words` words, ending on a sentence if possible."""
    text = _clean_ws(text)
    words = text.split()
    if len(words) <= target_words:
        return text
    # Prefer cutting at a sentence boundary within the first target_words*1.2 words
    budget = int(target_words * 1.25)
    candidate = " ".join(words[:budget])
    # Find the last sentence-ending punctuation within the candidate
    m = list(re.finditer(r"[.!?]", candidate))
    if m:
        last = m[-1].end()
        # Only accept if we're at or past target_words
        cut_words = len(candidate[:last].split())
        if cut_words >= target_words - 5:
            return candidate[:last].strip()
    # Fallback: cut at target_words, add ellipsis
    return " ".join(words[:target_words]).rstrip(",;:") + "..."


def parse_detail(url: str) -> Listing:
    resp = requests.get(url, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    html = resp.text
    soup = BeautifulSoup(html, "html.parser")

    # --- Address (h1 + h2) ---
    h1 = soup.find("h1")
    address = _clean_ws(h1.get_text(" ", strip=True)) if h1 else ""
    h2 = soup.find("h2")
    city = state = zip_code = ""
    if h2:
        h2t = _clean_ws(h2.get_text(" ", strip=True))
        # "Burlington, NC 27217" possibly with stray commas
        m = re.match(r"([^,]+),\s*([A-Z]{2})\s*(\d{5})", h2t)
        if m:
            city, state, zip_code = m.group(1).strip(), m.group(2), m.group(3)
        else:
            # Fallback: split by whitespace
            parts = h2t.replace(",", " ").split()
            if len(parts) >= 3:
                zip_code = parts[-1]
                state = parts[-2]
                city = " ".join(parts[:-2])

    # --- Headline (parsed first so KV fallback can use it) ---
    headline = None
    sc = soup.find("script", string=re.compile("RealEstateListing"))
    if sc and sc.string:
        m = re.search(r'"name":\s*"([^"]+)"', sc.string)
        if m:
            headline = m.group(1)

    # --- Core property info block ---
    info = soup.find(class_="rvw-details__property-info")
    info_text = _clean_ws(info.get_text(" ", strip=True)) if info else ""

    rent = None
    m = re.search(r"\$[\d,]+(?:\.\d{2})?", info_text)
    if m:
        rent = m.group()

    def _grab_num(label: str) -> Optional[str]:
        m = re.search(rf"(\d+(?:\.\d+)?)\s*{label}", info_text, re.I)
        return m.group(1) if m else None

    beds = _grab_num("Beds?")
    baths = _grab_num("Baths?")
    sqft = _grab_num("sqft")

    # Use the full list of known keys as a barrier so "Yes" doesn't bleed into "Date Available"
    KNOWN_KEYS = ["Building Type", "Pet Type", "Date Available", "Pets"]
    barrier = "|".join(re.escape(k) + r":" for k in KNOWN_KEYS)

    def _grab_kv(label: str) -> Optional[str]:
        pattern = rf"{re.escape(label)}:\s*(.+?)(?=\s+(?:{barrier})|$)"
        m = re.search(pattern, info_text)
        return m.group(1).strip() if m else None

    building_type = _grab_kv("Building Type")
    pets = _grab_kv("Pets")
    pet_type = _grab_kv("Pet Type")
    
    def _clamp_date(v):
        if not v:
            return v
        v = v.strip()
        # Accept ISO or m/d/y first, else the first capitalized word
        m = re.match(r"(\d{1,2}/\d{1,2}/\d{2,4}|\d{4}-\d{2}-\d{2})", v)
        if m:
            return m.group(1)
        m = re.match(r"([A-Z][a-z]+(?:\s+\d{1,2}(?:,\s*\d{4})?)?)", v)
        if m:
            return m.group(1)
        return v.split()[0] if v.split() else v
    date_available = _grab_kv("Date Available")
    date_available = _clamp_date(date_available)
    # Trim the headline if it accidentally got absorbed (happens when info block
    # runs directly into the property description without punctuation)
    if pet_type and headline and headline in pet_type:
        pet_type = pet_type.split(headline)[0].strip()

    # --- Description ---
    desc_el = soup.find(class_="description")
    description = _clean_ws(desc_el.get_text(" ", strip=True)) if desc_el else ""
    description = _strip_qualification_tail(description)

    # --- Features and amenities ---
    features: List[str] = []
    fa = soup.find(string=re.compile(r"Features and Amenities", re.I))
    if fa:
        section = fa.find_parent(["section", "div"])
        if section:
            for ul in section.find_all("ul"):
                for li in ul.find_all("li"):
                    t = _clean_ws(li.get_text(" ", strip=True))
                    if t and len(t) < 60:
                        features.append(t)
    # Dedup while preserving order
    seen = set()
    features = [f for f in features if not (f in seen or seen.add(f))]

    # --- Photos ---
    photos: List[str] = []
    seen_p = set()
    for img in soup.find_all("img"):
        src = img.get("data-src") or img.get("src") or ""
        if "cdn.rentvine.com" not in src:
            continue
        # Always request the "large" variant
        src = re.sub(r"/small\.jpg$", "/large.jpg", src)
        if src in seen_p:
            continue
        seen_p.add(src)
        photos.append(src)

    return Listing(
        address=address,
        city=city,
        state=state,
        zip_code=zip_code,
        url=url,
        rent=rent,
        beds=beds,
        baths=baths,
        sqft=sqft,
        building_type=building_type,
        pets=pets,
        pet_type=pet_type,
        date_available=date_available,
        headline=headline,
        description=description,
        features=features,
        photos=photos,
    )


# ---------------------------------------------------------------------------
# Fuzzy address match
# ---------------------------------------------------------------------------

def _normalize(s: str) -> str:
    s = s.lower()
    s = re.sub(r"[^a-z0-9 ]+", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    # Street type synonyms (collapse to a common token)
    subs = {
        r"\bstreet\b": "st",
        r"\bavenue\b": "ave",
        r"\bdrive\b": "dr",
        r"\bboulevard\b": "blvd",
        r"\bcourt\b": "ct",
        r"\bplace\b": "pl",
        r"\blane\b": "ln",
        r"\broad\b": "rd",
        r"\bapartment\b": "apt",
        r"\bnorth\b": "n",
        r"\bsouth\b": "s",
        r"\beast\b": "e",
        r"\bwest\b": "w",
    }
    for p, r in subs.items():
        s = re.sub(p, r, s)
    return re.sub(r"\s+", " ", s).strip()


def find_listing(query: str) -> Listing:
    """Fetch the index, fuzzy-match the query to a slug, then load the detail."""
    q_norm = _normalize(query)
    index = fetch_index()
    if not index:
        raise RuntimeError("No listings found on the index page.")

    # Score by substring match first, then SequenceMatcher
    scored = []
    for entry in index:
        slug_norm = _normalize(entry["slug"])
        ratio = SequenceMatcher(None, q_norm, slug_norm).ratio()
        sub_bonus = 0.25 if q_norm in slug_norm else 0.0
        # All query tokens present in slug
        q_tokens = q_norm.split()
        if q_tokens and all(tok in slug_norm.split() for tok in q_tokens):
            sub_bonus = max(sub_bonus, 0.35)
        scored.append((ratio + sub_bonus, entry))

    scored.sort(key=lambda x: x[0], reverse=True)
    top_score, top_entry = scored[0]
    if top_score < 0.35:
        addrs = ", ".join(e["slug"] for e in index[:8])
        raise RuntimeError(
            f"No listing matched {query!r} (best score {top_score:.2f}). "
            f"Current listings include: {addrs}"
        )
    listing = parse_detail(top_entry["url"])
    if listing.unit is None:
        listing.unit = _extract_unit(top_entry["slug"])
    return listing


# ---------------------------------------------------------------------------
# Photo downloader
# ---------------------------------------------------------------------------

def download_photo(url: str, retries: int = 3) -> Image.Image:
    last_err = None
    for attempt in range(retries):
        try:
            r = requests.get(url, headers=HEADERS, timeout=30)
            r.raise_for_status()
            img = Image.open(io.BytesIO(r.content))
            img.load()
            return img.convert("RGB")
        except Exception as e:
            last_err = e
            time.sleep(0.5 * (attempt + 1))
    raise RuntimeError(f"Failed to download {url}: {last_err}")


if __name__ == "__main__":
    import json
    import sys
    query = sys.argv[1] if len(sys.argv) > 1 else "916 Harris St"
    listing = find_listing(query)
    out = {k: v for k, v in listing.__dict__.items() if k != "photos"}
    out["photos_count"] = len(listing.photos)
    out["first_photo"] = listing.photos[0] if listing.photos else None
    print(json.dumps(out, indent=2))
   