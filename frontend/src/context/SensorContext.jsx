import { createContext, useContext } from 'react'
import useLiveSensors from '../hooks/useLiveSensors'

const SensorContext = createContext(null)

export function SensorProvider({ children }) {
  const value = useLiveSensors()
  return <SensorContext.Provider value={value}>{children}</SensorContext.Provider>
}

export function useSensor() {
  return useContext(SensorContext)
}
