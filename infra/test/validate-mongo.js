/* SPDX-License-Identifier: MIT
 * Copyright (c) 2025 Copilot-for-Consensus contributors
 */

// Validate Mongo collections and index names from collections.config.json.
// Exits non-zero on first failure to halt startup/CI.
// Note: Schema validation is now handled at the application layer, not at MongoDB level.

const fs = require('fs');
const path = require('path');

const dbName = process.env.MONGO_APP_DB || 'copilot';
const configPath = path.join('/schemas', 'documents', 'collections.config.json');

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

(() => {
  const collections = loadConfig();
  const targetDb = db.getSiblingDB(dbName);
  validateCollections(targetDb, collections);
  print(`Mongo validation succeeded for db '${dbName}'`);
})();
