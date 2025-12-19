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

// Global callbacks for auth operations
let globalSetToken: ((token: string) => void) | null = null
let globalOnUnauthorized: (() => void) | null = null

export const setAuthToken = (token: string) => {
  if (globalSetToken) {
    globalSetToken(token)
  }
}

export const setUnauthorizedCallback = (callback: () => void) => {
  globalOnUnauthorized = callback
}

export const getUnauthorizedCallback = () => globalOnUnauthorized

export const AuthProvider: React.FC<{ children: ReactNode }> = ({ children }) => {
  const [token, setTokenInternal] = useState<string | null>(() => {
    return localStorage.getItem('auth_token')
  })

  // Store the setter globally so it can be called from api.ts
  useEffect(() => {
    globalSetToken = setTokenInternal
  }, [])

  useEffect(() => {
    if (token) {
      localStorage.setItem('auth_token', token)
    } else {
      localStorage.removeItem('auth_token')
    }
  }, [token])

  const login = (provider: string = 'github') => {
    const audience = 'copilot-orchestrator'
    const redirectUri = `${window.location.origin}${import.meta.env.BASE_URL}callback`
    const loginUrl = `/auth/login?provider=${provider}&aud=${audience}&redirect_uri=${encodeURIComponent(redirectUri)}`
    window.location.href = loginUrl
  }

  const logout = () => {
    setTokenInternal(null)
    window.location.href = `${import.meta.env.BASE_URL}`
  }

  return (
    <AuthContext.Provider value={{ token, isAuthenticated: !!token, login, logout, setToken: setTokenInternal }}>
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
