import { createContext, useState, useEffect, useContext } from 'react'

export const JornadaContext = createContext()

export function JornadaProvider({ children }) {
  const [jornada, setJornada] = useState(() => {
    const saved = localStorage.getItem('jornada_global')
    return saved ? parseInt(saved) : 6
  })

  useEffect(() => {
    localStorage.setItem('jornada_global', String(jornada))
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
