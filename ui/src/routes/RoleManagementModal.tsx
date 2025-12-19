// SPDX-License-Identifier: MIT
// Copyright (c) 2025 Copilot-for-Consensus contributors

import { useState } from 'react'
import { assignUserRoles, revokeUserRoles, UserRoleRecord } from '../api'

interface RoleManagementModalProps {
  userId: string
  currentRoles: string[]
  action: 'assign' | 'revoke'
  onClose: (updated?: UserRoleRecord) => void
}

const AVAILABLE_ROLES = ['admin', 'contributor', 'viewer', 'moderator']

export function RoleManagementModal({ userId, currentRoles, action, onClose }: RoleManagementModalProps) {
  const [selectedRoles, setSelectedRoles] = useState<string[]>([])
  const [customRole, setCustomRole] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const availableForAction = action === 'assign'
    ? AVAILABLE_ROLES.filter((role) => !currentRoles.includes(role))
    : currentRoles

  const handleRoleToggle = (role: string) => {
    setSelectedRoles((prev) =>
      prev.includes(role) ? prev.filter((r) => r !== role) : [...prev, role]
    )
  }

  const handleAddCustomRole = () => {
    const trimmed = customRole.trim()
    if (trimmed && !selectedRoles.includes(trimmed)) {
      setSelectedRoles((prev) => [...prev, trimmed])
      setCustomRole('')
    }
  }

  const handleSubmit = async () => {
    if (selectedRoles.length === 0) {
      setError('Please select at least one role')
      return
    }

    setLoading(true)
    setError(null)

    try {
      let updated: UserRoleRecord
      if (action === 'assign') {
        updated = await assignUserRoles(userId, selectedRoles)
      } else {
        updated = await revokeUserRoles(userId, selectedRoles)
      }
      onClose(updated)
    } catch (e: unknown) {
      const message = e instanceof Error ? e.message : `Failed to ${action} roles`
      setError(message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="modal-overlay" onClick={() => onClose()}>
      <div className="modal-content" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <h2>{action === 'assign' ? '➕ Assign Roles' : '➖ Revoke Roles'}</h2>
          <button className="modal-close" onClick={() => onClose()}>
            ✕
          </button>
        </div>

        <div className="modal-body">
          <p className="modal-description">
            {action === 'assign'
              ? `Select roles to assign to user ${userId}`
              : `Select roles to revoke from user ${userId}`}
          </p>

          {error && <div className="error-message">{error}</div>}

          <div className="role-selection">
            <h3>Available Roles</h3>
            {availableForAction.length === 0 ? (
              <p className="no-reports">
                {action === 'assign'
                  ? 'All standard roles are already assigned'
                  : 'No roles to revoke'}
              </p>
            ) : (
              <div className="role-checkboxes">
                {availableForAction.map((role) => (
                  <label key={role} className="checkbox-label">
                    <input
                      type="checkbox"
                      checked={selectedRoles.includes(role)}
                      onChange={() => handleRoleToggle(role)}
                    />
                    <span className="badge role-badge">{role}</span>
                  </label>
                ))}
              </div>
            )}
          </div>

          {action === 'assign' && (
            <div className="custom-role-input">
              <h3>Add Custom Role</h3>
              <div className="filter-row">
                <div className="filter-group" style={{ flex: 1 }}>
                  <input
                    type="text"
                    value={customRole}
                    onChange={(e) => setCustomRole(e.target.value)}
                    placeholder="Enter custom role name"
                    onKeyPress={(e) => e.key === 'Enter' && handleAddCustomRole()}
                  />
                </div>
                <button onClick={handleAddCustomRole} disabled={!customRole.trim()}>
                  Add
                </button>
              </div>
            </div>
          )}

          {selectedRoles.length > 0 && (
            <div className="selected-roles">
              <h3>Selected Roles ({selectedRoles.length})</h3>
              <div className="role-badges">
                {selectedRoles.map((role) => (
                  <span key={role} className="badge role-badge">
                    {role}
                    <span
                      className="remove-role"
                      onClick={() => handleRoleToggle(role)}
                      title="Remove"
                    >
                      ✕
                    </span>
                  </span>
                ))}
              </div>
            </div>
          )}
        </div>

        <div className="modal-footer">
          <button onClick={() => onClose()} className="cancel-btn">
            Cancel
          </button>
          <button
            onClick={handleSubmit}
            disabled={loading || selectedRoles.length === 0}
            className={action === 'assign' ? 'action-btn edit' : 'action-btn delete'}
          >
            {loading ? 'Processing…' : action === 'assign' ? 'Assign Roles' : 'Revoke Roles'}
          </button>
        </div>
      </div>
    </div>
  )
}
