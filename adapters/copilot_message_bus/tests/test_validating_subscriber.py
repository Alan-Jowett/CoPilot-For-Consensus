# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Tests for ValidatingEventSubscriber."""

from unittest.mock import Mock, patch

import pytest
from copilot_message_bus.validating_subscriber import (
    SubscriberValidationError,
    ValidatingEventSubscriber,
)


class TestSubscriberValidationError:
    """Test SubscriberValidationError exception."""

    def test_subscriber_validation_error_init(self):
        """Test SubscriberValidationError initialization."""
        errors = ["Field 'event_type' is missing", "Field 'timestamp' is invalid"]
        exc = SubscriberValidationError("TestEvent", errors)

        assert exc.event_type == "TestEvent"
        assert exc.errors == errors
        assert "TestEvent" in str(exc)
        assert "Field 'event_type' is missing" in str(exc)


class TestValidatingEventSubscriber:
    """Test ValidatingEventSubscriber class."""

    def test_init_default(self):
        """Test initialization with default parameters."""
        mock_subscriber = Mock()
        subscriber = ValidatingEventSubscriber(subscriber=mock_subscriber)

        assert subscriber._subscriber == mock_subscriber
        assert subscriber._schema_provider is None
        assert subscriber._strict is True
        assert subscriber._callbacks == {}

    def test_init_with_schema_provider(self):
        """Test initialization with schema provider."""
        mock_subscriber = Mock()
        mock_provider = Mock()
        subscriber = ValidatingEventSubscriber(
            subscriber=mock_subscriber,
            schema_provider=mock_provider,
            strict=False,
        )

        assert subscriber._schema_provider == mock_provider
        assert subscriber._strict is False

    def test_validate_event_no_schema_provider(self):
        """Test validation skipped when no schema provider."""
        mock_subscriber = Mock()
        subscriber = ValidatingEventSubscriber(
            subscriber=mock_subscriber,
            schema_provider=None,
        )

        event = {"event_type": "TestEvent", "data": {}}
        is_valid, errors = subscriber._validate_event(event)

        assert is_valid is True
        assert errors == []

    def test_validate_event_missing_event_type(self):
        """Test validation fails for event without event_type."""
        mock_subscriber = Mock()
        mock_provider = Mock()
        subscriber = ValidatingEventSubscriber(
            subscriber=mock_subscriber,
            schema_provider=mock_provider,
        )

        event = {"data": {}}
        is_valid, errors = subscriber._validate_event(event)

        assert is_valid is False
        assert "event_type" in errors[0]

    def test_validate_event_with_valid_event(self):
        """Test validation succeeds for valid event."""
        mock_subscriber = Mock()
        mock_provider = Mock()
        mock_schema = {"type": "object"}
        mock_provider.get_schema.return_value = mock_schema

        subscriber = ValidatingEventSubscriber(
            subscriber=mock_subscriber,
            schema_provider=mock_provider,
        )

        with patch("copilot_schema_validation.validate_json") as mock_validate:
            mock_validate.return_value = (True, [])
            event = {"event_type": "TestEvent", "data": {}}

            is_valid, errors = subscriber._validate_event(event)

            assert is_valid is True
            assert errors == []
            mock_validate.assert_called_once_with(event, mock_schema, schema_provider=mock_provider)

    def test_validate_event_with_invalid_event(self):
        """Test validation fails for invalid event."""
        mock_subscriber = Mock()
        mock_provider = Mock()
        mock_schema = {"type": "object", "required": ["data"]}
        mock_provider.get_schema.return_value = mock_schema

        subscriber = ValidatingEventSubscriber(
            subscriber=mock_subscriber,
            schema_provider=mock_provider,
        )

        with patch("copilot_schema_validation.validate_json") as mock_validate:
            mock_validate.return_value = (False, ["Missing required field: data"])
            event = {"event_type": "TestEvent"}

            is_valid, errors = subscriber._validate_event(event)

            assert is_valid is False
            assert "Missing required field: data" in errors

    def test_validate_event_schema_not_found_strict(self):
        """Test validation in strict mode when schema not found."""
        mock_subscriber = Mock()
        mock_provider = Mock()
        mock_provider.get_schema.return_value = None

        subscriber = ValidatingEventSubscriber(
            subscriber=mock_subscriber,
            schema_provider=mock_provider,
            strict=True,
        )

        event = {"event_type": "UnknownEvent"}
        is_valid, errors = subscriber._validate_event(event)

        assert is_valid is False
        assert "No schema found" in errors[0]

    def test_validate_event_schema_not_found_non_strict(self):
        """Test validation in non-strict mode when schema not found."""
        mock_subscriber = Mock()
        mock_provider = Mock()
        mock_provider.get_schema.return_value = None

        subscriber = ValidatingEventSubscriber(
            subscriber=mock_subscriber,
            schema_provider=mock_provider,
            strict=False,
        )

        event = {"event_type": "UnknownEvent"}
        is_valid, errors = subscriber._validate_event(event)

        assert is_valid is True
        assert errors == []

    def test_validating_callback_wrapper_valid_event_strict(self):
        """Test callback wrapper with valid event in strict mode."""
        mock_subscriber = Mock()
        mock_provider = Mock()
        mock_schema = {"type": "object"}
        mock_provider.get_schema.return_value = mock_schema

        subscriber = ValidatingEventSubscriber(
            subscriber=mock_subscriber,
            schema_provider=mock_provider,
            strict=True,
        )

        mock_callback = Mock()
        event = {"event_type": "TestEvent", "data": {"id": 1}}

        with patch("copilot_schema_validation.validate_json") as mock_validate:
            mock_validate.return_value = (True, [])
            wrapper = subscriber._validating_callback_wrapper("TestEvent", mock_callback)
            wrapper(event)

            mock_callback.assert_called_once_with(event)

    def test_validating_callback_wrapper_invalid_event_strict(self):
        """Test callback wrapper with invalid event in strict mode."""
        mock_subscriber = Mock()
        mock_provider = Mock()
        mock_schema = {"type": "object"}
        mock_provider.get_schema.return_value = mock_schema

        subscriber = ValidatingEventSubscriber(
            subscriber=mock_subscriber,
            schema_provider=mock_provider,
            strict=True,
        )

        mock_callback = Mock()
        event = {"event_type": "TestEvent"}

        with patch("copilot_schema_validation.validate_json") as mock_validate:
            mock_validate.return_value = (False, ["Invalid field"])
            wrapper = subscriber._validating_callback_wrapper("TestEvent", mock_callback)

            with pytest.raises(SubscriberValidationError) as exc_info:
                wrapper(event)

            assert exc_info.value.event_type == "TestEvent"
            assert exc_info.value.errors == ["Invalid field"]
            mock_callback.assert_not_called()

    def test_validating_callback_wrapper_invalid_event_non_strict(self):
        """Test callback wrapper with invalid event in non-strict mode."""
        mock_subscriber = Mock()
        mock_provider = Mock()
        mock_schema = {"type": "object"}
        mock_provider.get_schema.return_value = mock_schema

        subscriber = ValidatingEventSubscriber(
            subscriber=mock_subscriber,
            schema_provider=mock_provider,
            strict=False,
        )

        mock_callback = Mock()
        event = {"event_type": "TestEvent"}

        with patch("copilot_schema_validation.validate_json") as mock_validate:
            mock_validate.return_value = (False, ["Invalid field"])
            wrapper = subscriber._validating_callback_wrapper("TestEvent", mock_callback)
            wrapper(event)

            # Callback should not be called
            mock_callback.assert_not_called()

    def test_validating_callback_wrapper_callback_error(self):
        """Test callback wrapper handles errors in original callback."""
        mock_subscriber = Mock()
        mock_provider = Mock()
        mock_schema = {"type": "object"}
        mock_provider.get_schema.return_value = mock_schema

        subscriber = ValidatingEventSubscriber(
            subscriber=mock_subscriber,
            schema_provider=mock_provider,
            strict=True,
        )

        mock_callback = Mock()
        mock_callback.side_effect = ValueError("Processing error")
        event = {"event_type": "TestEvent", "data": {}}

        with patch("copilot_schema_validation.validate_json") as mock_validate:
            mock_validate.return_value = (True, [])
            wrapper = subscriber._validating_callback_wrapper("TestEvent", mock_callback)

            with pytest.raises(ValueError) as exc_info:
                wrapper(event)

            assert "Processing error" in str(exc_info.value)
            mock_callback.assert_called_once_with(event)

    def test_connect_success(self):
        """Test successful connection."""
        mock_subscriber = Mock()
        mock_subscriber.connect.return_value = True

        subscriber = ValidatingEventSubscriber(subscriber=mock_subscriber)
        # Should not raise
        subscriber.connect()

        mock_subscriber.connect.assert_called_once()

    def test_connect_returns_none(self):
        """Test connect with None return (also success)."""
        mock_subscriber = Mock()
        mock_subscriber.connect.return_value = None

        subscriber = ValidatingEventSubscriber(subscriber=mock_subscriber)
        # Should not raise
        subscriber.connect()

        mock_subscriber.connect.assert_called_once()

    def test_connect_failure(self):
        """Test failed connection raises exception."""
        mock_subscriber = Mock()
        mock_subscriber.connect.side_effect = Exception("Connection failed")

        subscriber = ValidatingEventSubscriber(subscriber=mock_subscriber)

        with pytest.raises(Exception, match="Connection failed"):
            subscriber.connect()

    def test_disconnect(self):
        """Test disconnection."""
        mock_subscriber = Mock()

        subscriber = ValidatingEventSubscriber(subscriber=mock_subscriber)
        subscriber.disconnect()

        mock_subscriber.disconnect.assert_called_once()

    def test_subscribe(self):
        """Test subscribing to events."""
        mock_subscriber = Mock()
        mock_provider = Mock()
        mock_schema = {"type": "object"}
        mock_provider.get_schema.return_value = mock_schema

        subscriber = ValidatingEventSubscriber(
            subscriber=mock_subscriber,
            schema_provider=mock_provider,
        )

        mock_callback = Mock()

        with patch("copilot_schema_validation.validate_json") as mock_validate:
            mock_validate.return_value = (True, [])
            subscriber.subscribe(
                event_type="TestEvent",
                callback=mock_callback,
                routing_key="test.*",
            )

            # Check that callback was stored
            assert "TestEvent" in subscriber._callbacks
            assert subscriber._callbacks["TestEvent"] == mock_callback

            # Check that underlying subscriber was called
            mock_subscriber.subscribe.assert_called_once()
            call_kwargs = mock_subscriber.subscribe.call_args[1]
            assert call_kwargs["event_type"] == "TestEvent"
            assert call_kwargs["routing_key"] == "test.*"

    def test_start_consuming(self):
        """Test starting event consumption."""
        mock_subscriber = Mock()

        subscriber = ValidatingEventSubscriber(subscriber=mock_subscriber)
        subscriber.start_consuming()

        mock_subscriber.start_consuming.assert_called_once()

    def test_stop_consuming(self):
        """Test stopping event consumption."""
        mock_subscriber = Mock()

        subscriber = ValidatingEventSubscriber(subscriber=mock_subscriber)
        subscriber.stop_consuming()

        mock_subscriber.stop_consuming.assert_called_once()

    def test_integration_full_flow(self):
        """Test full flow: subscribe and process valid event."""
        mock_subscriber = Mock()
        mock_provider = Mock()
        mock_schema = {"type": "object"}
        mock_provider.get_schema.return_value = mock_schema

        subscriber = ValidatingEventSubscriber(
            subscriber=mock_subscriber,
            schema_provider=mock_provider,
            strict=True,
        )

        mock_callback = Mock()
        event = {"event_type": "TestEvent", "data": {"id": 1}}

        # Subscribe to event
        with patch("copilot_schema_validation.validate_json") as mock_validate:
            mock_validate.return_value = (True, [])
            subscriber.subscribe(
                event_type="TestEvent",
                callback=mock_callback,
            )

            # Get the wrapped callback that was passed to the underlying subscriber
            wrapped_callback = mock_subscriber.subscribe.call_args[1]["callback"]

            # Call the wrapped callback with a valid event
            wrapped_callback(event)

            # Original callback should be called
            mock_callback.assert_called_once_with(event)
