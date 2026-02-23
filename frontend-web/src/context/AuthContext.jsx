import { createContext, useContext, useState, useEffect, useCallback } from 'react'
import apiClient from '../services/apiClient'

const api_me = () => apiClient.get('/api/me/')
const api_login = (username, password) =>
  apiClient.post('/api/auth/login/', { username, password })
const api_logout = () => apiClient.post('/api/auth/logout/', {})
const api_register = (data) => apiClient.post('/api/auth/register/', data)

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null)
  const [loading, setLoading] = useState(true)

  // Fetch current user on mount (also sets Django CSRF cookie via ensure_csrf_cookie)
  const fetchUser = useCallback(async () => {
    try {
      const { data } = await api_me()
      setUser(data.authenticated ? data : null)
    } catch {
      setUser(null)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { fetchUser() }, [fetchUser])

  const login = async (username, password) => {
    const { data } = await api_login(username, password)
    setUser(data.user)
    return data
  }

  const logout = async () => {
    await api_logout()
    setUser(null)
  }

  const register = async (formData) => {
    const { data } = await api_register(formData)
    setUser(data.user)
    return data
  }

  return (
    <AuthContext.Provider value={{ user, loading, login, logout, register, refetchUser: fetchUser }}>
      {children}
    </AuthContext.Provider>
  )
}

export const useAuth = () => {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used inside AuthProvider')
  return ctx
}
