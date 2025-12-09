// SPDX-License-Identifier: MIT
// MongoDB initialization: collections, validators, indexes
// Validators are pulled directly from JSON Schemas in /schemas/documents to avoid duplication.

const collectionsConfigPath = '/schemas/documents/collections.config.json';

const dbName = process.env.MONGO_APP_DB || 'copilot';
const database = db.getSiblingDB(dbName);

function loadSchema(filePath) {
  // mongosh provides cat(); parse to JSON
  return JSON.parse(cat(filePath));
}

function loadCollectionsConfig() {
  return JSON.parse(cat(collectionsConfigPath));
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
