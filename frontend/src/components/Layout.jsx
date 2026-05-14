import { NavLink, Outlet, useNavigate } from 'react-router-dom'
import { SensorProvider, useSensor } from '../context/SensorContext'
import { useAuth } from '../context/AuthContext'

// ── SVG nav icons ────────────────────────────────────────────────────────
const GridIcon = () => (
  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/>
    <rect x="3" y="14" width="7" height="7" rx="1"/><rect x="14" y="14" width="7" height="7" rx="1"/>
  </svg>
)
const CheckUserIcon = () => (
  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/>
    <circle cx="9" cy="7" r="4"/>
    <polyline points="16 11 18 13 22 9"/>
  </svg>
)
const SlidersIcon = () => (
  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <line x1="4" y1="21" x2="4" y2="14"/><line x1="4" y1="10" x2="4" y2="3"/>
    <line x1="12" y1="21" x2="12" y2="12"/><line x1="12" y1="8" x2="12" y2="3"/>
    <line x1="20" y1="21" x2="20" y2="16"/><line x1="20" y1="12" x2="20" y2="3"/>
    <line x1="1" y1="14" x2="7" y2="14"/><line x1="9" y1="8" x2="15" y2="8"/>
    <line x1="17" y1="16" x2="23" y2="16"/>
  </svg>
)
const UserPlusIcon = () => (
  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M16 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/>
    <circle cx="8.5" cy="7" r="4"/>
    <line x1="20" y1="8" x2="20" y2="14"/>
    <line x1="23" y1="11" x2="17" y2="11"/>
  </svg>
)
const ClockIcon = () => (
  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <circle cx="12" cy="12" r="10"/>
    <polyline points="12 6 12 12 16 14"/>
  </svg>
)
const BarChartIcon = () => (
  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <line x1="18" y1="20" x2="18" y2="10"/>
    <line x1="12" y1="20" x2="12" y2="4"/>
    <line x1="6"  y1="20" x2="6"  y2="14"/>
  </svg>
)
const AlertTriangleIcon = () => (
  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/>
    <line x1="12" y1="9" x2="12" y2="13"/>
    <line x1="12" y1="17" x2="12.01" y2="17"/>
  </svg>
)
const TrendIcon = () => (
  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <polyline points="22 7 13.5 15.5 8.5 10.5 2 17"/>
    <polyline points="16 7 22 7 22 13"/>
  </svg>
)

const NAV = [
  { to: '/dashboard',  label: 'Dashboard',  Icon: GridIcon },
  { to: '/attendance', label: 'Attendance',  Icon: CheckUserIcon },
  { to: '/control',    label: 'Control',     Icon: SlidersIcon },
  { to: '/enrollment', label: 'Enrollment',  Icon: UserPlusIcon },
  { to: '/history',    label: 'History',     Icon: ClockIcon },
  { to: '/insights',   label: 'Insights',    Icon: BarChartIcon },
  { to: '/at-risk',      label: 'At-Risk',      Icon: AlertTriangleIcon },
  { to: '/forecasting',  label: 'Forecasting',  Icon: TrendIcon },
]

function Sidebar() {
  const { alerts, isConnected } = useSensor()
  const { professor, logout }   = useAuth()
  const navigate                = useNavigate()
  const unread = alerts.filter(a => !a.acknowledged).length

  function handleLogout() {
    logout()
    navigate('/login', { replace: true })
  }

  return (
    <aside className="sidebar-shell">
      {/* Brand */}
      <div className="sidebar-brand">
        <div className="sidebar-logo">
          <span className="sidebar-logo-text">SC</span>
        </div>
        <div>
          <span className="sidebar-brand-sub">SMU MedTech</span>
          <span className="sidebar-brand-name">Smart Classroom</span>
        </div>
      </div>

      {/* Navigation */}
      <nav className="sidebar-nav">
        {NAV.map(({ to, label, Icon }) => (
          <NavLink
            key={to}
            to={to}
            className={({ isActive }) =>
              `sidebar-nav-link ${isActive ? 'sidebar-nav-link-active' : 'sidebar-nav-link-inactive'}`
            }
          >
            <Icon />
            <span>{label}</span>
            {label === 'Dashboard' && unread > 0 && (
              <span className="sidebar-badge">{unread > 99 ? '99+' : unread}</span>
            )}
          </NavLink>
        ))}
      </nav>

      {/* Footer: professor + status */}
      <div className="sidebar-footer">
        {professor && (
          <div className="sidebar-professor">
            <div className="sidebar-avatar">
              {professor.name.charAt(0).toUpperCase()}
            </div>
            <div style={{ minWidth: 0 }}>
              <span className="sidebar-professor-name">{professor.name}</span>
              <span className="sidebar-professor-role">{professor.role}</span>
            </div>
          </div>
        )}

        <div className="sidebar-status-row">
          <span className={`sidebar-dot ${isConnected ? 'sidebar-dot-live' : 'sidebar-dot-offline'}`} />
          <span>{isConnected ? 'Live' : 'Disconnected'}</span>
          {professor && (
            <button onClick={handleLogout} className="sidebar-logout-btn">
              Sign out
            </button>
          )}
        </div>
      </div>
    </aside>
  )
}

export default function Layout() {
  return (
    <SensorProvider>
      <div className="flex h-screen overflow-hidden" style={{ background: 'var(--color-bg)' }}>
        <Sidebar />
        <main className="flex-1 overflow-auto p-5">
          <Outlet />
        </main>
      </div>
    </SensorProvider>
  )
}
