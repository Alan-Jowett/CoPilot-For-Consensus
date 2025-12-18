// SPDX-License-Identifier: MIT
// Copyright (c) 2025 Copilot-for-Consensus contributors

import { Outlet } from 'react-router-dom'

export function AppLayout() {
  return (
    <div className="container">
      <Outlet />
    </div>
  )
}
