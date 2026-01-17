// SPDX-License-Identifier: MIT
// Copyright (c) 2025 Copilot-for-Consensus contributors

import { useEffect, useState, useCallback } from 'react'
import { fetchPendingRoleAssignments, PendingRoleAssignment } from '../api'

export function PendingAssignments() {
  const [assignments, setAssignments] = useState<PendingRoleAssignment[]>([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [filters, setFilters] = useState({
    user_id: '',
    role: '',
    skip: 0,
    limit: 20,
  })

  const loadAssignments = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const data = await fetchPendingRoleAssignments(filters)
      setAssignments(Array.isArray(data.assignments) ? data.assignments : [])
      setTotal(data.total)
    } catch (e: unknown) {
      const message = e instanceof Error ? e.message : 'Failed to load pending assignments'
      setError(message)
    } finally {
      setLoading(false)
    }
  }, [filters])

  useEffect(() => {
    loadAssignments()
  }, [loadAssignments])

  const handleFilterChange = (field: string, value: string) => {
    setFilters((prev) => ({ ...prev, [field]: value, skip: 0 }))
  }

  const handleApplyFilters = () => {
    loadAssignments()
  }

  const handleClearFilters = () => {
    setFilters({ user_id: '', role: '', skip: 0, limit: 20 })
  }

  const handleNextPage = () => {
    setFilters((prev) => ({ ...prev, skip: prev.skip + prev.limit }))
  }

  const handlePrevPage = () => {
    setFilters((prev) => ({ ...prev, skip: Math.max(0, prev.skip - prev.limit) }))
  }

  return (
    <div>
      <div className="filters">
        <h2>Filters</h2>
        <div className="filter-row">
          <div className="filter-group">
            <label htmlFor="filter-user-id">User ID</label>
            <input
              id="filter-user-id"
              type="text"
              value={filters.user_id}
              onChange={(e) => handleFilterChange('user_id', e.target.value)}
              placeholder="Filter by user ID"
            />
          </div>
          <div className="filter-group">
            <label htmlFor="filter-role">Role</label>
            <input
              id="filter-role"
              type="text"
              value={filters.role}
              onChange={(e) => handleFilterChange('role', e.target.value)}
              placeholder="Filter by role"
            />
          </div>
        </div>
        <div className="button-group">
          <button onClick={handleApplyFilters}>Apply Filters</button>
          <button className="clear-btn" onClick={handleClearFilters}>
            Clear Filters
          </button>
        </div>
      </div>

      {error && <div className="error-message">{error}</div>}

      <div className="reports-table">
        {loading ? (
          <div className="no-reports">Loading…</div>
        ) : assignments.length === 0 ? (
          <div className="no-reports">
            <p>No pending role assignments found.</p>
          </div>
        ) : (
          <>
            <table>
              <thead>
                <tr>
                  <th>User ID</th>
                  <th>Email</th>
                  <th>Name</th>
                  <th>Requested Roles</th>
                  <th>Requested At</th>
                  <th>Status</th>
                </tr>
              </thead>
              <tbody>
                {assignments.map((assignment, idx) => (
                  <tr key={`${assignment.user_id}-${idx}`}>
                    <td>
                      <span className="citation-id">{assignment.user_id}</span>
                    </td>
                    <td>{assignment.user_email || 'N/A'}</td>
                    <td>{assignment.user_name || 'N/A'}</td>
                    <td>
                      <div className="role-badges">
                        {(assignment.requested_roles ?? []).map((role) => (
                          <span key={role} className="badge">
                            {role}
                          </span>
                        ))}
                      </div>
                    </td>
                    <td>
                      <span className="timestamp">
                        {new Date(assignment.requested_at).toLocaleString()}
                      </span>
                    </td>
                    <td>
                      <span className={`badge ${assignment.status === 'pending' ? 'warning' : ''}`}>
                        {assignment.status}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>

            <div className="pagination">
              <div>
                Showing {filters.skip + 1} - {Math.min(filters.skip + filters.limit, total)} of{' '}
                {total}
              </div>
              <div>
                <button onClick={handlePrevPage} disabled={filters.skip === 0}>
                  Previous
                </button>
                <button onClick={handleNextPage} disabled={filters.skip + filters.limit >= total}>
                  Next
                </button>
              </div>
            </div>
          </>
        )}
      </div>
    </div>
  )
}
