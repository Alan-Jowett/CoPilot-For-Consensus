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
  const isGrafanaAvailable = import.meta.env.VITE_GRAFANA_ENABLED === 'true'
  // Allow overriding the Grafana URL to force HTTPS (e.g., https://localhost/grafana/).
  // Default: if running on localhost, always prefer HTTPS on the gateway; otherwise, keep current origin.
  const defaultGrafanaUrl = typeof window !== 'undefined'
    ? (window.location.hostname === 'localhost'
        ? 'https://localhost/grafana/'
        : `${window.location.origin}/grafana/`)
    : '/grafana/'
  const grafanaUrl = import.meta.env.VITE_GRAFANA_URL || defaultGrafanaUrl
  
  if (!isAdmin || !isGrafanaAvailable) {
    return null
  }
  
  return (
    <div className={styles.adminPanel}>
      <div className={styles.label}>Admin Tools</div>
      <nav className={styles.navLinks}>
        <a
          href={grafanaUrl}
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
