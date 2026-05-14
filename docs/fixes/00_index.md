# Phase 21 — Fix Plans Index

Generated from code review of the Attendance Forecasting PR (Phase 21).

## Files

| File | Priority | Component | Issue |
|------|----------|-----------|-------|
| [01_HIGH_control_auth.md](01_HIGH_control_auth.md) | HIGH | Backend API | AC/lighting control auth downgraded from admin-only |
| [02_MED_timezone_subtraction.md](02_MED_timezone_subtraction.md) | MEDIUM | Backend Service | Naive vs aware datetime subtraction crash |
| [03_MED_detail_panel_stale.md](03_MED_detail_panel_stale.md) | MEDIUM | Frontend | Detail panel stays stale after "Recompute Now" |
| [04_MED_silent_catch.md](04_MED_silent_catch.md) | MEDIUM | Frontend | Silent catch in `handleRecompute` swallows real errors |
| [05_LOW_code_quality.md](05_LOW_code_quality.md) | LOW | Backend (3 items) | ORM type annotation, missing model_config, stub semantic |

## Fix Order (recommended)

1. `01` — Security gates should be confirmed and restored before any deployment
2. `02` — Crash risk in production if asyncpg returns naive datetimes
3. `03` + `04` — Frontend bugs, apply together (same file, close proximity)
4. `05` — Polish / type-safety pass, safe to batch into one commit
