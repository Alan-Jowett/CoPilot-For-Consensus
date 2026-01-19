// SPDX-License-Identifier: MIT
// Copyright (c) 2025 Copilot-for-Consensus contributors

import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { AdminDashboard } from './AdminDashboard'

// Mock the child components
vi.mock('./PendingAssignments', () => ({
  PendingAssignments: () => <div data-testid="pending-assignments">Pending Assignments Component</div>,
}))

vi.mock('./UserRolesList', () => ({
  UserRolesList: () => <div data-testid="user-roles-list">User Roles List Component</div>,
}))

describe('AdminDashboard', () => {
  it('renders admin dashboard with title', () => {
    render(<AdminDashboard />)
    
    expect(screen.getByText('🔐 Admin Dashboard')).toBeInTheDocument()
    expect(screen.getByText('Manage user roles and permissions')).toBeInTheDocument()
  })

  it('renders tab buttons', () => {
    render(<AdminDashboard />)
    
    expect(screen.getByRole('tab', { name: /User Roles/i })).toBeInTheDocument()
    expect(screen.getByRole('tab', { name: /Pending Assignments/i })).toBeInTheDocument()
  })

  it('defaults to users tab', () => {
    render(<AdminDashboard />)
    
    const usersTab = screen.getByRole('tab', { name: /User Roles/i })
    expect(usersTab).toHaveClass('active')
    expect(usersTab).toHaveAttribute('aria-selected', 'true')
    
    expect(screen.getByTestId('user-roles-list')).toBeInTheDocument()
    expect(screen.queryByTestId('pending-assignments')).not.toBeInTheDocument()
  })

  it('switches to pending assignments tab', async () => {
    const user = userEvent.setup()
    render(<AdminDashboard />)
    
    const pendingTab = screen.getByRole('tab', { name: /Pending Assignments/i })
    await user.click(pendingTab)
    
    expect(pendingTab).toHaveClass('active')
    expect(pendingTab).toHaveAttribute('aria-selected', 'true')
    
    expect(screen.getByTestId('pending-assignments')).toBeInTheDocument()
    expect(screen.queryByTestId('user-roles-list')).not.toBeInTheDocument()
  })

  it('switches back to users tab', async () => {
    const user = userEvent.setup()
    render(<AdminDashboard />)
    
    // Switch to pending
    await user.click(screen.getByRole('tab', { name: /Pending Assignments/i }))
    expect(screen.getByTestId('pending-assignments')).toBeInTheDocument()
    
    // Switch back to users
    await user.click(screen.getByRole('tab', { name: /User Roles/i }))
    expect(screen.getByTestId('user-roles-list')).toBeInTheDocument()
    expect(screen.queryByTestId('pending-assignments')).not.toBeInTheDocument()
  })

  it('has proper ARIA attributes for accessibility', () => {
    render(<AdminDashboard />)
    
    const usersTab = screen.getByRole('tab', { name: /User Roles/i })
    const pendingTab = screen.getByRole('tab', { name: /Pending Assignments/i })
    
    expect(usersTab).toHaveAttribute('id', 'users-tab')
    expect(usersTab).toHaveAttribute('aria-controls', 'users-tabpanel')
    
    expect(pendingTab).toHaveAttribute('id', 'pending-tab')
    expect(pendingTab).toHaveAttribute('aria-controls', 'pending-tabpanel')
    
    const tablist = screen.getByRole('tablist')
    expect(tablist).toHaveAttribute('aria-label', 'Admin management tabs')
  })
})
