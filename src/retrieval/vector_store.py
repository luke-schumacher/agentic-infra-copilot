"""
Vector Store Manager - RAG Retrieval Layer

Manages the vector database for RAG-based document retrieval using ChromaDB.
Handles document indexing, deduplication, and retrieval configuration.

Purpose:
- Store document embeddings in persistent ChromaDB
- Enable semantic search across ingested documents
- Provide retriever interface for RAG queries

Author: Thesis Project - Agentic Infra Co-Pilot
"""

import os
from pathlib import Path
from typing import List, Optional
import logging
from langchain_core.documents import Document
from langchain_core.retrievers import BaseRetriever

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


class VectorStoreManager:
    """Manages ChromaDB vector store for RAG document retrieval."""

    def __init__(
        self,
        persist_directory: str = "./chroma_db",
        collection_name: str = "infra_copilot",
        embedding_type: str = "auto"
    ):
        """
        Initialize the vector store manager.

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

        logger.info(f"Initialized VectorStoreManager with {self._get_embedding_type()}")
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
                raise ImportError("langchain-openai not installed. Run: pip install langchain-openai")
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

        logger.info(f"Indexing {len(documents)} documents...")

        # Check if collection already has documents
        current_count = self.get_document_count()

        if current_count > 0 and not force_reindex:
            logger.warning(
                f"Collection already contains {current_count} documents. "
                f"Set force_reindex=True to clear and re-index, or documents will be added."
            )
            response = input("\nOptions:\n  1. Skip (avoid duplicates)\n  2. Add anyway\n  3. Clear and re-index\nChoice (1/2/3): ").strip()

            if response == "1":
                logger.info("Skipping indexing to avoid duplicates")
                return 0
            elif response == "3":
                force_reindex = True

        if force_reindex and current_count > 0:
            logger.info(f"Clearing existing {current_count} documents (force_reindex=True)")
            # Delete the collection and recreate
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

        # Generate unique IDs for documents to avoid duplicates
        doc_ids = []
        for i, doc in enumerate(documents):
            # Create ID from source, type, and content hash
            source = doc.metadata.get('source', 'unknown')
            data_type = doc.metadata.get('data_type', 'unknown')
            content_hash = abs(hash(doc.page_content[:200]))  # Hash first 200 chars
            doc_id = f"{source}_{data_type}_{i}_{content_hash}"
            doc_ids.append(doc_id)

        # Add documents in batches
        total_indexed = 0
        for i in range(0, len(documents), batch_size):
            batch_docs = documents[i:i+batch_size]
            batch_ids = doc_ids[i:i+batch_size]

            try:
                self.vectorstore.add_documents(documents=batch_docs, ids=batch_ids)
                total_indexed += len(batch_docs)
                logger.info(f"Indexed batch {i//batch_size + 1}/{(len(documents)-1)//batch_size + 1} ({total_indexed}/{len(documents)} docs)")
            except Exception as e:
                logger.error(f"Error indexing batch: {e}")
                raise

        logger.info(f"Successfully indexed {total_indexed} documents")

        new_count = self.get_document_count()
        logger.info(f"Total documents in collection: {new_count}")

        return total_indexed

    def get_retriever(
        self,
        search_type: str = "similarity",
        k: int = 5,
        **kwargs
    ) -> BaseRetriever:
        """
        Get a retriever for querying the vector store.

        Args:
            search_type: Type of search ('similarity', 'mmr', 'similarity_score_threshold')
            k: Number of documents to retrieve
            **kwargs: Additional arguments for retriever configuration

        Returns:
            LangChain retriever object
        """
        logger.info(f"Creating retriever with search_type={search_type}, k={k}")

        retriever = self.vectorstore.as_retriever(
            search_type=search_type,
            search_kwargs={"k": k, **kwargs}
        )

        return retriever

    def similarity_search(
        self,
        query: str,
        k: int = 5
    ) -> List[Document]:
        """
        Perform similarity search directly.

        Args:
            query: Search query
            k: Number of results to return

        Returns:
            List of relevant documents
        """
        logger.info(f"Searching for: '{query}' (k={k})")
        results = self.vectorstore.similarity_search(query, k=k)
        logger.info(f"Found {len(results)} relevant documents")
        return results


def main():
    """Test the vector store with all three data loaders."""
    logger.info("=" * 60)
    logger.info("Testing Vector Store Manager")
    logger.info("=" * 60)

    # Import loaders
    import sys
    sys.path.append('.')

    from src.ingestion.siemens_loader import SiemensLoader
    from src.ingestion.illigo_loader import IlligoLoader
    from src.ingestion.telekom_loader import TelekomLoader

    try:
        # Step 1: Load all data
        logger.info("\n[Step 1/4] Loading data from all sources...")

        siemens_loader = SiemensLoader()
        siemens_docs = siemens_loader.load()
        logger.info(f"  Loaded {len(siemens_docs)} Siemens documents")

        illigo_loader = IlligoLoader()
        illigo_docs = illigo_loader.load()
        logger.info(f"  Loaded {len(illigo_docs)} Illigo documents")

        telekom_loader = TelekomLoader()
        telekom_docs = telekom_loader.load()
        logger.info(f"  Loaded {len(telekom_docs)} Telekom documents")

        # Combine all documents
        all_documents = siemens_docs + illigo_docs + telekom_docs
        logger.info(f"\nTotal documents to index: {len(all_documents)}")

        # Step 2: Initialize vector store
        logger.info("\n[Step 2/4] Initializing vector store...")
        vector_store = VectorStoreManager(
            persist_directory="./chroma_db",
            collection_name="infra_copilot"
        )

        # Step 3: Index documents
        logger.info("\n[Step 3/4] Indexing documents...")
        indexed_count = vector_store.index_documents(
            all_documents,
            force_reindex=True  # Clear and re-index for testing
        )
        logger.info(f"Successfully indexed {indexed_count} documents")

        # Step 4: Test retrieval with queries
        logger.info("\n[Step 4/4] Testing retrieval with queries...")

        # Get retriever
        retriever = vector_store.get_retriever(k=5)

        # Test Query 1: Telekom SLA/latency
        logger.info("\n" + "=" * 60)
        logger.info("TEST QUERY 1: Telekom Network Requirements")
        logger.info("=" * 60)

        test_query = "What is the latency requirement for the EV microgrid?"
        logger.info(f"\nQuery: '{test_query}'")

        # Retrieve documents
        results = retriever.invoke(test_query)

        logger.info(f"\nRetrieved {len(results)} relevant documents:")
        logger.info("=" * 60)

        for i, doc in enumerate(results, 1):
            print(f"\n--- Result {i} ---")
            print(f"Source Type: {doc.metadata.get('source_type', 'unknown')}")
            print(f"File: {doc.metadata.get('file_name', 'unknown')}")
            print(f"Content (first 300 chars):\n{doc.page_content[:300]}...")
            print()

        # Test Query 2: Illigo fault
        logger.info("\n" + "=" * 60)
        logger.info("TEST QUERY 2: Illigo Charging Station Fault")
        logger.info("=" * 60)

        fault_query = "What caused the ground fault at Koumassi station?"
        logger.info(f"\nQuery: '{fault_query}'")

        fault_results = retriever.invoke(fault_query)

        logger.info(f"\nRetrieved {len(fault_results)} relevant documents:")
        logger.info("=" * 60)

        for i, doc in enumerate(fault_results, 1):
            print(f"\n--- Result {i} ---")
            print(f"Source: {doc.metadata.get('source', 'unknown')}")
            print(f"Station: {doc.metadata.get('station_id', 'N/A')}")
            print(f"Fault Code: {doc.metadata.get('fault_code', 'N/A')}")
            print(f"Severity: {doc.metadata.get('severity', 'N/A')}")
            print(f"Content:\n{doc.page_content[:400]}...")
            print()

        # Test Query 3: Siemens pain points
        logger.info("\n" + "=" * 60)
        logger.info("TEST QUERY 3: Siemens Hospital Pain Points")
        logger.info("=" * 60)

        siemens_query = "Which hospitals have issues with coil positioning?"
        logger.info(f"\nQuery: '{siemens_query}'")

        siemens_results = retriever.invoke(siemens_query)

        logger.info(f"\nRetrieved {len(siemens_results)} relevant documents:")
        logger.info("=" * 60)

        for i, doc in enumerate(siemens_results, 1):
            print(f"\n--- Result {i} ---")
            print(f"Institution: {doc.metadata.get('institution', 'unknown')}")
            print(f"Country: {doc.metadata.get('country', 'N/A')}")
            print(f"Content:\n{doc.page_content[:400]}...")
            print()

        logger.info("\n" + "=" * 60)
        logger.info("VECTOR STORE TEST COMPLETED SUCCESSFULLY!")
        logger.info("=" * 60)
        logger.info("\nThe 'Brain' can now remember and recall all ingested data!")
        logger.info(f"Total documents indexed: {vector_store.get_document_count()}")

    except Exception as e:
        logger.error(f"Test failed: {str(e)}", exc_info=True)
        raise


if __name__ == "__main__":
    main()
