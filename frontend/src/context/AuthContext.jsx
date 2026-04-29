import { createContext, useContext, useState, useCallback } from 'react'

const AuthContext = createContext(null)

const TOKEN_KEY = 'sc_token'
const PROF_KEY  = 'sc_professor'

function loadStored() {
  try {
    const token = localStorage.getItem(TOKEN_KEY)
    const prof  = JSON.parse(localStorage.getItem(PROF_KEY) || 'null')
    return { token, professor: prof }
  } catch {
    return { token: null, professor: null }
  }
}

export function AuthProvider({ children }) {
  const stored = loadStored()
  const [token,     setToken]     = useState(stored.token)
  const [professor, setProfessor] = useState(stored.professor)

  const login = useCallback((loginResponse) => {
    const prof = {
      id:   loginResponse.professor_id,
      name: loginResponse.name,
      role: loginResponse.role,
    }
    localStorage.setItem(TOKEN_KEY, loginResponse.access_token)
    localStorage.setItem(PROF_KEY,  JSON.stringify(prof))
    setToken(loginResponse.access_token)
    setProfessor(prof)
  }, [])

  const logout = useCallback(() => {
    localStorage.removeItem(TOKEN_KEY)
    localStorage.removeItem(PROF_KEY)
    setToken(null)
    setProfessor(null)
  }, [])

  return (
    <AuthContext.Provider value={{ token, professor, login, logout, isAuthenticated: !!token }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used inside AuthProvider')
  return ctx
}
