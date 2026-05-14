# Fix Plan 01 — HIGH: Control API Auth Downgrade

## Problem

`backend/app/api/control.py` changed the dependency on both `/api/control/ac` and
`/api/control/lighting` from `require_admin` to `get_current_professor`:

```python
# Before (admin-only)
async def control_ac(body: RelayCommand, _: Professor = Depends(require_admin))

# After (any professor)
async def control_ac(body: RelayCommand, _: Professor = Depends(get_current_professor))
```

**This means any authenticated professor can now switch classroom AC and lighting on/off,
not just administrators.**

This is either:
- A correct intentional fix (professors should control their own classroom), or
- An accidental regression (admin gate was deliberate for physical safety reasons)

The existing CLAUDE.md spec says `POST /api/control/ac → {action}` without specifying
admin-only, which suggests the intent was professor-level access. However, the original
code deliberately used `require_admin`, implying a conscious security decision was made.

**Confirm the intended behavior before proceeding.**

---

## Decision Required

Ask the team / product owner:

> Should any professor be able to control AC and lighting, or only administrators?

| Option | Auth guard | Behaviour |
|--------|-----------|-----------|
| A — Any professor | `get_current_professor` | Current state after the change |
| B — Admin only | `require_admin` | Original state before the change |
| C — Own room only | Custom check | Professor can only control `room_id` they are assigned to |

Option C is the most principled but requires a `professor.room_id` field that does not
currently exist in the schema.

---

## Fix A — Confirm and document the intentional relaxation

If the team agrees any professor should control equipment, add a comment and update the
spec so the decision is explicit.

**File:** `backend/app/api/control.py`

```python
# Any authenticated professor may control classroom equipment.
# Admins were previously required; relaxed in Phase 21 to match UX spec.
@router.post("/ac", response_model=RelayCommandResponse)
async def control_ac(
    body: RelayCommand,
    _: Professor = Depends(get_current_professor),
) -> RelayCommandResponse:
```

Also update `CLAUDE.md` → API Endpoints → Control table:

```
POST /api/control/ac      — {room_id, action: on|off|auto} → MQTT + Redis  (professor+)
POST /api/control/lighting — same pattern                                    (professor+)
```

---

## Fix B — Revert to admin-only

If the team confirms the admin gate was intentional, revert:

**File:** `backend/app/api/control.py`

```python
from app.api.deps import require_admin   # restore the import

@router.post("/ac", response_model=RelayCommandResponse)
async def control_ac(
    body: RelayCommand,
    _: Professor = Depends(require_admin),
) -> RelayCommandResponse:

@router.post("/lighting", response_model=RelayCommandResponse)
async def control_lighting(
    body: RelayCommand,
    _: Professor = Depends(require_admin),
) -> RelayCommandResponse:
```

---

## Files to Touch

- `backend/app/api/control.py` (lines 34, 48)
- `CLAUDE.md` — update the Control section to document the chosen policy

## Verification

```bash
# As a non-admin professor JWT:
curl -X POST http://localhost:8000/api/control/ac \
  -H "Authorization: Bearer <professor_token>" \
  -H "Content-Type: application/json" \
  -d '{"room_id":"room1","action":"on"}'

# Expected with Fix A: 200 OK
# Expected with Fix B: 403 Forbidden
```
