<!-- SPDX-License-Identifier: MIT
  Copyright (c) 2025 Copilot-for-Consensus contributors -->

# Text Chunking Strategy

Abstraction layer for splitting long messages into semantically coherent chunks suitable for embedding.

## Architecture

```
Services (Chunking, Embedding, Summarization)
           ↓
    Uses Chunk abstraction
           ↓
    ThreadChunker (ABC)
         ↙   ↓   ↖
   Token  Fixed  Semantic
   Window  Size  Chunker
```

## Chunking Strategies

| Strategy | Implementation | Best For | Overhead |
|----------|----------------|----------|----------|
| **Token Window** | Token counter + sliding window | Balanced splitting (default) | Low |
| **Fixed Size** | Character-based chunks | Consistent chunk sizes | Low |
| **Semantic** | Sentence/paragraph boundaries | Meaning preservation | High |

## Input/Output

**Input** (Thread):
- `thread_id`: Unique identifier
- `text`: Full message body
- `metadata`: Sender, date, subject, etc.
- `messages`: List of constituent messages

**Output** (Chunk):
- `chunk_id`: Deterministic hash (thread_id + index)
- `text`: Chunk content
- `token_count`: Approximate token count
- `start_offset`, `end_offset`: Position in original text
- `overlap_with_previous`: Boolean (for context windows)
- `metadata`: Preserved from message level

## Configuration

**.env**:
```
CHUNK_STRATEGY=token_window  # or fixed_size, semantic
CHUNK_SIZE=512               # tokens or characters depending on strategy
CHUNK_OVERLAP=50             # for context preservation
```

## Usage in Services

```python
from copilot_chunking import create_chunker

chunker = create_chunker(strategy="token_window")
chunks = chunker.chunk(thread)  # Returns List[Chunk]

for chunk in chunks:
    print(f"Chunk {chunk.chunk_id}: {len(chunk.text)} chars, {chunk.token_count} tokens")
```

For detailed implementation, see [adapters/copilot_chunking/README.md](../../adapters/copilot_chunking/README.md) and [chunking/README.md](../../chunking/README.md).
