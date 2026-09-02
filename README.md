# Museme

A Dash app that recommends music by cosine similarity, over a catalogue of
3,815 tracks described by 66 audio features (`data/df_recommendation.csv`).

**[➡ Live demo](https://museme-s4u2.onrender.com)**
*(Render's free tier sleeps after 15 min of inactivity — the first load takes
about a minute.)*

Originally written in 2021 on Python 3.7 / Dash 1.19. Brought back to life in
August 2026 on Python 3.12 — see [Migration](#migration-2021---2026), which is
where most of the interesting work is.

![Museme recommending tracks similar to Daft Punk's "Get Lucky"](docs/screenshot.png)

## Running it

Requires Python 3.12 (`py -3.12 --version`).

```powershell
# from the project folder
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe index.py
```

Then open http://127.0.0.1:8050/

> Run `index.py`, **not** `app.py`: `app.py` only creates the Dash object,
> while `index.py` carries the layout and the callbacks.

### What the user does

1. Landing page: background video and a *Get it, let's try* button.
2. Clicking it reveals two dropdowns.
3. Pick an artist, then one of their tracks.
4. The app shows that track (cover art and an audio preview) and 10 recommendations.

Other pages: `/page-1` summary and a Plotly chart, `/page-2` about, `/page-3` resources.

## Structure

```
app.py              the shared Dash object
index.py            entry point: layout, routing, callbacks
components/
  engine/functions.py   data extraction and cosine recommendation
  layout/               one file per page (home, summary, about_us, ressources)
data/                 the two CSVs (features + recommendation)
assets/               CSS, images, favicon, background video (served by Dash)
audio/                working folders from the original app
legacy/               scripts outside the app, kept for reference
render.yaml           Render deployment blueprint
```

## Deployment (Render, free tier)

The app runs on Render's **free** plan: 512 MB of RAM, sleeps after 15 min
without traffic (~1 min to wake), 750 h/month per workspace.

`render.yaml` describes the whole service. On https://render.com:
*New > Blueprint*, point it at the GitHub repo, deploy.

Three things worth knowing, none of them obvious:

- **Render reads neither `Procfile` nor `runtime.txt`.** Both are Heroku
  leftovers, kept but inert here. The Python version comes from
  `.python-version`; without it Render would use its current default (3.14),
  for which the pinned pandas / numpy versions have no wheel.
- **A single gunicorn worker** (`--workers 1 --threads 4`). Each worker loads
  its own copy of the catalogue: two workers exceed the 512 MB limit.
- Measured footprint is ~195 MB at startup and ~206 MB in steady state.

The free plan allows neither a persistent disk nor scaling: since the app is
entirely read-only over version-controlled CSVs, neither matters here.

## Migration 2021 -> 2026

The business logic was deliberately left untouched. Only what actually
prevented the app from running was fixed:

| Fix | File | Why |
|---|---|---|
| `dash_html_components` / `dash_core_components` -> `from dash import html, dcc` | the 4 pages in `components/layout/` | packages absorbed into `dash`, then removed |
| `DataFrame.append` -> direct indexing | `components/engine/functions.py` | removed in pandas 2.0 |
| `app.run_server()` -> `app.run()` | `index.py` | renamed in Dash 3 |
| Normalised the return of `get_loc` | `components/engine/functions.py` | 31 titles in the CSV are duplicates: `get_loc` returned a boolean mask and crashed the recommendation |
| Dropped the `librosa` / `matplotlib` imports | `functions.py`, `index.py` | imported but never called; they dragged in an audio stack that will not compile on 3.12 |
| `gunicorn app:server` -> `gunicorn index:server` | `Procfile` | `app.py` has no layout: the deployment was serving a blank page |

## Going live in 2026

Changes made for hosting and rendering:

| Change | File | Why |
|---|---|---|
| Tab title `Museme` + `assets/favicon.ico` | `app.py`, `index.py` | the tab read `Dash`. The favicon is generated from `assets/images/Logo_Museme.jpg`; Dash serves `assets/favicon.ico` automatically |
| Left column grouped into `.left-panel` | `components/layout/home.py`, `assets/style.css` | `.input-box` (top 10%) and `.track-audio-player-box` (top 40%) were each absolutely positioned on their own: their heights do not depend on the window, so the two blocks overlapped as soon as a track was selected. They are now stacked in a single flex container |
| `dbc.Row` removed from the selection block | `components/layout/home.py` | Bootstrap's negative margins pushed the dropdowns out of their box |
| Similarity computed on a single row | `components/engine/functions.py` | the full 3,815 x 3,815 matrix was 116 MB, doubled by the DataFrame copy: a 243 MB peak per request. The matrix being symmetric, the result is identical |
| Catalogue and features cached (`lru_cache`) | `components/engine/functions.py` | the 5 MB CSV was re-read on every callback |
| Absolute data paths | `components/engine/functions.py` | relative paths assumed the working directory was the project root |
| Recommendation column moved into `.right-panel`, bounded and scrollable | `components/layout/home.py`, `assets/style.css` | the block was absolutely positioned with no height limit: its last rows fell off the screen, and the page body (entirely absolute, therefore zero-height) offered no scrolling to reach them |
| Translucent dark backdrop under the recommendations | `assets/style.css` | white text became unreadable over the bright frames of the video |
| Recommendation rows generated by a loop, in a CSS grid | `components/layout/home.py` | the 10 rows were hand-written as `dbc.Row` with 4 equal columns: the 50 px cover took a quarter of the width while long titles wrapped onto three lines |
| Placeholder cover when `Cover` is missing | `components/layout/home.py` | 61 tracks in the catalogue have no cover: the code produced `<img src="nan">`, i.e. a broken-image icon |
| Background video re-encoded: 179 MB -> 5.7 MB | `assets/videos/background.mp4` | above GitHub's 100 MB per-file limit. 854x480, no audio track, with slight blur from the encode — invisible, since the CSS already applies `blur(5px)` |

Effect on the recommendations, measured over 7 tracks (one of them a duplicate):
results strictly identical to the old implementation, peak memory 243 MB -> 17 MB,
and 1.22 s -> 0.02 s once the cache is warm.

Known issues, deliberately left alone:

- `index.py` creates a second `Dash` object that shadows the one in `app.py`.
  Shaky, but it works.
- `preprocessing.scale` emits a `UserWarning` about the scale of some CSV
  columns. No effect on the results.
- Moving from Bootstrap 4 to 5 may cause slight visual differences; most of the
  design comes from `assets/style.css` anyway.

## Background video

`assets/videos/background.mp4` (5.7 MB) is the web version, and it is the one in
Git. The original master (`assets/videos/Mon film 1.mp4`, 179 MB) is excluded by
`.gitignore`: the app no longer uses it, so it can be deleted or archived
elsewhere. To regenerate it:

```powershell
ffmpeg -i "assets\videos\Mon film 1.mp4" -an `
  -vf "gblur=sigma=1.2,scale=854:480:flags=lanczos" `
  -c:v libx264 -preset slow -crf 33 -pix_fmt yuv420p -g 50 `
  -movflags +faststart "assets\videos\background.mp4"
```

## License

MIT — see [LICENSE](LICENSE).
