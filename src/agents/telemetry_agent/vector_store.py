"""
Safety Auditor Vector Store

Agent-specific ChromaDB collection for MRI safety procedures, zone definitions,
and compliance documentation.
Provides retrieval capabilities for the Auditor's safety reasoning.

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


# Federated Agentic RAG: Allowed document types for this agent's cognitive silo
SILO_ALLOWED_TYPES = {
    'safety_procedure', 'safety_zone', 'personnel_requirement',
    'safety_event_flag', 'safety_pdf', 'safety_documentation',
    'compliance_data', 'zone_definition', 'telemetry_data',
}


class SafetyAuditorStore:
    """
    Agent-specific vector store for The Auditor (Agent 3 - Safety & Compliance).

    Uses a dedicated ChromaDB collection: 'safety_auditor_collection'
    Stores MRI safety procedures, zone definitions, and compliance documentation.

    Enforces cognitive silo separation: only safety/compliance-domain documents are accepted.
    """

    def __init__(
        self,
        persist_directory: str = "./chroma_db/telemetry_agent",
        collection_name: str = "safety_auditor_collection",
        embedding_type: str = "auto"
    ):
        if not CHROMA_AVAILABLE:
            raise ImportError(
                "langchain-chroma not installed. Run: pip install langchain-chroma chromadb"
            )

        self.persist_directory = Path(persist_directory)
        self.collection_name = collection_name

        self.persist_directory.mkdir(parents=True, exist_ok=True)

        self.embeddings = self._initialize_embeddings(embedding_type)

        self.vectorstore = Chroma(
            collection_name=self.collection_name,
            embedding_function=self.embeddings,
            persist_directory=str(self.persist_directory)
        )

        logger.info(f"Initialized SafetyAuditorStore with {self._get_embedding_type()}")
        logger.info(f"Persist directory: {self.persist_directory}")
        logger.info(f"Collection: {self.collection_name}")

    def _initialize_embeddings(self, embedding_type: str):
        if embedding_type == "auto":
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
        if OPENAI_AVAILABLE and isinstance(self.embeddings, OpenAIEmbeddings):
            return "OpenAI (text-embedding-3-small)"
        else:
            return "HuggingFace (all-MiniLM-L6-v2)"

    def get_document_count(self) -> int:
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
        if not documents:
            logger.warning("No documents to index")
            return 0

        logger.info(f"Indexing {len(documents)} documents into Safety Auditor store...")

        # Silo validation: reject documents from other domains
        valid_docs = []
        rejected = 0
        for doc in documents:
            data_type = doc.metadata.get('data_type', '')
            source_type = doc.metadata.get('source_type', '')
            if data_type in SILO_ALLOWED_TYPES or source_type in SILO_ALLOWED_TYPES:
                valid_docs.append(doc)
            else:
                rejected += 1
                logger.warning(
                    f"Silo violation: rejected document with data_type='{data_type}', "
                    f"source_type='{source_type}' (not in safety/compliance domain)"
                )
        if rejected > 0:
            logger.warning(f"Silo enforcement: rejected {rejected}/{len(documents)} documents")
        documents = valid_docs

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

        doc_ids = []
        for i, doc in enumerate(documents):
            source = doc.metadata.get('source_type', 'auditor')
            data_type = doc.metadata.get('data_type', 'safety')
            content_hash = abs(hash(doc.page_content[:200]))
            doc_id = f"auditor_{source}_{data_type}_{i}_{content_hash}"
            doc_ids.append(doc_id)

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
        logger.info(f"Searching Auditor documents for: '{query[:50]}...' (k={k})")

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
        logger.info(f"Searching Auditor documents with scores for: '{query[:50]}...'")
        results = self.vectorstore.similarity_search_with_score(query, k=k)
        logger.info(f"Found {len(results)} relevant documents with scores")
        return results

    def search_by_compliance_type(
        self,
        query: str,
        compliance_type: str,
        k: int = 5
    ) -> List[Document]:
        return self.similarity_search(
            query=query,
            k=k,
            filter_dict={"data_type": compliance_type}
        )

    def get_retriever(self, k: int = 5):
        return self.vectorstore.as_retriever(
            search_type="similarity",
            search_kwargs={"k": k}
        )

    def get_silo_audit(self) -> dict:
        """Return collection stats and unique data_types for silo auditing."""
        doc_count = self.get_document_count()
        data_types = set()
        try:
            collection = self.vectorstore._collection
            result = collection.get(include=["metadatas"])
            if result and result.get("metadatas"):
                for meta in result["metadatas"]:
                    if meta:
                        dt = meta.get("data_type", "unknown")
                        data_types.add(dt)
        except Exception as e:
            logger.warning(f"Silo audit metadata scan failed: {e}")
        return {
            "agent": "telemetry_agent",
            "collection": self.collection_name,
            "document_count": doc_count,
            "allowed_types": sorted(SILO_ALLOWED_TYPES),
            "actual_data_types": sorted(data_types),
            "silo_clean": data_types.issubset(SILO_ALLOWED_TYPES | {"unknown"}),
        }


# Backward compatibility alias
IlligoVectorStore = SafetyAuditorStore
