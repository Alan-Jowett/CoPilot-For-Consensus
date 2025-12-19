// SPDX-License-Identifier: MIT
// Copyright (c) 2025 Copilot-for-Consensus contributors

import React from 'react'
import ReactDOM from 'react-dom/client'
import { createBrowserRouter, RouterProvider, Navigate } from 'react-router-dom'
import { ThemeProvider } from './contexts/ThemeContext'
import { AuthProvider, setAuthToken, setUnauthorizedCallback } from './contexts/AuthContext'
import { AppLayout } from './ui/AppLayout'
import { ReportsList } from './routes/ReportsList'
import { ReportDetail } from './routes/ReportDetail'
import { ThreadSummary } from './routes/ThreadSummary'
import { ThreadDetail } from './routes/ThreadDetail'
import { MessageDetail } from './routes/MessageDetail'
import { SourcesList } from './routes/SourcesList'
import { SourceForm } from './routes/SourceForm'
import { AdminDashboard } from './routes/AdminDashboard'
import { Login } from './routes/Login'
import { Callback } from './routes/Callback'
import './styles.css'

const router = createBrowserRouter([
  {
    path: '/',
    element: <AppLayout />,
    children: [
      { index: true, element: <Navigate to="reports" replace /> },
      { path: 'reports', element: <ReportsList /> },
      { path: 'reports/:reportId', element: <ReportDetail /> },
      { path: 'threads/:threadId', element: <ThreadSummary /> },
      { path: 'threads/:threadId/messages', element: <ThreadDetail /> },
      { path: 'messages/:messageDocId', element: <MessageDetail /> },
      { path: 'sources', element: <SourcesList /> },
      { path: 'sources/new', element: <SourceForm /> },
      { path: 'sources/edit/:sourceName', element: <SourceForm /> },
      { path: 'admin', element: <AdminDashboard /> },
    ],
  },
  { path: 'login', element: <Login /> },
  { path: 'callback', element: <Callback /> },
], {
  // Ensure routing works when the app is served under /ui/
  basename: import.meta.env.BASE_URL,
})

// Set up auth callbacks
setUnauthorizedCallback(() => {
  window.location.href = `${import.meta.env.BASE_URL}login`
})

// Restore token from localStorage on page load
const token = localStorage.getItem('auth_token')
if (token) {
  setAuthToken(token)
}

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <AuthProvider>
      <ThemeProvider>
        <RouterProvider router={router} />
      </ThemeProvider>
    </AuthProvider>
  </React.StrictMode>
)
