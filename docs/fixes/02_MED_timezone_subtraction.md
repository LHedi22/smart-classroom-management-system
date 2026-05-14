# Fix Plan 02 — MEDIUM: Naive vs Aware Datetime Subtraction

## Problem

`backend/app/services/forecast_engine.py`, line 269:

```python
age = (datetime.now(timezone.utc) - fc.generated_at).total_seconds()
```

`datetime.now(timezone.utc)` is **timezone-aware**. If `fc.generated_at` is returned
by the ORM as a **naive** datetime (no `.tzinfo`), Python raises:

```
TypeError: can't subtract offset-naive and offset-aware datetimes
```

**When does this happen?**
The column is declared `DateTime(timezone=True)` in the ORM and the Alembic migration,
which tells asyncpg to return a tz-aware `datetime`. This works correctly when the DB
is PostgreSQL and asyncpg is the driver.

However it **can fail silently or raise** in:
- Unit tests that instantiate `AttendanceForecast` objects directly with
  `datetime.now()` (naive) as `generated_at`
- Any future migration to SQLite (which strips timezone info)
- Any future test with a synchronous SQLAlchemy session using psycopg2, which may
  return naive datetimes even for `TIMESTAMPTZ` columns depending on connection config

**Crash impact:** The freshness check is inside the per-course loop. One failing row
crashes the entire pipeline run for all subsequent courses.

---

## Root Cause

Python's `datetime` arithmetic requires both operands to be either both naive or both
aware. There is no implicit coercion.

---

## Fix

**File:** `backend/app/services/forecast_engine.py`

Apply a defensive normalization before the subtraction. This is a one-liner helper
that costs nothing at runtime and eliminates the entire class of error:

```python
# ── Timezone-safe age calculation ─────────────────────────────────────────

def _age_seconds(dt: datetime) -> float:
    """Return seconds since `dt`, handling naive datetimes defensively."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return (datetime.now(timezone.utc) - dt).total_seconds()
```

Then replace the inline subtraction (line 269) with:

```python
# Before
age = (datetime.now(timezone.utc) - fc.generated_at).total_seconds()

# After
age = _age_seconds(fc.generated_at)
```

Place `_age_seconds` near the top of the module, after the constants block
(after line 41 — the `_ACTION_MAP` dict).

---

## Same pattern in `at_risk_engine.py`

Check `backend/app/services/at_risk_engine.py` for the same pattern (the at-risk
pipeline has a similar freshness check). Apply the same fix there. You can import
`_age_seconds` from `forecast_engine` or move it to a shared `utils.py`:

```python
# Option: shared utility
# backend/app/utils.py

from datetime import datetime, timezone

def age_seconds(dt: datetime) -> float:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return (datetime.now(timezone.utc) - dt).total_seconds()
```

---

## Files to Touch

| File | Location | Change |
|------|----------|--------|
| `backend/app/services/forecast_engine.py` | ~line 42, ~line 269 | Add `_age_seconds`, replace inline subtraction |
| `backend/app/services/at_risk_engine.py` | freshness check | Same replacement |

---

## Verification

```python
# Quick smoke test — paste in a Python REPL:
from datetime import datetime, timezone

naive  = datetime(2025, 1, 1, 12, 0, 0)          # no tzinfo
aware  = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)

def _age_seconds(dt):
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return (datetime.now(timezone.utc) - dt).total_seconds()

# Both should return a number without raising:
print(_age_seconds(naive))
print(_age_seconds(aware))
```
