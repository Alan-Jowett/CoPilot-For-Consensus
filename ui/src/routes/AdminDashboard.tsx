// SPDX-License-Identifier: MIT
// Copyright (c) 2025 Copilot-for-Consensus contributors

import { useState } from 'react'
import { PendingAssignments } from './PendingAssignments'
import { UserRolesList } from './UserRolesList'

export function AdminDashboard() {
  const [activeTab, setActiveTab] = useState<'users' | 'pending'>('users')

  return (
    <div>
      <div className="page-header">
        <div>
          <h1>🔐 Admin Dashboard</h1>
          <p className="subtitle">Manage user roles and permissions</p>
        </div>
      </div>

      <div className="admin-tabs">
        <button
          className={`admin-tab ${activeTab === 'users' ? 'active' : ''}`}
          onClick={() => setActiveTab('users')}
        >
          👥 User Roles
        </button>
        <button
          className={`admin-tab ${activeTab === 'pending' ? 'active' : ''}`}
          onClick={() => setActiveTab('pending')}
        >
          ⏳ Pending Assignments
        </button>
      </div>

      <div className="admin-content">
        {activeTab === 'users' && <UserRolesList />}
        {activeTab === 'pending' && <PendingAssignments />}
      </div>
    </div>
  )
}
