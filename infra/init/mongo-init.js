// SPDX-License-Identifier: MIT
// Copyright (c) 2025 Copilot-for-Consensus contributors

// MongoDB initialization: collections and indexes
// Note: JSON Schema validators are NOT applied to avoid MongoDB compatibility issues.
// Schemas in /schemas/documents are maintained for documentation purposes only.

const collectionsConfigPath = '/schemas/documents/collections.config.json';
const fs = require('fs');

const dbName = process.env.MONGO_APP_DB || 'copilot';
const database = db.getSiblingDB(dbName);

function loadCollectionsConfig() {
  return JSON.parse(fs.readFileSync(collectionsConfigPath, 'utf8'));
}

function ensureCollection(name, validatorPath) {
  const exists = database.getCollectionNames().includes(name);
  if (!exists) {
    database.createCollection(name);
  }
  // Note: Validators are not applied to avoid MongoDB compatibility issues.
  // JSON schemas in /schemas/documents are maintained for documentation purposes only.
}

function ensureIndexes(name, indexSpecs) {
  const coll = database.getCollection(name);
  indexSpecs.forEach((spec) => {
    coll.createIndex(spec.keys, spec.options || {});
  });
}

function ensureFromConfig(definition) {
  if (!definition.name) {
    print('Skipping collection without name in config');
    return;
  }

  if (!definition.schema) {
    print(`Skipping collection '${definition.name}' because schema path is missing`);
    return;
  }

  ensureCollection(definition.name, definition.schema);

  if (Array.isArray(definition.indexes) && definition.indexes.length > 0) {
    ensureIndexes(definition.name, definition.indexes);
  }
}

const config = loadCollectionsConfig();
if (!config.collections || !Array.isArray(config.collections)) {
  throw new Error(`No collections found in ${collectionsConfigPath}`);
}

config.collections.forEach((definition) => ensureFromConfig(definition));

print(`Mongo init completed for database '${dbName}'`);
