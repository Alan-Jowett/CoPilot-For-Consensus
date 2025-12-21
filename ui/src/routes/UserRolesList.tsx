// SPDX-License-Identifier: MIT
// Copyright (c) 2025 Copilot-for-Consensus contributors

import { useState } from 'react'
import { searchUsers, UserRoleRecord } from '../api'
import { RoleManagementModal } from './RoleManagementModal'

export function UserRolesList() {
  const [searchTerm, setSearchTerm] = useState('')
  const [searchBy, setSearchBy] = useState<'user_id' | 'email' | 'name'>('email')
  const [userRecord, setUserRecord] = useState<UserRoleRecord | null>(null)
  const [searchResults, setSearchResults] = useState<UserRoleRecord[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [showModal, setShowModal] = useState(false)
  const [modalAction, setModalAction] = useState<'assign' | 'revoke'>('assign')

  const handleSearch = async () => {
    if (!searchTerm.trim()) {
      setError(`Please enter a ${searchBy.replace('_', ' ')}`)
      return
    }

    setLoading(true)
    setError(null)
    setSearchResults([])
    setUserRecord(null)
    try {
      const response = await searchUsers(searchTerm.trim(), searchBy)
      if (response.users.length === 0) {
        setError(`No users found matching "${searchTerm}"`)
      } else if (response.users.length === 1) {
        // If exactly one result, show it directly
        setUserRecord(response.users[0])
      } else {
        // Multiple results, show list to choose from
        setSearchResults(response.users)
      }
    } catch (e: unknown) {
      const message = e instanceof Error ? e.message : 'Failed to search users'
      setError(message)
      setUserRecord(null)
      setSearchResults([])
    } finally {
      setLoading(false)
    }
  }

  const handleSelectUser = (user: UserRoleRecord) => {
    setUserRecord(user)
    setSearchResults([])
  }

  // Handle keyboard navigation for search results
  const handleResultKeyDown = (e: React.KeyboardEvent, user: UserRoleRecord) => {
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault()
      handleSelectUser(user)
    }
  }

  // Helper function to get label for search field
  const getSearchFieldLabel = () => {
    switch (searchBy) {
      case 'user_id':
        return 'User ID'
      case 'email':
        return 'Email'
      case 'name':
        return 'Name'
      default:
        return 'Search Term'
    }
  }

  // Helper function to get user display name
  const getUserDisplayName = (user: UserRoleRecord) => {
    return user.name?.trim() || user.user_id
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
            <label htmlFor="search-by">Search By</label>
            <select
              id="search-by"
              value={searchBy}
              onChange={(e) => setSearchBy(e.target.value as 'user_id' | 'email' | 'name')}
            >
              <option value="email">Email</option>
              <option value="name">Name</option>
              <option value="user_id">User ID</option>
            </select>
          </div>
          <div className="filter-group">
            <label htmlFor="search-term">
              {getSearchFieldLabel()}
            </label>
            <input
              id="search-term"
              type="text"
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              placeholder={`Enter ${searchBy.replace('_', ' ')}`}
              onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
            />
          </div>
          <button onClick={handleSearch}>Search</button>
        </div>
      </div>

      {error && <div className="error-message">{error}</div>}

      {loading && <div className="no-reports">Loading…</div>}

      {/* Show search results list only when multiple users match (single results are shown directly in userRecord below) */}
      {searchResults.length > 1 && (
        <div className="search-results">
          <h3>Search Results ({searchResults.length} users found)</h3>
          <div className="user-results-list">
            {searchResults.map((user) => (
              <div
                key={user.user_id}
                className="user-result-item"
                onClick={() => handleSelectUser(user)}
                onKeyDown={(e) => handleResultKeyDown(e, user)}
                role="button"
                tabIndex={0}
                aria-label={`Select user ${getUserDisplayName(user)}`}
              >
                <div>
                  <strong>{getUserDisplayName(user)}</strong>
                </div>
                {user.email && <div className="user-metadata">{user.email}</div>}
                <div className="user-metadata">
                  <span className="citation-id">{user.user_id}</span>
                  {' • '}
                  <span className={`badge ${user.status === 'approved' ? 'enabled' : 'warning'}`}>
                    {user.status}
                  </span>
                  {user.roles.length > 0 && (
                    <>
                      {' • '}
                      Roles: {user.roles.join(', ')}
                    </>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {userRecord && (
        <div className="user-record-card">
          <div className="user-record-header">
            <div>
              <h2>{getUserDisplayName(userRecord)}</h2>
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
