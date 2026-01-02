// SPDX-License-Identifier: MIT
// Copyright (c) 2025 Copilot-for-Consensus contributors

import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vitejs.dev/config/
export default defineConfig({
  // Serve the SPA from subpath when behind the API gateway
  // Defaults to '/ui/' for production builds; override with VITE_BASE if needed
  base: process.env.VITE_BASE || '/ui/',
  plugins: [react()],
  // Environment variables available to the client
  define: {
    'process.env.REACT_APP_GRAFANA_ENABLED': JSON.stringify(process.env.REACT_APP_GRAFANA_ENABLED || 'false'),
  },
  server: {
    port: 8084,
  },
  preview: {
    port: 8084,
  },
})
