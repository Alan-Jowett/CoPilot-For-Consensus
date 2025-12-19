// SPDX-License-Identifier: MIT
// Copyright (c) 2025 Copilot-for-Consensus contributors

import { createContext, useContext, useEffect, useState, ReactNode } from 'react'

type Theme = 'light' | 'dark'

interface ThemeContextType {
  theme: Theme
  toggleTheme: () => void
}

const ThemeContext = createContext<ThemeContextType | undefined>(undefined)

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [theme, setTheme] = useState<Theme>(() => {
    // Check if running in browser (not SSR)
    if (typeof window === 'undefined') {
      return 'light'
    }
    
    try {
      // Check localStorage first
      const stored = localStorage.getItem('theme')
      if (stored === 'light' || stored === 'dark') {
        return stored
      }
    } catch (error) {
      // localStorage might be unavailable (SecurityError, etc.)
      console.warn('localStorage not available:', error)
    }
    
    // Fall back to system preference
    if (window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches) {
      return 'dark'
    }
    
    return 'light'
  })

  useEffect(() => {
    // Apply theme to document root
    document.documentElement.setAttribute('data-theme', theme)
    // Also update color-scheme for native browser elements
    document.documentElement.style.colorScheme = theme
    // Save to localStorage
    try {
      localStorage.setItem('theme', theme)
    } catch (error) {
      // localStorage might be unavailable
      console.warn('Failed to save theme to localStorage:', error)
    }
  }, [theme])

  const toggleTheme = () => {
    setTheme(prev => prev === 'light' ? 'dark' : 'light')
  }

  return (
    <ThemeContext.Provider value={{ theme, toggleTheme }}>
      {children}
    </ThemeContext.Provider>
  )
}

export function useTheme() {
  const context = useContext(ThemeContext)
  if (context === undefined) {
    throw new Error('useTheme must be used within a ThemeProvider')
  }
  return context
}
