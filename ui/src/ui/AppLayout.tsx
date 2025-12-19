// SPDX-License-Identifier: MIT
// Copyright (c) 2025 Copilot-for-Consensus contributors

import { Outlet } from 'react-router-dom'
import { ThemeToggle } from '../components/ThemeToggle'

export function AppLayout() {
  return (
    <div className="app-wrapper">
      <div className="theme-toggle-container">
        <ThemeToggle />
      </div>
      <div className="container">
        <Outlet />
      </div>
    </div>
  )
}
