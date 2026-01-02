// SPDX-License-Identifier: MIT
// Copyright (c) 2025 Copilot-for-Consensus contributors

import React from 'react'
import { useAuth } from '../contexts/AuthContext'
import styles from './AdminLinks.module.css'

/**
 * AdminLinks Component
 * 
 * Displays admin-only links and tools, visible only to users with admin role.
 * Includes link to Grafana for monitoring and observability (Docker Compose only).
 */
export function AdminLinks() {
  const { isAdmin } = useAuth()
  
  // Grafana is only available in Docker Compose deployments
  // For Azure deployments, this entire component is hidden
  const isGrafanaAvailable = process.env.REACT_APP_GRAFANA_ENABLED === 'true'
  
  if (!isAdmin || !isGrafanaAvailable) {
    return null
  }
  
  return (
    <div className={styles.adminPanel}>
      <div className={styles.label}>Admin Tools</div>
      <nav className={styles.navLinks}>
        <a
          href="/grafana/"
          target="_blank"
          rel="noopener noreferrer"
          className={styles.link}
          title="View monitoring dashboards, logs, and metrics"
        >
          📊 Grafana Dashboards
        </a>
      </nav>
    </div>
  )
}
