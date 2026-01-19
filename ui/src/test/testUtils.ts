// SPDX-License-Identifier: MIT
// Copyright (c) 2025 Copilot-for-Consensus contributors

import { vi } from 'vitest'

/**
 * Creates a mock fetch response
 */
export function createMockResponse(data: any, options: { status?: number; ok?: boolean } = {}) {
  const { status = 200, ok = true } = options
  return {
    ok,
    status,
    json: vi.fn().mockResolvedValue(data),
    text: vi.fn().mockResolvedValue(JSON.stringify(data)),
  } as unknown as Response
}

/**
 * Creates a mock fetch implementation that returns specific responses
 */
export function createMockFetch(responses: Record<string, any>) {
  return vi.fn((url: string) => {
    const urlString = typeof url === 'string' ? url : url.toString()
    
    // Find matching response based on URL pattern
    for (const [pattern, response] of Object.entries(responses)) {
      if (urlString.includes(pattern)) {
        return Promise.resolve(createMockResponse(response))
      }
    }
    
    // Default 404 response
    return Promise.resolve(createMockResponse({ detail: 'Not found' }, { status: 404, ok: false }))
  })
}

/**
 * Wait for async operations to complete
 */
export function waitForAsync() {
  return new Promise(resolve => setTimeout(resolve, 0))
}
