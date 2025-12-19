// SPDX-License-Identifier: MIT
// Copyright (c) 2025 Copilot-for-Consensus contributors

import { useState } from 'react'
import { fetchUserRoles, UserRoleRecord } from '../api'
import { RoleManagementModal } from './RoleManagementModal'

export function UserRolesList() {
  const [userId, setUserId] = useState('')
  const [userRecord, setUserRecord] = useState<UserRoleRecord | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [showModal, setShowModal] = useState(false)
  const [modalAction, setModalAction] = useState<'assign' | 'revoke'>('assign')

  const handleSearch = async () => {
    if (!userId.trim()) {
      setError('Please enter a user ID')
      return
    }

    setLoading(true)
    setError(null)
    try {
      const record = await fetchUserRoles(userId.trim())
      setUserRecord(record)
    } catch (e: unknown) {
      const message = e instanceof Error ? e.message : 'Failed to fetch user roles'
      setError(message)
      setUserRecord(null)
    } finally {
      setLoading(false)
    }
  }

  const handleAssignRoles = () => {
    setModalAction('assign')
    setShowModal(true)
  }

  const handleRevokeRoles = () => {
    setModalAction('revoke')
    setShowModal(true)
  }

  const handleModalClose = (updated?: UserRoleRecord) => {
    setShowModal(false)
    if (updated) {
      setUserRecord(updated)
    }
  }

  return (
    <div>
      <div className="filters">
        <h2>Search User</h2>
        <div className="filter-row">
          <div className="filter-group">
            <label>User ID</label>
            <input
              type="text"
              value={userId}
              onChange={(e) => setUserId(e.target.value)}
              placeholder="Enter user ID"
              onKeyPress={(e) => e.key === 'Enter' && handleSearch()}
            />
          </div>
          <button onClick={handleSearch}>Search</button>
        </div>
      </div>

      {error && <div className="error-message">{error}</div>}

      {loading && <div className="no-reports">Loading…</div>}

      {userRecord && (
        <div className="user-record-card">
          <div className="user-record-header">
            <div>
              <h2>{userRecord.name || userRecord.user_id}</h2>
              <div className="user-metadata">
                <div className="metadata-item">
                  <strong>User ID:</strong> <span className="citation-id">{userRecord.user_id}</span>
                </div>
                {userRecord.email && (
                  <div className="metadata-item">
                    <strong>Email:</strong> {userRecord.email}
                  </div>
                )}
                <div className="metadata-item">
                  <strong>Status:</strong>{' '}
                  <span className={`badge ${userRecord.status === 'approved' ? 'enabled' : 'warning'}`}>
                    {userRecord.status}
                  </span>
                </div>
              </div>
            </div>
            <div className="user-actions">
              <button className="action-btn edit" onClick={handleAssignRoles}>
                ➕ Assign Roles
              </button>
              <button
                className="action-btn delete"
                onClick={handleRevokeRoles}
                disabled={userRecord.roles.length === 0}
              >
                ➖ Revoke Roles
              </button>
            </div>
          </div>

          <div className="user-roles-section">
            <h3>Current Roles</h3>
            {userRecord.roles.length === 0 ? (
              <p className="no-reports">No roles assigned</p>
            ) : (
              <div className="role-badges">
                {userRecord.roles.map((role) => (
                  <span key={role} className="badge role-badge">
                    {role}
                  </span>
                ))}
              </div>
            )}
          </div>

          {userRecord.updated_at && (
            <div className="timestamp user-record-timestamp">
              Last updated: {new Date(userRecord.updated_at).toLocaleString()}
            </div>
          )}
        </div>
      )}

      {showModal && userRecord && (
        <RoleManagementModal
          userId={userRecord.user_id}
          currentRoles={userRecord.roles}
          action={modalAction}
          onClose={handleModalClose}
        />
      )}
    </div>
  )
}
