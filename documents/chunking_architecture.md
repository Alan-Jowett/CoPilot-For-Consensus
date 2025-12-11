<!-- SPDX-License-Identifier: MIT
  Copyright (c) 2025 Copilot-for-Consensus contributors -->

# Thread Chunking Architecture

## Overview

This document describes the architecture of the thread chunking abstraction layer implemented in the Copilot-for-Consensus project.

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                          Services Layer                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐      │
│  │  Chunking    │    │  Embedding   │    │Summarization │      │
│  │  Service     │    │  Service     │    │  Service     │      │
│  └──────┬───────┘    └──────┬───────┘    └──────┬───────┘      │
│         │                   │                   │               │
│         └───────────────────┴───────────────────┘               │
│                             │                                    │
│                  Uses Chunk abstraction                          │
│                             │                                    │
└─────────────────────────────┼────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│              Chunking Abstraction Layer (SDK)                    │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  ┌────────────────────────────────────────────────────────┐     │
│  │           ThreadChunker (ABC)                          │     │
│  │  + chunk(thread: Thread) -> List[Chunk]               │     │
│  └───────────────────┬────────────────────────────────────┘     │
│                      │                                           │
│          ┌───────────┼───────────┐                              │
│          │           │           │                              │
│          ▼           ▼           ▼                              │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐                        │
│  │  Token   │ │  Fixed   │ │ Semantic │                        │
│  │  Window  │ │  Size    │ │ Chunker  │                        │
│  │ Chunker  │ │ Chunker  │ │          │                        │
│  └──────────┘ └──────────┘ └──────────┘                        │
│                                                                   │
│  ┌────────────────────────────────────────────────────────┐     │
│  │  Data Classes                                          │     │
│  │  - Thread: Input (thread_id, text, metadata, messages)│     │
│  │  - Chunk: Output (chunk_id, text, token_count, etc.)  │     │
│  └────────────────────────────────────────────────────────┘     │
│                                                                   │
│  ┌────────────────────────────────────────────────────────┐     │
│  │  Factory: create_chunker(strategy, **params)          │     │
│  └────────────────────────────────────────────────────────┘     │
│                                                                   │
└─────────────────────────────┬─────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                   Configuration Layer                            │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  Environment Variables:                                          │
│  - CHUNKING_STRATEGY (token_window|fixed_size|semantic)         │
│  - CHUNK_SIZE_TOKENS                                            │
│  - CHUNK_OVERLAP_TOKENS                                         │
│  - MESSAGES_PER_CHUNK                                           │
│  - MIN_CHUNK_SIZE_TOKENS                                        │
│  - MAX_CHUNK_SIZE_TOKENS                                        │
│                                                                   │
└───────────────────────────────────────────────────────────────────┘
```

## Component Details

### ThreadChunker (Abstract Interface)

**Purpose**: Defines the contract for all chunking strategies.

**Method**: `chunk(thread: Thread) -> List[Chunk]`

**Implementations**:
1. TokenWindowChunker
2. FixedSizeChunker
3. SemanticChunker

### Strategy 1: TokenWindowChunker

```
Input Text (100 words)
│
├─► Window 1 (words 0-50)  ──► Chunk 1 (50 words)
│    └─► Overlap: words 40-50
│
├─► Window 2 (words 40-90) ──► Chunk 2 (50 words)
│    └─► Overlap: words 80-90
│
└─► Window 3 (words 80-100) ─► Chunk 3 (20 words)
```

**Features**:
- Fixed-size windows with configurable overlap
- Ensures context preservation across boundaries
- Predictable chunk sizes

### Strategy 2: FixedSizeChunker

```
Thread with 10 messages
│
├─► Chunk 1: Messages 1-5
│
└─► Chunk 2: Messages 6-10
```

**Features**:
- Groups N consecutive messages
- Preserves conversation flow
- Maintains message boundaries

### Strategy 3: SemanticChunker

```
Text: "Sentence 1. Sentence 2. Sentence 3. Sentence 4. Sentence 5."
│
├─► Chunk 1: "Sentence 1. Sentence 2."
│   (approaching target size)
│
└─► Chunk 2: "Sentence 3. Sentence 4. Sentence 5."
    (approaching target size)
```

**Features**:
- Splits on sentence boundaries
- Groups sentences to approach target size
- Maintains semantic coherence

## Data Flow

### 1. Chunking Service Flow

```
Email Message/Thread
        │
        ▼
┌────────────────┐
│  Create Thread │
│  object        │
└────────┬───────┘
         │
         ▼
┌────────────────┐
│ Select Chunker │
│ (from config)  │
└────────┬───────┘
         │
         ▼
