<!-- SPDX-License-Identifier: MIT
  Copyright (c) 2025 Copilot-for-Consensus contributors -->

# Schema Versioning Guide

This document outlines the versioning strategy for all JSON Schemas used in the Copilot for Consensus project, including event schemas and document schemas. It ensures long-term compatibility, contributor clarity, and safe schema evolution.

---

## 📦 Schema Types

We maintain two categories of schemas:

- Event Schemas: Define the structure of messages passed through the pub/sub pipeline (e.g., ThreadParsed, SummaryGenerated)
- Document Schemas: Define the structure of IETF drafts, diffs, and metadata (e.g., draft.schema.json, draft-diff.schema.json)

---

## 🧱 Versioning Strategy

All schemas are versioned using a directory-based approach:

`
documents/
  schemas/
    events/
      v1/
        thread-parsed.schema.json
        summary-generated.schema.json
    documents/
      v1/
        draft.schema.json
        draft-diff.schema.json
`

Each schema version is immutable. Any breaking change (e.g., removing a field, changing a type) must result in a new version (e.g., v2/).

---

## 🧩 Envelope Versioning

All events are wrapped in a shared envelope defined in event-envelope.schema.json, which includes:

`json
{
  "type": "ThreadParsed",
  "version": "v1",
  "payload": { ... }
}
`

This allows services to dynamically resolve and validate the correct schema for the payload.

---

## 🔍 Schema Registry

A centralized schema registry maps (type, version) pairs to schema file paths. This enables:

- Dynamic validation at runtime
- Support for multiple versions in parallel
- Clear contributor expectations

Example:

`python
SCHEMA_REGISTRY = {
  "v1.ThreadParsed": "schemas/events/v1/thread-parsed.schema.json",
  "v1.Draft": "schemas/documents/v1/draft.schema.json",
}
`

---

## 🔄 Making Schema Changes

- ✅ Non-breaking changes (e.g., adding optional fields) may be allowed within a version
- ❌ Breaking changes (e.g., removing fields, changing types) require a new version
- 🧪 All changes must be accompanied by updated tests and example payloads

---

#$ 📚 Contributor Tips

- Always validate your payloads against the correct schema version
- Use the schema registry to resolve schemas dynamically
- When in doubt, create a new version rather than modifying an existing one
