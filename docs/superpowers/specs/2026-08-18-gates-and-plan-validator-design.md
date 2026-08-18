# Build the fidelity extension, humanization gate, and plan-as-validator

**Date:** 2026-08-18
**Status:** Approved
**Supersedes:** `2026-08-18-plan-run-commands-design.md` — that spec assumed
deterministic script generation inside this codebase (`pipeline/script.py`
calling no LLM, mapping CSV rows to scenes directly). CLAUDE.md changed same
day: script generation is now Claude working interactively in Cowork,
drafting the shot-list JSON directly against the schema and writing it to
`out/shotplans/<unit>_shotplan.json`. `script.py`/`assets.py`/`shotlist.py`
as previously designed are **not built** — there is no code path left for
them to serve. This spec replaces that scope with what CLAUDE.md's updated
`LOCKED DECISIONS` table actually asks for: two gates and a validator.

## Context

Because generation is now fully open-ended (an LLM drafting freely, not
template-filling), the gates are the only technical safety net left — not a
backup to a safe fixed-rule mapping, which no longer exists. `plan` and `run`
change role accordingly: `plan` stops being a generator-stub and becomes a
**validator** for an already-authored shot plan; `run` is unaffected by this
change and stays out of scope for this pass per explicit prioritisation.

Two things must exist before any shot plan is render-ready, for **both**
lanes now (`lanes.yaml`: `season.human_script_review` flipped from `false`
to `true` the same day, matching `blueprint`):

1. The existing fidelity gate extended to catch fabrication, not just
   flattening.
2. A new humanization gate checking the mechanical half of CLAUDE.md
   Section XI.

## Goal

