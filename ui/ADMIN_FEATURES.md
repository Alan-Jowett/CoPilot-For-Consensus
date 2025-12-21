<!-- SPDX-License-Identifier: MIT
  Copyright (c) 2025 Copilot-for-Consensus contributors -->

# Admin Role Management UI

This document describes the Admin Role Management UI features added to the SPA React client.

## Features

### 1. Admin Dashboard
Located at `/admin`, the Admin Dashboard provides two main tabs:

- **User Roles**: Search and manage roles for individual users
- **Pending Assignments**: View and filter pending role assignment requests

### 2. User Roles Management

#### Search User
- Search for users by:
  - **Email**: Search by email address (partial match, case-insensitive)
  - **Name**: Search by user's display name (partial match, case-insensitive)
  - **User ID**: Search by exact user ID
- Select search type from dropdown before entering search term
- Displays user information including email, name, status, and assigned roles
- For searches with multiple results, shows a list of matching users to select from

#### Assign Roles
- Click "Assign Roles" to open the role assignment modal
- Select from standard roles: admin, contributor, viewer, moderator
- Add custom roles by typing a role name
- Multiple roles can be assigned at once

#### Revoke Roles
- Click "Revoke Roles" to open the role revocation modal
- Select which roles to remove from the user
- Multiple roles can be revoked at once

### 3. Pending Assignments

View and filter pending role assignment requests with the following features:

- **Filters**: Filter by user ID or role name
- **Pagination**: Navigate through results (20 per page by default)
- **Information Displayed**:
  - User ID
  - Email and name (if available)
  - Requested roles
  - Request timestamp
  - Status

### 4. Navigation

Access the Admin Dashboard via the navigation bar:
- 🔐 Admin link appears in the top navigation
- Only accessible to users with admin role (enforced by backend)

## Authentication

The Admin UI requires authentication with a valid JWT token that includes the `admin` role.

### Token Storage
Tokens are expected to be stored in either:
- `localStorage` under the key `auth_token`
- `sessionStorage` under the key `auth_token`

### Error Handling
The UI provides clear error messages for common scenarios:
- **401 Unauthorized**: "Please login with admin credentials"
- **403 Forbidden**: "Admin role required"
- **404 Not Found**: User or resource not found

## API Integration

The UI integrates with the following auth service endpoints:

- `GET /auth/admin/role-assignments/pending` - List pending assignments
- `GET /auth/admin/users/search` - Search for users by email, name, or user_id
- `GET /auth/admin/users/{user_id}/roles` - Get user roles
- `POST /auth/admin/users/{user_id}/roles` - Assign roles to user
- `DELETE /auth/admin/users/{user_id}/roles` - Revoke roles from user

All requests include the JWT token in the `Authorization: Bearer <token>` header.

## Design

The Admin UI follows the existing design system:
- Consistent color scheme supporting both light and dark themes
- Standard button styles and badges
- Modal dialogs for confirmations
- Table layouts for data display
- Responsive design

## Future Enhancements

Potential improvements for future iterations:
- Bulk role assignment operations
- Role assignment approval workflow
- Audit log of role changes
- Role-based access control visualization
- Advanced search filters (e.g., by role, status, provider)
- Export user list with roles
