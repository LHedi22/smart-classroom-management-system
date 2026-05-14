# Fix Plan 03 — MEDIUM: Detail Panel Stays Stale After "Recompute Now"

## Problem

`frontend/src/pages/Forecasting.jsx`, `handleRecompute` function (lines 463–475):

```javascript
async function handleRecompute() {
  setRecomputing(true)
  try {
    await client.post('/forecasting/recompute')
  } catch {
    // silent
  }
  setTimeout(() => {
    fetchList()
    setSelected(s => s ? { ...s } : s)  // ← this does NOT trigger a detail refetch
    setRecomputing(false)
  }, 3000)
}
```

**Why the detail panel doesn't update:**

`DetailPanel` receives `courseId={selected?.course_id}` and watches it in a `useEffect`:

```javascript
useEffect(() => {
  if (!courseId) { setDetail(null); return }
  client.get(`/forecasting/${courseId}`)
    ...
}, [courseId])   // ← only fires when courseId string value changes
```

`setSelected(s => s ? { ...s } : s)` creates a new object reference, but
`selected?.course_id` is the **same string value**. React compares `useEffect`
dependencies by value (`Object.is`), so `courseId` is unchanged → the effect does
not re-run → the detail panel shows stale data.

**User impact:** After clicking "Recompute Now" and waiting 3 seconds, the list
refreshes but the detail panel continues showing the old interpretation and chart
until the user manually clicks away and back.

---

## Root Cause

`DetailPanel` is controlled by a single `courseId` prop. Changing the parent object
that holds `course_id` has no effect on the child's `useEffect` dependency.

---

## Fix

Add a `detailKey` counter to the parent state. Incrementing it causes React to
**remount** `DetailPanel`, which triggers its `useEffect` unconditionally.

**File:** `frontend/src/pages/Forecasting.jsx`

### Step 1 — Add `detailKey` state (near other `useState` declarations, ~line 441)

```javascript
const [detailKey, setDetailKey] = useState(0)
```

### Step 2 — Increment the key in `handleRecompute` alongside `fetchList()`

```javascript
// Inside the setTimeout callback:
setTimeout(() => {
  fetchList()
  setDetailKey(k => k + 1)   // forces DetailPanel remount → refetches detail
  setRecomputing(false)
}, 3000)

// Remove the now-redundant setSelected spread:
// setSelected(s => s ? { ...s } : s)   ← delete this line
```

### Step 3 — Pass `detailKey` as the `key` prop on `DetailPanel` (~line 540)

```jsx
<DetailPanel
  key={detailKey}
  courseId={selected?.course_id}
  isAdmin={isAdmin}
  onRecompute={handleRecompute}
  recomputing={recomputing}
/>
```

### Why `key` works

React uses `key` to decide whether to reuse or destroy+recreate a component.
Changing `key` forces a full remount, resetting all internal state (`detail`,
`loading`) and re-running all `useEffect` hooks — exactly what is needed here.

---

## Alternative (without remount)

If remounting `DetailPanel` is undesirable (e.g., it causes a visible flash),
expose a `refreshToken` prop and add it to the `useEffect` dependency array:

```javascript
// DetailPanel
useEffect(() => {
  if (!courseId) { setDetail(null); return }
  setLoading(true)
  client.get(`/forecasting/${courseId}`)
    .then(r => setDetail(r.data))
    .catch(() => setDetail(null))
    .finally(() => setLoading(false))
}, [courseId, refreshToken])   // ← refreshToken triggers re-fetch without remount
```

The `key` approach (Step 3 above) is simpler and equally correct for this use case.

---

## Files to Touch

| File | Location | Change |
|------|----------|--------|
| `frontend/src/pages/Forecasting.jsx` | ~line 441 | Add `detailKey` state |
| `frontend/src/pages/Forecasting.jsx` | ~line 471 | Replace spread with `setDetailKey(k => k + 1)` |
| `frontend/src/pages/Forecasting.jsx` | ~line 540 | Add `key={detailKey}` to `<DetailPanel>` |

---

## Verification

1. Open the Forecasting page and select a course.
2. Click "Recompute Now".
3. After ~3 seconds the detail panel should show a loading skeleton briefly, then
   reload with fresh data.
4. The course list should also refresh.
