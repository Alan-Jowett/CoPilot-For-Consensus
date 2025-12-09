// SPDX-License-Identifier: MIT
// MongoDB initialization: collections, validators, indexes

const dbName = process.env.MONGO_APP_DB || 'copilot';
const database = db.getSiblingDB(dbName);

function ensureCollection(name, validator) {
  const exists = database.getCollectionNames().includes(name);
  if (!exists) {
    database.createCollection(name, { validator });
  } else if (validator) {
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
ensureCollection('archives', {
  $jsonSchema: {
    bsonType: 'object',
    required: ['archive_id', 'source', 'ingestion_date', 'status'],
    additionalProperties: false,
    properties: {
      archive_id: { bsonType: 'string' },
      source: { bsonType: 'string' },
      source_url: { bsonType: 'string' },
      format: { bsonType: 'string' },
      ingestion_date: { bsonType: 'date' },
      message_count: { bsonType: 'int' },
      file_path: { bsonType: 'string' },
      status: { bsonType: 'string', enum: ['pending', 'processed', 'failed'] }
    }
  }
});
ensureIndexes('archives', [
  { keys: { archive_id: 1 }, options: { unique: true, name: 'archive_id_unique' } },
  { keys: { source: 1 }, options: { name: 'source_idx' } },
  { keys: { ingestion_date: 1 }, options: { name: 'ingestion_date_idx' } },
  { keys: { status: 1 }, options: { name: 'status_idx' } }
]);

// messages
ensureCollection('messages', {
  $jsonSchema: {
    bsonType: 'object',
    required: ['message_id', 'archive_id', 'thread_id', 'date', 'body_normalized', 'created_at'],
    additionalProperties: false,
    properties: {
      message_id: { bsonType: 'string' },
      archive_id: { bsonType: 'string' },
      thread_id: { bsonType: 'string' },
      in_reply_to: { bsonType: 'string' },
      references: { bsonType: 'array', items: { bsonType: 'string' } },
      subject: { bsonType: 'string' },
      from: {
        bsonType: 'object',
        required: ['email'],
        additionalProperties: false,
        properties: {
          name: { bsonType: 'string' },
          email: { bsonType: 'string' }
        }
      },
      to: {
        bsonType: 'array',
        items: {
          bsonType: 'object',
          required: ['email'],
          additionalProperties: false,
          properties: {
            name: { bsonType: 'string' },
            email: { bsonType: 'string' }
          }
        }
      },
      cc: {
        bsonType: 'array',
        items: {
          bsonType: 'object',
          required: ['email'],
          additionalProperties: false,
          properties: {
            name: { bsonType: 'string' },
            email: { bsonType: 'string' }
          }
        }
      },
      date: { bsonType: 'date' },
      body_raw: { bsonType: 'string' },
      body_normalized: { bsonType: 'string' },
      body_html: { bsonType: 'string' },
      headers: { bsonType: 'object' },
      attachments: {
        bsonType: 'array',
        items: {
          bsonType: 'object',
          required: ['filename', 'content_type', 'size_bytes'],
          additionalProperties: false,
          properties: {
            filename: { bsonType: 'string' },
            content_type: { bsonType: 'string' },
            size_bytes: { bsonType: 'int' },
            hash_sha256: { bsonType: 'string' }
          }
        }
      },
      draft_mentions: { bsonType: 'array', items: { bsonType: 'string' } },
      created_at: { bsonType: 'date' }
    }
  }
});
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
ensureCollection('chunks', {
  $jsonSchema: {
    bsonType: 'object',
    required: ['chunk_id', 'message_id', 'thread_id', 'chunk_index', 'text', 'created_at', 'embedding_generated'],
    additionalProperties: false,
    properties: {
      chunk_id: { bsonType: 'string' },
      message_id: { bsonType: 'string' },
      thread_id: { bsonType: 'string' },
      chunk_index: { bsonType: 'int' },
      text: { bsonType: 'string' },
      token_count: { bsonType: 'int' },
      start_offset: { bsonType: 'int' },
      end_offset: { bsonType: 'int' },
      overlap_with_previous: { bsonType: 'bool' },
      metadata: { bsonType: 'object' },
      created_at: { bsonType: 'date' },
      embedding_generated: { bsonType: 'bool' }
    }
  }
});
ensureIndexes('chunks', [
  { keys: { chunk_id: 1 }, options: { unique: true, name: 'chunk_id_unique' } },
  { keys: { message_id: 1 }, options: { name: 'message_id_idx' } },
  { keys: { thread_id: 1 }, options: { name: 'thread_id_idx' } },
  { keys: { created_at: 1 }, options: { name: 'created_at_idx' } },
  { keys: { embedding_generated: 1 }, options: { name: 'embedding_generated_idx' } }
]);

// threads
ensureCollection('threads', {
  $jsonSchema: {
    bsonType: 'object',
    required: ['thread_id', 'archive_id', 'first_message_date', 'last_message_date', 'has_consensus', 'created_at'],
    additionalProperties: false,
    properties: {
      thread_id: { bsonType: 'string' },
      archive_id: { bsonType: 'string' },
      subject: { bsonType: 'string' },
      participants: {
        bsonType: 'array',
        items: {
          bsonType: 'object',
          required: ['email'],
          additionalProperties: false,
          properties: {
            name: { bsonType: 'string' },
            email: { bsonType: 'string' }
          }
        }
      },
      message_count: { bsonType: 'int' },
      first_message_date: { bsonType: 'date' },
      last_message_date: { bsonType: 'date' },
      draft_mentions: { bsonType: 'array', items: { bsonType: 'string' } },
      has_consensus: { bsonType: 'bool' },
      consensus_type: { bsonType: 'string' },
      summary_id: { bsonType: 'string' },
      created_at: { bsonType: 'date' }
    }
  }
});
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
ensureCollection('summaries', {
  $jsonSchema: {
    bsonType: 'object',
    required: ['summary_id', 'summary_type', 'generated_at', 'content_markdown'],
    additionalProperties: false,
    properties: {
      summary_id: { bsonType: 'string' },
      thread_id: { bsonType: 'string' },
      summary_type: { bsonType: 'string' },
      title: { bsonType: 'string' },
      content_markdown: { bsonType: 'string' },
      content_html: { bsonType: 'string' },
      citations: { bsonType: 'array', items: { bsonType: 'object' } },
      generated_by: { bsonType: 'string' },
      generated_at: { bsonType: 'date' },
      metadata: { bsonType: 'object' }
    }
  }
});
ensureIndexes('summaries', [
  { keys: { summary_id: 1 }, options: { unique: true, name: 'summary_id_unique' } },
  { keys: { thread_id: 1 }, options: { name: 'thread_id_idx' } },
  { keys: { summary_type: 1 }, options: { name: 'summary_type_idx' } },
  { keys: { generated_at: 1 }, options: { name: 'generated_at_idx' } }
]);

print(`Mongo init completed for database '${dbName}'`);
