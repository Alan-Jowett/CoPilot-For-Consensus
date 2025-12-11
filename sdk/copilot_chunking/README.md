<!-- SPDX-License-Identifier: MIT
  Copyright (c) 2025 Copilot-for-Consensus contributors -->

# Thread Chunking Abstraction Layer

## Overview

The thread chunking abstraction layer provides a flexible, pluggable interface for breaking up email threads into smaller, semantically coherent chunks before embedding or summarization. This enables experimentation with different chunking strategies to optimize summarization quality and embedding relevance.

## Architecture

### Core Components

1. **ThreadChunker (Abstract Interface)**: Base class defining the chunking interface
2. **Chunk (Data Class)**: Represents a single chunk with text and metadata
3. **Thread (Data Class)**: Represents an email thread or message to be chunked
4. **Concrete Implementations**:
   - `TokenWindowChunker`: Sliding window based on token count
   - `FixedSizeChunker`: Fixed number of messages per chunk
   - `SemanticChunker`: Sentence boundary-based chunking
5. **Factory Method**: `create_chunker()` for instantiating chunkers from configuration

## Quick Start

### Basic Usage

```python
from copilot_chunking import Thread, create_chunker

# Create a thread
thread = Thread(
    thread_id="<msg123@example.com>",
    text="Your email content here...",
    metadata={
        "sender": "alice@example.com",
        "subject": "Discussion topic",
        "date": "2023-10-15T12:00:00Z"
    }
)

# Create a chunker (token window strategy)
chunker = create_chunker("token_window", chunk_size=384, overlap=50)

# Chunk the thread
chunks = chunker.chunk(thread)

# Process chunks
for chunk in chunks:
    print(f"Chunk {chunk.chunk_index}: {chunk.token_count} tokens")
    print(f"Text: {chunk.text[:100]}...")
```

### Using Different Strategies

```python
# Token Window Chunker (default)
chunker = create_chunker(
    strategy="token_window",
    chunk_size=384,
    overlap=50,
    min_chunk_size=100,
    max_chunk_size=512
)

# Fixed Size Chunker
chunker = create_chunker(
    strategy="fixed_size",
    messages_per_chunk=5
)

# Semantic Chunker
chunker = create_chunker(
    strategy="semantic",
    chunk_size=400
)
```

## Chunking Strategies

### 1. TokenWindowChunker

**Purpose**: Split text using a sliding window based on token count with configurable overlap.

**Use Cases**:
- General-purpose chunking for embedding models with token limits
- When you need predictable, uniform chunk sizes
- When context preservation across chunks is important

**Configuration**:
```python
TokenWindowChunker(
    chunk_size=384,        # Target chunk size in tokens
    overlap=50,            # Overlap between consecutive chunks
    min_chunk_size=100,    # Minimum chunk size (discard smaller)
    max_chunk_size=512     # Maximum chunk size (hard limit)
)
```

**Behavior**:
- Splits text into windows of approximately `chunk_size` tokens
- Overlaps consecutive windows by `overlap` tokens to preserve context
- Discards chunks smaller than `min_chunk_size` (except the last chunk)
- Never exceeds `max_chunk_size`

**Example**:
```python
from copilot_chunking import TokenWindowChunker, Thread

chunker = TokenWindowChunker(chunk_size=200, overlap=20)
thread = Thread(
    thread_id="test",
    text="Long email text...",
    metadata={"sender": "user@example.com"}
)
chunks = chunker.chunk(thread)
```

### 2. FixedSizeChunker

**Purpose**: Group N consecutive messages together, preserving conversation flow.

**Use Cases**:
- When processing threaded discussions
- When message boundaries are important
- When you want to preserve conversational context

**Configuration**:
```python
FixedSizeChunker(
    messages_per_chunk=5   # Number of messages per chunk
)
```

**Behavior**:
- Groups exactly N messages into each chunk (except possibly the last)
- Works with explicit message lists or text split by paragraph breaks
- Preserves message IDs and metadata for each message in the chunk

