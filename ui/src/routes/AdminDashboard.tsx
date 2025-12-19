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

      <div className="admin-tabs" role="tablist" aria-label="Admin management tabs">
        <button
          role="tab"
          aria-selected={activeTab === 'users'}
          aria-controls="users-tabpanel"
          id="users-tab"
          className={`admin-tab ${activeTab === 'users' ? 'active' : ''}`}
          onClick={() => setActiveTab('users')}
        >
          👥 User Roles
        </button>
        <button
          role="tab"
          aria-selected={activeTab === 'pending'}
          aria-controls="pending-tabpanel"
          id="pending-tab"
          className={`admin-tab ${activeTab === 'pending' ? 'active' : ''}`}
          onClick={() => setActiveTab('pending')}
        >
          ⏳ Pending Assignments
        </button>
      </div>

      <div
        id="users-tabpanel"
        role="tabpanel"
        aria-labelledby="users-tab"
        className="admin-content"
        hidden={activeTab !== 'users'}
      >
        {activeTab === 'users' && <UserRolesList />}
      </div>
      <div
        id="pending-tabpanel"
        role="tabpanel"
        aria-labelledby="pending-tab"
        className="admin-content"
        hidden={activeTab !== 'pending'}
      >
        {activeTab === 'pending' && <PendingAssignments />}
      </div>
    </div>
  )
}
