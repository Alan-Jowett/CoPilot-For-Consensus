// SPDX-License-Identifier: MIT
// Copyright (c) 2025 Copilot-for-Consensus contributors

import React, { createContext, useContext, useState, useEffect, ReactNode, useRef, useCallback } from 'react'

interface UserInfo {
  sub: string
  email: string
  name: string
  roles?: string[]
  exp?: number  // Token expiration timestamp (seconds since epoch)
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

// Token refresh configuration constants
const TOKEN_REFRESH_BUFFER_SECONDS = 300 // Refresh 5 minutes before expiration
const MIN_REFRESH_BUFFER_FRACTION = 0.5 // Or halfway for short-lived tokens

// Note: Multi-tab coordination
// Currently, each tab independently schedules refresh timers. Since the refresh involves
// a full-page redirect and tokens are shared via httpOnly cookies, race conditions are
// handled by the browser's cookie mechanism. However, multiple simultaneous refreshes may
// occur if tabs refresh at similar times. Future improvement could use BroadcastChannel API
// or localStorage events to coordinate refresh across tabs.

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
  // Track refresh timer in a ref so cleanup never captures stale state.
  const refreshTimerIdRef = useRef<number | null>(null)

  // Function to refresh the token silently
  // Note: This function initiates navigation and never returns
  const refreshToken = useCallback(() => {
    console.log('[AuthContext] Attempting silent token refresh')
    
    // Save current location so we can return after refresh (including hash fragment)
    const currentPath = window.location.pathname + window.location.search + window.location.hash
    sessionStorage.setItem('postRefreshUrl', currentPath)
    
    // Redirect to refresh endpoint which will initiate OIDC prompt=none flow
    // The OIDC provider will redirect back to /callback which will set new cookie
    // and redirect back to the saved location
    window.location.href = '/auth/refresh'
  }, [])

  // Clear the refresh timer
  const clearRefreshTimer = useCallback(() => {
    if (refreshTimerIdRef.current !== null) {
      clearTimeout(refreshTimerIdRef.current)
      refreshTimerIdRef.current = null
    }
  }, [])

  // Schedule automatic token refresh before expiration
  const scheduleTokenRefresh = useCallback((expirationTimestamp: number) => {
    clearRefreshTimer()

    const now = Math.floor(Date.now() / 1000) // Current time in seconds
    const expiresIn = expirationTimestamp - now // Time until expiration in seconds
    
    // Refresh before expiration with a buffer, or halfway through for short-lived tokens
    // For tokens >10 minutes: refresh 5 minutes before expiry
    // For tokens <10 minutes: refresh halfway through (e.g., 3 min token refreshes at 1.5 min)
    // For very short or expired tokens: schedule a deferred refresh to allow initial render
    const refreshBuffer = Math.min(TOKEN_REFRESH_BUFFER_SECONDS, Math.floor(expiresIn * MIN_REFRESH_BUFFER_FRACTION))
    const refreshIn = Math.max(0, expiresIn - refreshBuffer)

    console.log(
      `[AuthContext] Token expires in ${expiresIn}s, scheduling refresh in ${refreshIn}s`
    )

    if (refreshIn > 0) {
      const timerId = setTimeout(() => {
        console.log('[AuthContext] Refresh timer triggered')
        refreshToken()
      }, refreshIn * 1000) as number // setTimeout returns number in browser

      refreshTimerIdRef.current = timerId
    } else {
      // Token already expired or very close to expiration; defer refresh slightly
      // to allow the UI to render first, avoiding redirect during initial render
      console.log('[AuthContext] Token already expired, scheduling immediate refresh')
      const timerId = setTimeout(() => {
        console.log('[AuthContext] Immediate refresh timer triggered')
        refreshToken()
      }, 100) as number // 100ms delay to let UI render
      refreshTimerIdRef.current = timerId
    }
  }, [clearRefreshTimer, refreshToken])

  // Function to check authentication status by calling /auth/userinfo
  const checkAuth = useCallback(async () => {
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
        
        // Schedule token refresh if expiration is available
        if (data.exp) {
          scheduleTokenRefresh(data.exp)
        }
      } else {
        console.log('[AuthContext] Not authenticated (status:', response.status, ')')
        setUserInfo(null)
        setIsAuthenticated(false)
        setIsAdmin(false)
        clearRefreshTimer()
      }
    } catch (error) {
      console.error('[AuthContext] Error checking auth:', error)
      setUserInfo(null)
      setIsAuthenticated(false)
      setIsAdmin(false)
      clearRefreshTimer()
    } finally {
      setIsCheckingAuth(false)
    }
  }, [scheduleTokenRefresh, clearRefreshTimer])

  // Check authentication on mount
  // Note: checkAuth is included in dependencies to satisfy exhaustive-deps, but since
  // it's wrapped in useCallback with stable dependencies (scheduleTokenRefresh, clearRefreshTimer),
  // it won't cause re-renders after the initial mount. The effect only runs once on mount.
  useEffect(() => {
    console.log('[AuthContext] Component mounted, checking auth')
    checkAuth()

    // Cleanup refresh timer on unmount
    return () => {
      clearRefreshTimer()
    }
  }, [checkAuth, clearRefreshTimer]) // checkAuth is stable due to useCallback with stable deps

  const login = (provider: string = 'github') => {
    const audience = 'copilot-for-consensus'
    const redirectUri = `${window.location.origin}${import.meta.env.BASE_URL}callback`
    const loginUrl = `/auth/login?provider=${provider}&aud=${audience}&redirect_uri=${encodeURIComponent(redirectUri)}`
    window.location.href = loginUrl
  }

  const logout = async () => {
    try {
      // Clear refresh timer
      clearRefreshTimer()

      // Call the logout endpoint to clear the httpOnly cookie
      const response = await fetch('/auth/logout', {
        method: 'POST',
        credentials: 'include'
      })

      if (!response.ok) {
        console.error('[AuthContext] Logout failed with status:', response.status)
      }
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : 'Unknown error'
      console.error('[AuthContext] Logout error:', errorMessage)
    }

    // Clear local state regardless of API call result
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
      {isCheckingAuth ? (
        <div style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          minHeight: '100vh',
          fontFamily: 'system-ui, -apple-system, sans-serif'
        }}>
          <div style={{ textAlign: 'center' }}>
            <div style={{
              width: '48px',
              height: '48px',
              border: '4px solid #f3f3f3',
              borderTop: '4px solid #3498db',
              borderRadius: '50%',
              animation: 'spin 1s linear infinite',
              margin: '0 auto 16px'
            }} />
            <p style={{ color: '#666', margin: 0 }}>Loading...</p>
          </div>
        </div>
      ) : children}
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
