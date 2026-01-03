<!-- SPDX-License-Identifier: MIT
  Copyright (c) 2025 Copilot-for-Consensus contributors -->

# Microservices Authentication & Authorization

Centralized JWT-based authentication and role-based access control (RBAC) across all microservices.

## Architecture

```
User → OIDC Login (GitHub/Google/Microsoft)
       ↓
Auth Service (issues JWT)
       ↓
User/Client (carries JWT in Authorization header)
       ↓
Microservice (validates JWT via JWKS, enforces role requirements)
```

## Service Integration Status

| Service | Status | Required Role | Public Endpoints |
|---------|--------|---------------|------------------|
| **Auth** | ✅ Issuer | N/A | `/login`, `/callback`, `/keys`, `/health`, `/readyz`, `/docs`, `/openapi.json` |
| **Reporting API** | ✅ Protected | `reader` | `/health`, `/`, `/readyz`, `/docs`, `/openapi.json` |
| **Orchestrator** | ✅ Protected | `orchestrator` | `/health`, `/readyz`, `/docs`, `/openapi.json` |
| **Chunking** | ✅ Protected | `processor` | `/health`, `/readyz`, `/docs`, `/openapi.json` |
| **Embedding** | ✅ Protected | `processor` | `/health`, `/readyz`, `/docs`, `/openapi.json` |
| **Parsing** | ✅ Protected | `processor` | `/health`, `/readyz`, `/docs`, `/openapi.json` |
| **Summarization** | ✅ Protected | `processor` | `/health`, `/readyz`, `/docs`, `/openapi.json` |
| **Ingestion API** | ✅ Protected | `admin` | `/health`, `/`, `/readyz`, `/docs`, `/openapi.json` |

## Standard Roles

- **`reader`**: Read-only access to reports and summaries
- **`contributor`**: Feedback and discussion participation
- **`processor`**: Internal service role for processing pipeline
- **`orchestrator`**: Coordinate workflow and trigger summarization
- **`admin`**: Full administrative access (source management, user management)
- **`chair`**: Working group chair privileges (future)

Role assignment is based on:
- OIDC provider claims (GitHub orgs, Google/Microsoft groups)
- Manual assignment via role management API (future)
- Default: new users receive `reader` role

## Authentication Flow

### 1. User Login
```bash
curl -i "http://localhost:8090/login?provider=github&aud=copilot-reporting"
# Redirects to provider (GitHub/Google/Microsoft)
# Callback returns JWT
```

### 2. API Request with JWT
```bash
curl -H "Authorization: Bearer <jwt-token>" \
     http://localhost:8080/reporting/api/reports
```

### 3. Token Validation

Middleware validates:
1. Extract JWT from `Authorization: Bearer <token>` header
2. Fetch JWKS from auth service (`http://auth:8090/keys`)
3. Validate JWT signature using public key
4. Check token expiration (`exp` claim)
5. Validate audience (`aud` claim matches service name)
6. Enforce role requirements (`roles` claim)
7. Add claims to `request.state` for handlers

## Configuration

**.env file**:
```
AUTH_SERVICE_URL=http://auth:8090
OIDC_PROVIDER=github  # or google, microsoft
OIDC_CLIENT_ID=<your-client-id>
OIDC_CLIENT_SECRET=<your-client-secret>
JWT_SECRET=<your-jwt-secret-key>
JWT_ALGORITHM=HS256
JWT_EXPIRY_SECONDS=3600
```

## Integration in Services

Use the `copilot_auth` adapter:
```python
from copilot_auth import create_auth_handler, require_role

app = FastAPI()
auth_handler = create_auth_handler(
    auth_service_url="http://auth:8090",
    service_name="my-service",
    service_audience="my-service"
)

@app.get("/protected")
@require_role("processor")
async def protected_endpoint(request: Request):
    user_id = request.state.user_id
    roles = request.state.roles
    return {"message": f"Hello {user_id}"}
```

See [docs/features/authentication.md](authentication.md) for detailed integration examples and best practices.
