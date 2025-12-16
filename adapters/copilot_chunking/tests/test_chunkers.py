# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Tests for thread chunking strategies."""

import pytest
from copilot_chunking import (
    ThreadChunker,
    TokenWindowChunker,
    FixedSizeChunker,
    SemanticChunker,
    Chunk,
    Thread,
    create_chunker,
)


class TestChunkDataClass:
    """Tests for Chunk data class."""
    
    def test_chunk_creation(self):
        """Test creating a Chunk instance."""
        chunk = Chunk(
            chunk_id="test-123",
            text="This is a test chunk.",
            chunk_index=0,
            token_count=5,
            metadata={"sender": "test@example.com"}
        )
        
        assert chunk.chunk_id == "test-123"
        assert chunk.text == "This is a test chunk."
        assert chunk.chunk_index == 0
        assert chunk.token_count == 5
        assert chunk.metadata["sender"] == "test@example.com"
        assert chunk.start_offset is None
        assert chunk.end_offset is None
    
    def test_chunk_with_offsets(self):
        """Test chunk with character offsets."""
        chunk = Chunk(
            chunk_id="test-456",
            text="Another chunk",
            chunk_index=1,
            token_count=2,
            metadata={},
            start_offset=0,
            end_offset=13
        )
        
        assert chunk.start_offset == 0
        assert chunk.end_offset == 13


class TestThreadDataClass:
    """Tests for Thread data class."""
    
    def test_thread_creation(self):
        """Test creating a Thread instance."""
        thread = Thread(
            thread_id="thread-001",
            text="This is a sample email thread.",
            metadata={"subject": "Test Subject"}
        )
        
        assert thread.thread_id == "thread-001"
        assert thread.text == "This is a sample email thread."
        assert thread.metadata["subject"] == "Test Subject"
        assert thread.messages is None
    
    def test_thread_with_messages(self):
        """Test thread with explicit messages."""
        messages = [
            {"message_id": "msg1", "text": "First message"},
            {"message_id": "msg2", "text": "Second message"}
        ]
        thread = Thread(
            thread_id="thread-002",
            text="Combined text",
            metadata={},
            messages=messages
        )
        
        assert thread.messages == messages
        assert len(thread.messages) == 2


class TestTokenWindowChunker:
    """Tests for TokenWindowChunker."""
    
    def test_initialization(self):
        """Test chunker initialization with default values."""
        chunker = TokenWindowChunker()
        
        assert chunker.chunk_size == 384
        assert chunker.overlap == 50
        assert chunker.min_chunk_size == 100
        assert chunker.max_chunk_size == 512
    
    def test_initialization_custom_values(self):
        """Test chunker initialization with custom values."""
        chunker = TokenWindowChunker(
            chunk_size=200,
            overlap=20,
            min_chunk_size=50,
            max_chunk_size=300
        )
        
        assert chunker.chunk_size == 200
        assert chunker.overlap == 20
        assert chunker.min_chunk_size == 50
        assert chunker.max_chunk_size == 300
    
    def test_chunk_short_text(self):
        """Test chunking a short text that fits in one chunk."""
        chunker = TokenWindowChunker(chunk_size=100, min_chunk_size=10)
        thread = Thread(
            thread_id="test-thread",
            text="This is a short text that should fit in one chunk.",
            metadata={"sender": "test@example.com"},
            message_key="msgkey-0000000001"
        )
        
        chunks = chunker.chunk(thread)
        
        assert len(chunks) == 1
        assert chunks[0].chunk_index == 0
        assert chunks[0].text == thread.text
        assert chunks[0].metadata["sender"] == "test@example.com"
    
    def test_chunk_long_text(self):
        """Test chunking a longer text into multiple chunks."""
        chunker = TokenWindowChunker(chunk_size=10, overlap=2, min_chunk_size=5)
        
        # Create a text with many words
        words = ["word"] * 30
        text = " ".join(words)
        
        thread = Thread(
            thread_id="test-thread",
            text=text,
            metadata={"subject": "Test"},
            message_key="msgkey-0000000001"
        )
        
        chunks = chunker.chunk(thread)
        
        # Should have multiple chunks
        assert len(chunks) > 1
        
        # Check chunk indices are sequential
        for i, chunk in enumerate(chunks):
            assert chunk.chunk_index == i
        
        # Check metadata is preserved
        for chunk in chunks:
            assert chunk.metadata["subject"] == "Test"
    
    def test_chunk_empty_text_raises_error(self):
        """Test that empty text raises ValueError."""
        chunker = TokenWindowChunker()
        thread = Thread(
            thread_id="test-thread",
            text="",
            metadata={},
            message_key="msgkey-0000000001"
        )
        
        with pytest.raises(ValueError, match="Thread text cannot be empty"):
            chunker.chunk(thread)
    
    def test_chunk_whitespace_only_raises_error(self):
        """Test that whitespace-only text raises ValueError."""
        chunker = TokenWindowChunker()
        thread = Thread(
            thread_id="test-thread",
            text="   \n\n  ",
            metadata={},
            message_key="msgkey-0000000001"
        )
        
        with pytest.raises(ValueError, match="Thread text cannot be empty"):
            chunker.chunk(thread)
    
    def test_chunk_with_overlap(self):
        """Test that overlap is applied correctly."""
        chunker = TokenWindowChunker(chunk_size=5, overlap=2, min_chunk_size=3)
        
        text = "one two three four five six seven eight nine ten"
        thread = Thread(
            thread_id="test-thread",
            text=text,
            metadata={},
            message_key="msgkey-0000000001"
        )
        
        chunks = chunker.chunk(thread)
        
        # Should have overlapping content between chunks
        assert len(chunks) >= 2


