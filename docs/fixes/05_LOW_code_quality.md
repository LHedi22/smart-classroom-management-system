# Fix Plan 05 — LOW: Code Quality (3 items)

Three low-priority polish items. Safe to apply in a single commit.

---

## 05-A — ORM Type Annotation Bug (`Mapped[DateTime]`)

### Problem

`backend/app/models/db_models.py`, line 281:

```python
generated_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), nullable=False)
```

`Mapped[X]` declares the **Python-side type** of the attribute — what you get when
you access `instance.generated_at` in Python code. Here `X = DateTime` refers to
SQLAlchemy's `DateTime` column type class, not Python's `datetime.datetime`.

This is incorrect. The correct Python type for a timestamp column is `datetime`:

```python
# Wrong: SQLAlchemy column type used as Python type annotation
generated_at: Mapped[DateTime] = ...

# Correct: Python datetime type annotation
generated_at: Mapped[datetime] = ...
```

**Impact:** No runtime error (SQLAlchemy 2.0 ignores the Python type hint at runtime),
but type checkers (mypy, pyright) and IDE autocompletion will treat
`instance.generated_at` as a `DateTime` object (which has no `.isoformat()`, `.year`,
etc.) instead of a `datetime` object. This causes false positives in type checking and
misleading IDE suggestions.

### Fix

**File:** `backend/app/models/db_models.py`

Ensure `datetime` is imported at the top of the file (it likely already is —
check the existing imports):

```python
from datetime import datetime   # should already be present
```

Change line 281:

```python
# Before
generated_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), nullable=False)

# After
generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
```

Also verify the same pattern is used correctly in `AtRiskExplanation`:

```python
# at_risk_explanations table — check this column too:
generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
```

---

## 05-B — Missing `model_config` on `CourseForecastResponse`

### Problem

`backend/app/models/schemas.py`, `CourseForecastResponse` class (line ~379):

```python
class CourseForecastResponse(BaseModel):
    course_id: str
    course_code: str
    ...
    # missing: model_config = {"from_attributes": True}
```

Every other response schema in this file that maps from ORM objects includes:

```python
model_config = {"from_attributes": True}
```

This setting enables Pydantic v2's `from_attributes` mode, which allows
`Model.model_validate(orm_instance)` to work correctly by reading ORM attributes
by name.

`CourseForecastResponse` is currently constructed manually in `_make_response()`
(not via `model_validate`), so this **does not cause a bug today**. However:

- The inconsistency creates a trap for the next developer who tries to use
  `model_validate` on an `AttendanceForecast` ORM object.
- It violates the convention established by all other response schemas in the file.

### Fix

**File:** `backend/app/models/schemas.py`

Add `model_config` to `CourseForecastResponse`:

```python
class CourseForecastResponse(BaseModel):
    course_id: str
    course_code: str
    course_name: str
    trend_data: list[TrendDataPoint]
    sessions_analyzed: int
    expected_next_rate: float | None
    trend_classification: str | None
    confidence_level: str | None
    interpretation: str | None
    suggested_action: str | None
    ollama_reachable: bool
    generated_at: datetime | None

    model_config = {"from_attributes": True}   # ← add this
```

---

## 05-C — Semantic Mismatch: `ollama_reachable=True` in Null-Forecast Stub

### Problem

`backend/app/api/forecast.py`, `_make_response()` (line 64):

```python
def _make_response(course: Course, fc: AttendanceForecast | None) -> CourseForecastResponse:
    if fc is None:
        return CourseForecastResponse(
            ...
            ollama_reachable=True,   # ← hardcoded optimistic value
            generated_at=None,
        )
```

This stub is returned when the pipeline hasn't run yet for a course. The frontend
uses `ollama_reachable` to decide whether to show an amber "AI unavailable" warning.

If Ollama is genuinely down and no row exists yet:
- The stub says `ollama_reachable=True` (Ollama is fine)
- But the stub also says `generated_at=None` (not yet generated)

The frontend renders the "Generating forecast…" card for `generated_at=None`, which
is correct — but if a developer later adds logic that checks `ollama_reachable` before
showing the generating message, the false `True` would hide a real problem.

This is a semantic inconsistency: the stub is optimistic about Ollama when we simply
don't know the state yet.

### Fix

**File:** `backend/app/api/forecast.py`

Use `None` (or add a dedicated flag) to represent "unknown":

**Option A (minimal)** — Use `True` but add a comment making the intent explicit:

```python
if fc is None:
    return CourseForecastResponse(
        ...
        # ollama_reachable is unknown at this point; True is optimistic default.
        # The frontend uses generated_at=None to determine the "Generating…" state,
        # not ollama_reachable, so this value is not user-visible in this branch.
        ollama_reachable=True,
        generated_at=None,
    )
```

**Option B (schema change)** — Make `ollama_reachable` nullable in the schema
to express the "unknown" state:

```python
# schemas.py
ollama_reachable: bool | None   # None = pipeline hasn't run yet
```

```python
# forecast.py — stub
ollama_reachable=None,   # unknown: pipeline hasn't run yet
```

Option A is simpler and avoids a frontend change. Option B is more semantically
correct. **Recommend Option A** given no user-visible impact in the current frontend.

---

## Summary of Files to Touch

| Sub-item | File | Line | Change |
|----------|------|------|--------|
| 05-A | `backend/app/models/db_models.py` | ~281 | `Mapped[DateTime]` → `Mapped[datetime]` |
| 05-B | `backend/app/models/schemas.py` | end of `CourseForecastResponse` | Add `model_config = {"from_attributes": True}` |
| 05-C | `backend/app/api/forecast.py` | ~64 | Add explanatory comment (Option A) |

All three changes are non-breaking and require no migration.
