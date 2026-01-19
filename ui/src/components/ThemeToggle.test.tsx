// SPDX-License-Identifier: MIT
// Copyright (c) 2025 Copilot-for-Consensus contributors

import { describe, it, expect, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { ThemeToggle } from './ThemeToggle'
import { ThemeProvider } from '../contexts/ThemeContext'

describe('ThemeToggle', () => {
  beforeEach(() => {
    // Reset localStorage to ensure light theme by default
    localStorage.clear()
    // Reset document attributes
    document.documentElement.removeAttribute('data-theme')
    document.documentElement.style.colorScheme = ''
  })

  it('renders theme toggle button', () => {
    render(
      <ThemeProvider>
        <ThemeToggle />
      </ThemeProvider>
    )

    const button = screen.getByRole('button')
    expect(button).toBeInTheDocument()
    expect(button).toHaveClass('theme-toggle')
  })

  it('shows correct icon and label for light theme', () => {
    render(
      <ThemeProvider>
        <ThemeToggle />
      </ThemeProvider>
    )

    const button = screen.getByRole('button')
    expect(button).toHaveAttribute('aria-label', 'Switch to dark mode')
    expect(button).toHaveAttribute('title', 'Switch to dark mode')
    
    // Moon icon should be present (switch to dark mode)
    const svg = button.querySelector('svg')
    expect(svg).toBeInTheDocument()
  })

  it('toggles theme when clicked', async () => {
    const user = userEvent.setup()

    render(
      <ThemeProvider>
        <ThemeToggle />
      </ThemeProvider>
    )

    const button = screen.getByRole('button')
    
    // Initially light mode - shows moon icon (switch to dark)
    expect(button).toHaveAttribute('aria-label', 'Switch to dark mode')
    
    // Click to toggle to dark mode
    await user.click(button)
    
    // Now dark mode - shows sun icon (switch to light)
    expect(button).toHaveAttribute('aria-label', 'Switch to light mode')
    expect(button).toHaveAttribute('title', 'Switch to light mode')
  })

  it('toggles multiple times', async () => {
    const user = userEvent.setup()

    render(
      <ThemeProvider>
        <ThemeToggle />
      </ThemeProvider>
    )

    const button = screen.getByRole('button')
    
    // Initially light mode - shows moon icon (switch to dark)
    expect(button).toHaveAttribute('aria-label', 'Switch to dark mode')
    
    // Light -> Dark
    await user.click(button)
    expect(button).toHaveAttribute('aria-label', 'Switch to light mode')
    
    // Dark -> Light
    await user.click(button)
    expect(button).toHaveAttribute('aria-label', 'Switch to dark mode')
    
    // Light -> Dark
    await user.click(button)
    expect(button).toHaveAttribute('aria-label', 'Switch to light mode')
  })

  it('has accessible attributes', () => {
    render(
      <ThemeProvider>
        <ThemeToggle />
      </ThemeProvider>
    )

    const button = screen.getByRole('button')
    expect(button).toHaveAttribute('aria-label')
    expect(button).toHaveAttribute('title')
  })
})
