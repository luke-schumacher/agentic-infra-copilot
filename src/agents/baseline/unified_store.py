"""
Unified Vector Store for Baseline Mode

Combines documents from all three domain loaders (Telekom, Siemens, Illigo)
into a single ChromaDB collection for single-agent baseline evaluation.

This enables fair A/B comparison between:
- Single-agent: One agent with access to ALL domain knowledge
- Multi-agent: Tripartite architecture with specialized agents

Author: Thesis Project - Agentic Infra Co-Pilot
"""

import os
from pathlib import Path
from typing import List, Optional
import logging
from langchain_core.documents import Document

# ChromaDB vector store
try:
    from langchain_chroma import Chroma
    CHROMA_AVAILABLE = True
except ImportError:
    CHROMA_AVAILABLE = False

# HuggingFace embeddings (same as other agents for fair comparison)
try:
    from langchain_huggingface import HuggingFaceEmbeddings
    HUGGINGFACE_AVAILABLE = True
except ImportError:
    HUGGINGFACE_AVAILABLE = False

# Import domain-specific loaders
from src.agents.telekom_minister.data_loader import TelekomLoader
from src.agents.siemens_technician.data_loader import SiemensLoader
from src.agents.illigo_operator.data_loader import IlligoLoader

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class UnifiedVectorStore:
    """
    Unified vector store combining all three domain knowledge bases.

    Used for single-agent baseline mode in A/B comparison.
    Ensures fair comparison by using identical:
    - Embedding model (all-MiniLM-L6-v2)
    - Chunking parameters (1000 chars, 200 overlap)
    - Retrieval parameters (k=5)
    """

    def __init__(
        self,
        persist_directory: str = "./chroma_db/baseline_unified",
        collection_name: str = "baseline_unified_collection"
    ):
        """
        Initialize the unified vector store.

        Args:
            persist_directory: Directory for ChromaDB persistent storage
            collection_name: Name of the ChromaDB collection
        """
        if not CHROMA_AVAILABLE:
            raise ImportError(
                "langchain-chroma not installed. Run: pip install langchain-chroma chromadb"
            )

        if not HUGGINGFACE_AVAILABLE:
            raise ImportError(
                "langchain-huggingface not installed. Run: pip install langchain-huggingface sentence-transformers"
            )

        self.persist_directory = Path(persist_directory)
        self.collection_name = collection_name

        # Create persist directory
        self.persist_directory.mkdir(parents=True, exist_ok=True)

        # Initialize embeddings - MUST match other agents for fair comparison
        logger.info("Using HuggingFace embeddings (all-MiniLM-L6-v2) for fair baseline comparison")
        self.embeddings = HuggingFaceEmbeddings(
            model_name="all-MiniLM-L6-v2",
            model_kwargs={'device': 'cpu'},
            encode_kwargs={'normalize_embeddings': True}
        )

        # Initialize ChromaDB
        self.vectorstore = Chroma(
            collection_name=self.collection_name,
            embedding_function=self.embeddings,
            persist_directory=str(self.persist_directory)
        )

        logger.info(f"Initialized UnifiedVectorStore")
        logger.info(f"Persist directory: {self.persist_directory}")
        logger.info(f"Collection: {self.collection_name}")

    def get_document_count(self) -> int:
        """Get the number of documents in the vector store."""
        try:
            collection = self.vectorstore._collection
            return collection.count()
        except Exception as e:
            logger.warning(f"Could not get document count: {e}")
            return 0

    def load_all_domain_documents(self) -> List[Document]:
        """
        Load documents from ALL three domain loaders.

        Returns:
            Combined list of documents from Telekom, Siemens, and Illigo
        """
        all_documents = []

        # Load Telekom documents (governance, SLAs, intents)
        logger.info("Loading Telekom (governance) documents...")
        try:
            telekom_loader = TelekomLoader()
            telekom_docs = telekom_loader.load()
            # Tag documents with unified metadata
            for doc in telekom_docs:
                doc.metadata['baseline_domain'] = 'governance'
                doc.metadata['original_agent'] = 'telekom_minister'
            all_documents.extend(telekom_docs)
            logger.info(f"Loaded {len(telekom_docs)} Telekom documents")
        except Exception as e:
            logger.error(f"Error loading Telekom documents: {e}")

        # Load Siemens documents (hardware, equipment specs)
        logger.info("Loading Siemens (hardware) documents...")
        try:
            siemens_loader = SiemensLoader()
            siemens_docs = siemens_loader.load()
            # Tag documents with unified metadata
            for doc in siemens_docs:
                doc.metadata['baseline_domain'] = 'hardware'
                doc.metadata['original_agent'] = 'siemens_technician'
            all_documents.extend(siemens_docs)
            logger.info(f"Loaded {len(siemens_docs)} Siemens documents")
        except Exception as e:
            logger.error(f"Error loading Siemens documents: {e}")

        # Load Illigo documents (operations, telemetry, fault logs)
        logger.info("Loading Illigo (operations) documents...")
        try:
            illigo_loader = IlligoLoader()
            illigo_docs = illigo_loader.load()
            # Tag documents with unified metadata
            for doc in illigo_docs:
                doc.metadata['baseline_domain'] = 'operations'
                doc.metadata['original_agent'] = 'illigo_operator'
            all_documents.extend(illigo_docs)
            logger.info(f"Loaded {len(illigo_docs)} Illigo documents")
        except Exception as e:
            logger.error(f"Error loading Illigo documents: {e}")

        logger.info(f"Total unified documents: {len(all_documents)}")
        return all_documents

    def index_documents(
        self,
        documents: Optional[List[Document]] = None,
        force_reindex: bool = False,
        batch_size: int = 100
    ) -> int:
        """
        Index documents into the unified vector store.

        Args:
            documents: Documents to index (if None, loads from all loaders)
            force_reindex: Clear existing collection before indexing
            batch_size: Number of documents per batch

        Returns:
            Number of documents indexed
        """
        # Load documents if not provided
        if documents is None:
            documents = self.load_all_domain_documents()

        if not documents:
            logger.warning("No documents to index")
            return 0

        logger.info(f"Indexing {len(documents)} documents into unified baseline store...")

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

        # Generate unique IDs
        doc_ids = []
        for i, doc in enumerate(documents):
            domain = doc.metadata.get('baseline_domain', 'unknown')
            data_type = doc.metadata.get('data_type', 'general')
            content_hash = abs(hash(doc.page_content[:200]))
            doc_id = f"baseline_{domain}_{data_type}_{i}_{content_hash}"
            doc_ids.append(doc_id)

        # Index in batches
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

        logger.info(f"Successfully indexed {total_indexed} documents into unified store")
        return total_indexed

    def similarity_search(
        self,
        query: str,
        k: int = 5,
        filter_domain: Optional[str] = None
    ) -> List[Document]:
        """
        Perform similarity search across all domains.

        Args:
            query: Search query
            k: Number of results
            filter_domain: Optional domain filter ('governance', 'hardware', 'operations')

        Returns:
            List of relevant documents
        """
        logger.info(f"Searching unified baseline store for: '{query[:50]}...' (k={k})")

        if filter_domain:
            # Filter by domain if specified
            results = self.vectorstore.similarity_search(
                query,
                k=k,
                filter={"baseline_domain": filter_domain}
            )
        else:
            # Search across all domains
            results = self.vectorstore.similarity_search(query, k=k)

        # Log domain distribution of results
        domain_counts = {}
        for doc in results:
            domain = doc.metadata.get('baseline_domain', 'unknown')
            domain_counts[domain] = domain_counts.get(domain, 0) + 1
        logger.info(f"Found {len(results)} documents. Domain distribution: {domain_counts}")

        return results

    def get_retriever(self, k: int = 5):
        """Get a retriever for this vector store."""
        return self.vectorstore.as_retriever(
            search_type="similarity",
            search_kwargs={"k": k}
        )


def main():
    """Test the unified vector store."""
    logger.info("=" * 60)
    logger.info("Testing Unified Baseline Vector Store")
    logger.info("=" * 60)

    try:
        store = UnifiedVectorStore()

        # Check if already indexed
        current_count = store.get_document_count()
        logger.info(f"Current document count: {current_count}")

        if current_count == 0:
            # Index all documents
            count = store.index_documents(force_reindex=True)
            logger.info(f"Indexed {count} documents")

        # Test search
        test_query = "ground fault at charging station causing billing issues"
        results = store.similarity_search(test_query, k=5)

        logger.info(f"\nSearch results for: '{test_query}'")
        for i, doc in enumerate(results):
            domain = doc.metadata.get('baseline_domain', 'unknown')
            logger.info(f"\n{i+1}. [{domain}] {doc.page_content[:200]}...")

        logger.info("\n" + "=" * 60)
        logger.info("Unified Vector Store test completed!")
        logger.info("=" * 60)

    except Exception as e:
        logger.error(f"Test failed: {e}", exc_info=True)
        raise


if __name__ == "__main__":
    main()
