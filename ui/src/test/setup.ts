// SPDX-License-Identifier: MIT
// Copyright (c) 2025 Copilot-for-Consensus contributors

import '@testing-library/jest-dom'
import { cleanup } from '@testing-library/react'
import { afterEach, vi } from 'vitest'

// Cleanup after each test
afterEach(() => {
  cleanup()
})

// Mock window.matchMedia for components that use media queries
Object.defineProperty(window, 'matchMedia', {
  writable: true,
  value: vi.fn().mockImplementation(query => ({
    matches: false,
    media: query,
    onchange: null,
    addListener: vi.fn(),
    removeListener: vi.fn(),
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
    dispatchEvent: vi.fn(),
  })),
})

// Mock navigator.clipboard for copy functionality
// Use defineProperty with configurable: true to allow user-event to override it
Object.defineProperty(navigator, 'clipboard', {
  writable: true,
  configurable: true,
  value: {
    writeText: vi.fn().mockResolvedValue(undefined),
  },
})

// Mock import.meta.env for environment variables
const originalEnv = import.meta.env
vi.stubGlobal('import.meta', {
  env: {
    ...originalEnv,
    BASE_URL: '/ui/',
    DEV: false,
    VITE_REPORTING_API_URL: '',
  },
})


