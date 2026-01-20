"""
Telekom Minister Data Loader

Processes Telekom infrastructure documentation PDFs for RAG-based querying:
- ETSI standards
- Service Level Agreements (SLAs)
- Network Intent documentation
- Troubleshooting procedures

Migrated from src/ingestion/telekom_loader.py for agent-specific ownership.

Author: Thesis Project - Agentic Infra Co-Pilot
"""

from pathlib import Path
from typing import List
import logging
from langchain_core.documents import Document
from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class TelekomLoader:
    """Loads and chunks Telekom PDF documentation for the Minister agent."""

    def __init__(
        self,
        pdf_dir: str = "data/raw/telekom",
        chunk_size: int = 1000,
        chunk_overlap: int = 200
    ):
        """
        Initialize the Telekom loader.

        Args:
            pdf_dir: Directory containing Telekom PDF files
            chunk_size: Size of text chunks in characters
            chunk_overlap: Overlap between chunks in characters
        """
        self.pdf_dir = Path(pdf_dir)
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    def load(self) -> List[Document]:
        """
        Load all PDF files from the Telekom directory and split into chunks.

        Returns:
            List of LangChain Documents with chunked text
        """
        logger.info(f"Loading Telekom PDFs from {self.pdf_dir}")

        if not self.pdf_dir.exists():
            logger.warning(f"Directory not found: {self.pdf_dir}. Creating it.")
            self.pdf_dir.mkdir(parents=True, exist_ok=True)
            logger.warning("Directory created but no PDFs found. Returning empty list.")
            return []

        # Find all PDF files
        pdf_files = list(self.pdf_dir.glob("*.pdf"))

        if not pdf_files:
            logger.warning(f"No PDF files found in {self.pdf_dir}")
            return []

        logger.info(f"Found {len(pdf_files)} PDF files to process")

        all_documents = []

        # Initialize text splitter
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=self.chunk_size,
            chunk_overlap=self.chunk_overlap,
            length_function=len,
            separators=["\n\n", "\n", ". ", " ", ""]
        )

        # Process each PDF
        for pdf_file in pdf_files:
            try:
                logger.info(f"Processing: {pdf_file.name}")

                # Load PDF using LangChain PyPDFLoader
                loader = PyPDFLoader(str(pdf_file))
                documents = loader.load()

                logger.info(f"  Loaded {len(documents)} pages from {pdf_file.name}")

                # Split documents into chunks
                chunks = text_splitter.split_documents(documents)

                logger.info(f"  Created {len(chunks)} chunks")

                # Enhance metadata for Minister-specific context
                for chunk in chunks:
                    chunk.metadata.update({
                        'source_type': 'telekom_documentation',
                        'data_type': 'network_intent',
                        'file_name': pdf_file.name,
                        'content_type': 'pdf_document',
                        'agent': 'telekom_minister'
                    })

                all_documents.extend(chunks)

            except Exception as e:
                logger.error(f"Error processing {pdf_file.name}: {str(e)}")
                continue

        logger.info(f"Total documents created: {len(all_documents)}")
        return all_documents

    def load_single_pdf(self, pdf_path: str) -> List[Document]:
        """
        Load a single PDF file and split into chunks.

        Args:
            pdf_path: Path to a specific PDF file

        Returns:
            List of LangChain Documents
        """
        pdf_file = Path(pdf_path)

        if not pdf_file.exists():
            logger.error(f"PDF file not found: {pdf_path}")
            raise FileNotFoundError(f"PDF file not found: {pdf_path}")

        logger.info(f"Loading single PDF: {pdf_file.name}")

        # Load PDF
        loader = PyPDFLoader(str(pdf_file))
        documents = loader.load()

        logger.info(f"Loaded {len(documents)} pages")

        # Split into chunks
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=self.chunk_size,
            chunk_overlap=self.chunk_overlap,
            length_function=len,
            separators=["\n\n", "\n", ". ", " ", ""]
        )

        chunks = text_splitter.split_documents(documents)

        logger.info(f"Created {len(chunks)} chunks")

        # Enhance metadata
        for chunk in chunks:
            chunk.metadata.update({
                'source_type': 'telekom_documentation',
                'data_type': 'network_intent',
                'file_name': pdf_file.name,
                'content_type': 'pdf_document',
                'agent': 'telekom_minister'
            })

        return chunks


def main():
    """Test the Telekom loader."""
    logger.info("=" * 60)
    logger.info("Testing Telekom Minister Data Loader")
    logger.info("=" * 60)

    try:
        loader = TelekomLoader()
        documents = loader.load()

        logger.info(f"\nSuccessfully loaded {len(documents)} document chunks")

        if not documents:
            logger.warning("\nNo documents were loaded.")
            logger.info("\nTo test with actual data:")
            logger.info("1. Place PDF files in data/raw/telekom/")
            logger.info("2. Run this script again")
        else:
            # Display first chunk as example
            logger.info("\n" + "=" * 60)
            logger.info("EXAMPLE DOCUMENT CHUNK:")
            logger.info("=" * 60)
            print(f"\nContent (first 300 chars):\n{documents[0].page_content[:300]}...\n")
            print(f"Metadata:\n{documents[0].metadata}\n")

        logger.info("\n" + "=" * 60)
        logger.info("Loader test completed!")
        logger.info("=" * 60)

    except Exception as e:
        logger.error(f"Test failed: {str(e)}", exc_info=True)
        raise


if __name__ == "__main__":
    main()
