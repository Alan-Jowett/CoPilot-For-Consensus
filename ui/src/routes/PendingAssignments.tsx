// SPDX-License-Identifier: MIT
// Copyright (c) 2025 Copilot-for-Consensus contributors

import { useEffect, useState, useCallback } from 'react'
import { fetchPendingRoleAssignments, PendingRoleAssignment, assignUserRoles, denyRoleAssignment } from '../api'

export function PendingAssignments() {
  const [assignments, setAssignments] = useState<PendingRoleAssignment[]>([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [processingIds, setProcessingIds] = useState<Set<string>>(new Set())
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set())
  const [successMessage, setSuccessMessage] = useState<string | null>(null)
  const [filters, setFilters] = useState({
    user_id: '',
    role: '',
    skip: 0,
    limit: 20,
  })

  const loadAssignments = useCallback(async () => {
    setLoading(true)
    setError(null)
    setSuccessMessage(null)
    try {
      const data = await fetchPendingRoleAssignments(filters)
      setAssignments(Array.isArray(data.assignments) ? data.assignments : [])
      setTotal(data.total)
      // Clear selection when data changes
      setSelectedIds(new Set())
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

  const handleApprove = async (assignment: PendingRoleAssignment) => {
    setProcessingIds((prev) => new Set(prev).add(assignment.user_id))
    setError(null)
    setSuccessMessage(null)
    try {
      await assignUserRoles(assignment.user_id, assignment.requested_roles)
      setSuccessMessage(`Approved role assignment for ${assignment.user_id}`)
      // Reload assignments
      await loadAssignments()
    } catch (e: unknown) {
      const message = e instanceof Error ? e.message : 'Failed to approve role assignment'
      setError(message)
    } finally {
      setProcessingIds((prev) => {
        const next = new Set(prev)
        next.delete(assignment.user_id)
        return next
      })
    }
  }

  const handleReject = async (assignment: PendingRoleAssignment) => {
    setProcessingIds((prev) => new Set(prev).add(assignment.user_id))
    setError(null)
    setSuccessMessage(null)
    try {
      await denyRoleAssignment(assignment.user_id)
      setSuccessMessage(`Rejected role assignment for ${assignment.user_id}`)
      // Reload assignments
      await loadAssignments()
    } catch (e: unknown) {
      const message = e instanceof Error ? e.message : 'Failed to reject role assignment'
      setError(message)
    } finally {
      setProcessingIds((prev) => {
        const next = new Set(prev)
        next.delete(assignment.user_id)
        return next
      })
    }
  }

  const handleToggleSelect = (userId: string) => {
    setSelectedIds((prev) => {
      const next = new Set(prev)
      if (next.has(userId)) {
        next.delete(userId)
      } else {
        next.add(userId)
      }
      return next
    })
  }

  const handleSelectAll = () => {
    if (selectedIds.size === assignments.length) {
      setSelectedIds(new Set())
    } else {
      setSelectedIds(new Set(assignments.map((a) => a.user_id)))
    }
  }

  const handleBulkApprove = async () => {
    if (selectedIds.size === 0) return

    setError(null)
    setSuccessMessage(null)
    const selectedAssignments = assignments.filter((a) => selectedIds.has(a.user_id))
    let successCount = 0
    const failures: Array<{ userId: string; error: string }> = []

    for (const assignment of selectedAssignments) {
      setProcessingIds((prev) => new Set(prev).add(assignment.user_id))
      try {
        await assignUserRoles(assignment.user_id, assignment.requested_roles)
        successCount++
      } catch (e: unknown) {
        const errorMsg = e instanceof Error ? e.message : 'Unknown error'
        failures.push({ userId: assignment.user_id, error: errorMsg })
      }
      setProcessingIds((prev) => {
        const next = new Set(prev)
        next.delete(assignment.user_id)
        return next
      })
    }

    if (successCount > 0) {
      setSuccessMessage(`Approved ${successCount} role assignment${successCount > 1 ? 's' : ''}`)
    }
    if (failures.length > 0) {
      const failureDetails = failures.map((f) => `${f.userId}: ${f.error}`).join('; ')
      setError(`Failed to approve ${failures.length} assignment${failures.length > 1 ? 's' : ''}: ${failureDetails}`)
    }

    // Reload assignments
    await loadAssignments()
  }

  const handleBulkReject = async () => {
    if (selectedIds.size === 0) return

    setError(null)
    setSuccessMessage(null)
    const selectedAssignments = assignments.filter((a) => selectedIds.has(a.user_id))
    let successCount = 0
    const failures: Array<{ userId: string; error: string }> = []

    for (const assignment of selectedAssignments) {
      setProcessingIds((prev) => new Set(prev).add(assignment.user_id))
      try {
        await denyRoleAssignment(assignment.user_id)
        successCount++
      } catch (e: unknown) {
        const errorMsg = e instanceof Error ? e.message : 'Unknown error'
        failures.push({ userId: assignment.user_id, error: errorMsg })
      }
      setProcessingIds((prev) => {
        const next = new Set(prev)
        next.delete(assignment.user_id)
        return next
      })
    }

    if (successCount > 0) {
      setSuccessMessage(`Rejected ${successCount} role assignment${successCount > 1 ? 's' : ''}`)
    }
    if (failures.length > 0) {
      const failureDetails = failures.map((f) => `${f.userId}: ${f.error}`).join('; ')
      setError(`Failed to reject ${failures.length} assignment${failures.length > 1 ? 's' : ''}: ${failureDetails}`)
    }

    // Reload assignments
    await loadAssignments()
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
      {successMessage && <div className="success-message">{successMessage}</div>}

      <div className="reports-table">
        {loading ? (
          <div className="no-reports">Loading…</div>
        ) : assignments.length === 0 ? (
          <div className="no-reports">
            <p>No pending role assignments found.</p>
          </div>
        ) : (
          <>
            {/* Bulk actions bar */}
            {selectedIds.size > 0 && (
              <div className="bulk-actions-bar">
                <div>
                  <strong>{selectedIds.size}</strong> selected
                </div>
                <div className="button-group">
                  <button
                    className="action-btn edit"
                    onClick={handleBulkApprove}
                    disabled={processingIds.size > 0}
                  >
                    ✓ Approve Selected
                  </button>
                  <button
                    className="action-btn delete"
                    onClick={handleBulkReject}
                    disabled={processingIds.size > 0}
                  >
                    ✕ Reject Selected
                  </button>
                </div>
              </div>
            )}

            <table>
              <thead>
                <tr>
                  <th>
                    <input
                      type="checkbox"
                      checked={selectedIds.size === assignments.length && assignments.length > 0}
                      onChange={handleSelectAll}
                      aria-label="Select all assignments"
                    />
                  </th>
                  <th>User ID</th>
                  <th>Email</th>
                  <th>Name</th>
                  <th>Requested Roles</th>
                  <th>Requested At</th>
                  <th>Status</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {assignments.map((assignment, idx) => {
                  const isProcessing = processingIds.has(assignment.user_id)
                  const isSelected = selectedIds.has(assignment.user_id)
                  return (
                    <tr key={`${assignment.user_id}-${idx}`}>
                      <td>
                        <input
                          type="checkbox"
                          checked={isSelected}
                          onChange={() => handleToggleSelect(assignment.user_id)}
                          disabled={isProcessing}
                          aria-label={`Select ${assignment.user_id}`}
                        />
                      </td>
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
                      <td>
                        <div className="action-buttons">
                          <button
                            className="action-btn edit small"
                            onClick={() => handleApprove(assignment)}
                            disabled={isProcessing}
                            aria-label={`Approve ${assignment.user_id}`}
                            title="Approve and assign roles"
                          >
                            {isProcessing ? '⏳' : '✓'}
                          </button>
                          <button
                            className="action-btn delete small"
                            onClick={() => handleReject(assignment)}
                            disabled={isProcessing}
                            aria-label={`Reject ${assignment.user_id}`}
                            title="Reject role assignment"
                          >
                            {isProcessing ? '⏳' : '✕'}
                          </button>
                        </div>
                      </td>
                    </tr>
                  )
                })}
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
