# Deploying the team-facing web app

The web app (`app.py`) is a Streamlit application. Team members use it
entirely in a browser: they type an address, pick five photos from a
thumbnail grid, and download a flyer PDF + Instagram PNG.

There are two good ways to get it online.

## Option A — Streamlit Community Cloud (recommended, free)

Streamlit Cloud gives you a public URL like
`https://ds-marketing.streamlit.app` that anyone on your team can visit. No
server, no maintenance.

### One-time setup

1. **Create a GitHub repo** for this code. It doesn't matter if the repo is
   public or private — Streamlit Cloud supports both.
2. From inside `outputs/ds_flyer/`, push the folder to the repo:
   ```bash
   cd outputs/ds_flyer
   git init
   git add .
   git commit -m "D&S marketing materials generator"
   git branch -M main
   git remote add origin https://github.com/<your-user>/ds-marketing.git
   git push -u origin main
   ```
3. Go to <https://streamlit.io/cloud> and sign in with that same GitHub
   account.
4. Click **New app → Deploy from GitHub**.
5. Select your repo, branch `main`, and set the main file to **`app.py`**.
6. Click **Deploy**. Wait ~2 minutes for the build to finish.
7. Copy the URL it gives you and share it with the team.

That's it. When you push updates to the repo, Streamlit Cloud auto-redeploys.

### Files that make the deploy work

- `app.py` — the web UI
- `requirements.txt` — Python packages Streamlit Cloud will install
- `packages.txt` — Debian packages for cairosvg (Cairo, Pango, etc.)
- `assets/` — logo SVGs and bundled Poppins fonts (so the deploy doesn't
  depend on any system-installed fonts)

### Restricting access

Streamlit Cloud has an authentication toggle in the app settings
(**Settings → Sharing → "Viewer access"**). You can restrict the app to a
Google Workspace domain (e.g. anyone with a `@dspropertiesnc.com` email) or
invite specific emails.

## Option B — Run it on a laptop/office PC

If you want to avoid the cloud entirely, anyone on the team can run the app
on their own machine:

```bash
# one-time setup
pip install -r requirements.txt

# start the app (opens in the default browser at http://localhost:8501)
streamlit run app.py
```

System requirements: Python 3.10+ and the Cairo libraries
(`libcairo2`, `libpango-1.0-0`, `libgdk-pixbuf-2.0-0`). On macOS those come
with `brew install cairo pango`. On Windows, installing GTK for Windows
from <https://github.com/tschoonj/GTK-for-Windows-Runtime-Environment-Installer/releases>
is the easiest path. On Ubuntu/Debian: `sudo apt install libcairo2 libpango-1.0-0
libpangocairo-1.0-0 libgdk-pixbuf-2.0-0`.

## Updating the app

- **Brand/text changes** (phone, email, tagline, colors, QR settings): edit
  `layout.py`. One file covers both the flyer and the IG post.
- **Feature-bullet phrasing**: extend `_DESCRIPTION_HIGHLIGHTS` in
  `layout.py` to teach the extractor new selling points.
- **Layout tweaks**: `flyer.py` for the 8.5×11 PDF, `instagram.py` for the
  square post.
- **UI copy**: `app.py`.

After any change, commit and push — Streamlit Cloud redeploys automatically.

## Troubleshooting

| Symptom | Fix |
|--------|-----|
| "No font found" on deploy | Make sure `assets/fonts/Poppins-Bold.ttf` etc. are committed to the repo (they're bundled fallbacks). |
| "cairocffi OSError: cannot load library libcairo.so.2" | `packages.txt` is missing from the repo root. |
| QR code won't scan | Some older scanners struggle with inverted (white-on-black) QRs. Swap `fg_color=WHITE, bg_color=BLACK` to the opposite in `flyer.py`/`instagram.py`. |
| Listing not found for address | Run `python generate.py --list` locally to see exactly what slugs the site exposes today, then match against that. |
