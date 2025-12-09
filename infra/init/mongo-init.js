// SPDX-License-Identifier: MIT
// MongoDB initialization: collections, validators, indexes
// Validators are pulled directly from JSON Schemas in /schemas/documents to avoid duplication.

const dbName = process.env.MONGO_APP_DB || 'copilot';
const database = db.getSiblingDB(dbName);

function loadSchema(filePath) {
  // mongosh provides cat(); parse to JSON
  return JSON.parse(cat(filePath));
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

// archives
ensureCollection('archives', '/schemas/documents/archives.schema.json');
ensureIndexes('archives', [
  { keys: { archive_id: 1 }, options: { unique: true, name: 'archive_id_unique' } },
  { keys: { source: 1 }, options: { name: 'source_idx' } },
  { keys: { ingestion_date: 1 }, options: { name: 'ingestion_date_idx' } },
  { keys: { status: 1 }, options: { name: 'status_idx' } }
]);

// messages
ensureCollection('messages', '/schemas/documents/messages.schema.json');
ensureIndexes('messages', [
  { keys: { message_id: 1 }, options: { unique: true, name: 'message_id_unique' } },
  { keys: { archive_id: 1 }, options: { name: 'archive_id_idx' } },
  { keys: { thread_id: 1 }, options: { name: 'thread_id_idx' } },
  { keys: { date: 1 }, options: { name: 'date_idx' } },
  { keys: { in_reply_to: 1 }, options: { name: 'in_reply_to_idx' } },
  { keys: { draft_mentions: 1 }, options: { name: 'draft_mentions_idx' } },
  { keys: { created_at: 1 }, options: { name: 'created_at_idx' } }
]);

// chunks
ensureCollection('chunks', '/schemas/documents/chunks.schema.json');
ensureIndexes('chunks', [
  { keys: { chunk_id: 1 }, options: { unique: true, name: 'chunk_id_unique' } },
  { keys: { message_id: 1 }, options: { name: 'message_id_idx' } },
  { keys: { thread_id: 1 }, options: { name: 'thread_id_idx' } },
  { keys: { created_at: 1 }, options: { name: 'created_at_idx' } },
  { keys: { embedding_generated: 1 }, options: { name: 'embedding_generated_idx' } }
]);

// threads
ensureCollection('threads', '/schemas/documents/threads.schema.json');
ensureIndexes('threads', [
  { keys: { thread_id: 1 }, options: { unique: true, name: 'thread_id_unique' } },
  { keys: { archive_id: 1 }, options: { name: 'archive_id_idx' } },
  { keys: { first_message_date: 1 }, options: { name: 'first_message_date_idx' } },
  { keys: { last_message_date: 1 }, options: { name: 'last_message_date_idx' } },
  { keys: { draft_mentions: 1 }, options: { name: 'draft_mentions_idx' } },
  { keys: { has_consensus: 1 }, options: { name: 'has_consensus_idx' } },
  { keys: { summary_id: 1 }, options: { name: 'summary_id_idx' } },
  { keys: { created_at: 1 }, options: { name: 'created_at_idx' } }
]);

// summaries
ensureCollection('summaries', '/schemas/documents/summaries.schema.json');
ensureIndexes('summaries', [
  { keys: { summary_id: 1 }, options: { unique: true, name: 'summary_id_unique' } },
  { keys: { thread_id: 1 }, options: { name: 'thread_id_idx' } },
  { keys: { summary_type: 1 }, options: { name: 'summary_type_idx' } },
  { keys: { generated_at: 1 }, options: { name: 'generated_at_idx' } }
]);

print(`Mongo init completed for database '${dbName}'`);
