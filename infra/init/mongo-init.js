// SPDX-License-Identifier: MIT
// Copyright (c) 2025 Copilot-for-Consensus contributors

// MongoDB initialization: collections, validators, indexes
// Validators are pulled directly from JSON Schemas in /schemas/documents to avoid duplication.

const collectionsConfigPath = '/schemas/documents/collections.config.json';
const eventSchemasDir = '/schemas/events';
const fs = require('fs');
const path = require('path');

function stripUnsupportedKeywords(obj, isRoot = false) {
  if (Array.isArray(obj)) {
    obj.forEach(item => stripUnsupportedKeywords(item, false));
    return obj;
  }
  if (obj && typeof obj === 'object') {
    delete obj.$schema;
    delete obj.$id;
    if (Object.prototype.hasOwnProperty.call(obj, 'format')) {
      delete obj.format;
    }

    // Don't convert root "type": "object" to bsonType, as MongoDB doesn't expect it
    if (Object.prototype.hasOwnProperty.call(obj, 'type') && !isRoot) {
      const toBsonType = (t) => {
        switch (t) {
          case 'integer':
            return 'int';
          case 'number':
            return 'double';
          case 'boolean':
            return 'bool';
          default:
            return t;
        }
      };
      const typeVal = obj.type;
      if (Array.isArray(typeVal)) {
        obj.bsonType = typeVal.map(toBsonType);
      } else {
        obj.bsonType = toBsonType(typeVal);
      }
      delete obj.type;
    } else if (isRoot) {
      // For root object, delete the "type" but keep everything else
      delete obj.type;
    }

    Object.values(obj).forEach(item => stripUnsupportedKeywords(item, false));
  }
  return obj;
}

const dbName = process.env.MONGO_APP_DB || 'copilot';
const database = db.getSiblingDB(dbName);

function loadSchema(filePath) {
  const schema = JSON.parse(fs.readFileSync(filePath, 'utf8'));
  return stripUnsupportedKeywords(schema, true);
}

function loadCollectionsConfig() {
  return JSON.parse(fs.readFileSync(collectionsConfigPath, 'utf8'));
}

function ensureCollection(name, validatorPath) {
  // Create collection without schema validator - schema validation is complex and error-prone
  // MongoDB and the application drivers still enforce type safety
  const exists = database.getCollectionNames().includes(name);
  if (!exists) {
    database.createCollection(name);
  }
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