Extend `pipeline/gates/fidelity.py` with a fabrication check. Add
`pipeline/gates/humanization.py`. Rewire `produce.py plan --unit <ID>` to
validate an existing shot plan (schema + both gates) and report pass/fail/
warn — never to generate one. Prove it with a hand-authored bad BP34 shot
plan (a real prior draft's exact failure mode) and a clean one.

## Non-goals

- `pipeline/script.py`, `pipeline/assets.py`, `pipeline/shotlist.py` —
  removed from scope entirely, not deferred. Shot-plan authoring happens in
  Cowork chat, not in this codebase.
- `pipeline/render.py`, `pipeline/tracker.py` — explicitly held for a
  follow-up pass, per this session's own scoping decision. Not touched here.
- Deciding the voice-sample audition-vs-cloning question (still Sri's call,
  still moot — `audio.py` doesn't exist).
- Any LLM call inside this codebase, for anything. The fabrication and
  humanization checks are pattern/overlap-based, deterministic, matching
  `fidelity.py`'s own documented principle that an LLM judge is advisory
  only and never the sole gate.
- Building a detector for the *positive* half of Section XI (contractions,
  active voice, "sounds like Sri"). That half is an explicit judgement call
  made during drafting against `Founder_Voice_Sample.md`, not something a
  pattern-matcher can verify — attempting to automate it would be
  overreach, not rigor.

## Decisions locked during brainstorming

1. **The fabrication check is `warn`, not hard-fail.** Unlike the existing
   hedge/absolute/hook/trap checks, which are precise pattern matches on a
   fixed marker vocabulary, a "does this number/proper-noun/claim trace back
   to the source" check is inherently noisier — legitimate light
   rephrasing (`"seven-year retention"` → `"seven years"`) will trigger
   false positives. Matches the existing module's own stated principle:
   noisy judgement stays advisory, only precise deterministic checks
   hard-fail.
2. **All of `humanization.py`'s checks are `warn`, not hard-fail**, for the
   same reason plus one more: whether a three-item list is "genuinely three
   separate ideas" (allowed) or a lazy triplet (flagged) is exactly the
   judgement call CLAUDE.md Section XI itself defers to a human read. A
   mechanical check can find the pattern; it cannot rule on the exception.
3. **Extraction for the fabrication check runs against the CSV's own
   structured `header_text`/`body_text` fields** (via `unit.slides`, already
   parsed by `source.py`), not the raw CSV file text — confirmed necessary
   after testing a naive full-file regex against BP34's CSV and finding it
   picks up row numbers and the CSV header row as false "numbers" and
   "proper nouns."
4. **`plan --unit <ID>` never falls back to generating a shot plan.** If
   `out/shotplans/<ID>_shotplan.json` doesn't exist, it says so plainly and
   exits nonzero. Generation lives entirely outside this codebase now.

## Approach

### `pipeline/gates/fidelity.py` — add a fabrication check

New function `check_fabrication(unit, script) -> list[Finding]`, called from
inside the existing `check()` and folded into its returned list (existing
checks 1-6 are untouched, per the user's explicit instruction not to touch
them).

- Build the source corpus from `unit.slides`: concatenate
  `f"{s.header_text} {s.body_text}"` for all 10 slides.
- Extract candidates from the script's on-screen text
  (`sc.get("voiceover", "")` per scene, matching how the rest of the module
  reads script text):
  - Numbers: regex matching digit sequences, percentages, and money/duration
    patterns (`\b\d[\d,]*\.?\d*%?\b`, plus a duration-word pattern like
    `\b(one|two|three|four|five|six|seven|eight|nine|ten)[\s-](year|month|day)s?\b`
    since retention periods are as likely to be spelled out as digits).
  - Proper-noun-like sequences: capitalized word runs, excluding the first
    word of each sentence (crude but workable — the existing module already
    accepts "advisory, not authoritative" as the standard for this class of
    check).
- For each candidate, check whether it (or a normalized/singular/plural
  variant) appears as a substring of the normalized source corpus. If not,
  emit a `warn` finding, code `POSSIBLE_FABRICATION`, naming the candidate
  and which scene it came from.
- Skip candidates that are also present in `HEDGE_MARKERS` or
  `FLATTENING_MARKERS` matches already reported by the existing checks —
  avoid duplicate noise on the same span.

### `pipeline/gates/humanization.py` — new module

Mirrors `fidelity.py`'s shape: `Finding` dataclass (`severity`, `code`,
`message` — same shape, reused, not redefined, to keep the two gates'
reports easy to combine and print together), `check(script) -> list[Finding]`,
`passed(findings) -> bool`.

Checks (`script` is the shot-plan dict; only `headline`/`body` text across
`scenes` is checked, same fields the fidelity gate reads):

- **Triplets** — regex for `X, Y, and Z` / `X, Y and Z` (comma-separated
  three-item lists). `warn`, code `POSSIBLE_TRIPLET`.
- **Banned inflated/corporate words** — exact list from CLAUDE.md Section
  XI: `innovative`, `transformative`, `groundbreaking`, `leveraging`,
  `synergies`, `best practices`. Case-insensitive substring match. `warn`,
  code `BANNED_PHRASE`.
- **Artificial parallelism** — regex for `it's not X, it's Y` / `not X,
  but Y` constructions. `warn`, code `ARTIFICIAL_PARALLELISM`.

No check for contractions, sentence length, active voice, or "does it sound
like Sri" — those are Section XI's positive guidance and judgement-call
territory respectively, not banned-pattern detection, and out of scope per
Decision/Non-goal above.

### `produce.py plan --unit <ID>` — rewritten as a validator

1. `source.load_unit(cfg, unit_id)` — needed for the CSV side of both the
   fidelity gate (existing behaviour) and the new fabrication check.
2. Check `out/shotplans/<unit_id>_shotplan.json` exists. If not: print
   `"No shot plan found for {unit_id}. Author one in Cowork chat against "
   "schemas/shotlist.schema.json, then run plan again to validate it."` and
   return a nonzero exit code. Stop here — no generation attempt.
3. Load the JSON, validate against `schemas/shotlist.schema.json` via
   `jsonschema.validate()`. A schema failure is reported and is fatal —
   nothing downstream is meaningful against a malformed shot plan.
4. Build the `script` dict shape `gates.fidelity.check()` expects
   (`{"lane": ..., "scenes": [{"slide_refs": ..., "voiceover": headline +
   " " + body}, ...]}`) from the loaded shot plan's `scenes` array — this is
   a format adapter, not a generator: it reads what's already in the shot
   plan and reshapes it for the gate's existing interface, introducing no
   new content.
5. Run `gates.fidelity.check(unit, script)` (existing checks + new
   fabrication check together, since they're one function).
6. Run `gates.humanization.check(script)`.
7. Run `gates.brand.check(cfg, unit, shotlist)` against the loaded shot plan
   directly (unaffected by this change — still a pure JSON/schema-adjacent
   check, still makes sense pre-render).
8. Print a clear report: schema result, then each gate's findings grouped by
   severity (fail / warn), then an overall verdict line.
9. Print the `human_script_review` sign-off notice for the unit's lane
   (checked via `cfg.lane(unit.lane)["human_script_review"]` — now `true`
   unconditionally for both lanes, but read from config rather than
   hardcoded, since the setting is what governs this, not an assumption
   about which lanes need it). Make clear: passing gates is necessary, not
   sufficient — a human must sign off before `run`.

`produce.py run --unit <ID>` is untouched in this pass (stays a stub — see
Non-goals).

## Testing

Hand-author two `out/shotplans/BP34_shotplan.json` fixtures (the tool
author, not a live LLM call — simulating what a Cowork-drafted shot plan
would look like):

- **Bad:** flattens slide 4's `"Retention usually wins, narrowly... it
  generally overrides an erasure request for those specific records"` into
  a flat rule; introduces a fabricated retention-period number the CSV
  never states; includes a triplet and the word "leveraging" somewhere in
  its on-screen text.
- **Clean:** faithful to BP34's CSV, no fabricated details, no banned
  phrases, hedges preserved.

Run `produce.py plan --unit BP34` against each. Confirm:
- Bad plan: fidelity gate fails on flattening (existing check, still
  works), fabrication check warns on the invented number, humanization gate
  warns on the triplet and "leveraging."
- Clean plan: schema valid, fidelity gate passes, fabrication check has
  nothing to flag (BP34's own body text carries no bare statistics per
  inspection — the earlier design phase confirmed this directly against the
  real CSV — so a faithful plan should introduce none either),
  humanization gate has nothing to flag, human-review notice still prints
  (mandatory regardless of gate results).

## Open item carried forward, unchanged

Sri's voice-reference samples (audition vs. cloning) — still his call, still
not decided here, still doesn't block this pass.
