// SPDX-License-Identifier: MIT
// Copyright (c) 2025 Copilot-for-Consensus contributors

import { useAuth } from '../contexts/AuthContext'

interface AccessDeniedProps {
  message?: string
  showLogout?: boolean
}

/**
 * Component to display when a user lacks required permissions.
 * Shows a clear message and optionally a logout button.
 */
export function AccessDenied({ message, showLogout = true }: AccessDeniedProps) {
  const { logout } = useAuth()

  const defaultMessage = `You do not have permission to access this resource. Please contact an administrator to request access.`

  return (
    <div style={{
      maxWidth: '600px',
      margin: '40px auto',
      padding: '24px',
      border: '1px solid var(--border-color, #ddd)',
      borderRadius: '8px',
      backgroundColor: 'var(--bg-secondary, #f9f9f9)',
      textAlign: 'center'
    }}>
      <div style={{
        fontSize: '48px',
        marginBottom: '16px',
        color: 'var(--error-color, #d32f2f)'
      }}>
        🚫
      </div>
      <h2 style={{
        fontSize: '24px',
        marginBottom: '16px',
        color: 'var(--text-primary, #333)'
      }}>
        Access Denied
      </h2>
      <p style={{
        fontSize: '16px',
        lineHeight: '1.5',
        marginBottom: '24px',
        color: 'var(--text-secondary, #666)'
      }}>
        {message || defaultMessage}
      </p>
      {showLogout && (
        <button
          onClick={logout}
          style={{
            padding: '10px 20px',
            fontSize: '14px',
            backgroundColor: 'var(--primary-color, #1976d2)',
            color: 'white',
            border: 'none',
            borderRadius: '4px',
            cursor: 'pointer'
          }}
        >
          Logout
        </button>
      )}
    </div>
  )
}