class TestFixedSizeChunker:
    """Tests for FixedSizeChunker."""
    
    def test_initialization(self):
        """Test chunker initialization."""
        chunker = FixedSizeChunker(messages_per_chunk=5)
        assert chunker.messages_per_chunk == 5
    
    def test_initialization_default(self):
        """Test default initialization."""
        chunker = FixedSizeChunker()
        assert chunker.messages_per_chunk == 5
    
    def test_initialization_invalid_value(self):
        """Test that invalid messages_per_chunk raises error."""
        with pytest.raises(ValueError, match="messages_per_chunk must be at least 1"):
            FixedSizeChunker(messages_per_chunk=0)
    
    def test_chunk_with_text_blocks(self):
        """Test chunking text split by paragraph breaks."""
        chunker = FixedSizeChunker(messages_per_chunk=2)
        
        text = "Message 1 content.\n\nMessage 2 content.\n\nMessage 3 content.\n\nMessage 4 content."
        thread = Thread(
            thread_id="test-thread",
            text=text,
            metadata={"subject": "Test"},
            message_key="msgkey-0000000001"
        )
        
        chunks = chunker.chunk(thread)
        
        # Should have 2 chunks (4 messages / 2 per chunk)
        assert len(chunks) == 2
        assert chunks[0].chunk_index == 0
        assert chunks[1].chunk_index == 1
    
    def test_chunk_with_explicit_messages(self):
        """Test chunking with explicit message list."""
        chunker = FixedSizeChunker(messages_per_chunk=3)
        
        messages = [
            {"message_id": "msg1", "message_key": "msgkey1", "text": "First message"},
            {"message_id": "msg2", "message_key": "msgkey2", "text": "Second message"},
            {"message_id": "msg3", "message_key": "msgkey3", "text": "Third message"},
            {"message_id": "msg4", "message_key": "msgkey4", "text": "Fourth message"},
            {"message_id": "msg5", "message_key": "msgkey5", "text": "Fifth message"},
        ]
        
        thread = Thread(
            thread_id="test-thread",
            text="",
            metadata={"subject": "Test"},
            messages=messages,
            message_key="msgkey-0000000001"
        )
        
        chunks = chunker.chunk(thread)
        
        # Should have 2 chunks (5 messages / 3 per chunk = 2 chunks)
        assert len(chunks) == 2
        assert "msgkey1" in chunks[0].metadata["message_keys"]
        assert "msgkey2" in chunks[0].metadata["message_keys"]
        assert "msgkey3" in chunks[0].metadata["message_keys"]
        assert chunks[0].metadata["message_count"] == 3
        
        assert "msgkey4" in chunks[1].metadata["message_keys"]
        assert "msgkey5" in chunks[1].metadata["message_keys"]
        assert chunks[1].metadata["message_count"] == 2
    
    def test_chunk_empty_thread_raises_error(self):
        """Test that empty thread raises ValueError."""
        chunker = FixedSizeChunker()
        thread = Thread(
            thread_id="test-thread",
            text="",
            metadata={},
            message_key="msgkey-0000000001"
        )
        
        with pytest.raises(ValueError, match="Thread must have either messages or text"):
            chunker.chunk(thread)
    
    def test_chunk_single_message(self):
        """Test chunking with a single message."""
        chunker = FixedSizeChunker(messages_per_chunk=2)
        
        messages = [{"message_id": "msg1", "message_key": "msgkey1", "body": "Only message"}]
        thread = Thread(
            thread_id="test-thread",
            text="",
            metadata={},
            messages=messages,
            message_key="msgkey-0000000001"
        )
        
        chunks = chunker.chunk(thread)
        
        assert len(chunks) == 1
        assert chunks[0].chunk_index == 0