**Example with explicit messages**:
```python
from copilot_chunking import FixedSizeChunker, Thread

chunker = FixedSizeChunker(messages_per_chunk=3)
thread = Thread(
    thread_id="thread-001",
    text="",
    metadata={"subject": "Discussion"},
    messages=[
        {"message_id": "msg1", "text": "First message"},
        {"message_id": "msg2", "text": "Second message"},
        {"message_id": "msg3", "text": "Third message"},
        {"message_id": "msg4", "text": "Fourth message"},
    ]
)
chunks = chunker.chunk(thread)
# Result: 2 chunks (3 messages in first, 1 in second)
```

**Example with text blocks**:
```python
# Text split by double newlines is treated as separate messages
thread = Thread(
    thread_id="thread-002",
    text="Message 1\n\nMessage 2\n\nMessage 3\n\nMessage 4",
    metadata={"subject": "Discussion"}
)
chunks = chunker.chunk(thread)
```

### 3. SemanticChunker

**Purpose**: Split text on sentence boundaries for semantic coherence.

**Use Cases**:
- When preserving complete sentences is important
- When semantic coherence matters more than fixed sizes
- When working with well-structured prose

**Configuration**:
```python
SemanticChunker(
    target_chunk_size=400,  # Target size (groups sentences to approach this)
    split_on_speaker=False  # Future: split on speaker changes
)
```

**Behavior**:
- Splits text into sentences using regex patterns
- Groups sentences until target chunk size is approached
- Creates a new chunk when adding another sentence would exceed the target
- Always preserves complete sentences (never splits mid-sentence)

**Example**:
```python
from copilot_chunking import SemanticChunker, Thread

chunker = SemanticChunker(target_chunk_size=300)
thread = Thread(
    thread_id="test",
    text=(
        "First sentence. Second sentence with more detail. "
        "Third sentence continues. Fourth wraps up the paragraph. "
        "Fifth sentence starts a new idea."
    ),
    metadata={"sender": "user@example.com"}
)
chunks = chunker.chunk(thread)
```

**Note**: This is currently a scaffold implementation. Future enhancements could include:
- Proper sentence tokenization using NLTK or spaCy
- Speaker turn detection in conversations
- Semantic similarity-based grouping using embeddings

## Data Structures

### Thread

Represents an email thread or message to be chunked.

```python
@dataclass
class Thread:
    thread_id: str                          # Unique identifier
    text: str                               # Text content to chunk
    metadata: Dict[str, Any]                # Context information
    messages: Optional[List[Dict]] = None   # Optional message list
```

**Fields**:
- `thread_id`: Unique identifier for the thread (e.g., Message-ID)
- `text`: The text content to chunk (single message or combined thread)
- `metadata`: Context information (sender, subject, date, etc.)
- `messages`: Optional list of individual messages for FixedSizeChunker

### Chunk

Represents a single chunk produced by a chunker.

```python
@dataclass
class Chunk:
    chunk_id: str                   # Unique identifier (UUID)
    text: str                       # Chunk text content
    chunk_index: int                # Sequential position (0-based)
    token_count: int                # Number of tokens
    metadata: Dict[str, Any]        # Context from original thread
    start_offset: Optional[int]     # Character offset (optional)
    end_offset: Optional[int]       # End character offset (optional)
```

**Fields**:
- `chunk_id`: Unique identifier (auto-generated UUID)
- `text`: The actual chunk text content
- `chunk_index`: Sequential position within the source (0-based)
- `token_count`: Number of tokens (word-based approximation)
- `metadata`: Inherited from thread, may include chunk-specific additions
- `start_offset`, `end_offset`: Character offsets in original text (optional)

## Integration with Services

### Chunking Service

The chunking service uses the abstraction to support multiple strategies:

```python
from copilot_chunking import create_chunker
from chunking_config import ChunkingConfig

class ChunkingService:
    def __init__(self, config: ChunkingConfig = None):
        self.config = config or ChunkingConfig()
        self.chunker = create_chunker(**self.config.get_chunker_params())
    
    def chunk_message(self, message_id, text, metadata):
        thread = Thread(thread_id=message_id, text=text, metadata=metadata)
        return self.chunker.chunk(thread)
```

