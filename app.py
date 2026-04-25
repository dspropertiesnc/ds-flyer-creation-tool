"""Streamlit web app for the Doss & Spaulding marketing-materials generator."""
from __future__ import annotations

import io
import os
from typing import List

import cairosvg
import streamlit as st
from PIL import Image

from scraper import find_listing, download_photo
from flyer import render_flyer_image, save_pdf
from instagram import render_instagram_image
from layout import ASSETS_DIR


# --- Page config ------------------------------------------------------------

st.set_page_config(
    page_title="D&S Marketing Materials",
    page_icon="🏠",
    layout="wide",
    initial_sidebar_state="collapsed",
)

_GOLD = "#a78248"

st.markdown(
    f"""
    <style>
      .stApp {{background-color: #ffffff;}}
      h1 {{color: #111; font-weight: 800;}}
      /* Gray input box with black text */
      .stTextInput > div > div > input {{
          background-color: #f0f0f0 !important;
          color: #000000 !important;
      }}
      .slot-chip {{display: inline-block; background: {_GOLD}; color: white;
                  padding: 2px 10px; border-radius: 12px; font-size: 0.75rem;
                  font-weight: 700; margin-bottom: 4px;}}
      .muted {{color: #555; font-size: 0.85rem;}}
    </style>
    """,
    unsafe_allow_html=True,
)


# --- Session state ----------------------------------------------------------

if "listing" not in st.session_state:
    st.session_state.listing = None
if "photo_images" not in st.session_state:
    st.session_state.photo_images = []
if "selection" not in st.session_state:
    st.session_state.selection = []
if "flyer_bytes" not in st.session_state:
    st.session_state.flyer_bytes = None
if "ig_bytes" not in st.session_state:
    st.session_state.ig_bytes = None


def _reset_outputs():
    st.session_state.flyer_bytes = None
    st.session_state.ig_bytes = None


@st.cache_data
def _logo_image(width: int = 520):
    png = cairosvg.svg2png(
        url=os.path.join(ASSETS_DIR, "logo_horizontal.svg"),
        output_width=width,
    )
    return Image.open(io.BytesIO(png)).convert("RGBA")


# --- Header (logo) ----------------------------------------------------------

cols_h = st.columns([1, 2, 1])
with cols_h[1]:
    st.image(_logo_image(520), use_container_width=True)
st.title("Listing Marketing Materials")
st.caption(
    "Type a property address from the website, pick five photos, and generate "
    "a printable flyer and a square social-media post."
)


# --- Step 1: Find listing ---------------------------------------------------

st.subheader("1 · Find the listing")

col_addr, col_btn = st.columns([4, 1])
with col_addr:
    query = st.text_input(
        "Street address (fuzzy match is fine)",
        value=st.session_state.get("last_query", ""),
        placeholder="e.g. 916 Harris St",
        label_visibility="collapsed",
    )
with col_btn:
    find_clicked = st.button("Find listing", type="primary", use_container_width=True)

if find_clicked and query.strip():
    st.session_state.last_query = query
    st.session_state.selection = []
    _reset_outputs()
    with st.spinner("Fetching listing + photos…"):
        try:
            listing = find_listing(query.strip())
            st.session_state.listing = listing
            st.session_state.photo_images = [download_photo(u) for u in listing.photos]
        except Exception as e:
            st.error(f"Couldn't find a listing for {query!r}: {e}")
            st.session_state.listing = None


listing = st.session_state.listing
if listing is None:
    st.info(
        "Enter an address above and click **Find listing** to get started.\n\n"
        "**Note:** This tool only pulls listings that are currently active on "
        "[dspropertiesnc.com](https://www.dspropertiesnc.com/greensboro-homes-for-rent). "
        "If you don't see your property, double-check that it's listed there."
    )
    st.stop()


# --- Step 2: Listing summary ------------------------------------------------

st.subheader("2 · Confirm the match")

cols = st.columns(4)
cols[0].metric("Rent", f"{listing.rent}/mo" if listing.rent else "—")
cols[1].metric("Beds / Baths", f"{listing.beds or '—'} / {listing.baths or '—'}")
cols[2].metric("Sqft", listing.sqft or "—")
cols[3].metric("Type", listing.building_type or "—")

st.markdown(f"**{listing.full_address}**")
st.markdown(f"[Open on dspropertiesnc.com ↗]({listing.url})")

with st.expander("Scraped description (used for the About section)"):
    st.write(listing.description or "(none)")


# --- Step 3: Photo picker ---------------------------------------------------

st.subheader("3 · Pick five photos")
st.caption(
    "Click thumbnails in this order: **1. Hero** (big top photo) · "
    "**2 – 5. Grid tiles** (shown in a 2×2 below the price bar)."
)

sel = st.session_state.selection


