# Admin Role Management UI - Component Structure

This document describes the component architecture for the Admin Role Management UI.

## Component Hierarchy

```
AdminDashboard (Route: /admin)
├── Tab Navigation
│   ├── User Roles Tab
│   └── Pending Assignments Tab
│
├── UserRolesList (when User Roles tab is active)
│   ├── Search Filters
│   │   └── User ID Input + Search Button
│   ├── User Record Card (shown after search)
│   │   ├── User Information Display
│   │   │   ├── Name/User ID
│   │   │   ├── Email
│   │   │   └── Status Badge
│   │   ├── Action Buttons
│   │   │   ├── Assign Roles Button
│   │   │   └── Revoke Roles Button
│   │   └── Current Roles Section
│   │       └── Role Badges (list of assigned roles)
│   └── RoleManagementModal (opened on action)
│
└── PendingAssignments (when Pending tab is active)
    ├── Filters Section
    │   ├── User ID Filter
    │   ├── Role Filter
    │   ├── Apply Filters Button
    │   └── Clear Filters Button
    ├── Data Table
    │   ├── User ID Column
    │   ├── Email Column
    │   ├── Name Column
    │   ├── Requested Roles Column (badges)
    │   ├── Requested At Column (timestamp)
    │   └── Status Column (badge)
    └── Pagination Controls
        ├── Results Count Display
        ├── Previous Button
        └── Next Button
```

## Component Details

### AdminDashboard
**File:** `ui/src/routes/AdminDashboard.tsx`
- Main container component
- Manages active tab state
- Renders either UserRolesList or PendingAssignments based on tab

### UserRolesList
**File:** `ui/src/routes/UserRolesList.tsx`
- User search functionality
- Displays user role information
- Opens RoleManagementModal for assign/revoke actions
- Handles loading and error states

### PendingAssignments
**File:** `ui/src/routes/PendingAssignments.tsx`
- Fetches and displays pending role assignment requests
- Filter controls for user_id and role
- Pagination support (20 items per page)
- Auto-refreshes when filters change

### RoleManagementModal
**File:** `ui/src/routes/RoleManagementModal.tsx`
- Modal dialog for role operations
- Two modes: 'assign' and 'revoke'
- Shows available roles as checkboxes
- Supports custom role addition (assign mode only)
- Displays selected roles with remove option
- Confirmation buttons with loading states

## Data Flow

```
User Interaction
    ↓
Component Event Handler
    ↓
API Call (from api.ts)
    ↓
NGINX Proxy (/auth/)
    ↓
Auth Service Backend
    ↓
Response Processing
    ↓
State Update
    ↓
UI Re-render
```

## API Functions

Located in `ui/src/api.ts`:

1. **fetchPendingRoleAssignments(params)**
   - GET /auth/admin/role-assignments/pending
   - Supports filtering by user_id, role
   - Pagination via limit/skip
   - Returns: assignments array + total count

2. **fetchUserRoles(userId)**
   - GET /auth/admin/users/{userId}/roles
   - Returns: user role record with current roles

3. **assignUserRoles(userId, roles)**
   - POST /auth/admin/users/{userId}/roles
   - Body: { roles: string[] }
   - Returns: updated user role record

4. **revokeUserRoles(userId, roles)**
   - DELETE /auth/admin/users/{userId}/roles
   - Body: { roles: string[] }
   - Returns: updated user role record

All API calls include:
- JWT token in Authorization header
- Proper error handling (401, 403, 404)
- User-friendly error messages

## Styling

CSS classes added to `ui/src/styles.css`:

### Admin-specific Styles
- `.admin-tabs` - Tab navigation container
- `.admin-tab` - Individual tab button
- `.admin-tab.active` - Active tab state
- `.admin-content` - Tab content container

### User Record Styles
- `.user-record-card` - User information card
- `.user-record-header` - Header with actions
- `.user-metadata` - User metadata section
- `.metadata-item` - Individual metadata row
- `.user-actions` - Action buttons container
- `.user-roles-section` - Current roles display
- `.user-record-timestamp` - Last updated timestamp

### Modal Styles
- `.modal-overlay` - Full-screen overlay
- `.modal-content` - Modal dialog container
- `.modal-header` - Modal title and close button
- `.modal-body` - Scrollable content area
- `.modal-footer` - Action buttons
- `.modal-close` - Close button
- `.custom-role-input` - Custom role input section
- `.custom-role-field` - Custom role input field

### Role Display Styles
- `.role-badges` - Container for role badges
- `.role-badge` - Individual role badge
- `.role-checkboxes` - Role selection list
- `.remove-role` - Remove role button in badge

## Theme Support

All components support both light and dark themes using CSS variables:
- Background colors: `--bg-primary`, `--bg-secondary`, `--bg-tertiary`
- Text colors: `--text-primary`, `--text-secondary`, `--text-tertiary`
- Border colors: `--border-primary`, `--border-secondary`
- Action colors: `--color-primary`, `--color-success`, `--color-warning`

## Navigation Integration

The Admin Dashboard is integrated into the main navigation:

**File:** `ui/src/ui/AppLayout.tsx`
```tsx
<Link to="/admin" className={isActive('/admin') ? 'nav-link active' : 'nav-link'}>
  🔐 Admin
</Link>
```

**Route Configuration:** `ui/src/main.tsx`
```tsx
{ path: 'admin', element: <AdminDashboard /> }
```

## Error Handling

All components handle common error scenarios:

1. **Loading States**: Display "Loading…" message
2. **Empty States**: User-friendly "No data" messages
3. **API Errors**: Clear error banners with specific messages
4. **Authentication Errors**:
   - 401: "Unauthorized - Please login with admin credentials"
   - 403: "Forbidden - Admin role required"
   - 404: "User not found"

## Future Considerations

The architecture supports future enhancements:
- Real-time updates via WebSockets
- Bulk operations on multiple users
- Role approval workflows
- Audit log integration
- Advanced filtering and search
- Export functionality