**Configuration via Environment Variables**:
```bash
export CHUNKING_STRATEGY=token_window
export CHUNK_SIZE_TOKENS=384
export CHUNK_OVERLAP_TOKENS=50
export MIN_CHUNK_SIZE_TOKENS=100
export MAX_CHUNK_SIZE_TOKENS=512

# For fixed_size strategy
export CHUNKING_STRATEGY=fixed_size
export MESSAGES_PER_CHUNK=5

# For semantic strategy
export CHUNKING_STRATEGY=semantic
export CHUNK_SIZE_TOKENS=400
```

### Embedding Service

The embedding service works uniformly with all chunking strategies:

```python
from copilot_chunking import Chunk
from typing import List

class EmbeddingService:
    def generate_embeddings(self, chunks: List[Chunk]):
        """Generate embeddings for chunks from any strategy."""
        embeddings = []
        for chunk in chunks:
            vector = self._embed(chunk.text)
            embeddings.append({
                "chunk_id": chunk.chunk_id,
                "vector": vector,
                "metadata": chunk.metadata
            })
        return embeddings
```

### Summarization Service

The summarization service uses chunks for RAG-based summarization:

```python
from copilot_chunking import Chunk
from typing import List

class SummarizationService:
    def summarize_chunks(self, chunks: List[Chunk], top_k: int = 12):
        """Summarize using retrieved chunks from any strategy."""
        # Use top-k most relevant chunks
        selected = chunks[:top_k]
        
        # Build context from chunks
        context = "\n\n".join(chunk.text for chunk in selected)
        
        # Generate summary with LLM
        summary = self._generate_summary(context)
        
        # Extract citations
        citations = self._extract_citations(selected)
        
        return {"summary": summary, "citations": citations}
```

## Factory Method

The `create_chunker()` factory method provides a convenient way to instantiate chunkers:

```python
def create_chunker(
    strategy: str,
    chunk_size: Optional[int] = None,
    overlap: Optional[int] = None,
    messages_per_chunk: Optional[int] = None,
    **kwargs
) -> ThreadChunker
```

**Parameters**:
- `strategy`: Chunking strategy name (case-insensitive)
  - `"token_window"`: TokenWindowChunker
  - `"fixed_size"`: FixedSizeChunker
  - `"semantic"`: SemanticChunker
- `chunk_size`: Target chunk size (for token_window, semantic)
- `overlap`: Overlap between chunks (for token_window)
- `messages_per_chunk`: Messages per chunk (for fixed_size)
- `**kwargs`: Additional strategy-specific parameters

**Example**:
```python
# Create with defaults
chunker = create_chunker("token_window")

# Create with custom parameters
chunker = create_chunker(
    "token_window",
    chunk_size=256,
    overlap=30,
    min_chunk_size=50
)
```

## Benefits

### 1. Flexibility
- Easy to experiment with different chunking approaches
- No need to modify downstream services when changing strategies
- Supports multiple strategies in the same system

### 2. Modularity
- Clean separation of concerns
- Chunking logic isolated from service logic
- Easy to add new strategies without breaking existing code

### 3. Testability
- Each strategy can be tested independently
- Mock chunks for testing downstream services
- Integration tests work with any strategy

### 4. Consistency
- Uniform interface across all strategies
- Consistent metadata handling
- Predictable behavior for downstream services

## Extending the Framework

### Creating a Custom Chunker

To create a custom chunking strategy:

```python
from copilot_chunking import ThreadChunker, Thread, Chunk
from typing import List
from uuid import uuid4

class CustomChunker(ThreadChunker):
    """Custom chunking strategy."""
    
    def __init__(self, custom_param: int = 100):
        self.custom_param = custom_param
    
    def chunk(self, thread: Thread) -> List[Chunk]:
        """Implement custom chunking logic."""
        if not thread.text or not thread.text.strip():
            raise ValueError("Thread text cannot be empty")
        
        # Your custom chunking logic here
        chunks = []
        
        # Example: split every N characters
        text = thread.text
        chunk_index = 0
        
        for i in range(0, len(text), self.custom_param):
            chunk_text = text[i:i + self.custom_param]
            chunk = Chunk(
                chunk_id=str(uuid4()),
                text=chunk_text,
                chunk_index=chunk_index,
                token_count=len(chunk_text.split()),
                metadata=thread.metadata.copy()
            )
            chunks.append(chunk)
            chunk_index += 1
        
        return chunks
```

