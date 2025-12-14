// SPDX-License-Identifier: MIT
// Copyright (c) 2025 Copilot-for-Consensus contributors

// Simple smoke test: insert a minimal messages document to verify Mongo accepts it.
// Usage from container:
//   mongosh "mongodb://${MONGO_INITDB_ROOT_USERNAME}:${MONGO_INITDB_ROOT_PASSWORD}@documentdb:27017/admin" /test/test_insert.js
// Usage from host (default credentials):
//   mongosh "mongodb://admin:PLEASE_CHANGE_ME@localhost:27017/admin" /path/to/test_insert.js

const dbName = process.env.MONGO_APP_DB || 'copilot';
const database = db.getSiblingDB(dbName);

// Minimal messages document satisfying required fields from messages.schema.json
const testMessage = {
  message_id: 'smoke-test-message-001',
  archive_id: '00000000-0000-0000-0000-000000000001',
  thread_id: 'smoke-test-thread-001',
  date: new Date().toISOString(),
  body_normalized: 'This is a smoke test message to verify MongoDB schema acceptance.',
  created_at: new Date().toISOString()
};

try {
  const result = database.getCollection('messages').insertOne(testMessage);
  
  if (result.acknowledged && result.insertedId) {
    print('✓ Success: Message inserted with _id:', result.insertedId);
    print('  message_id:', testMessage.message_id);
    print('  Verify with: db.messages.findOne({message_id: "smoke-test-message-001"})');
  } else {
    print('✗ Failed: Insert not acknowledged');
    quit(1);
  }
} catch (error) {
  print('✗ Error inserting message:', error.message);
  quit(1);
}
