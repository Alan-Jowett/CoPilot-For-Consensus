// SPDX-License-Identifier: MIT
// MongoDB initialization: collections, validators, indexes
// Validators are pulled directly from JSON Schemas in /schemas/documents to avoid duplication.

const collectionsConfigPath = '/schemas/documents/collections.config.json';
const fs = require('fs');

function stripUnsupportedKeywords(obj) {
  if (Array.isArray(obj)) {
    obj.forEach(stripUnsupportedKeywords);
    return obj;
  }
  if (obj && typeof obj === 'object') {
    delete obj.$schema;
    delete obj.$id;
    if (Object.prototype.hasOwnProperty.call(obj, 'format')) {
      delete obj.format;
    }

    if (Object.prototype.hasOwnProperty.call(obj, 'type')) {
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
    }

    Object.values(obj).forEach(stripUnsupportedKeywords);
  }
  return obj;
}

const dbName = process.env.MONGO_APP_DB || 'copilot';
const database = db.getSiblingDB(dbName);

function loadSchema(filePath) {
  const schema = JSON.parse(fs.readFileSync(filePath, 'utf8'));
  return stripUnsupportedKeywords(schema);
}

function loadCollectionsConfig() {
  return JSON.parse(fs.readFileSync(collectionsConfigPath, 'utf8'));
}

function ensureCollection(name, validatorPath) {
  const validator = { $jsonSchema: loadSchema(validatorPath) };
  const exists = database.getCollectionNames().includes(name);
  if (!exists) {
    database.createCollection(name, { validator });
  } else {
    database.runCommand({ collMod: name, validator });
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
