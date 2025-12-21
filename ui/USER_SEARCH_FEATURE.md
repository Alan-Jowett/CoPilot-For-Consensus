<!-- SPDX-License-Identifier: MIT
  Copyright (c) 2025 Copilot-for-Consensus contributors -->

# User Search Feature - Implementation Summary

## Overview

This document describes the enhanced user search functionality in the Role Management UI. Previously, admins could only search for users by exact user ID. Now, admins can search by email, name, or user ID with more flexible matching.

## Changes Made

### Backend Changes

#### 1. RoleStore (`auth/app/role_store.py`)
Added new `search_users()` method that supports:
- **User ID**: Exact match search
- **Email**: Case-insensitive partial match
- **Name**: Case-insensitive partial match

```python
def search_users(
    self,
    search_term: str,
    search_by: str = "user_id",
) -> list[dict[str, Any]]:
    """Search for users by various fields."""
```

#### 2. Auth API (`auth/main.py`)
Added new search endpoint:
```
GET /admin/users/search?search_term={term}&search_by={field}
```

Query parameters:
- `search_term` (required): The search term to look for
- `search_by` (required): Field to search by ('user_id', 'email', or 'name')

Returns:
```json
{
  "users": [...],
  "count": 3,
  "search_by": "email",
  "search_term": "example"
}
```

### Frontend Changes

#### 1. API Client (`ui/src/api.ts`)
Added `searchUsers()` function:
```typescript
export async function searchUsers(
  searchTerm: string,
  searchBy: 'user_id' | 'email' | 'name' = 'email'
): Promise<UserSearchResponse>
```

#### 2. UserRolesList Component (`ui/src/routes/UserRolesList.tsx`)
Enhanced UI with:
- **Search Type Dropdown**: Select between Email, Name, or User ID
- **Dynamic Label**: Input label changes based on selected search type
- **Multiple Results Handling**: 
  - Single result: Display directly
  - Multiple results: Show clickable list to select user
  - No results: Display helpful message

## User Interface

### Before
```
Search User
┌─────────────────┐
│ User ID         │
│ ┌─────────────┐ │
│ │ Enter user ID │
│ └─────────────┘ │
│ [Search]        │
└─────────────────┘
```

### After
```
Search User
┌──────────────────────────────────┐
│ Search By: [▼ Email          ]   │
│                                  │
│ Email                            │
│ ┌──────────────────────────────┐ │
│ │ Enter email                  │ │
│ └──────────────────────────────┘ │
│ [Search]                         │
└──────────────────────────────────┘

When multiple results found:
┌──────────────────────────────────┐
│ Search Results (3 users found)   │
│ ┌──────────────────────────────┐ │
│ │ Alice Smith                  │ │
│ │ alice@example.com            │ │
│ │ github:123 • approved        │ │
│ └──────────────────────────────┘ │
│ ┌──────────────────────────────┐ │
│ │ Alice Johnson                │ │
│ │ alice.j@example.com          │ │
│ │ github:456 • pending         │ │
│ └──────────────────────────────┘ │
│ ...                              │
└──────────────────────────────────┘
```

## Usage Examples

### Example 1: Search by Email
1. Select "Email" from the dropdown
2. Enter "alice@example"
3. Click Search
4. Results show all users with emails containing "alice@example" (case-insensitive)

### Example 2: Search by Name
1. Select "Name" from the dropdown
2. Enter "smith"
3. Click Search
4. Results show all users with "smith" in their name (case-insensitive)

### Example 3: Search by User ID (Exact Match)
1. Select "User ID" from the dropdown
2. Enter "github:123"
3. Click Search
4. Results show the exact user with that ID (if exists)

## Benefits

1. **More User-Friendly**: Admins can search by email or name instead of needing to know the exact user ID
2. **Flexible Matching**: Email and name searches support partial, case-insensitive matching
3. **Better Discoverability**: When multiple users match, all are shown for selection
4. **Maintains Backward Compatibility**: User ID search still works as before

## Testing

### Unit Tests
Added 6 new unit tests in `auth/tests/test_role_store_admin.py`:
- `test_search_by_user_id_exact_match`
- `test_search_by_email_partial_match`
- `test_search_by_name_case_insensitive`
- `test_search_invalid_field`
- `test_search_no_results`
- `test_search_handles_missing_field`

All tests pass successfully.

### Manual Testing
To test manually:
1. Start the services with `docker-compose up`
2. Login as an admin user
3. Navigate to Admin → User Roles
4. Try searching by:
   - Email: Enter part of an email address
   - Name: Enter part of a user's name
   - User ID: Enter a complete user ID

## Security Considerations

- Search endpoint requires admin role (enforced via `require_admin_role()`)
- All searches are logged for audit purposes
- No sensitive data is exposed in search results
- Input validation prevents invalid search fields

## Performance Notes

- User ID searches query the database directly (efficient)
- Email and name searches fetch all documents and filter in-memory
  - This is acceptable for MVP with small-to-medium user bases
  - For production with large user bases, consider:
    - Adding database indexes for email and name fields
    - Implementing database-level regex/text search
    - Using a dedicated search service (e.g., Elasticsearch)

## Documentation Updates

- Updated `ui/ADMIN_FEATURES.md` with new search capabilities
- Added this implementation summary document
