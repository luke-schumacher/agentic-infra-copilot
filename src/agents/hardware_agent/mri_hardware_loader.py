"""
MRI Hardware Data Loader

Loads processed Siemens MRI hardware data for the Hardware Agent:
- Documentation index (PDF metadata)
- Equipment specifications
- MRI Protocol PDFs
- Questionnaire survey data

Uses preprocessed CSVs from data/processed/hardware/ for fast RAG ingestion.

Environment Variables:
- HARDWARE_DATA_DIR: Path to processed hardware data (default: data/processed/hardware)
- RAW_PDF_DIR: Path to raw MRI PDFs (default: data/raw/siemens)

Author: Thesis Project - Healthcare MAS
"""

import os
import pandas as pd
from pathlib import Path
from typing import List, Dict, Any, Optional
import logging
from langchain_core.documents import Document
from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Default paths (can be overridden via environment variables)
DEFAULT_PROCESSED_DIR = "data/processed/hardware"
DEFAULT_RAW_PDF_DIR = "data/raw/siemens"


class MRIHardwareLoader:
    """Loads MRI hardware documentation and specifications for RAG."""

    def __init__(
        self,
        processed_dir: Optional[str] = None,
        raw_pdf_dir: Optional[str] = None,
        chunk_size: int = 1000,
        chunk_overlap: int = 200
    ):
        """
        Initialize the MRI Hardware loader.

        Args:
            processed_dir: Directory with preprocessed CSVs (env: HARDWARE_DATA_DIR)
            raw_pdf_dir: Directory with raw MRI PDFs (env: RAW_PDF_DIR)
            chunk_size: Size of text chunks for PDFs
            chunk_overlap: Overlap between chunks
        """
        self.processed_dir = Path(
            processed_dir or os.getenv("HARDWARE_DATA_DIR", DEFAULT_PROCESSED_DIR)
        )
        self.raw_pdf_dir = Path(
            raw_pdf_dir or os.getenv("RAW_PDF_DIR", DEFAULT_RAW_PDF_DIR)
        )
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

        logger.info(f"MRIHardwareLoader initialized with processed_dir={self.processed_dir}, raw_pdf_dir={self.raw_pdf_dir}")

    def load_documentation_index(self) -> List[Document]:
        """
        Load documentation index with PDF metadata.

        Returns:
            List of Documents with documentation metadata
        """
        csv_path = self.processed_dir / "documentation_index.csv"

        if not csv_path.exists():
            logger.warning(f"Documentation index not found: {csv_path}")
            return []

        logger.info(f"Loading documentation index: {csv_path}")

        try:
            df = pd.read_csv(csv_path, encoding='utf-8')
            documents = []

            # Group by category for better context
            for category in df['category'].unique():
                category_df = df[df['category'] == category]

                text_parts = [f"MRI DOCUMENTATION - {category}"]
                text_parts.append(f"Total documents: {len(category_df)}")
                text_parts.append("")

                for _, row in category_df.iterrows():
                    text_parts.append(f"- {row['filename']}")
                    text_parts.append(f"  Size: {row['size_mb']} MB")
                    text_parts.append(f"  Path: {row['path']}")
                    text_parts.append("")

                doc = Document(
                    page_content="\n".join(text_parts),
                    metadata={
                        'source_type': 'documentation_index',
                        'data_type': 'mri_documentation',
                        'category': category,
                        'doc_count': len(category_df),
                        'file_name': csv_path.name,
                        'agent': 'hardware_agent'
                    }
                )
                documents.append(doc)

            logger.info(f"Loaded {len(documents)} documentation categories")
            return documents

        except Exception as e:
            logger.error(f"Error loading documentation index: {str(e)}")
            return []

    def load_equipment_specifications(self) -> List[Document]:
        """
        Load equipment specifications from CSV.

        Returns:
            List of Documents with equipment specifications
        """
        csv_path = self.processed_dir / "versicharge_specifications.csv"

        if not csv_path.exists():
            logger.warning(f"Equipment specifications not found: {csv_path}")
            return []

        logger.info(f"Loading equipment specifications: {csv_path}")

        try:
            df = pd.read_csv(csv_path, encoding='utf-8')
            documents = []

            # Group by category for better context
            if 'category' in df.columns:
                for category in df['category'].unique():
                    category_df = df[df['category'] == category]
                    specs_text = [f"EQUIPMENT SPECIFICATIONS - {category}"]

                    for _, row in category_df.iterrows():
                        unit = row.get('unit', '') or ''
                        desc = row.get('description', '') or ''
                        specs_text.append(
                            f"- {row['parameter']}: {row['value']} {unit}"
                        )
                        if desc:
                            specs_text.append(f"  Description: {desc}")

                        fault_rel = row.get('fault_relevance')
                        if pd.notna(fault_rel) and fault_rel != 'N/A':
                            specs_text.append(f"  Fault Relevance: {fault_rel}")

                    doc = Document(
                        page_content="\n".join(specs_text),
                        metadata={
                            'source_type': 'equipment_specification',
                            'data_type': 'mri_hardware_specs',
                            'category': category,
                            'spec_count': len(category_df),
                            'file_name': csv_path.name,
                            'agent': 'hardware_agent'
                        }
                    )
                    documents.append(doc)
            else:
                # Flat structure
                specs_text = ["EQUIPMENT SPECIFICATIONS"]
                for _, row in df.iterrows():
                    specs_text.append(f"- {row.iloc[0]}: {row.iloc[1]}")

                doc = Document(
                    page_content="\n".join(specs_text),
                    metadata={
                        'source_type': 'equipment_specification',
                        'data_type': 'mri_hardware_specs',
                        'file_name': csv_path.name,
                        'agent': 'hardware_agent'
                    }
                )
                documents.append(doc)

            logger.info(f"Loaded {len(documents)} equipment specification groups")
            return documents

        except Exception as e:
            logger.error(f"Error loading equipment specifications: {str(e)}")
            return []

    def load_questionnaire_data(self) -> List[Document]:
        """
        Load questionnaire survey data from processed CSVs.

        Returns:
            List of Documents with survey responses
        """
        documents = []

        # Load wide format
        wide_path = self.processed_dir / "sample_processed_wide_format.csv"
        if wide_path.exists():
            try:
                df = pd.read_csv(wide_path, encoding='utf-8')
                logger.info(f"Loading questionnaire wide format: {len(df)} rows")

                for idx, row in df.iterrows():
                    text_parts = [f"MRI FACILITY SURVEY - Response {idx + 1}"]

                    for col in df.columns:
                        if pd.notna(row[col]):
                            text_parts.append(f"- {col}: {row[col]}")

                    doc = Document(
                        page_content="\n".join(text_parts),
                        metadata={
                            'source_type': 'questionnaire',
                            'data_type': 'facility_survey',
                            'response_id': idx,
                            'file_name': wide_path.name,
                            'agent': 'hardware_agent'
                        }
                    )
                    documents.append(doc)

            except Exception as e:
                logger.error(f"Error loading wide format: {str(e)}")

        # Load long format
        long_path = self.processed_dir / "sample_processed_long_format.csv"
        if long_path.exists():
            try:
                df = pd.read_csv(long_path, encoding='utf-8')
                logger.info(f"Loading questionnaire long format: {len(df)} rows")

                if 'response_id' in df.columns:
                    grouped = df.groupby('response_id')
                    for response_id, group in grouped:
                        text_parts = [f"Survey Response: {response_id}"]

                        for _, row in group.iterrows():
                            q = row.get('question_text', row.get('question', 'Unknown'))
                            a = row.get('answer_value', row.get('answer', 'No answer'))
                            text_parts.append(f"Q: {q}")
                            text_parts.append(f"A: {a}")
                            text_parts.append("")

                        doc = Document(
                            page_content="\n".join(text_parts),
                            metadata={
                                'source_type': 'questionnaire',
                                'data_type': 'facility_survey_long',
                                'response_id': str(response_id),
                                'file_name': long_path.name,
                                'agent': 'hardware_agent'
                            }
                        )
                        documents.append(doc)

            except Exception as e:
                logger.error(f"Error loading long format: {str(e)}")

        logger.info(f"Loaded {len(documents)} questionnaire documents")
        return documents

    def load_mri_pdfs(self, categories: Optional[List[str]] = None) -> List[Document]:
        """
        Load and chunk MRI-related PDFs.

        Args:
            categories: Filter by categories (e.g., ['System Specifications', 'Protocol Management'])
                       If None, loads all MRI-related PDFs

        Returns:
            List of chunked Documents from PDFs
        """
        # First check if we have a documentation index
        index_path = self.processed_dir / "documentation_index.csv"

        if not index_path.exists():
            logger.warning("No documentation index found, scanning raw directory")
            pdf_files = list(self.raw_pdf_dir.glob("*.pdf"))
        else:
            df = pd.read_csv(index_path)

            # Filter by categories if specified
            if categories:
                df = df[df['category'].isin(categories)]

            # Filter out non-MRI related PDFs (e.g., versicharge wallbox)
            mri_keywords = ['MRI', 'MAGNETOM', 'DCS_MR', 'Protocol', 'Radiologist']
            df = df[df['filename'].str.contains('|'.join(mri_keywords), case=False, na=False)]

            pdf_files = [Path(row['path']) for _, row in df.iterrows()]

        if not pdf_files:
            logger.warning("No MRI PDFs found")
            return []

        logger.info(f"Loading {len(pdf_files)} MRI PDFs")

        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=self.chunk_size,
            chunk_overlap=self.chunk_overlap,
            length_function=len,
            separators=["\n\n", "\n", ". ", " ", ""]
        )

        all_documents = []

        for pdf_path in pdf_files:
            if not pdf_path.exists():
                logger.warning(f"PDF not found: {pdf_path}")
                continue

            try:
                logger.info(f"Processing: {pdf_path.name}")

                loader = PyPDFLoader(str(pdf_path))
                documents = loader.load()

                logger.info(f"  Loaded {len(documents)} pages")

                chunks = text_splitter.split_documents(documents)

                logger.info(f"  Created {len(chunks)} chunks")

                # Enhance metadata
                for chunk in chunks:
                    chunk.metadata.update({
                        'source_type': 'mri_documentation',
                        'data_type': 'protocol_pdf',
                        'file_name': pdf_path.name,
                        'content_type': 'pdf_document',
                        'agent': 'hardware_agent'
                    })

                all_documents.extend(chunks)

            except Exception as e:
                logger.error(f"Error processing {pdf_path.name}: {str(e)}")
                continue

        logger.info(f"Total PDF chunks created: {len(all_documents)}")
        return all_documents

    def load(self, include_pdfs: bool = True) -> List[Document]:
        """
        Load all hardware data.

        Args:
            include_pdfs: Whether to load and chunk PDFs (slower)

        Returns:
            List of all Documents
        """
        logger.info(f"Loading MRI hardware data from {self.processed_dir}")

        all_documents = []

        # Load documentation index
        doc_index = self.load_documentation_index()
        all_documents.extend(doc_index)

        # Load equipment specifications
        specs = self.load_equipment_specifications()
        all_documents.extend(specs)

        # Load questionnaire data
        questionnaire = self.load_questionnaire_data()
        all_documents.extend(questionnaire)

        # Optionally load PDFs
        if include_pdfs:
            pdfs = self.load_mri_pdfs()
            all_documents.extend(pdfs)

        logger.info(f"Total documents loaded: {len(all_documents)}")
        return all_documents

    def get_summary(self) -> Dict[str, Any]:
        """
        Get a summary of available data.

        Returns:
            Dictionary with data statistics
        """
        summary = {
            'processed_dir': str(self.processed_dir),
            'raw_pdf_dir': str(self.raw_pdf_dir),
            'files': {}
        }

        for csv_file in self.processed_dir.glob("*.csv"):
            try:
                df = pd.read_csv(csv_file)
                summary['files'][csv_file.name] = {
                    'rows': len(df),
                    'columns': list(df.columns)
                }
            except Exception as e:
                summary['files'][csv_file.name] = {'error': str(e)}

        # Count PDFs
        if self.raw_pdf_dir.exists():
            pdf_count = len(list(self.raw_pdf_dir.glob("*.pdf")))
            summary['pdf_count'] = pdf_count

        return summary


def main():
    """Test the MRI Hardware loader."""
    logger.info("=" * 60)
    logger.info("Testing MRI Hardware Data Loader")
    logger.info("=" * 60)

    try:
        loader = MRIHardwareLoader()

        # Print summary
        summary = loader.get_summary()
        logger.info(f"\nData Summary:")
        for file, info in summary.get('files', {}).items():
            logger.info(f"  {file}: {info}")
        logger.info(f"  PDFs available: {summary.get('pdf_count', 0)}")

        # Load without PDFs for quick test
        documents = loader.load(include_pdfs=False)

        logger.info(f"\nLoaded {len(documents)} documents (excluding PDFs)")

        if documents:
            logger.info("\n" + "=" * 60)
            logger.info("EXAMPLE DOCUMENT:")
            logger.info("=" * 60)
            print(f"\nContent:\n{documents[0].page_content[:500]}...\n")
            print(f"Metadata:\n{documents[0].metadata}\n")

        logger.info("\n" + "=" * 60)
        logger.info("Loader test completed!")
        logger.info("=" * 60)

    except Exception as e:
        logger.error(f"Test failed: {str(e)}", exc_info=True)
        raise


if __name__ == "__main__":
    main()