class TestSemanticChunker:
    """Tests for SemanticChunker."""
    
    def test_initialization(self):
        """Test chunker initialization."""
        chunker = SemanticChunker(target_chunk_size=400)
        assert chunker.target_chunk_size == 400
        assert chunker.split_on_speaker is False
    
    def test_initialization_default(self):
        """Test default initialization."""
        chunker = SemanticChunker()
        assert chunker.target_chunk_size == 400
    
    def test_chunk_single_sentence(self):
        """Test chunking a single sentence."""
        chunker = SemanticChunker(target_chunk_size=100)
        
        thread = Thread(
            thread_id="test-thread",
            text="This is a single sentence.",
            metadata={"sender": "test@example.com"},
            message_key="msgkey-0000000001"
        )
        
        chunks = chunker.chunk(thread)
        
        assert len(chunks) == 1
        assert chunks[0].text == "This is a single sentence."
    
    def test_chunk_multiple_sentences(self):
        """Test chunking multiple sentences."""
        chunker = SemanticChunker(target_chunk_size=10)
        
        text = (
            "This is the first sentence. "
            "Here is the second sentence. "
            "And this is the third one. "
            "Finally, we have the fourth sentence."
        )
        
        thread = Thread(
            thread_id="test-thread",
            text=text,
            metadata={},
            message_key="msgkey-0000000001"
        )
        
        chunks = chunker.chunk(thread)
        
        # Should have multiple chunks due to low target size
        assert len(chunks) > 1
        
        # Each chunk should contain complete sentences
        for chunk in chunks:
            # Sentences should end with punctuation
            assert chunk.text.strip()[-1] in '.!?'
    
    def test_chunk_respects_target_size(self):
        """Test that chunker groups sentences to approach target size."""
        chunker = SemanticChunker(target_chunk_size=20)
        
        # Create multiple short sentences
        sentences = [f"Sentence number {i}." for i in range(10)]
        text = " ".join(sentences)
        
        thread = Thread(
            thread_id="test-thread",
            text=text,
            metadata={},
            message_key="msgkey-0000000001"
        )
        
        chunks = chunker.chunk(thread)
        
        # Should have multiple chunks
        assert len(chunks) > 1
        
        # Each chunk should have sequential indices
        for i, chunk in enumerate(chunks):
            assert chunk.chunk_index == i
    
    def test_chunk_empty_text_raises_error(self):
        """Test that empty text raises ValueError."""
        chunker = SemanticChunker()
        thread = Thread(
            thread_id="test-thread",
            text="",
            metadata={},
            message_key="msgkey-0000000001"
        )
        
        with pytest.raises(ValueError, match="Thread text cannot be empty"):
            chunker.chunk(thread)
    
    def test_split_sentences(self):
        """Test the sentence splitting helper method."""
        chunker = SemanticChunker()
        
        text = "First sentence. Second sentence! Third sentence? Fourth."
        sentences = chunker._split_sentences(text)
        
        assert len(sentences) == 4
        assert sentences[0] == "First sentence."
        assert sentences[1] == "Second sentence!"
        assert sentences[2] == "Third sentence?"
        assert sentences[3] == "Fourth."


