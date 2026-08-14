# Video evidence — `video_evidence` (Playwright by default · hyperframes on request)

Concrete implementation of the `video_evidence` extension point: produce a demo video of a
screen/feature and record it as evidence a change works. **Two engines, one producer** — the
flow picks the engine:

| Engine | When | What it produces |
|---|---|---|
| **Playwright** (DEFAULT — normal evidence flow) | a UI change wants moving proof (Step 4b) | a recording of the **real browser session** driving the screen (`.webm`, → `.mp4` with FFmpeg) |
| **hyperframes** (EXPLICIT custom request only) | the user asks for a demo/explainer — *"make an explainer video of screen X"* | a **deterministic, captioned slideshow** of the captured screenshots, CI-reproducible |

The rule of thumb the user set: **normal flow → Playwright; hyperframes only when the deliverable
itself is a personalized explainer video.** Either engine: a missing toolchain yields **BLOCKED**,
never a fake pass.

## When it fires (cheap gate — terminal, not LLM)
```bash
# (a) UI change wants moving proof — the normal flow → Playwright recording
python3 scripts/web_verify.py detect --base origin/main   # fe-changed? then record a session video

# (b) explicit request for a personalized explainer → hyperframes
python3 scripts/video_evidence.py detect --goal "<the skill argument or issue title/body>"
```
`detect` matches a video noun (`vídeo`/`video`/`screencast`/`walkthrough`/`gif`…) near a
make/show verb (`faça`/`crie`/`grave`/`make`/`create`/`record`/`demo`…), EN/PT/ES. A match means the
deliverable IS a video → route it to the **hyperframes** engine. No match → the ordinary UI-change
path uses the **Playwright** engine for moving proof. This is intent classification by regex, not
the LLM.

## The default flow — Playwright session recording
The normal evidence path. `video_evidence verify` (no `--engine`) records the live screen:

1. **`video_evidence verify --url <url> --expect <text>`** drives a headless browser to the URL
   with Playwright's native video recording ON (`test.use({ video: 'on' })`), holds for `--seconds`,
   and writes a `.webm` of the real session under `.simplicio/orchestrator/tee/video/<name>-<issue>-pw/`.
2. The worker locates the recording, converts it to `.mp4` when **FFmpeg** is present (otherwise the
   `.webm` is kept — both are real recordings), appends the ledger row, and prints the verdict.
3. `--upload --pr N` attaches the file to the PR as a link (never bytes).

Requirements (preflighted; BLOCK if absent): **Node.js 22+** + **Playwright** (`npx playwright
install --with-deps chromium`). FFmpeg is optional (it only transcodes `.webm` → `.mp4`).

## The custom-explainer flow — hyperframes slideshow
Only when the work-item or skill argument explicitly asks for a demo/explainer video. hyperframes
renders an HTML composition deterministically; the source is the screenshots `web_verify` already
captured:

1. **`web_verify run`** drives the UI and writes per-step PNGs into `.simplicio/orchestrator/tee/web/`.
2. **`video_evidence verify --engine hyperframes --frames .simplicio/orchestrator/tee/web --title "Screen X"`**
   scaffolds those exact PNGs into a captioned hyperframes composition and runs
   `npx hyperframes render` → a deterministic MP4 walkthrough.

Requirements (preflighted; BLOCK if absent): **Node.js 22+** and **FFmpeg**. Credit: **hyperframes**
by HeyGen — <https://github.com/heygen-com/hyperframes> (open-source, no API keys, local render via
headless Chrome + FFmpeg). A pure-synthetic demo (no live UI) feeds `--shots a.png,b.png` directly.

## Capture into the evidence ledger
All artifacts write to `.simplicio/orchestrator/tee/video/`. Append a ledger row recording **path + a
one-line verdict** — never the bytes:
```
video_evidence: PASS — demo video (playwright) project=login-demo file=.simplicio/orchestrator/tee/video/login-demo-12.mp4
video_evidence: PASS — demo MP4 (hyperframes) project=login-demo mp4=.simplicio/orchestrator/tee/video/login-demo-12.mp4
```

## Attach to the PR (link, don't paste)
```bash
gh release upload "evidence-pr<N>" .simplicio/orchestrator/tee/video/login-demo-12.mp4
gh pr comment <N> --body "🎬 video_evidence ✅  demo video attached: <url>"
```

## Token economy (critical)
- NEVER feed video bytes, frames, or composition HTML into context. Evidence = **file path/URL +
  boolean verdict**, exactly like `web_verify`.
- Playwright records during the same drive `web_verify` already does — don't double-drive the UI.
  hyperframes reuses the screenshots `web_verify` already captured — don't re-capture.
- Clamp `npx` output through the orient catalog (tee to file; feed back only the verdict + first N
  error lines).

## Enforcement (simplicio-review rubric line)
At MEDIUM+, when the work-item was an explicit **video request**, `simplicio-review` REQUIRES a
`video_evidence` ledger entry with a video path and a PASS verdict, else FAIL. For an ordinary UI
change the moving proof is the **Playwright** recording (the screenshot+trace from `web_verify`
already suffices as the minimum); the hyperframes explainer is REQUIRED only when the deliverable
itself is the personalized demo video.

## Runnable worker (`scripts/video_evidence.py`)
The prose above is the contract; `scripts/video_evidence.py` is the runnable form. Verbs:
```bash
python3 scripts/video_evidence.py detect  --goal "<request text>" [--exit-code]
# default evidence flow — Playwright session recording:
python3 scripts/video_evidence.py verify  --url http://localhost:3000/login --name login-demo \
    --expect "Sign in" [--seconds 4] [--issue N] [--upload --pr N]
python3 scripts/video_evidence.py record  --url <url> --name NAME [--expect TEXT] [--seconds 4]
# explicit custom explainer — hyperframes:
python3 scripts/video_evidence.py verify  --engine hyperframes --name NAME \
    --frames .simplicio/orchestrator/tee/web --title "Screen X" [--seconds 2.0] [--issue N]
python3 scripts/video_evidence.py scaffold --name NAME --frames DIR --title "Screen X"
python3 scripts/video_evidence.py render   --name NAME [--issue N]
python3 scripts/video_evidence.py lint     --name NAME
```
`verify` defaults to the Playwright engine; `--engine hyperframes` selects the slideshow. A missing
toolchain (Node 22+; Playwright for the default engine, FFmpeg/hyperframes for the explainer) yields
**BLOCKED**, never a fake pass — identical discipline to `web_verify`.

## Scope (don't over-engineer)
Default flow = one Playwright recording of the screen running. Custom-explainer flow = one
deterministic captioned hyperframes MP4 of the captured screens. Skip: authored GSAP/Lottie/Three.js
animations, Lambda distributed render, audio narration, multi-composition reels.
