# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Integration-style unit tests for validation in publisher/subscriber flows."""

import json
import sys
import types

import pytest

from copilot_events.rabbitmq_publisher import RabbitMQPublisher
from copilot_events.rabbitmq_subscriber import RabbitMQSubscriber


class DummySchemaProvider:
    """Simple schema provider for tests."""

    def __init__(self, schema):
        self._schema = schema

    def get_schema(self, event_type):
        return self._schema if event_type == self._schema.get("title", event_type) else None

    def list_event_types(self):
        return [self._schema.get("title")]


class DummyChannel:
    def __init__(self):
        self.published = False
        self.publish_kwargs = None

    def basic_publish(self, **kwargs):
        self.published = True
        self.publish_kwargs = kwargs


class DummyMethod:
    def __init__(self):
        self.delivery_tag = 1


class DummyAckChannel:
    def __init__(self):
        self.acked = False
        self.nacked = False
        self.requeue = None

    def basic_ack(self, delivery_tag):
        self.acked = True
        self.delivery_tag = delivery_tag

    def basic_nack(self, delivery_tag, requeue=False):
        self.nacked = True
        self.delivery_tag = delivery_tag
        self.requeue = requeue


@pytest.fixture(autouse=True)
def stub_pika(monkeypatch):
    """Stub the pika module so BasicProperties is available without RabbitMQ."""

    class BasicProperties:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

    dummy = types.SimpleNamespace(BasicProperties=BasicProperties)
    monkeypatch.setitem(sys.modules, "pika", dummy)
    yield
    monkeypatch.delitem(sys.modules, "pika", raising=False)


def _simple_schema(event_type="TestEvent"):
    return {
        "title": event_type,
        "type": "object",
        "properties": {
            "event_type": {"const": event_type},
            "value": {"type": "integer"},
        },
        "required": ["event_type", "value"],
        "additionalProperties": False,
    }


def test_publisher_validation_success():
    provider = DummySchemaProvider(_simple_schema())
    pub = RabbitMQPublisher(validate_events=True, schema_provider=provider)
    pub.channel = DummyChannel()  # bypass real connection

    event = {"event_type": "TestEvent", "value": 1}
    ok = pub.publish(exchange="x", routing_key="rk", event=event)

    assert ok is True
    assert pub.channel.published is True


def test_publisher_validation_failure_blocks_publish():
    provider = DummySchemaProvider(_simple_schema())
    pub = RabbitMQPublisher(validate_events=True, schema_provider=provider)
    pub.channel = DummyChannel()

    event = {"event_type": "TestEvent"}  # missing required value
    ok = pub.publish(exchange="x", routing_key="rk", event=event)

    assert ok is False
    assert pub.channel.published is False


def test_subscriber_validation_success_ack():
    provider = DummySchemaProvider(_simple_schema("SubEvent"))
    sub = RabbitMQSubscriber(
        host="localhost",
        validate_events=True,
        schema_provider=provider,
        auto_ack=False,
    )
    sub.callbacks["SubEvent"] = lambda evt: None

    channel = DummyAckChannel()
    method = DummyMethod()
    body = json.dumps({"event_type": "SubEvent", "value": 2}).encode()

    sub._on_message(channel, method, None, body)

    assert channel.acked is True
    assert channel.nacked is False


def test_subscriber_validation_failure_nack():
    provider = DummySchemaProvider(_simple_schema("SubEvent"))
    sub = RabbitMQSubscriber(
        host="localhost",
        validate_events=True,
        schema_provider=provider,
        auto_ack=False,
    )
    sub.callbacks["SubEvent"] = lambda evt: None

    channel = DummyAckChannel()
    method = DummyMethod()
    body = json.dumps({"event_type": "SubEvent"}).encode()  # missing value

    sub._on_message(channel, method, None, body)

    assert channel.nacked is True
    assert channel.requeue is False
