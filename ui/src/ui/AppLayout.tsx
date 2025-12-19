// SPDX-License-Identifier: MIT
// Copyright (c) 2025 Copilot-for-Consensus contributors

import { Outlet, Link, useLocation } from 'react-router-dom'
import { ThemeToggle } from '../components/ThemeToggle'

export function AppLayout() {
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
        <Outlet />
      </div>
    </div>
  )
}
