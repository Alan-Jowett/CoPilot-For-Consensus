// SPDX-License-Identifier: MIT
// Copyright (c) 2025 Copilot-for-Consensus contributors

import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Login } from './Login'
import { AuthProvider } from '../contexts/AuthContext'

// Mock fetch for auth check
const setupAuthMock = (isAuthenticated: boolean) => {
  const fetchMock = vi.fn()
  if (isAuthenticated) {
    fetchMock.mockResolvedValue({
      ok: true,
      json: async () => ({
        sub: 'github|123',
        email: 'test@test.com',
        name: 'Test User',
        roles: ['user'],
      }),
    })
  } else {
    fetchMock.mockResolvedValue({
      ok: false,
      status: 401,
    })
  }
  global.fetch = fetchMock
  return fetchMock
}

describe('Login', () => {
  const originalLocation = window.location

  beforeEach(() => {
    // Mock window.location
    delete (window as any).location
    window.location = { ...originalLocation, href: '' } as Location
  })

  afterEach(() => {
    vi.restoreAllMocks()
    window.location = originalLocation
  })

  it('renders login page with title', async () => {
    setupAuthMock(false)

    render(
      <AuthProvider>
        <Login />
      </AuthProvider>
    )

    // Wait for auth check to complete
    await screen.findByText('Copilot for Consensus')
    
    expect(screen.getByText('Sign in to continue')).toBeInTheDocument()
  })

  it('renders all sign-in provider buttons', async () => {
    setupAuthMock(false)

    render(
      <AuthProvider>
        <Login />
      </AuthProvider>
    )

    await screen.findByText('Copilot for Consensus')

    expect(screen.getByText('Sign in with GitHub')).toBeInTheDocument()
    expect(screen.getByText('Sign in with Google')).toBeInTheDocument()
    expect(screen.getByText('Sign in with Microsoft')).toBeInTheDocument()
  })

  it('renders privacy notice', async () => {
    setupAuthMock(false)

    render(
      <AuthProvider>
        <Login />
      </AuthProvider>
    )

    await screen.findByText('Copilot for Consensus')

    expect(screen.getByText(/By signing in, you agree to our terms and privacy policy/i)).toBeInTheDocument()
  })

  it('calls login with github provider', async () => {
    setupAuthMock(false)
    const user = userEvent.setup()

    render(
      <AuthProvider>
        <Login />
      </AuthProvider>
    )

    await screen.findByText('Copilot for Consensus')

    const githubButton = screen.getByText('Sign in with GitHub')
    await user.click(githubButton)

    // Should redirect to auth endpoint
    expect(window.location.href).toContain('/auth/login')
    expect(window.location.href).toContain('provider=github')
  })

  it('calls login with google provider', async () => {
    setupAuthMock(false)
    const user = userEvent.setup()

    render(
      <AuthProvider>
        <Login />
      </AuthProvider>
    )

    await screen.findByText('Copilot for Consensus')

    const googleButton = screen.getByText('Sign in with Google')
    await user.click(googleButton)

    expect(window.location.href).toContain('/auth/login')
    expect(window.location.href).toContain('provider=google')
  })

  it('calls login with microsoft provider', async () => {
    setupAuthMock(false)
    const user = userEvent.setup()

    render(
      <AuthProvider>
        <Login />
      </AuthProvider>
    )

    await screen.findByText('Copilot for Consensus')

    const microsoftButton = screen.getByText('Sign in with Microsoft')
    await user.click(microsoftButton)

    expect(window.location.href).toContain('/auth/login')
    expect(window.location.href).toContain('provider=microsoft')
  })

  it('redirects authenticated users to reports', async () => {
    setupAuthMock(true)

    render(
      <AuthProvider>
        <Login />
      </AuthProvider>
    )

    // Give time for auth check and redirect
    await new Promise(resolve => setTimeout(resolve, 100))

    expect(window.location.href).toContain('reports')
  })
})
