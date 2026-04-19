import { createContext, useState, useEffect, useContext } from 'react'
import { DEFAULT_JORNADA, readStoredJornada, writeStoredJornada } from '../utils/jornada'

export const JornadaContext = createContext()

export function JornadaProvider({ children }) {
  const [jornada, setJornada] = useState(() => {
    return readStoredJornada('jornada_global', DEFAULT_JORNADA)
  })

  useEffect(() => {
    writeStoredJornada(jornada)
  }, [jornada])

  return (
    <JornadaContext.Provider value={{ jornada, setJornada }}>
      {children}
    </JornadaContext.Provider>
  )
}

export function useJornada() {
  const context = useContext(JornadaContext)
  if (!context) {
    throw new Error('useJornada must be used within JornadaProvider')
  }
  return context
}
