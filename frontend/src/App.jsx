import { Routes, Route, Navigate } from 'react-router-dom'
import { AuthProvider, useAuth } from './context/AuthContext'
import Layout from './components/Layout'
import Login from './pages/Login'
import Dashboard from './pages/Dashboard'
import Attendance from './pages/Attendance'
import Control from './pages/Control'
import Enrollment from './pages/Enrollment'
import History from './pages/History'
import Insights from './pages/Insights'
import AtRisk from './pages/AtRisk'
import Forecasting from './pages/Forecasting'

function ProtectedRoute({ children }) {
  const { isAuthenticated } = useAuth()
  return isAuthenticated ? children : <Navigate to="/login" replace />
}

function PublicRoute({ children }) {
  const { isAuthenticated } = useAuth()
  return isAuthenticated ? <Navigate to="/dashboard" replace /> : children
}

export default function App() {
  return (
    <AuthProvider>
      <Routes>
        <Route
          path="/login"
          element={<PublicRoute><Login /></PublicRoute>}
        />
        <Route
          path="/"
          element={<ProtectedRoute><Layout /></ProtectedRoute>}
        >
          <Route index element={<Navigate to="/dashboard" replace />} />
          <Route path="dashboard"  element={<Dashboard />} />
          <Route path="attendance" element={<Attendance />} />
          <Route path="control"    element={<Control />} />
          <Route path="enrollment" element={<Enrollment />} />
          <Route path="history"    element={<History />} />
          <Route path="insights"   element={<Insights />} />
          <Route path="at-risk"      element={<AtRisk />} />
          <Route path="forecasting"  element={<Forecasting />} />
        </Route>
        <Route path="*" element={<Navigate to="/dashboard" replace />} />
      </Routes>
    </AuthProvider>
  )
}
