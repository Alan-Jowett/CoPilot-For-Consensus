// SPDX-License-Identifier: MIT
// Copyright (c) 2025 Copilot-for-Consensus contributors

import React from 'react'
import ReactDOM from 'react-dom/client'
import { createBrowserRouter, RouterProvider, Navigate } from 'react-router-dom'
import { AppLayout } from './ui/AppLayout'
import { ReportsList } from './routes/ReportsList'
import { ReportDetail } from './routes/ReportDetail'
import { ThreadSummary } from './routes/ThreadSummary'
import { ThreadDetail } from './routes/ThreadDetail'
import { MessageDetail } from './routes/MessageDetail'
import './styles.css'

const router = createBrowserRouter([
  {
    path: '/',
    element: <AppLayout />,
    children: [
      { index: true, element: <Navigate to="/reports" replace /> },
      { path: 'reports', element: <ReportsList /> },
      { path: 'reports/:reportId', element: <ReportDetail /> },
      { path: 'threads/:threadId', element: <ThreadDetail /> },
      { path: 'threads/:threadId/summary', element: <ThreadSummary /> },
      { path: 'messages/:messageDocId', element: <MessageDetail /> },
    ],
  },
])

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <RouterProvider router={router} />
  </React.StrictMode>
)
