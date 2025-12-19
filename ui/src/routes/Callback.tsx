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

    if (error_param) {
      setError(`OAuth error: ${error_param}`)
      setLoading(false)
      return
    }

    if (token) {
      // Token received directly from auth service
      localStorage.setItem('auth_token', token)
      setAuthToken(token)
      // Redirect to reports
      window.location.href = `${import.meta.env.BASE_URL}reports`
    } else if (code) {
      // Exchange authorization code for token
      exchangeCodeForToken(code)
    } else {
      setError('No authorization token received')
      setLoading(false)
    }
  }, [searchParams])

  const exchangeCodeForToken = async (code: string) => {
    try {
      const response = await fetch('/auth/callback', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ code }),
      })

      if (!response.ok) {
        const error = await response.json().catch(() => ({
          detail: `Token exchange failed: ${response.status}`,
        }))
        throw new Error(error.detail)
      }

      const data = await response.json()
      if (data.token) {
        localStorage.setItem('auth_token', data.token)
        setAuthToken(data.token)
        window.location.href = `${import.meta.env.BASE_URL}reports`
      } else {
        throw new Error('No token in response')
      }
    } catch (err) {
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
