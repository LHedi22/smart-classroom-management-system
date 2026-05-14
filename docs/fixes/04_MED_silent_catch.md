# Fix Plan 04 — MEDIUM: Silent Catch in `handleRecompute` Swallows Real Errors

## Problem

`frontend/src/pages/Forecasting.jsx`, `handleRecompute` (lines 463–469):

```javascript
async function handleRecompute() {
  setRecomputing(true)
  try {
    await client.post('/forecasting/recompute')
  } catch {
    // 202 Accepted — ignore
  }
  ...
}
```

**The comment is factually wrong.** A `202 Accepted` response resolves the `await`
successfully — it never enters the `catch` block. Only actual errors land here:

| Scenario | HTTP Status | Current behaviour |
|----------|------------|-------------------|
| Non-admin professor clicks button | 403 Forbidden | Silently ignored |
| Backend is down / CORS error | Network error | Silently ignored |
| Internal server error | 500 | Silently ignored |
| Recompute accepted | 202 | Resolves normally (never reaches catch) |

The button shows "Recompute Now" to admin users only (`isAdmin` guard in JSX), so
the 403 case cannot happen through normal UI interaction — but it can happen if the
`isAdmin` flag is cached stale after a role change, or during development.

More importantly, **any network failure is silently swallowed**, and the
`setTimeout(..., 3000)` fires anyway, making it look like the recompute started when
it actually failed.

---

## Root Cause

The `catch` block was written with the intent of ignoring the 202 response. The
author confused "the endpoint returns 202" (a success status code) with a thrown error.

---

## Fix

**File:** `frontend/src/pages/Forecasting.jsx`

Replace the silent catch with a state variable that can surface the error, then clear
it after a short timeout.

### Step 1 — Add `recomputeError` state (~line 442, near other state declarations)

```javascript
const [recomputeError, setRecomputeError] = useState(null)
```

### Step 2 — Replace the silent catch

```javascript
async function handleRecompute() {
  setRecomputing(true)
  setRecomputeError(null)
  try {
    await client.post('/forecasting/recompute')
  } catch (err) {
    const msg = err?.response?.data?.detail || err?.message || 'Recompute failed'
    setRecomputeError(msg)
    setRecomputing(false)
    return   // don't fake a successful refresh
  }
  setTimeout(() => {
    fetchList()
    setDetailKey(k => k + 1)   // see Fix 03
    setRecomputing(false)
  }, 3000)
}
```

### Step 3 — Render the error near the Recompute button

In `DetailPanel` props, pass `recomputeError` down, or render it in the parent
`Forecasting` component above the panels. The simplest approach — render inline
next to the button inside `DetailPanel`:

Since `onRecompute` / `recomputing` are already props, add `recomputeError`:

```jsx
// In Forecasting (parent), pass the prop:
<DetailPanel
  key={detailKey}
  courseId={selected?.course_id}
  isAdmin={isAdmin}
  onRecompute={handleRecompute}
  recomputing={recomputing}
  recomputeError={recomputeError}   // new
/>
```

In `DetailPanel`, accept and render it near the button:

```jsx
function DetailPanel({ courseId, isAdmin, onRecompute, recomputing, recomputeError }) {
  ...
  {isAdmin && (
    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: 6 }}>
      <button
        className="btn-secondary"
        style={{ display: 'flex', alignItems: 'center', gap: 6 }}
        onClick={onRecompute}
        disabled={recomputing}
      >
        <RefreshIcon />
        {recomputing ? 'Starting…' : 'Recompute Now'}
      </button>
      {recomputeError && (
        <span style={{ fontSize: 'var(--text-xs)', color: 'var(--color-red)' }}>
          {recomputeError}
        </span>
      )}
    </div>
  )}
```

---

## Minimal Acceptable Fix (if the above is too large in scope)

At minimum, log the error so it appears in browser DevTools:

```javascript
} catch (err) {
  console.error('Forecasting recompute failed:', err?.response?.status, err?.message)
}
```

This prevents silent failures in development without requiring UI changes.

---

## Files to Touch

| File | Location | Change |
|------|----------|--------|
| `frontend/src/pages/Forecasting.jsx` | ~line 442 | Add `recomputeError` state |
| `frontend/src/pages/Forecasting.jsx` | `handleRecompute` | Replace empty catch with error capture + early return |
| `frontend/src/pages/Forecasting.jsx` | `<DetailPanel>` JSX | Pass `recomputeError` prop |
| `frontend/src/pages/Forecasting.jsx` | `DetailPanel` function signature | Accept and render `recomputeError` |

---

## Verification

1. Temporarily remove the `isAdmin` guard from the Recompute button so a
   non-admin professor can click it.
2. Click "Recompute Now" as a non-admin professor.
3. The button should stop spinning and show a red error message (403) instead of
   silently completing.
4. Restore the `isAdmin` guard.
