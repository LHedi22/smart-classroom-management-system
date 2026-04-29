export default function DemoModeBanner({ isDemoMode }) {
  if (!isDemoMode) return null
  return (
    <div className="bg-amber-900/60 border border-amber-600 rounded-xl px-4 py-2.5 text-sm text-amber-200 flex items-center gap-2">
      <span aria-hidden="true">⚠️</span>
      <span>Demo Mode — No hardware connected. Showing simulated data.</span>
    </div>
  )
}
