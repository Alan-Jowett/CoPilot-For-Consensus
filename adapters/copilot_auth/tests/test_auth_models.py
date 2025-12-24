# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Tests for authentication models."""

from copilot_auth import User


class TestUser:
    """Tests for User model."""

    def test_user_creation_with_required_fields(self):
        """Test creating a user with only required fields."""
        user = User(
            id="user-123",
            email="test@example.com",
            name="Test User"
        )

        assert user.id == "user-123"
        assert user.email == "test@example.com"
        assert user.name == "Test User"
        assert user.roles == []
        assert user.affiliations == []

    def test_user_creation_with_all_fields(self):
        """Test creating a user with all fields."""
        user = User(
            id="user-456",
            email="contributor@example.com",
            name="Jane Contributor",
            roles=["contributor", "reviewer"],
            affiliations=["IETF", "W3C"]
        )

        assert user.id == "user-456"
        assert user.email == "contributor@example.com"
        assert user.name == "Jane Contributor"
        assert user.roles == ["contributor", "reviewer"]
        assert user.affiliations == ["IETF", "W3C"]

    def test_has_role_returns_true_for_existing_role(self):
        """Test has_role returns True for existing role."""
        user = User(
            id="user-789",
            email="chair@example.com",
            name="Working Group Chair",
            roles=["chair", "contributor"]
        )

        assert user.has_role("chair") is True
        assert user.has_role("contributor") is True

    def test_has_role_returns_false_for_missing_role(self):
        """Test has_role returns False for missing role."""
        user = User(
            id="user-789",
            email="chair@example.com",
            name="Working Group Chair",
            roles=["chair"]
        )

        assert user.has_role("admin") is False
        assert user.has_role("reviewer") is False

    def test_has_affiliation_returns_true_for_existing_affiliation(self):
        """Test has_affiliation returns True for existing affiliation."""
        user = User(
            id="user-101",
            email="member@example.com",
            name="IETF Member",
            affiliations=["IETF", "IRTF"]
        )

        assert user.has_affiliation("IETF") is True
        assert user.has_affiliation("IRTF") is True

    def test_has_affiliation_returns_false_for_missing_affiliation(self):
        """Test has_affiliation returns False for missing affiliation."""
        user = User(
            id="user-101",
            email="member@example.com",
            name="IETF Member",
            affiliations=["IETF"]
        )

        assert user.has_affiliation("W3C") is False
        assert user.has_affiliation("IEEE") is False

    def test_to_dict_includes_all_fields(self):
        """Test to_dict includes all fields."""
        user = User(
            id="user-202",
            email="test@example.com",
            name="Test User",
            roles=["contributor"],
            affiliations=["IETF"]
        )

        result = user.to_dict()

        assert result == {
            "id": "user-202",
            "email": "test@example.com",
            "name": "Test User",
            "roles": ["contributor"],
            "affiliations": ["IETF"]
        }

    def test_to_dict_with_empty_lists(self):
        """Test to_dict with empty roles and affiliations."""
        user = User(
            id="user-303",
            email="test@example.com",
            name="Test User"
        )

        result = user.to_dict()

        assert result["roles"] == []
        assert result["affiliations"] == []

    def test_user_equality(self):
        """Test that two users with same data are equal."""
        user1 = User(
            id="user-404",
            email="test@example.com",
            name="Test User",
            roles=["contributor"],
            affiliations=["IETF"]
        )
        user2 = User(
            id="user-404",
            email="test@example.com",
            name="Test User",
            roles=["contributor"],
            affiliations=["IETF"]
        )

        assert user1 == user2

    def test_user_inequality(self):
        """Test that two users with different data are not equal."""
        user1 = User(
            id="user-505",
            email="test1@example.com",
            name="Test User 1"
        )
        user2 = User(
            id="user-606",
            email="test2@example.com",
            name="Test User 2"
        )

        assert user1 != user2
