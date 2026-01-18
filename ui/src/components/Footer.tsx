// SPDX-License-Identifier: MIT
// Copyright (c) 2025 Copilot-for-Consensus contributors

import React from 'react'

export function Footer() {
  const feedbackUrl = 'https://github.com/Alan-Jowett/CoPilot-For-Consensus/issues/new?template=feedback.md'

  return (
    <footer className="app-footer">
      <div className="footer-container">
        <div className="footer-content">
          <span className="footer-text">
            Copilot for Consensus - Open Source AI Assistant
          </span>
          <a
            href={feedbackUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="footer-link"
          >
            📝 Send Feedback
          </a>
        </div>
      </div>
    </footer>
  )
}
