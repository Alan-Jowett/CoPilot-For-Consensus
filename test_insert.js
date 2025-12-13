use('copilot')
try {
  db.messages.insertOne({
    message_id: 'test123', 
    archive_id: '00000000-0000-0000-0000-000000000000', 
    thread_id: 'thread1', 
    date: new ISODate('2025-01-01T00:00:00Z'), 
    body_normalized: 'test', 
    created_at: new ISODate('2025-01-01T00:00:00Z')
  })
  print('Success')
} catch(e) {
  print('Error: ' + e.message)
}
