---
name: simplicio-tasks
description: Legacy compatibility alias for `/simplicio-loop`. Use only when an older install, adapter, or saved prompt still invokes `/simplicio-tasks`; immediately route the run through `../simplicio-loop/SKILL.md`, which now owns the public core + loop protocol.
---

# /simplicio-tasks — legacy alias for /simplicio-loop

`/simplicio-loop` is now the single public command for Simplicio's autonomous body-of-work
orchestration. This file remains only so older installs, adapter docs, or saved prompts that still
mention `/simplicio-tasks` keep working without breaking.

## What to do

1. Treat `/simplicio-tasks <goal>` exactly as `/simplicio-loop <goal>`.
2. Load and follow `../simplicio-loop/SKILL.md` as the authoritative protocol.
3. Keep these shared references for deep detail when needed:

| Need depth on… | Read |
|---|---|
| the 50 extension points + fallbacks | `../simplicio-loop/references/extension-points.md` |
| token economy (catalog, caps, clamp, tee+CCR, terminal table) | `../simplicio-loop/references/token-economy.md` |
| discover / intake / route / autoscale / speed / model-routing | `../simplicio-loop/references/orchestration.md` |
| quality loop · safety gates · delivery · feedback | `../simplicio-loop/references/quality-safety-delivery.md` |
| 24/7 standing loop · arming the watcher | `../simplicio-loop/references/standing-loop-247.md` |
| front-end proof via Playwright | `../simplicio-loop/references/web-evidence.md` |
| demo-video proof (Playwright default · hyperframes on request) | `../simplicio-loop/references/video-evidence.md` |

## Compatibility note

- Public docs, installers, and runtime entry files should point to `/simplicio-loop`.
- Older prompts such as `/simplicio-tasks finish all the open issues` are still accepted as an
  alias and should be executed with the unified `/simplicio-loop` contract.