### Adding to Factory Method

To make your custom chunker available via the factory:

```python
def create_chunker(strategy: str, **kwargs) -> ThreadChunker:
    strategy_lower = strategy.lower()
    
    if strategy_lower == "token_window":
        return TokenWindowChunker(**kwargs)
    elif strategy_lower == "fixed_size":
        return FixedSizeChunker(**kwargs)
    elif strategy_lower == "semantic":
        return SemanticChunker(**kwargs)
    elif strategy_lower == "custom":
        return CustomChunker(**kwargs)
    else:
        raise ValueError(f"Unknown strategy: {strategy}")
```

## Testing

### Unit Tests

The SDK includes comprehensive unit tests for all chunkers:

```bash
cd sdk
pytest tests/test_chunkers.py -v
```

Test coverage includes:
- Interface validation
- Each chunker implementation
- Factory method
- Edge cases (empty text, single sentences, etc.)
- Error handling

### Integration Tests

Example integration tests for services:

```python
def test_chunking_service_with_strategies():
    """Test chunking service with different strategies."""
    for strategy in ["token_window", "fixed_size", "semantic"]:
        config = ChunkingConfig()
        config.chunking_strategy = strategy
        service = ChunkingService(config)
        
        chunks = service.chunk_message(
            message_id="test",
            text="Test message content.",
            metadata={"sender": "test@example.com"}
        )
        
        assert len(chunks) > 0
        assert all(isinstance(c, Chunk) for c in chunks)
```

## Best Practices

### 1. Choose the Right Strategy

- **TokenWindowChunker**: Default choice for most use cases
  - Predictable chunk sizes
  - Works well with embedding models
  - Good for general-purpose chunking

- **FixedSizeChunker**: When message boundaries matter
  - Preserves conversation flow
  - Good for threaded discussions
  - Best with explicit message lists

- **SemanticChunker**: When semantic coherence is critical
  - Preserves complete sentences
  - Better for summarization
  - Good for well-structured content

### 2. Configure Appropriately

- Match `chunk_size` to your embedding model's token limit
- Use `overlap` to preserve context (typically 10-15% of chunk_size)
- Set `min_chunk_size` to avoid tiny fragments
- Consider your use case (embedding vs. summarization)

### 3. Handle Metadata

- Always include relevant metadata (sender, date, subject)
- Metadata is preserved across chunks
- Use metadata for filtering and retrieval

### 4. Error Handling

```python
try:
    chunks = chunker.chunk(thread)
except ValueError as e:
    # Handle empty or invalid input
    logger.error(f"Chunking failed: {e}")
    # Use fallback strategy or skip
```

## Future Enhancements

Planned improvements to the chunking abstraction:

- [ ] Proper tokenization using tiktoken or transformers
- [ ] Semantic similarity-based chunking using embeddings
- [ ] Speaker turn detection in conversations
- [ ] Multi-language support
- [ ] Adaptive chunk sizing based on content density
- [ ] Chunk quality scoring
- [ ] Parallel processing for large documents
- [ ] Chunk caching for duplicate content
- [ ] Support for markdown-aware chunking
- [ ] Integration with LangChain text splitters

## Examples

See the following example files for complete implementations:

- `chunking/chunking_service.py`: Chunking service using the abstraction
- `chunking/chunking_config.py`: Configuration management
- `embedding/embedding_integration.py`: Embedding service integration
- `summarization/summarization_integration.py`: Summarization service integration

## References

- [Event Schemas](../documents/SCHEMA.md)
- [Chunking Service README](../../chunking/README.md)
- [Embedding Service README](../../embedding/README.md)
- [Summarization Service README](../../summarization/README.md)
