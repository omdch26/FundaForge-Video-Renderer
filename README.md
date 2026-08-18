# FundaForge Video Renderer

Turns finished FundaForge carousels into YouTube Shorts. 86 units, two lanes,
one command each.

**Python orchestrates. Remotion renders.** No React per episode.

## Quick start

```bash
# 1. Python
python -m venv .venv
.venv\Scripts\activate          # Windows
pip install -r requirements.txt

# 2. Remotion
cd remotion && npm install && cd ..

# 3. Secrets
copy .env.example .env          # then fill it in

# 4. Check the wiring before spending any credits
python produce.py doctor
```

## Usage

```bash
python produce.py doctor                  # verify config, paths, fonts, keys
python produce.py plan   --unit S1E05     # dry run: cost + duration estimate, no spend
python produce.py run    --unit S1E05     # full pipeline
python produce.py run    --season 1       # batch
python produce.py drift                   # which shipped videos are now stale
```

Output lands in `out/<unit_id>/`:

```
script.json  voice.mp3  shotlist.json  captions.srt  <unit>.mp4  meta.json  manifest.json
```

## Pipeline

```
Unit_Index.xlsx -> CSV  (source of truth; hashed for drift detection)
   |
   v  script.py      LLM expands 10 slides into a paced video script
   |-- G1  fidelity  hedge preservation + claim coverage   [hard fail]
   |-- G1b review    Blueprints only, human, mandatory
   |-- G2  brand     palette, fonts, amber semantics       [hard fail]
   v  audio.py       ElevenLabs + character-level timestamps
   |-- G3  audio     duration, pace, clipping
   v  assets.py      SVGs from vector library + manual drops + type cards
   v  shotlist.py    -> shotlist.json  (the Python/Remotion contract)
   v  render.py      npx remotion render
   |-- G4  batch     human, watch and approve
   v  meta.py        title, description, SRT, playlist -> upload PRIVATE only
```

## Manual image drops

Optional. Never blocks a render — a missing file falls back to a type-only card.

```
assets/manual/<UNIT_ID>/<UNIT_ID>_s<NN>_<slot>.png|svg
e.g. assets/manual/BP34/BP34_s07_split.svg
```

Each run writes `out/<unit>/asset_manifest.json` listing every slot it wanted,
which were filled and which fell back — drop files in and re-render just those.

## Rules that are not negotiable

- Everything outside `06_Video_Production/` is **read-only**
- **Never publish.** Uploads are private drafts; going public is a human action
- **Never delete.** Superseded output moves to `out/<unit>/_superseded/`
- **No AI-generated imagery.** Type-first, plus the existing SVG library
- Colours and fonts come from `config/brand.json`. Nowhere else.

See `CLAUDE.md` for the full brief.
