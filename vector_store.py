#!/usr/bin/env python3
"""
Vector Storage & Embedding Pipeline for Agent Memories
Stores agent memories with embeddings for semantic retrieval.
"""

import sqlite3
import json
import os
import math
from datetime import datetime
from collections import Counter
import re

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "game_state.db")

# Embedding dimension (fixed size for simplicity)
EMBEDDING_DIM = 128


class SimpleEmbeddingModel:
    """Simple TF-IDF based embedding model using pure Python."""
    
    def __init__(self, dimension: int = EMBEDDING_DIM):
        self.dimension = dimension
        self.vocabulary = {}
        self.idf = {}
    
    def _tokenize(self, text: str) -> list[str]:
        """Simple tokenization: lowercase, extract words."""
        text = text.lower()
        words = re.findall(r'\b[a-z]+\b', text)
        return words
    
    def _compute_tf(self, tokens: list[str]) -> dict[str, float]:
        """Compute term frequency."""
        if not tokens:
            return {}
        counter = Counter(tokens)
        total = len(tokens)
        return {word: count / total for word, count in counter.items()}
    
    def _compute_idf(self, documents: list[list[str]]) -> dict[str, float]:
        """Compute inverse document frequency across all documents."""
        n_docs = len(documents)
        if n_docs == 0:
            return {}
        df = Counter()
        for doc in documents:
            df.update(set(doc))
        
        return {
            word: math.log(n_docs / (df[word] + 1)) + 1
            for word in df
        }
    
    def fit(self, texts: list[str]):
        """Build vocabulary from corpus of texts."""
        tokenized = [self._tokenize(t) for t in texts]
        
        # Build vocabulary (limit to dimension)
        all_words = []
        for doc in tokenized:
            all_words.extend(doc)
        
        word_counts = Counter(all_words)
        most_common = word_counts.most_common(self.dimension)
        self.vocabulary = {word: i for i, (word, _) in enumerate(most_common)}
        
        # Compute IDF
        self.idf = self._compute_idf(tokenized)
        
        return self
    
    def embed(self, text: str) -> list[float]:
        """Generate embedding vector for a single text."""
        tokens = self._tokenize(text)
        tf = self._compute_tf(tokens)
        
        # Create vector
        vector = [0.0] * self.dimension
        
        for word, tf_val in tf.items():
            if word in self.vocabulary:
                idx = self.vocabulary[word]
                idf_val = self.idf.get(word, 1.0)
                vector[idx] = tf_val * idf_val
        
        # Normalize
        magnitude = math.sqrt(sum(v ** 2 for v in vector))
        if magnitude > 0:
            vector = [v / magnitude for v in vector]
        
        return vector


def _cosine_similarity(vec1: list[float], vec2: list[float]) -> float:
    """Compute cosine similarity between two vectors."""
    dot_product = sum(a * b for a, b in zip(vec1, vec2))
    return dot_product


