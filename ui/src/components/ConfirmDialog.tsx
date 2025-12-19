// SPDX-License-Identifier: MIT
// Copyright (c) 2025 Copilot-for-Consensus contributors

import { useEffect, useRef, MouseEvent } from 'react'

interface ConfirmDialogProps {
  isOpen: boolean
  title: string
  message: string
  onConfirm: () => void
  onCancel: () => void
  confirmText?: string
  cancelText?: string
  confirmButtonClass?: string
}

/**
 * Reusable confirmation dialog component.
 *
 * Provides an accessible modal dialog for confirming destructive actions.
 * Features:
 * - Keyboard navigation (Escape to cancel, Tab/Shift+Tab to cycle between buttons)
 * - Focus trap (prevents tabbing out of modal)
 * - Focus management (focuses cancel button on open for safety)
 * - Screen reader support (ARIA attributes)
 * - Matches application design system
 * - Backdrop click to cancel
 */
export function ConfirmDialog({
  isOpen,
  title,
  message,
  onConfirm,
  onCancel,
  confirmText = 'Confirm',
  cancelText = 'Cancel',
  confirmButtonClass = 'delete',
}: ConfirmDialogProps) {
  const dialogRef = useRef<HTMLDivElement>(null)
  const cancelButtonRef = useRef<HTMLButtonElement>(null)
  const confirmButtonRef = useRef<HTMLButtonElement>(null)

  // Handle keyboard events
  useEffect(() => {
    if (!isOpen) return

    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        onCancel()
      } else if (e.key === 'Tab') {
        // Focus trap: cycle between cancel and confirm buttons
        e.preventDefault()
        const activeElement = document.activeElement
        
        if (e.shiftKey) {
          // Shift+Tab: reverse direction
          if (activeElement === cancelButtonRef.current) {
            confirmButtonRef.current?.focus()
          } else {
            cancelButtonRef.current?.focus()
          }
        } else {
          // Tab: forward direction
          if (activeElement === confirmButtonRef.current) {
            cancelButtonRef.current?.focus()
          } else {
            confirmButtonRef.current?.focus()
          }
        }
      }
    }

    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [isOpen, onCancel])

  // Focus management - focus the cancel button when modal opens for safety
  // This prevents accidental confirmations of destructive actions
  useEffect(() => {
    if (isOpen && cancelButtonRef.current) {
      cancelButtonRef.current.focus()
    }
  }, [isOpen])

  // Handle backdrop click
  const handleBackdropClick = (e: MouseEvent<HTMLDivElement>) => {
    if (e.target === e.currentTarget) {
      onCancel()
    }
  }

  if (!isOpen) return null

  return (
    <div
      className="modal-overlay"
      onClick={handleBackdropClick}
    >
      <div
        className="modal-content"
        ref={dialogRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby="confirm-dialog-title"
        aria-describedby="confirm-dialog-message"
      >
        <h2 id="confirm-dialog-title" className="modal-title">
          {title}
        </h2>
        <p id="confirm-dialog-message" className="modal-message">
          {message}
        </p>
        <div className="modal-actions">
          <button
            type="button"
            className="modal-btn cancel-btn"
            onClick={onCancel}
            ref={cancelButtonRef}
          >
            {cancelText}
          </button>
          <button
            type="button"
            className={`modal-btn ${confirmButtonClass}`}
            onClick={onConfirm}
            ref={confirmButtonRef}
          >
            {confirmText}
          </button>
        </div>
      </div>
    </div>
  )
}
