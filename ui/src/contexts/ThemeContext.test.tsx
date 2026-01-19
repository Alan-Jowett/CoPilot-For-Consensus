// SPDX-License-Identifier: MIT
// Copyright (c) 2025 Copilot-for-Consensus contributors

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { ThemeProvider, useTheme } from './ThemeContext'

describe('ThemeContext', () => {
  let localStorageMock: { [key: string]: string }

  beforeEach(() => {
    localStorageMock = {}
    
    // Mock localStorage
    global.Storage.prototype.getItem = vi.fn((key: string) => localStorageMock[key] || null)
    global.Storage.prototype.setItem = vi.fn((key: string, value: string) => {
      localStorageMock[key] = value
    })
    global.Storage.prototype.removeItem = vi.fn((key: string) => {
      delete localStorageMock[key]
    })
    global.Storage.prototype.clear = vi.fn(() => {
      localStorageMock = {}
    })

    // Reset document attributes
    document.documentElement.removeAttribute('data-theme')
    document.documentElement.style.colorScheme = ''
    
    // Reset matchMedia to default (light theme)
    Object.defineProperty(window, 'matchMedia', {
      writable: true,
      value: vi.fn().mockImplementation(query => ({
        matches: false, // Default to not matching dark mode
        media: query,
        onchange: null,
        addListener: vi.fn(),
        removeListener: vi.fn(),
        addEventListener: vi.fn(),
        removeEventListener: vi.fn(),
        dispatchEvent: vi.fn(),
      })),
    })
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  function TestComponent() {
    const { theme, toggleTheme } = useTheme()
    return (
      <div>
        <div data-testid="theme">{theme}</div>
        <button onClick={toggleTheme}>Toggle</button>
      </div>
    )
  }

  describe('ThemeProvider', () => {
    it('defaults to light theme', () => {
      render(
        <ThemeProvider>
          <TestComponent />
        </ThemeProvider>
      )

      expect(screen.getByTestId('theme')).toHaveTextContent('light')
    })

    it('restores theme from localStorage', () => {
      localStorageMock['theme'] = 'dark'

      render(
        <ThemeProvider>
          <TestComponent />
        </ThemeProvider>
      )

      expect(screen.getByTestId('theme')).toHaveTextContent('dark')
    })

    it('toggles theme', async () => {
      const user = userEvent.setup()

      render(
        <ThemeProvider>
          <TestComponent />
        </ThemeProvider>
      )

      expect(screen.getByTestId('theme')).toHaveTextContent('light')

      await user.click(screen.getByText('Toggle'))

      expect(screen.getByTestId('theme')).toHaveTextContent('dark')

      await user.click(screen.getByText('Toggle'))

      expect(screen.getByTestId('theme')).toHaveTextContent('light')
    })

    it('saves theme to localStorage', async () => {
      const user = userEvent.setup()
      
      render(
        <ThemeProvider>
          <TestComponent />
        </ThemeProvider>
      )

      // Wait for initial render to complete
      await waitFor(() => {
        expect(screen.getByTestId('theme')).toHaveTextContent('light')
      })

      // Initial theme should be saved
      expect(localStorageMock['theme']).toBe('light')

      // Toggle theme
      await user.click(screen.getByText('Toggle'))

      await waitFor(() => {
        expect(screen.getByTestId('theme')).toHaveTextContent('dark')
        expect(localStorageMock['theme']).toBe('dark')
      })
    })

    it('applies theme to document', async () => {
      const user = userEvent.setup()

      render(
        <ThemeProvider>
          <TestComponent />
        </ThemeProvider>
      )

      // Initial theme
      await waitFor(() => {
        expect(document.documentElement.getAttribute('data-theme')).toBe('light')
        expect(document.documentElement.style.colorScheme).toBe('light')
      })

      // Toggle to dark
      await user.click(screen.getByText('Toggle'))

      await waitFor(() => {
        expect(document.documentElement.getAttribute('data-theme')).toBe('dark')
        expect(document.documentElement.style.colorScheme).toBe('dark')
      })
    })

    it('handles localStorage errors gracefully', () => {
      // Mock localStorage to throw error
      global.Storage.prototype.setItem = vi.fn(() => {
        throw new Error('SecurityError')
      })

      const consoleWarn = vi.spyOn(console, 'warn').mockImplementation(() => {})

      render(
        <ThemeProvider>
          <TestComponent />
        </ThemeProvider>
      )

      expect(screen.getByTestId('theme')).toHaveTextContent('light')
      // Component should still work even with localStorage errors

      consoleWarn.mockRestore()
    })

    it('falls back to system preference when localStorage is unavailable', () => {
      // Mock localStorage to throw error on getItem
      global.Storage.prototype.getItem = vi.fn(() => {
        throw new Error('SecurityError')
      })

      // Mock matchMedia to return dark preference
      const matchMediaMock = vi.fn().mockImplementation(query => ({
        matches: query === '(prefers-color-scheme: dark)',
        media: query,
        onchange: null,
        addListener: vi.fn(),
        removeListener: vi.fn(),
        addEventListener: vi.fn(),
        removeEventListener: vi.fn(),
        dispatchEvent: vi.fn(),
      }))
      
      Object.defineProperty(window, 'matchMedia', {
        writable: true,
        value: matchMediaMock,
      })

      const consoleWarn = vi.spyOn(console, 'warn').mockImplementation(() => {})

      render(
        <ThemeProvider>
          <TestComponent />
        </ThemeProvider>
      )

      expect(screen.getByTestId('theme')).toHaveTextContent('dark')
      // Component should work despite localStorage error

      consoleWarn.mockRestore()
    })
  })

  describe('useTheme hook', () => {
    it('throws error when used outside ThemeProvider', () => {
      // Suppress console.error for this test
      const consoleError = vi.spyOn(console, 'error').mockImplementation(() => {})

      expect(() => render(<TestComponent />)).toThrow('useTheme must be used within a ThemeProvider')

      consoleError.mockRestore()
    })
  })
})
