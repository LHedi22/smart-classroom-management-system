import { Routes, Route, Navigate } from 'react-router-dom'
import Layout from './components/Layout'
import Dashboard from './pages/Dashboard'
import Attendance from './pages/Attendance'
import Control from './pages/Control'
import Enrollment from './pages/Enrollment'
import History from './pages/History'

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<Layout />}>
        <Route index element={<Navigate to="/dashboard" replace />} />
        <Route path="dashboard"  element={<Dashboard />} />
        <Route path="attendance" element={<Attendance />} />
        <Route path="control"    element={<Control />} />
        <Route path="enrollment" element={<Enrollment />} />
        <Route path="history"    element={<History />} />
      </Route>
    </Routes>
  )
}
