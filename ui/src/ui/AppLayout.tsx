// SPDX-License-Identifier: MIT
// Copyright (c) 2025 Copilot-for-Consensus contributors

import React, { Component, ReactNode } from 'react'
import { Outlet, Link, useLocation } from 'react-router-dom'
import { ThemeToggle } from '../components/ThemeToggle'

interface ErrorBoundaryState {
  hasError: boolean
  error: Error | null
}

class ErrorBoundary extends Component<{ children: ReactNode }, ErrorBoundaryState> {
  constructor(props: { children: ReactNode }) {
    super(props)
    this.state = { hasError: false, error: null }
  }

  static getDerivedStateFromError(error: Error) {
    return { hasError: true, error }
  }

  componentDidCatch(error: Error) {
    // If we got UNAUTHORIZED error, redirect to login
    if (error.message === 'UNAUTHORIZED') {
      window.location.href = `${import.meta.env.BASE_URL}login`
    }
  }

  render() {
    if (this.state.hasError) {
      if (this.state.error?.message === 'UNAUTHORIZED') {
        return (
          <div style={{ padding: '20px', textAlign: 'center' }}>
            <p>Redirecting to login...</p>
          </div>
        )
      }
      return (
        <div style={{ padding: '20px', textAlign: 'center' }}>
          <h2>Error</h2>
          <p>{this.state.error?.message || 'An unexpected error occurred'}</p>
          <p>
            <a href={`${import.meta.env.BASE_URL}reports`}>
              Return to reports
            </a>
          </p>
        </div>
      )
    }

    return this.props.children
  }
}

function AppLayoutContent() {
  const location = useLocation()
  
  const isActive = (path: string) => {
    if (path === '/') {
      return location.pathname === '/'
    }
    return location.pathname === path || location.pathname.startsWith(`${path}/`)
  }
  
  return (
    <div className="app-layout">
      <nav className="app-nav">
        <div className="nav-container">
          <div className="nav-brand">
            <h2>Copilot for Consensus</h2>
          </div>
          <div className="nav-links">
            <Link 
              to="/reports" 
              className={isActive('/reports') ? 'nav-link active' : 'nav-link'}
            >
              📊 Reports
            </Link>
            <Link 
              to="/sources" 
              className={isActive('/sources') ? 'nav-link active' : 'nav-link'}
            >
              📥 Ingestion Sources
            </Link>
            <Link 
              to="/admin" 
              className={isActive('/admin') ? 'nav-link active' : 'nav-link'}
            >
              🔐 Admin
            </Link>
            <ThemeToggle />
          </div>
        </div>
      </nav>
      <div className="container">
        <ErrorBoundary>
          <Outlet />
        </ErrorBoundary>
      </div>
    </div>
  )
}

export function AppLayout() {
  return <AppLayoutContent />
}
