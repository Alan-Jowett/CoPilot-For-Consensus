// SPDX-License-Identifier: MIT
// Copyright (c) 2025 Copilot-for-Consensus contributors

import React, { useEffect, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import styles from './Callback.module.css'

export function Callback() {
  const [searchParams] = useSearchParams()
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    console.log('[Callback] Component mounted, searchParams:', Object.fromEntries(searchParams))

    // Extract token from URL parameters
    // OAuth2 authorization servers typically redirect with:
    // - code parameter: authorization code to exchange for token
    // - state parameter: CSRF protection
    // Or for implicit flow:
    // - token parameter: JWT token directly
    // - token_type parameter: usually "Bearer"

    const token = searchParams.get('token')
    const code = searchParams.get('code')
    const error_param = searchParams.get('error')

    console.log('[Callback] Extracted: token=%s, code=%s, error=%s', !!token, !!code, error_param)

    if (error_param) {
      // Check if this is a silent refresh that failed (e.g., login_required)
      const postRefreshUrl = sessionStorage.getItem('postRefreshUrl')
      if (postRefreshUrl && (error_param === 'login_required' || error_param === 'interaction_required')) {
        // Silent refresh failed because OIDC session expired
        // Clear the saved URL and redirect to login
        sessionStorage.removeItem('postRefreshUrl')
        console.log('[Callback] Silent refresh failed (OIDC session expired), redirecting to login')
        setError('Your session has expired. Please log in again.')
        setTimeout(() => {
          window.location.href = `${import.meta.env.BASE_URL}login`
        }, 2000)
        return
      }
      
      setError(`OAuth error: ${error_param}`)
      setLoading(false)
      return
    }

    if (token) {
      // Token received directly from auth service
      // The token is already set as an httpOnly cookie by the auth service
      console.log('[Callback] Token found in URL params, cookie should be set by auth service')

      // Check if this is a token refresh (return to saved page)
      const postRefreshUrl = sessionStorage.getItem('postRefreshUrl')
      let redirectUrl = '/ui/reports'

      if (postRefreshUrl) {
        // Return to page where refresh was triggered
        redirectUrl = postRefreshUrl
        sessionStorage.removeItem('postRefreshUrl')
        console.log('[Callback] Token refreshed, returning to:', redirectUrl)
      } else {
        // Check for legacy postLoginUrl for backward compatibility
        const postLoginUrl = sessionStorage.getItem('postLoginUrl')
        if (postLoginUrl) {
          redirectUrl = postLoginUrl
          sessionStorage.removeItem('postLoginUrl')
          console.log('[Callback] Normal login, returning to:', redirectUrl)
        } else {
          console.log('[Callback] Normal login, redirecting to reports')
        }
      }

      // Redirect to destination
      console.log('[Callback] Redirecting to', redirectUrl)
      window.location.href = redirectUrl
    } else if (code) {
      // Exchange authorization code for token
      console.log('[Callback] Code found, exchanging for token')
      exchangeCodeForToken(code)
    } else {
      setError('No authorization token received')
      setLoading(false)
    }
  }, [searchParams])

  const exchangeCodeForToken = async (code: string) => {
    try {
      // The /callback endpoint is actually handled by the auth service at the gateway
      // We need to fetch it with the code and state parameters
      const state = searchParams.get('state')
      if (!state) {
        throw new Error('Missing state parameter')
      }

      console.log('[Callback] Exchanging code for token, calling /auth/callback...')
      const response = await fetch(`/auth/callback?code=${encodeURIComponent(code)}&state=${encodeURIComponent(state)}`, {
        credentials: 'include'  // Include cookies in request
      })

      console.log('[Callback] Response status:', response.status)

      if (!response.ok) {
        const error = await response.json().catch(() => ({
          detail: `Token exchange failed: ${response.status}`,
        }))
        throw new Error(error.detail)
      }

      const data = await response.json()
      console.log('[Callback] Got response:', { access_token: !!data.access_token, token_type: data.token_type })

      if (data.access_token) {
        // Token is set as httpOnly cookie by the auth service
        // No need to store in localStorage (security improvement)
        console.log('[Callback] Token received and set as httpOnly cookie by auth service')

        // Check if this is a token refresh (return to saved page)
        const postRefreshUrl = sessionStorage.getItem('postRefreshUrl')
        let redirectUrl = '/ui/reports'

        if (postRefreshUrl) {
          // Return to page where refresh was triggered
          redirectUrl = postRefreshUrl
          sessionStorage.removeItem('postRefreshUrl')
          console.log('[Callback] Token refreshed, returning to:', redirectUrl)
        } else {
          // Check for legacy postLoginUrl for backward compatibility
          const postLoginUrl = sessionStorage.getItem('postLoginUrl')
          if (postLoginUrl) {
            redirectUrl = postLoginUrl
            sessionStorage.removeItem('postLoginUrl')
            console.log('[Callback] Normal login, returning to:', redirectUrl)
          } else {
            console.log('[Callback] Normal login, redirecting to reports')
          }
        }

        // Redirect after a short delay to allow logs to be read
        console.log('[Callback] Will redirect to', redirectUrl, 'in 1 second (or enable "Preserve log" in DevTools)')
        setTimeout(() => {
          console.log('[Callback] NOW redirecting to', redirectUrl)
          window.location.href = redirectUrl
        }, 1000)
      } else {
        throw new Error('No token in response')
      }
    } catch (err) {
      console.error('[Callback] Error:', err)
      setError(err instanceof Error ? err.message : 'Token exchange failed')
      setLoading(false)
    }
  }

  return (
    <div className={styles.container}>
      <div className={styles.card}>
        {loading && (
          <>
            <div className={styles.spinner}></div>
            <p className={styles.message}>
              Signing you in...
            </p>
          </>
        )}

        {error && (
          <>
            <h2 className={styles.error}>Authentication Error</h2>
            <p className={styles.errorDetail}>{error}</p>
            <a
              href={`${import.meta.env.BASE_URL}login`}
              className={styles.link}
            >
              Return to login
            </a>
          </>
        )}
      </div>
    </div>
  )
}