def _slot_label(i: int) -> str:
    if i not in sel:
        return ""
    pos = sel.index(i) + 1
    names = {1: "HERO", 2: "TILE 1", 3: "TILE 2", 4: "TILE 3", 5: "TILE 4"}
    return names.get(pos, f"#{pos}")


col_count = 5
gallery = st.session_state.photo_images
rows = [gallery[i : i + col_count] for i in range(0, len(gallery), col_count)]

for row_start, row in zip(range(0, len(gallery), col_count), rows):
    cols = st.columns(col_count)
    for j, img in enumerate(row):
        idx = row_start + j
        with cols[j]:
            label = _slot_label(idx)
            if label:
                st.markdown(f'<div class="slot-chip">{label}</div>', unsafe_allow_html=True)
            else:
                st.markdown('<div style="height:22px"></div>', unsafe_allow_html=True)
            st.image(img, use_container_width=True)
            key = f"pick_{idx}"
            selected = idx in sel
            label_btn = "✓ Selected" if selected else f"Select #{len(sel) + 1}" if len(sel) < 5 else "Full"
            disabled = (not selected) and len(sel) >= 5
            if st.button(label_btn, key=key, disabled=disabled, use_container_width=True):
                if selected:
                    sel.remove(idx)
                else:
                    sel.append(idx)
                _reset_outputs()
                st.rerun()

col_status, col_clear = st.columns([3, 1])
with col_status:
    if len(sel) < 5:
        st.markdown(
            f'<span class="muted">Selected {len(sel)}/5 photos. '
            f'Pick {5 - len(sel)} more to enable generation.</span>',
            unsafe_allow_html=True,
        )
    else:
        st.success("Great — five photos selected.")
with col_clear:
    if st.button("Clear selection", disabled=not sel, use_container_width=True):
        st.session_state.selection = []
        _reset_outputs()
        st.rerun()


# --- Step 4: Generate -------------------------------------------------------

st.subheader("4 · Generate marketing materials")

can_generate = len(sel) == 5

col_flyer, col_ig = st.columns(2)

with col_flyer:
    st.markdown("**8.5 × 11 Flyer (PDF)**")
    gen_flyer = st.button("Generate flyer", type="primary", disabled=not can_generate,
                          use_container_width=True, key="btn_flyer")
    if gen_flyer:
        with st.spinner("Rendering flyer…"):
            photos = [gallery[i] for i in sel]
            img = render_flyer_image(listing, photos)
            buf = io.BytesIO()
            rgb = Image.new("RGB", img.size, (255, 255, 255))
            if img.mode == "RGBA":
                rgb.paste(img, mask=img.split()[3])
            else:
                rgb.paste(img)
            rgb.save(buf, "PDF", resolution=300.0)
            st.session_state.flyer_bytes = buf.getvalue()
    if st.session_state.flyer_bytes:
        st.download_button(
            "⬇ Download flyer.pdf",
            data=st.session_state.flyer_bytes,
            file_name=f"{listing.address.replace(' ', '_')}_flyer.pdf",
            mime="application/pdf",
            use_container_width=True,
        )

with col_ig:
    st.markdown("**1080 × 1080 Instagram post (PNG)**")
    gen_ig = st.button("Generate Instagram post", type="primary", disabled=not can_generate,
                       use_container_width=True, key="btn_ig")
    if gen_ig:
        with st.spinner("Rendering Instagram post…"):
            photos = [gallery[i] for i in sel]
            img = render_instagram_image(listing, photos)
            buf = io.BytesIO()
            img.convert("RGB").save(buf, "PNG", optimize=True)
            st.session_state.ig_bytes = buf.getvalue()
    if st.session_state.ig_bytes:
        st.download_button(
            "⬇ Download instagram.png",
            data=st.session_state.ig_bytes,
            file_name=f"{listing.address.replace(' ', '_')}_instagram.png",
            mime="image/png",
            use_container_width=True,
        )

if st.session_state.flyer_bytes or st.session_state.ig_bytes:
    st.subheader("Previews")
    pcol1, pcol2 = st.columns(2)
    if st.session_state.flyer_bytes:
        with pcol1:
            st.markdown("**Flyer (PDF)** — use the download button to get the original.")
            try:
                import pdf2image
                preview = pdf2image.convert_from_bytes(st.session_state.flyer_bytes, dpi=100)[0]
                st.image(preview, use_container_width=True)
            except Exception:
                photos = [gallery[i] for i in sel]
                st.image(render_flyer_image(listing, photos), use_container_width=True)
    if st.session_state.ig_bytes:
        with pcol2:
            st.markdown("**Instagram post**")
            st.image(st.session_state.ig_bytes, use_container_width=True)


# --- Footer -----------------------------------------------------------------

st.markdown("---")
st.caption(
    "Built for Doss & Spaulding Properties · dspropertiesnc.com · "
    "Questions or feature requests? Talk to the person who set this up."
)
