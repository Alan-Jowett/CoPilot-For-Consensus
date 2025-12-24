// SPDX-License-Identifier: MIT
// Copyright (c) 2025 Copilot-for-Consensus contributors

import React, { createContext, useContext, useState, useEffect, useMemo, ReactNode } from 'react'
import { jwtDecode } from 'jwt-decode'

interface JWTPayload {
  sub: string
  email: string
  name: string
  roles?: string[]
  [key: string]: any
}

interface AuthContextType {
  token: string | null
  isAuthenticated: boolean
  isAdmin: boolean
  login: (provider: string) => void
  logout: () => void
  setToken: (token: string) => void
}

const AuthContext = createContext<AuthContextType | undefined>(undefined)

// Global callbacks for auth operations
let globalSetToken: ((token: string) => void) | null = null
let globalOnUnauthorized: (() => void) | null = null

export const setAuthToken = (token: string) => {
  console.log('[AuthContext] setAuthToken called with:', token.substring(0, 50) + '...')
  if (globalSetToken) {
    console.log('[AuthContext] Calling globalSetToken')
    globalSetToken(token)
  } else {
    console.error('[AuthContext] globalSetToken is not set!')
  }
}

export const setUnauthorizedCallback = (callback: () => void) => {
  globalOnUnauthorized = callback
}

export const getUnauthorizedCallback = () => globalOnUnauthorized

/**
 * Check if the user has admin role from JWT token
 */
export const isUserAdmin = (token: string | null): boolean => {
  if (!token) return false
  
  try {
    const decoded = jwtDecode<JWTPayload>(token)
    // Check if 'admin' role exists in the roles array
    return decoded.roles?.includes('admin') ?? false
  } catch (err) {
    console.error('[AuthContext] Failed to decode token:', err)
    return false
  }
}

export const AuthProvider: React.FC<{ children: ReactNode }> = ({ children }) => {
  // Initialize both token and isAdmin from a single localStorage read to avoid duplicate access
  const initialState = useMemo(() => {
    const stored = localStorage.getItem('auth_token')
    console.log('[AuthContext] Initialized from localStorage:', !!stored)
    return {
      token: stored,
      isAdmin: isUserAdmin(stored)
    }
  }, [])

  const [token, setTokenInternal] = useState<string | null>(initialState.token)
  const [isAdmin, setIsAdmin] = useState<boolean>(initialState.isAdmin)

  // Store the setter globally so it can be called from api.ts
  useEffect(() => {
    console.log('[AuthContext] Setting global setToken')
    globalSetToken = setTokenInternal
  }, [])

  useEffect(() => {
    console.log('[AuthContext] Token changed:', !!token)
    if (token) {
      localStorage.setItem('auth_token', token)
      // Update admin status when token changes
      setIsAdmin(isUserAdmin(token))
    } else {
      localStorage.removeItem('auth_token')
      setIsAdmin(false)
    }
  }, [token])

  const login = (provider: string = 'github') => {
    const audience = 'copilot-for-consensus'
    const redirectUri = `${window.location.origin}${import.meta.env.BASE_URL}callback`
    const loginUrl = `/auth/login?provider=${provider}&aud=${audience}&redirect_uri=${encodeURIComponent(redirectUri)}`
    window.location.href = loginUrl
  }

  const logout = () => {
    setTokenInternal(null)
    window.location.href = `${import.meta.env.BASE_URL}`
  }

  return (
    <AuthContext.Provider value={{ token, isAuthenticated: !!token, isAdmin, login, logout, setToken: setTokenInternal }}>
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
