// SPDX-License-Identifier: MIT
// Copyright (c) 2025 Copilot-for-Consensus contributors

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import { AuthProvider, useAuth, isUserAdmin } from './AuthContext'
import { createMockResponse } from '../test/testUtils'

describe('AuthContext', () => {
  let fetchMock: ReturnType<typeof vi.fn>
  const originalLocation = window.location

  beforeEach(() => {
    fetchMock = vi.fn()
    global.fetch = fetchMock
    
    // Mock window.location
    delete (window as any).location
    window.location = { ...originalLocation, href: '' } as Location
  })

  afterEach(() => {
    vi.restoreAllMocks()
    window.location = originalLocation
  })

  describe('isUserAdmin', () => {
    it('returns true for users with admin role', () => {
      const userInfo = { sub: '1', email: 'admin@test.com', name: 'Admin', roles: ['admin'] }
      expect(isUserAdmin(userInfo)).toBe(true)
    })

    it('returns false for users without admin role', () => {
      const userInfo = { sub: '1', email: 'user@test.com', name: 'User', roles: ['user'] }
      expect(isUserAdmin(userInfo)).toBe(false)
    })

    it('returns false for null userInfo', () => {
      expect(isUserAdmin(null)).toBe(false)
    })

    it('returns false when roles array is undefined', () => {
      const userInfo = { sub: '1', email: 'user@test.com', name: 'User' }
      expect(isUserAdmin(userInfo)).toBe(false)
    })
  })

  describe('AuthProvider', () => {
    it('shows loading state initially', () => {
      fetchMock.mockImplementation(() => new Promise(() => {})) // Never resolves

      render(
        <AuthProvider>
          <div>Content</div>
        </AuthProvider>
      )

      expect(screen.getByText('Loading...')).toBeInTheDocument()
    })

    it('authenticates user successfully', async () => {
      const mockUserInfo = {
        sub: 'github|123',
        email: 'user@test.com',
        name: 'Test User',
        roles: ['user'],
      }
      fetchMock.mockResolvedValue(createMockResponse(mockUserInfo))

      function TestComponent() {
        const { isAuthenticated, userInfo } = useAuth()
        return (
          <div>
            {isAuthenticated ? 'Authenticated' : 'Not authenticated'}
            {userInfo && <div>Email: {userInfo.email}</div>}
          </div>
        )
      }

      render(
        <AuthProvider>
          <TestComponent />
        </AuthProvider>
      )

      await waitFor(() => {
        expect(screen.getByText('Authenticated')).toBeInTheDocument()
      })
      expect(screen.getByText('Email: user@test.com')).toBeInTheDocument()
    })

    it('sets admin flag for admin users', async () => {
      const mockUserInfo = {
        sub: 'github|123',
        email: 'admin@test.com',
        name: 'Admin User',
        roles: ['admin'],
      }
      fetchMock.mockResolvedValue(createMockResponse(mockUserInfo))

      function TestComponent() {
        const { isAdmin } = useAuth()
        return <div>{isAdmin ? 'Admin' : 'Not admin'}</div>
      }

      render(
        <AuthProvider>
          <TestComponent />
        </AuthProvider>
      )

      await waitFor(() => {
        expect(screen.getByText('Admin')).toBeInTheDocument()
      })
    })

    it('handles authentication failure', async () => {
      fetchMock.mockResolvedValue(createMockResponse({}, { status: 401, ok: false }))

      function TestComponent() {
        const { isAuthenticated } = useAuth()
        return <div>{isAuthenticated ? 'Authenticated' : 'Not authenticated'}</div>
      }

      render(
        <AuthProvider>
          <TestComponent />
        </AuthProvider>
      )

      await waitFor(() => {
        expect(screen.getByText('Not authenticated')).toBeInTheDocument()
      })
    })

    it('login redirects to auth endpoint', async () => {
      fetchMock.mockResolvedValue(createMockResponse({ sub: '1', email: 'test@test.com', name: 'Test' }))

      function TestComponent() {
        const { login } = useAuth()
        return <button onClick={() => login('github')}>Login</button>
      }

      render(
        <AuthProvider>
          <TestComponent />
        </AuthProvider>
      )

      await waitFor(() => {
        expect(screen.getByText('Login')).toBeInTheDocument()
      })

      screen.getByText('Login').click()

      expect(window.location.href).toContain('/auth/login')
      expect(window.location.href).toContain('provider=github')
      expect(window.location.href).toContain('aud=copilot-for-consensus')
    })

    it('logout clears state and redirects', async () => {
      const mockUserInfo = {
        sub: 'github|123',
        email: 'user@test.com',
        name: 'Test User',
        roles: ['user'],
      }
      
      // First call for initial auth check, second call for logout
      fetchMock
        .mockResolvedValueOnce(createMockResponse(mockUserInfo))
        .mockResolvedValueOnce(createMockResponse({}, { status: 200, ok: true }))

      function TestComponent() {
        const { isAuthenticated, logout } = useAuth()
        return (
          <div>
            <div>{isAuthenticated ? 'Authenticated' : 'Not authenticated'}</div>
            <button onClick={logout}>Logout</button>
          </div>
        )
      }

      render(
        <AuthProvider>
          <TestComponent />
        </AuthProvider>
      )

      await waitFor(() => {
        expect(screen.getByText('Authenticated')).toBeInTheDocument()
      })

      screen.getByText('Logout').click()

      await waitFor(() => {
        expect(fetchMock).toHaveBeenCalledWith(
          '/auth/logout',
          expect.objectContaining({ method: 'POST', credentials: 'include' })
        )
      })
    })
  })

  describe('useAuth hook', () => {
    it('throws error when used outside AuthProvider', () => {
      // Suppress console.error for this test
      const consoleError = vi.spyOn(console, 'error').mockImplementation(() => {})

      function TestComponent() {
        useAuth()
        return <div>Test</div>
      }

      expect(() => render(<TestComponent />)).toThrow('useAuth must be used within an AuthProvider')

      consoleError.mockRestore()
    })
  })
})
