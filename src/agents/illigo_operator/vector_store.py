"""
Illigo Operator Vector Store

Agent-specific ChromaDB collection for charging station data and event logs.
Provides retrieval capabilities for the Operator's live monitoring reasoning.

Author: Thesis Project - Agentic Infra Co-Pilot
"""

import os
from pathlib import Path
from typing import List, Optional, Dict, Any
import logging
from langchain_core.documents import Document

# ChromaDB vector store
try:
    from langchain_chroma import Chroma
    CHROMA_AVAILABLE = True
except ImportError:
    CHROMA_AVAILABLE = False

# Try OpenAI embeddings first, fallback to HuggingFace
try:
    from langchain_openai import OpenAIEmbeddings
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False

try:
    from langchain_huggingface import HuggingFaceEmbeddings
    HUGGINGFACE_AVAILABLE = True
except ImportError:
    HUGGINGFACE_AVAILABLE = False

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class IlligoVectorStore:
    """
    Agent-specific vector store for Illigo Operator.

    Uses a dedicated ChromaDB collection: 'illigo_operator_collection'
    Stores charging station statistics, event logs, and fault data.
    """

    def __init__(
        self,
        persist_directory: str = "./chroma_db/illigo_operator",
        collection_name: str = "illigo_operator_collection",
        embedding_type: str = "auto"
    ):
        """
        Initialize the Illigo Operator vector store.

        Args:
            persist_directory: Directory for ChromaDB persistent storage
            collection_name: Name of the ChromaDB collection
            embedding_type: 'openai', 'huggingface', or 'auto' (auto-detect)
        """
        if not CHROMA_AVAILABLE:
            raise ImportError(
                "langchain-chroma not installed. Run: pip install langchain-chroma chromadb"
            )

        self.persist_directory = Path(persist_directory)
        self.collection_name = collection_name

        # Create persist directory if it doesn't exist
        self.persist_directory.mkdir(parents=True, exist_ok=True)

        # Initialize embeddings
        self.embeddings = self._initialize_embeddings(embedding_type)

        # Initialize ChromaDB vector store
        self.vectorstore = Chroma(
            collection_name=self.collection_name,
            embedding_function=self.embeddings,
            persist_directory=str(self.persist_directory)
        )

        logger.info(f"Initialized IlligoVectorStore with {self._get_embedding_type()}")
        logger.info(f"Persist directory: {self.persist_directory}")
        logger.info(f"Collection: {self.collection_name}")

    def _initialize_embeddings(self, embedding_type: str):
        """
        Initialize embedding model based on availability and configuration.

        Args:
            embedding_type: 'openai', 'huggingface', or 'auto'

        Returns:
            Embedding model instance
        """
        if embedding_type == "auto":
            # Auto-detect: prefer OpenAI if API key is set, else HuggingFace
            if OPENAI_AVAILABLE and os.getenv("OPENAI_API_KEY"):
                embedding_type = "openai"
            elif HUGGINGFACE_AVAILABLE:
                embedding_type = "huggingface"
            else:
                raise RuntimeError(
                    "No embedding model available. Install either:\n"
                    "  pip install langchain-openai (and set OPENAI_API_KEY)\n"
                    "  pip install langchain-huggingface sentence-transformers"
                )

        if embedding_type == "openai":
            if not OPENAI_AVAILABLE:
                raise ImportError("langchain-openai not installed.")
            if not os.getenv("OPENAI_API_KEY"):
                raise ValueError("OPENAI_API_KEY not set in environment")

            logger.info("Using OpenAI embeddings (text-embedding-3-small)")
            return OpenAIEmbeddings(model="text-embedding-3-small")

        elif embedding_type == "huggingface":
            if not HUGGINGFACE_AVAILABLE:
                raise ImportError(
                    "langchain-huggingface not installed. Run: pip install langchain-huggingface sentence-transformers"
                )

            logger.info("Using HuggingFace embeddings (all-MiniLM-L6-v2)")
            return HuggingFaceEmbeddings(
                model_name="all-MiniLM-L6-v2",
                model_kwargs={'device': 'cpu'},
                encode_kwargs={'normalize_embeddings': True}
            )

        else:
            raise ValueError(f"Unknown embedding_type: {embedding_type}")

    def _get_embedding_type(self) -> str:
        """Get the name of the embedding model being used."""
        if OPENAI_AVAILABLE and isinstance(self.embeddings, OpenAIEmbeddings):
            return "OpenAI (text-embedding-3-small)"
        else:
            return "HuggingFace (all-MiniLM-L6-v2)"

    def get_document_count(self) -> int:
        """
        Get the number of documents currently in the vector store.

        Returns:
            Number of documents
        """
        try:
            collection = self.vectorstore._collection
            return collection.count()
        except Exception as e:
            logger.warning(f"Could not get document count: {e}")
            return 0

    def index_documents(
        self,
        documents: List[Document],
        force_reindex: bool = False,
        batch_size: int = 100
    ) -> int:
        """
        Index documents into the vector store.

        Args:
            documents: List of LangChain Document objects
            force_reindex: If True, clear existing collection before indexing
            batch_size: Number of documents to index per batch

        Returns:
            Number of documents indexed
        """
        if not documents:
            logger.warning("No documents to index")
            return 0

        logger.info(f"Indexing {len(documents)} documents into Illigo Operator store...")

        current_count = self.get_document_count()

        if force_reindex and current_count > 0:
            logger.info(f"Clearing existing {current_count} documents (force_reindex=True)")
            try:
                self.vectorstore._client.delete_collection(self.collection_name)
                self.vectorstore = Chroma(
                    collection_name=self.collection_name,
                    embedding_function=self.embeddings,
                    persist_directory=str(self.persist_directory)
                )
                logger.info("Collection cleared successfully")
            except Exception as e:
                logger.error(f"Error clearing collection: {e}")

        # Generate unique IDs for documents
        doc_ids = []
        for i, doc in enumerate(documents):
            source = doc.metadata.get('source_type', 'illigo')
            data_type = doc.metadata.get('data_type', 'event')
            event_id = doc.metadata.get('event_id', '')
            content_hash = abs(hash(doc.page_content[:200]))
            doc_id = f"illigo_{source}_{data_type}_{event_id}_{i}_{content_hash}"
            doc_ids.append(doc_id)

        # Add documents in batches
        total_indexed = 0
        for i in range(0, len(documents), batch_size):
            batch_docs = documents[i:i+batch_size]
            batch_ids = doc_ids[i:i+batch_size]

            try:
                self.vectorstore.add_documents(documents=batch_docs, ids=batch_ids)
                total_indexed += len(batch_docs)
                logger.info(
                    f"Indexed batch {i//batch_size + 1}/{(len(documents)-1)//batch_size + 1} "
                    f"({total_indexed}/{len(documents)} docs)"
                )
            except Exception as e:
                logger.error(f"Error indexing batch: {e}")
                raise

        logger.info(f"Successfully indexed {total_indexed} documents")
        return total_indexed

    def similarity_search(
        self,
        query: str,
        k: int = 5,
        filter_dict: Optional[dict] = None
    ) -> List[Document]:
        """
        Perform similarity search.

        Args:
            query: Search query
            k: Number of results to return
            filter_dict: Optional metadata filters

        Returns:
            List of relevant documents
        """
        logger.info(f"Searching Illigo documents for: '{query[:50]}...' (k={k})")

        if filter_dict:
            results = self.vectorstore.similarity_search(query, k=k, filter=filter_dict)
        else:
            results = self.vectorstore.similarity_search(query, k=k)

        logger.info(f"Found {len(results)} relevant documents")
        return results

    def similarity_search_with_score(
        self,
        query: str,
        k: int = 5
    ) -> List[tuple]:
        """
        Perform similarity search with relevance scores.

        Args:
            query: Search query
            k: Number of results to return

        Returns:
            List of (Document, score) tuples
        """
        logger.info(f"Searching Illigo documents with scores for: '{query[:50]}...'")
        results = self.vectorstore.similarity_search_with_score(query, k=k)
        logger.info(f"Found {len(results)} relevant documents with scores")
        return results

    def search_fault_events(
        self,
        query: str,
        k: int = 5
    ) -> List[Document]:
        """
        Search specifically for fault events.

        Args:
            query: Search query
            k: Number of results to return

        Returns:
            List of relevant fault event documents
        """
        return self.similarity_search(
            query=query,
            k=k,
            filter_dict={"data_type": "fault_event"}
        )

    def search_by_station(
        self,
        query: str,
        station_id: str,
        k: int = 5
    ) -> List[Document]:
        """
        Search documents filtered by station ID.

        Args:
            query: Search query
            station_id: Station identifier
            k: Number of results to return

        Returns:
            List of relevant documents for the specified station
        """
        return self.similarity_search(
            query=query,
            k=k,
            filter_dict={"station_id": station_id}
        )

    def search_by_severity(
        self,
        query: str,
        severity: str,
        k: int = 5
    ) -> List[Document]:
        """
        Search documents filtered by severity level.

        Args:
            query: Search query
            severity: Severity level (e.g., 'High', 'Medium', 'Low')
            k: Number of results to return

        Returns:
            List of relevant documents matching the severity
        """
        return self.similarity_search(
            query=query,
            k=k,
            filter_dict={"severity": severity}
        )

    def get_recent_events(
        self,
        station_id: Optional[str] = None,
        k: int = 10
    ) -> List[Document]:
        """
        Get recent events, optionally filtered by station.

        Args:
            station_id: Optional station filter
            k: Number of results to return

        Returns:
            List of recent event documents
        """
        # Search for events with a generic query
        if station_id:
            return self.search_by_station(
                query="recent events status notification fault",
                station_id=station_id,
                k=k
            )
        else:
            return self.similarity_search(
                query="recent events status notification fault",
                k=k,
                filter_dict={"data_type": "fault_event"}
            )

    def get_retriever(self, k: int = 5):
        """
        Get a retriever for this vector store.

        Args:
            k: Number of documents to retrieve

        Returns:
            LangChain retriever
        """
        return self.vectorstore.as_retriever(
            search_type="similarity",
            search_kwargs={"k": k}
        )
