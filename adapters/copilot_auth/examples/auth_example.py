# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Example demonstrating authentication usage in services.

This example shows how to integrate the authentication abstraction layer
into a Flask application for role-based access control.
"""

from flask import Flask, request, jsonify
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from copilot_auth import create_identity_provider, User, AuthenticationError

# Create Flask app
app = Flask(__name__)

# Create identity provider (using mock for this example)
provider = create_identity_provider(provider_type="mock")

# For demo purposes, add some test users if using mock provider
if hasattr(provider, 'add_user'):
    # Add a regular contributor
    provider.add_user(
        "token-contributor",
        User(
            id="user-1",
            email="contributor@example.com",
            name="Jane Contributor",
            roles=["contributor"],
            affiliations=["IETF"]
        )
    )
    
    # Add a working group chair
    provider.add_user(
        "token-chair",
        User(
            id="user-2",
            email="chair@example.com",
            name="John Chair",
            roles=["contributor", "chair"],
            affiliations=["IETF", "IRTF"]
        )
    )


def get_authenticated_user():
    """Extract and validate authentication token from request.
    
    Returns:
        User object if authenticated, None otherwise
    """
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return None
    
    token = auth_header[7:]  # Remove "Bearer " prefix
    
    try:
        return provider.get_user(token)
    except AuthenticationError:
        return None


def require_role(role: str):
    """Decorator to require a specific role for endpoint access."""
    def decorator(f):
        def wrapper(*args, **kwargs):
            user = get_authenticated_user()
            if not user:
                return jsonify({"error": "Authentication required"}), 401
            
            if not user.has_role(role):
                return jsonify({
                    "error": f"Role '{role}' required",
                    "user_roles": user.roles
                }), 403
            
            # Add user to kwargs so endpoint can use it
            kwargs['user'] = user
            return f(*args, **kwargs)
        
        wrapper.__name__ = f.__name__
        return wrapper
    return decorator


@app.route("/", methods=["GET"])
def health():
    """Public health check endpoint."""
    return jsonify({"status": "ok", "service": "auth-example"}), 200


@app.route("/api/profile", methods=["GET"])
def get_profile():
    """Get authenticated user's profile (requires authentication)."""
    user = get_authenticated_user()
    if not user:
        return jsonify({"error": "Authentication required"}), 401
    
    return jsonify({
        "profile": user.to_dict(),
        "message": f"Welcome, {user.name}!"
    }), 200


@app.route("/api/summaries", methods=["GET"])
@require_role("contributor")
def get_summaries(user):
    """Get summaries (requires contributor role)."""
    return jsonify({
        "summaries": [
            {"id": "summary-1", "title": "Thread Summary 1"},
            {"id": "summary-2", "title": "Thread Summary 2"},
        ],
        "user": user.name,
        "message": "Summaries retrieved successfully"
    }), 200


@app.route("/api/admin/reports", methods=["POST"])
@require_role("chair")
def create_report(user):
    """Create a report (requires chair role)."""
    data = request.get_json() or {}
    
    return jsonify({
        "report_id": "report-123",
        "title": data.get("title", "Untitled Report"),
        "created_by": user.name,
        "message": "Report created successfully"
    }), 201


@app.route("/api/wg-members", methods=["GET"])
def get_wg_members():
    """Get working group members (requires IETF affiliation)."""
    user = get_authenticated_user()
    if not user:
        return jsonify({"error": "Authentication required"}), 401
    
    if not user.has_affiliation("IETF"):
        return jsonify({
            "error": "IETF affiliation required",
            "user_affiliations": user.affiliations
        }), 403
    
    return jsonify({
        "members": [
            {"name": "Alice", "role": "chair"},
            {"name": "Bob", "role": "contributor"},
        ],
        "message": "Working group members retrieved"
    }), 200


if __name__ == "__main__":
    print("\n" + "="*60)
    print("Authentication Example Service")
    print("="*60)
    print("\nTest the endpoints with curl:")
    print("\n1. Health check (no auth required):")
    print("   curl http://localhost:5000/")
    print("\n2. Get profile (requires any valid token):")
    print("   curl -H 'Authorization: Bearer token-contributor' \\")
    print("        http://localhost:5000/api/profile")
    print("\n3. Get summaries (requires 'contributor' role):")
    print("   curl -H 'Authorization: Bearer token-contributor' \\")
    print("        http://localhost:5000/api/summaries")
    print("\n4. Create report (requires 'chair' role):")
    print("   curl -X POST -H 'Authorization: Bearer token-chair' \\")
    print("        -H 'Content-Type: application/json' \\")
    print("        -d '{\"title\": \"My Report\"}' \\")
    print("        http://localhost:5000/api/admin/reports")
    print("\n5. Get WG members (requires 'IETF' affiliation):")
    print("   curl -H 'Authorization: Bearer token-chair' \\")
    print("        http://localhost:5000/api/wg-members")
    print("\n6. Try with invalid token (should fail):")
    print("   curl -H 'Authorization: Bearer invalid-token' \\")
    print("        http://localhost:5000/api/profile")
    print("\n" + "="*60 + "\n")
    
    # Note: debug=True is for example purposes only
    # In production, use a production WSGI server like gunicorn
    app.run(host="0.0.0.0", port=5000, debug=False)