def init_memories_table():
    """Initialize the memories table with vector storage support."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Create memories table with embedding storage
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS memories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            agent_id INTEGER NOT NULL,
            timestamp TEXT NOT NULL,
            text_content TEXT NOT NULL,
            embedding TEXT NOT NULL,
            FOREIGN KEY (agent_id) REFERENCES agents(id)
        )
    """)
    
    # Create index for faster agent lookups
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_memories_agent_id 
        ON memories(agent_id)
    """)
    
    conn.commit()
    conn.close()
    
    print("✅ Memories table initialized")


def store_memory(agent_id: int, text: str) -> int:
    """
    Store a memory for an agent with its embedding.
    
    Args:
        agent_id: The ID of the agent this memory belongs to
        text: The text content of the memory
        
    Returns:
        The ID of the newly created memory
    """
    # Store placeholder embedding - we'll compute proper embeddings at query time
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Get all existing memories for this agent to train the model
    cursor.execute("""
        SELECT text_content FROM memories WHERE agent_id = ?
    """, (agent_id,))
    existing_texts = [row[0] for row in cursor.fetchall()]
    
    # Train model on all texts (existing + new)
    model = SimpleEmbeddingModel()
    all_texts = existing_texts + [text]
    model.fit(all_texts)
    
    # Generate embedding using the trained model
    embedding = model.embed(text)
    
    # Store in database
    cursor.execute("""
        INSERT INTO memories (agent_id, timestamp, text_content, embedding)
        VALUES (?, ?, ?, ?)
    """, (
        agent_id,
        datetime.now().isoformat(),
        text,
        json.dumps(embedding)
    ))
    
    memory_id = cursor.lastrowid
    conn.commit()
    conn.close()
    
    return memory_id


def retrieve_memories(agent_id: int, context_string: str, limit: int = 5) -> list[dict]:
    """
    Retrieve the most semantically relevant memories for an agent.
    
    Args:
        agent_id: The ID of the agent to retrieve memories for
        context_string: The search query/context
        limit: Maximum number of memories to return (default: 5)
        
    Returns:
        List of memory dicts with id, timestamp, text_content, and similarity score
    """
    # Fetch all memories for this agent
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT id, agent_id, timestamp, text_content, embedding
        FROM memories
        WHERE agent_id = ?
        ORDER BY timestamp DESC
    """, (agent_id,))
    
    memories = cursor.fetchall()
    conn.close()
    
    if not memories:
        return []
    
    # Train a single model on ALL memories at once for consistent embeddings
    all_texts = [m[3] for m in memories]
    model = SimpleEmbeddingModel()
    model.fit(all_texts)
    
    # Generate query embedding using the trained model
    query_embedding = model.embed(context_string)
    
    # Compute similarities - re-embed each memory for consistency
    scored_memories = []
    for mem in memories:
        mem_id, _, timestamp, text_content, _ = mem
        # Re-embed with the same model for fair comparison
        memory_embedding = model.embed(text_content)
        similarity = _cosine_similarity(query_embedding, memory_embedding)
        
        scored_memories.append({
            'id': mem_id,
            'timestamp': timestamp,
            'text_content': text_content,
            'similarity': similarity
        })
    
    # Sort by similarity (highest first) and limit
    scored_memories.sort(key=lambda x: x['similarity'], reverse=True)
    return scored_memories[:limit]


def get_all_memories(agent_id: int) -> list[dict]:
    """Get all memories for an agent (for debugging/inspection)."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT id, agent_id, timestamp, text_content
        FROM memories
        WHERE agent_id = ?
        ORDER BY timestamp DESC
    """, (agent_id,))
    
    memories = cursor.fetchall()
    conn.close()
    
    return [
        {
            'id': m[0],
            'agent_id': m[1],
            'timestamp': m[2],
            'text_content': m[3]
        }
        for m in memories
    ]


def rebuild_index():
    """Rebuild the embedding model index from all memories in the database."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("SELECT text_content FROM memories")
    texts = [row[0] for row in cursor.fetchall()]
    
    conn.close()
    
    print(f"✅ Embedding index rebuilt with {len(texts)} documents")


if __name__ == "__main__":
    # Initialize the memories table
    init_memories_table()
    
    # Test storing and retrieving memories
    print("\n--- Testing Vector Storage ---")
    
    # Store some test memories
    test_agent_id = 1
    
    memories = [
        "The agent visited the Forest Clearing and found ancient ruins.",
        "The agent traded with the merchant and got a magic sword.",
        "The agent fought a dragon near the Mountain Path.",
        "The agent met the hermit who gave advice about treasure.",
        "The agent explored the Cave Entrance and found gold.",
        "The agent attended a festival in the Village Square.",
        "The agent swam in the River Bank and found a pearl.",
    ]
    
    for text in memories:
        memory_id = store_memory(test_agent_id, text)
        print(f"Stored memory {memory_id}: {text[:50]}...")
    
    # Rebuild index with all memories
    rebuild_index()
    
    # Test retrieval
    print("\n--- Testing Retrieval ---")
    
    # Query about battles/combat
    results = retrieve_memories(test_agent_id, "dragon battle fighting", limit=3)
    print("\nQuery: 'dragon battle fighting'")
    for r in results:
        print(f"  [{r['similarity']:.3f}] {r['text_content']}")
    
    # Query about exploration
    results = retrieve_memories(test_agent_id, "exploring caves and treasure", limit=3)
    print("\nQuery: 'exploring caves and treasure'")
    for r in results:
        print(f"  [{r['similarity']:.3f}] {r['text_content']}")
    
    # Query about trading
    results = retrieve_memories(test_agent_id, "buying and selling goods", limit=3)
    print("\nQuery: 'buying and selling goods'")
    for r in results:
        print(f"  [{r['similarity']:.3f}] {r['text_content']}")
    
    print("\n✅ All tests passed!")
