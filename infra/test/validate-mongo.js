/* SPDX-License-Identifier: MIT
 * Copyright (c) 2025 Copilot-for-Consensus contributors
 */

// Validate Mongo collections, validators, and index names from collections.config.json.
// Also validates that event_schemas collection is populated with all event types.
// Exits non-zero on first failure to halt startup/CI.

const fs = require('fs');
const path = require('path');

const dbName = process.env.MONGO_APP_DB || 'copilot';
const configPath = path.join('/schemas', 'documents', 'collections.config.json');
const eventSchemasDir = '/schemas/events';

function loadConfig() {
  const raw = fs.readFileSync(configPath, 'utf8');
  const parsed = JSON.parse(raw);
  if (!parsed.collections || !Array.isArray(parsed.collections)) {
    throw new Error('collections.config.json is missing "collections" array');
  }
  return parsed.collections;
}

function validateCollections(targetDb, expectedCollections) {
  const existing = targetDb.getCollectionNames();

  expectedCollections.forEach((coll) => {
    if (!existing.includes(coll.name)) {
      throw new Error(`Missing collection: ${coll.name}`);
    }

    const info = targetDb.getCollectionInfos({ name: coll.name })[0] || {};
    if (!info.options || !info.options.validator) {
      throw new Error(`Missing validator on collection: ${coll.name}`);
    }

    const presentIndexes = targetDb.getCollection(coll.name).getIndexes().map((i) => i.name);
    (coll.indexes || []).forEach((idx) => {
      const idxName = idx.options && idx.options.name;
      if (!idxName) {
        throw new Error(`Index entry missing name for collection: ${coll.name}`);
      }
      if (!presentIndexes.includes(idxName)) {
        throw new Error(`Missing index '${idxName}' on collection '${coll.name}'`);
      }
    });
  });
}

function validateEventSchemas(targetDb) {
  const collName = 'event_schemas';
  const existing = targetDb.getCollectionNames();
  if (!existing.includes(collName)) {
    throw new Error(`Missing collection: ${collName}`);
  }

  const coll = targetDb.getCollection(collName);
  const eventFiles = fs.readdirSync(eventSchemasDir)
    .filter((f) => f.toLowerCase().endsWith('.json'));

  if (eventFiles.length === 0) {
    throw new Error('No event schema files found in /schemas/events');
  }

  const storedCount = coll.countDocuments({});
  if (storedCount !== eventFiles.length) {
    throw new Error(
      `Event schemas count mismatch: found ${eventFiles.length} files but only ${storedCount} documents in collection`
    );
  }

  // Verify each expected event type is present
  eventFiles.forEach((file) => {
    const name = file.replace(/\.schema\.json$/i, '').replace(/\.json$/i, '');
    const doc = coll.findOne({ name });
    if (!doc) {
      throw new Error(`Missing event schema document for: ${name}`);
    }
    if (!doc.schema || typeof doc.schema !== 'object') {
      throw new Error(`Event schema document for '${name}' missing or invalid schema field`);
    }
  });
}

(() => {
  const collections = loadConfig();
  const targetDb = db.getSiblingDB(dbName);
  validateCollections(targetDb, collections);
  validateEventSchemas(targetDb);
  print(`Mongo validation succeeded for db '${dbName}'`);
})();