┌────────────────┐
│ chunk(thread)  │
└────────┬───────┘
         │
         ▼
  List[Chunk]
```

### 2. Embedding Service Flow

```
ChunksPrepared Event
        │
        ▼
┌────────────────┐
│ Retrieve Chunks│
│ from DB        │
└────────┬───────┘
         │
         ▼
┌────────────────┐
│ Generate       │
│ Embeddings     │
└────────┬───────┘
         │
         ▼
┌────────────────┐
│ Store in       │
│ Vector DB      │
└────────────────┘
```

### 3. Summarization Service Flow

```
SummarizationRequested Event
        │
        ▼
┌────────────────┐
│ Retrieve Top-K │
│ Chunks from    │
│ Vector Store   │
└────────┬───────┘
         │
         ▼
┌────────────────┐
│ Build Context  │
│ from Chunks    │
└────────┬───────┘
         │
         ▼
┌────────────────┐
│ Call LLM for   │
│ Summary        │
└────────┬───────┘
         │
         ▼
┌────────────────┐
│ Extract        │
│ Citations      │
└────────────────┘
```

## Strategy Selection

The factory method selects the appropriate strategy based on configuration:

```python
def create_chunker(strategy: str, **params) -> ThreadChunker:
    """
    Factory method for creating chunkers.
    
    Strategy mapping:
    - "token_window" → TokenWindowChunker
    - "fixed_size"   → FixedSizeChunker
    - "semantic"     → SemanticChunker
    """
    if strategy.lower() == "token_window":
        return TokenWindowChunker(**params)
    elif strategy.lower() == "fixed_size":
        return FixedSizeChunker(**params)
    elif strategy.lower() == "semantic":
        return SemanticChunker(**params)
    else:
        raise ValueError(f"Unknown strategy: {strategy}")
```

## Configuration Examples

### Example 1: Token Window with Default Settings

```bash
export CHUNKING_STRATEGY=token_window
export CHUNK_SIZE_TOKENS=384
export CHUNK_OVERLAP_TOKENS=50
```

Result: 384-token chunks with 50-token overlap

### Example 2: Fixed Size for Threaded Discussions

```bash
export CHUNKING_STRATEGY=fixed_size
export MESSAGES_PER_CHUNK=5
```

Result: 5 messages per chunk

### Example 3: Semantic for Well-Structured Content

```bash
export CHUNKING_STRATEGY=semantic
export CHUNK_SIZE_TOKENS=400
```

Result: Sentence-based chunks approaching 400 tokens

## Integration Points

### Service Integration

All services interact with chunks through the standard Chunk interface:

```python
@dataclass
class Chunk:
    chunk_id: str
    text: str
    chunk_index: int
    token_count: int
    metadata: Dict[str, Any]
    start_offset: Optional[int] = None
    end_offset: Optional[int] = None
```

Services don't need to know which chunking strategy was used - they just process Chunk objects.

### Event Flow

```
Parsing Service
      │
      ▼
 JSONParsed Event
      │
      ▼
Chunking Service ──┐
      │            │ Uses ThreadChunker abstraction
      ▼            │
ChunksPrepared ◄───┘
      │
      ├──► Embedding Service
      │
      └──► (Orchestration Service)
                │
                ▼
          Summarization Service
```

## Benefits

### 1. Flexibility
- Switch strategies via configuration
- No code changes required
- Easy experimentation

### 2. Modularity
- Clean separation of concerns
- Strategy logic isolated from services
- Easy to add new strategies

### 3. Consistency
- Uniform interface across strategies
- Predictable behavior for services
- Standard metadata handling

### 4. Testability
- Independent testing of strategies
- Mock chunks for service tests
- Integration tests work with any strategy

## Future Enhancements

1. **Advanced Tokenization**
   - Replace word-based counting with tiktoken
   - Support for different encoding models

2. **Semantic Similarity**
   - Use embeddings for semantic chunking
   - Group similar content together

3. **Speaker Detection**
   - Identify speaker turns in conversations
   - Split on speaker boundaries

4. **Adaptive Sizing**
   - Adjust chunk size based on content density
   - Dynamic overlap based on context importance

5. **Quality Metrics**
   - Score chunk quality
   - Optimize for embedding relevance

## References

- [Chunking Implementation](../adapters/copilot_chunking/copilot_chunking/chunkers.py)
- [Chunking Documentation](../adapters/copilot_chunking/README.md)
- [Chunking Service README](../chunking/README.md)
- [Test Suite](../adapters/copilot_chunking/tests/test_chunkers.py)
