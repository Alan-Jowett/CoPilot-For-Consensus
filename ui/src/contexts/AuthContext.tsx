// SPDX-License-Identifier: MIT
// Copyright (c) 2025 Copilot-for-Consensus contributors

import React, { createContext, useContext, useState, useEffect, ReactNode } from 'react'

interface UserInfo {
  sub: string
  email: string
  name: string
  roles?: string[]
}

interface AuthContextType {
  isAuthenticated: boolean
  isAdmin: boolean
  userInfo: UserInfo | null
  login: (provider: string) => void
  logout: () => void
  checkAuth: () => Promise<void>
}

const AuthContext = createContext<AuthContextType | undefined>(undefined)

// Global callbacks for auth operations
let globalOnUnauthorized: (() => void) | null = null

export const setUnauthorizedCallback = (callback: () => void) => {
  globalOnUnauthorized = callback
}

export const getUnauthorizedCallback = () => globalOnUnauthorized

/**
 * Check if the user has admin role from user info
 */
export const isUserAdmin = (userInfo: UserInfo | null): boolean => {
  if (!userInfo) return false
  return userInfo.roles?.includes('admin') ?? false
}

export const AuthProvider: React.FC<{ children: ReactNode }> = ({ children }) => {
  const [userInfo, setUserInfo] = useState<UserInfo | null>(null)
  const [isAdmin, setIsAdmin] = useState<boolean>(false)
  const [isAuthenticated, setIsAuthenticated] = useState<boolean>(false)
  const [isCheckingAuth, setIsCheckingAuth] = useState<boolean>(true)

  // Function to check authentication status by calling /auth/userinfo
  const checkAuth = async () => {
    try {
      console.log('[AuthContext] Checking authentication via /auth/userinfo')
      const response = await fetch('/auth/userinfo', {
        credentials: 'include'  // Include httpOnly cookies
      })
      
      if (response.ok) {
        const data = await response.json()
        console.log('[AuthContext] User authenticated:', data.email)
        setUserInfo(data)
        setIsAuthenticated(true)
        setIsAdmin(data.roles?.includes('admin') ?? false)
      } else {
        console.log('[AuthContext] Not authenticated (status:', response.status, ')')
        setUserInfo(null)
        setIsAuthenticated(false)
        setIsAdmin(false)
      }
    } catch (error) {
      console.error('[AuthContext] Error checking auth:', error)
      setUserInfo(null)
      setIsAuthenticated(false)
      setIsAdmin(false)
    } finally {
      setIsCheckingAuth(false)
    }
  }

  // Check authentication on mount
  useEffect(() => {
    console.log('[AuthContext] Component mounted, checking auth')
    checkAuth()
  }, [])

  const login = (provider: string = 'github') => {
    const audience = 'copilot-for-consensus'
    const redirectUri = `${window.location.origin}${import.meta.env.BASE_URL}callback`
    const loginUrl = `/auth/login?provider=${provider}&aud=${audience}&redirect_uri=${encodeURIComponent(redirectUri)}`
    window.location.href = loginUrl
  }

  const logout = async () => {
    try {
      // Call the logout endpoint to clear the httpOnly cookie
      await fetch('/auth/logout', {
        method: 'POST',
        credentials: 'include'
      })
    } catch (error) {
      console.error('[AuthContext] Logout error:', error)
    }
    
    // Clear local state
    setUserInfo(null)
    setIsAuthenticated(false)
    setIsAdmin(false)
    
    // Redirect to login
    window.location.href = `${import.meta.env.BASE_URL}`
  }

  return (
    <AuthContext.Provider value={{ 
      isAuthenticated, 
      isAdmin, 
      userInfo,
      login, 
      logout,
      checkAuth 
    }}>
      {!isCheckingAuth && children}
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
