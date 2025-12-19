// SPDX-License-Identifier: MIT
// Copyright (c) 2025 Copilot-for-Consensus contributors

import React, { createContext, useContext, useState, useEffect, ReactNode } from 'react'

interface AuthContextType {
  token: string | null
  isAuthenticated: boolean
  login: (provider: string) => void
  logout: () => void
  setToken: (token: string) => void
}

const AuthContext = createContext<AuthContextType | undefined>(undefined)

export const AuthProvider: React.FC<{ children: ReactNode }> = ({ children }) => {
  const [token, setToken] = useState<string | null>(() => {
    return localStorage.getItem('auth_token')
  })

  useEffect(() => {
    if (token) {
      localStorage.setItem('auth_token', token)
    } else {
      localStorage.removeItem('auth_token')
    }
  }, [token])

  const login = (provider: string = 'github') => {
    const audience = 'copilot-orchestrator'
    const redirectUri = encodeURIComponent(`${window.location.origin}${import.meta.env.BASE_URL}callback`)
    const loginUrl = `/auth/login?provider=${provider}&aud=${audience}`
    window.location.href = loginUrl
  }

  const logout = () => {
    setToken(null)
    window.location.href = `${import.meta.env.BASE_URL}`
  }

  return (
    <AuthContext.Provider value={{ token, isAuthenticated: !!token, login, logout, setToken }}>
      {children}
    </AuthContext.Provider>
  )
}

export const useAuth = () => {
  const context = useContext(AuthContext)
  if (context === undefined) {
    throw new Error('useAuth must be used within an AuthProvider')
  }
  return context
}
