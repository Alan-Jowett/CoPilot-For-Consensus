// SPDX-License-Identifier: MIT
// Copyright (c) 2025 Copilot-for-Consensus contributors

import React, { useEffect, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { setAuthToken } from '../contexts/AuthContext'
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
    // - access_token parameter: JWT token directly
    // - token_type parameter: usually "Bearer"

    const token = searchParams.get('token')
    const code = searchParams.get('code')
    const error_param = searchParams.get('error')

    console.log('[Callback] Extracted: token=%s, code=%s, error=%s', !!token, !!code, error_param)

    if (error_param) {
      setError(`OAuth error: ${error_param}`)
      setLoading(false)
      return
    }

    if (token) {
      // Token received directly from auth service
      console.log('[Callback] Token found in URL params, storing and redirecting')
      localStorage.setItem('auth_token', token)
      setAuthToken(token)
      // Redirect to reports
      window.location.href = '/ui/reports'
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
      const response = await fetch(`/auth/callback?code=${encodeURIComponent(code)}&state=${encodeURIComponent(state)}`)

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
        console.log('[Callback] Storing token and redirecting to /ui/reports')
        localStorage.setItem('auth_token', data.access_token)
        setAuthToken(data.access_token)
        window.location.href = '/ui/reports'
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
