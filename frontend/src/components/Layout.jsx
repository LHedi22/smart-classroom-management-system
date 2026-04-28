import { NavLink, Outlet } from 'react-router-dom'
import { SensorProvider, useSensor } from '../context/SensorContext'

const NAV = [
  { to: '/dashboard',  label: 'Dashboard',  icon: '▦' },
  { to: '/attendance', label: 'Attendance',  icon: '✓' },
  { to: '/control',    label: 'Control',     icon: '⚙' },
  { to: '/enrollment', label: 'Enrollment',  icon: '◉' },
  { to: '/history',    label: 'History',     icon: '⏱' },
]

function Sidebar() {
  const { alerts, isConnected } = useSensor()
  const unread = alerts.filter(a => !a.acknowledged).length

  return (
    <aside className="w-56 bg-gray-900 border-r border-gray-800 flex flex-col shrink-0">
      <div className="px-5 py-4 border-b border-gray-800">
        <p className="text-[10px] text-gray-500 uppercase tracking-widest">SMU MedTech</p>
        <p className="text-sm font-semibold text-white mt-0.5">Smart Classroom</p>
      </div>

      <nav className="flex-1 px-3 py-3 space-y-0.5">
        {NAV.map(({ to, label, icon }) => (
          <NavLink
            key={to}
            to={to}
            className={({ isActive }) =>
              `flex items-center gap-2.5 px-3 py-2 rounded-lg text-sm transition-colors ${
                isActive
                  ? 'bg-indigo-600 text-white font-medium'
                  : 'text-gray-400 hover:bg-gray-800 hover:text-white'
              }`
            }
          >
            <span className="text-base leading-none">{icon}</span>
            <span>{label}</span>
            {label === 'Dashboard' && unread > 0 && (
              <span className="ml-auto bg-red-500 text-white text-[10px] font-bold rounded-full px-1.5 py-0.5 leading-none">
                {unread > 99 ? '99+' : unread}
              </span>
            )}
          </NavLink>
        ))}
      </nav>

      <div className="px-5 py-3 border-t border-gray-800 flex items-center gap-2 text-xs text-gray-500">
        <span className={`w-2 h-2 rounded-full shrink-0 ${isConnected ? 'bg-green-500 animate-pulse' : 'bg-red-500'}`} />
        {isConnected ? 'Live' : 'Disconnected'}
      </div>
    </aside>
  )
}

export default function Layout() {
  return (
    <SensorProvider>
      <div className="flex h-screen overflow-hidden">
        <Sidebar />
        <main className="flex-1 overflow-auto">
          <Outlet />
        </main>
      </div>
    </SensorProvider>
  )
}