class TestCreateChunker:
    """Tests for create_chunker factory method."""
    
    def test_create_token_window_chunker(self):
        """Test creating a TokenWindowChunker."""
        chunker = create_chunker("token_window")
        assert isinstance(chunker, TokenWindowChunker)
        assert chunker.chunk_size == 384
    
    def test_create_token_window_chunker_custom(self):
        """Test creating a TokenWindowChunker with custom params."""
        chunker = create_chunker(
            "token_window",
            chunk_size=200,
            overlap=30
        )
        assert isinstance(chunker, TokenWindowChunker)
        assert chunker.chunk_size == 200
        assert chunker.overlap == 30
    
    def test_create_fixed_size_chunker(self):
        """Test creating a FixedSizeChunker."""
        chunker = create_chunker("fixed_size")
        assert isinstance(chunker, FixedSizeChunker)
        assert chunker.messages_per_chunk == 5
    
    def test_create_fixed_size_chunker_custom(self):
        """Test creating a FixedSizeChunker with custom params."""
        chunker = create_chunker("fixed_size", messages_per_chunk=10)
        assert isinstance(chunker, FixedSizeChunker)
        assert chunker.messages_per_chunk == 10
    
    def test_create_semantic_chunker(self):
        """Test creating a SemanticChunker."""
        chunker = create_chunker("semantic")
        assert isinstance(chunker, SemanticChunker)
        assert chunker.target_chunk_size == 400
    
    def test_create_semantic_chunker_custom(self):
        """Test creating a SemanticChunker with custom params."""
        chunker = create_chunker("semantic", chunk_size=500)
        assert isinstance(chunker, SemanticChunker)
        assert chunker.target_chunk_size == 500
    
    def test_create_chunker_case_insensitive(self):
        """Test that strategy names are case-insensitive."""
        chunker1 = create_chunker("TOKEN_WINDOW")
        chunker2 = create_chunker("Fixed_Size")
        chunker3 = create_chunker("SEMANTIC")
        
        assert isinstance(chunker1, TokenWindowChunker)
        assert isinstance(chunker2, FixedSizeChunker)
        assert isinstance(chunker3, SemanticChunker)
    
    def test_create_chunker_unknown_strategy(self):
        """Test that unknown strategy raises ValueError."""
        with pytest.raises(ValueError, match="Unknown chunking strategy"):
            create_chunker("invalid_strategy")
    
    def test_create_chunker_with_kwargs(self):
        """Test passing additional kwargs to chunkers."""
        chunker = create_chunker(
            "token_window",
            min_chunk_size=50,
            max_chunk_size=600
        )
        assert isinstance(chunker, TokenWindowChunker)
        assert chunker.min_chunk_size == 50
        assert chunker.max_chunk_size == 600


class TestThreadChunkerInterface:
    """Tests for ThreadChunker abstract interface."""
    
    def test_cannot_instantiate_abstract_class(self):
        """Test that ThreadChunker cannot be instantiated directly."""
        with pytest.raises(TypeError):
            ThreadChunker()
    
    def test_subclass_must_implement_chunk(self):
        """Test that subclasses must implement chunk method."""
        class IncompleteChunker(ThreadChunker):
            pass
        
        with pytest.raises(TypeError):
            IncompleteChunker()
    
    def test_valid_subclass(self):
        """Test that a valid subclass can be created."""
        class ValidChunker(ThreadChunker):
            def chunk(self, thread: Thread) -> list:
                return []
        
        chunker = ValidChunker()
        assert isinstance(chunker, ThreadChunker)
        result = chunker.chunk(Thread("test", "text", {}, message_key="msgkey-0000000001"))
        assert result == []
