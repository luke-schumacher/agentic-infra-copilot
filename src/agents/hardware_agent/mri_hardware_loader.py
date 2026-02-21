"""
Diagnostic Specialist Data Loader

Loads processed data for The Specialist (Agent 1 - Diagnostic & Technical):
- DICOM conformance data (SOP Class UIDs from DCS PDFs)
- Per-customer error profiles from event logs
- DCS/CSPL technical documentation PDFs
- Event log errors via Polars lazy loading

Environment Variables:
- HARDWARE_DATA_DIR: Path to processed hardware data (default: data/processed/hardware)
- RAW_PDF_DIR: Path to raw MRI PDFs (default: data/raw/siemens)
- PARQUET_DATA_DIR: Path to raw parquet event logs (default: data/raw/siemens/eventlog_txt)

Author: Thesis Project - Agentic Infra Co-Pilot
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

DEFAULT_PROCESSED_DIR = "data/processed/hardware"
DEFAULT_RAW_PDF_DIR = "data/raw/siemens"
DEFAULT_PARQUET_DIR = "data/raw/siemens/eventlog_txt"

# DCS PDFs that are relevant for The Specialist
DCS_PDF_PATTERNS = [
    'DCS_MR_XA50', 'DCS_MR_XA51A', 'DCS_MR_XA60',
    'MAGNETOM_SOLA_CSPL', 'MAGNETOM Sola CSPL'
]


class MRIHardwareLoader:
    """Loads DICOM conformance data, hardware specs, and event log errors for RAG."""

    def __init__(
        self,
        processed_dir: Optional[str] = None,
        raw_pdf_dir: Optional[str] = None,
        parquet_dir: Optional[str] = None,
        chunk_size: int = 1000,
        chunk_overlap: int = 200
    ):
        self.processed_dir = Path(
            processed_dir or os.getenv("HARDWARE_DATA_DIR", DEFAULT_PROCESSED_DIR)
        )
        self.raw_pdf_dir = Path(
            raw_pdf_dir or os.getenv("RAW_PDF_DIR", DEFAULT_RAW_PDF_DIR)
        )
        self.parquet_dir = Path(
            parquet_dir or os.getenv("PARQUET_DATA_DIR", DEFAULT_PARQUET_DIR)
        )
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

        logger.info(f"MRIHardwareLoader initialized: processed={self.processed_dir}, pdfs={self.raw_pdf_dir}")

    def load_dicom_conformance(self) -> List[Document]:
        """Load DICOM SOP Class conformance data extracted from DCS PDFs."""
        csv_path = self.processed_dir / "dicom_sop_classes.csv"

        if not csv_path.exists():
            logger.warning(f"DICOM conformance data not found: {csv_path}")
            return []

        logger.info(f"Loading DICOM conformance: {csv_path}")

        try:
            df = pd.read_csv(csv_path, encoding='utf-8')
            documents = []

            # Group by source PDF for context
            group_col = 'source_pdf' if 'source_pdf' in df.columns else df.columns[0]
            for source, group in df.groupby(group_col):
                text_parts = [
                    f"DICOM CONFORMANCE - {source}",
                    f"Total SOP Classes: {len(group)}",
                    ""
                ]

                for _, row in group.iterrows():
                    uid = row.get('sop_class_uid', row.get('uid', ''))
                    name = row.get('sop_class_name', row.get('name', ''))
                    role = row.get('role', '')
                    supported = row.get('supported', '')
                    text_parts.append(f"- {name} ({uid})")
                    if role:
                        text_parts.append(f"  Role: {role}, Supported: {supported}")

                doc = Document(
                    page_content="\n".join(text_parts),
                    metadata={
                        'source_type': 'dicom_conformance',
                        'data_type': 'sop_class_table',
                        'source_pdf': str(source),
                        'sop_count': len(group),
                        'file_name': csv_path.name,
                        'agent': 'hardware_agent'
                    }
                )
                documents.append(doc)

            logger.info(f"Loaded {len(documents)} DICOM conformance document groups")
            return documents

        except Exception as e:
            logger.error(f"Error loading DICOM conformance: {str(e)}")
            return []

    def load_known_failure_modes(self) -> List[Document]:
        """Load per-customer error profiles from preprocessed event log summaries."""
        csv_path = self.processed_dir / "per_customer_error_profiles.csv"

        if not csv_path.exists():
            logger.warning(f"Error profiles not found: {csv_path}")
            return []

        logger.info(f"Loading error profiles: {csv_path}")

        try:
            df = pd.read_csv(csv_path, encoding='utf-8')
            documents = []

            # Group by customer_id
            group_col = 'customer_id' if 'customer_id' in df.columns else df.columns[0]
            for customer_id, group in df.groupby(group_col):
                text_parts = [
                    f"ERROR PROFILE - Customer {customer_id}",
                    f"Total error types: {len(group)}",
                    ""
                ]

                for _, row in group.iterrows():
                    source = row.get('source', row.get('error_source', ''))
                    count = row.get('occurrence_count', row.get('count', 0))
                    severity = row.get('severity', row.get('level', ''))
                    text_parts.append(f"- {source}: {count} occurrences ({severity})")

                doc = Document(
                    page_content="\n".join(text_parts),
                    metadata={
                        'source_type': 'error_profile',
                        'data_type': 'customer_error_summary',
                        'customer_id': str(customer_id),
                        'error_type_count': len(group),
                        'file_name': csv_path.name,
                        'agent': 'hardware_agent'
                    }
                )
                documents.append(doc)

            logger.info(f"Loaded {len(documents)} customer error profiles")
            return documents

        except Exception as e:
            logger.error(f"Error loading failure modes: {str(e)}")
            return []

    def load_failure_mode_catalog(self) -> List[Document]:
        """Load curated failure mode catalog (FM-001 through FM-020)."""
        csv_path = self.processed_dir / "failure_modes.csv"

        if not csv_path.exists():
            logger.warning(f"Failure mode catalog not found: {csv_path}")
            return []

        logger.info(f"Loading failure mode catalog: {csv_path}")

        try:
            df = pd.read_csv(csv_path, encoding='utf-8')
            documents = []

            for _, row in df.iterrows():
                fm_id = row.get('failure_id', '')
                mode = row.get('failure_mode', '')
                component = row.get('component', '')
                symptom = row.get('symptom', '')
                root_cause = row.get('root_cause', '')
                detection = row.get('detection_method', '')
                severity = row.get('severity', '')
                mttr = row.get('mttr_hours', '')
                repair = row.get('repair_action', '')
                parts = row.get('spare_parts_required', '')
                pm = row.get('preventive_maintenance', '')

                text_parts = [
                    f"FAILURE MODE {fm_id}: {mode}",
                    f"Component: {component}",
                    f"Severity: {severity}",
                    f"Symptom: {symptom}",
                    f"Root Cause: {root_cause}",
                    f"Detection Method: {detection}",
                    f"Mean Time to Repair: {mttr} hours",
                    f"Repair Action: {repair}",
                    f"Spare Parts: {parts}",
                    f"Preventive Maintenance: {pm}",
                ]

                doc = Document(
                    page_content="\n".join(text_parts),
                    metadata={
                        'source_type': 'failure_catalog',
                        'data_type': 'known_failure_mode',
                        'failure_id': str(fm_id),
                        'failure_mode': str(mode),
                        'component': str(component),
                        'severity': str(severity),
                        'file_name': csv_path.name,
                        'agent': 'hardware_agent'
                    }
                )
                documents.append(doc)

            logger.info(f"Loaded {len(documents)} failure mode definitions")
            return documents

        except Exception as e:
            logger.error(f"Error loading failure mode catalog: {str(e)}")
            return []

    def load_event_log_errors(self, customer_id: Optional[str] = None, limit: int = 2000) -> List[Document]:
        """
        Load error events from Parquet files via LazyParquetLoader.

        Args:
            customer_id: Optional filter by customer
            limit: Max events per customer to load
        """
        try:
            from src.preprocessing.parquet_loader import LazyParquetLoader
        except ImportError:
            logger.warning("LazyParquetLoader not available, skipping event log loading")
            return []

        try:
            loader = LazyParquetLoader(str(self.parquet_dir))
            documents = []

            if customer_id:
                customers = [customer_id]
            else:
                customers = loader.list_customers()  # All customers

            for cid in customers:
                try:
                    errors = loader.query_events_for_customer(cid, severity='E', limit=limit)
                    if errors.is_empty():
                        continue

                    text_parts = [
                        f"EVENT LOG ERRORS - Customer {cid}",
                        f"Error events (sample of {len(errors)}):",
                        ""
                    ]

                    for row in errors.iter_rows(named=True):
                        source = row.get('source', 'unknown')
                        desc = str(row.get('masked_description', row.get('description', '')))[:150]
                        event_id = row.get('event_id', '')
                        text_parts.append(f"- [{source}] {event_id}: {desc}")

                    doc = Document(
                        page_content="\n".join(text_parts[:200]),  # Cap at ~200 lines
                        metadata={
                            'source_type': 'event_log',
                            'data_type': 'error_events',
                            'customer_id': cid,
                            'event_count': len(errors),
                            'agent': 'hardware_agent'
                        }
                    )
                    documents.append(doc)

                except Exception as e:
                    logger.warning(f"Error loading events for {cid}: {e}")
                    continue

            logger.info(f"Loaded {len(documents)} event log error documents")
            return documents

        except Exception as e:
            logger.error(f"Error loading event log errors: {str(e)}")
            return []

    def load_documentation_index(self) -> List[Document]:
        """Load documentation index with PDF metadata."""
        csv_path = self.processed_dir / "documentation_index.csv"

        if not csv_path.exists():
            logger.warning(f"Documentation index not found: {csv_path}")
            return []

        logger.info(f"Loading documentation index: {csv_path}")

        try:
            df = pd.read_csv(csv_path, encoding='utf-8')
            documents = []

            for category in df['category'].unique():
                category_df = df[df['category'] == category]

                text_parts = [f"MRI DOCUMENTATION - {category}"]
                text_parts.append(f"Total documents: {len(category_df)}")
                text_parts.append("")

                for _, row in category_df.iterrows():
                    text_parts.append(f"- {row['filename']}")
                    text_parts.append(f"  Size: {row['size_mb']} MB")
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

    def load_mri_pdfs(self) -> List[Document]:
        """Load and chunk DCS/CSPL technical documentation PDFs."""
        # Find DCS PDFs only
        pdf_files = []
        for pattern in DCS_PDF_PATTERNS:
            found = list(self.raw_pdf_dir.glob(f"*{pattern}*"))
            pdf_files.extend([f for f in found if f.suffix.lower() == '.pdf'])

        # Deduplicate (skip copies like "DCS_MR_XA60 (1).pdf")
        seen_stems = set()
        unique_pdfs = []
        for pdf in pdf_files:
            stem = pdf.stem.split(' (')[0]  # Remove " (1)" suffix
            if stem not in seen_stems:
                seen_stems.add(stem)
                unique_pdfs.append(pdf)

        if not unique_pdfs:
            logger.warning("No DCS/CSPL PDFs found")
            return []

        logger.info(f"Loading {len(unique_pdfs)} DCS/CSPL PDFs")

        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=self.chunk_size,
            chunk_overlap=self.chunk_overlap,
            length_function=len,
            separators=["\n\n", "\n", ". ", " ", ""]
        )

        all_documents = []

        for pdf_path in unique_pdfs:
            try:
                logger.info(f"Processing: {pdf_path.name}")
                loader = PyPDFLoader(str(pdf_path))
                documents = loader.load()

                chunks = text_splitter.split_documents(documents)

                for chunk in chunks:
                    chunk.metadata.update({
                        'source_type': 'dcs_documentation',
                        'data_type': 'dicom_conformance_pdf',
                        'file_name': pdf_path.name,
                        'agent': 'hardware_agent'
                    })

                all_documents.extend(chunks)
                logger.info(f"  Created {len(chunks)} chunks from {len(documents)} pages")

            except Exception as e:
                logger.error(f"Error processing {pdf_path.name}: {str(e)}")
                continue

        logger.info(f"Total PDF chunks created: {len(all_documents)}")
        return all_documents

    def load_common_failure_modes(self) -> List[Document]:
        """Load common failure modes from raw data CSV."""
        csv_path = self.raw_pdf_dir / "common_failure_modes.csv"

        if not csv_path.exists():
            logger.warning(f"Common failure modes CSV not found: {csv_path}")
            return []

        logger.info(f"Loading common failure modes: {csv_path}")

        try:
            df = pd.read_csv(csv_path, encoding='utf-8')
            documents = []

            for _, row in df.iterrows():
                fm_id = row.get('failure_id', '')
                mode = row.get('failure_mode', '')
                component = row.get('component', '')
                symptom = row.get('symptom', '')
                root_cause = row.get('root_cause', '')
                severity = row.get('severity', '')
                repair = row.get('repair_action', '')

                text_parts = [
                    f"COMMON FAILURE MODE {fm_id}: {mode}",
                    f"Component: {component}",
                    f"Severity: {severity}",
                    f"Symptom: {symptom}",
                    f"Root Cause: {root_cause}",
                    f"Repair Action: {repair}",
                ]

                doc = Document(
                    page_content="\n".join(text_parts),
                    metadata={
                        'source_type': 'failure_catalog',
                        'data_type': 'common_failure_mode',
                        'failure_id': str(fm_id),
                        'component': str(component),
                        'severity': str(severity),
                        'file_name': csv_path.name,
                        'agent': 'hardware_agent'
                    }
                )
                documents.append(doc)

            logger.info(f"Loaded {len(documents)} common failure modes")
            return documents

        except Exception as e:
            logger.error(f"Error loading common failure modes: {str(e)}")
            return []

    def load(self, include_pdfs: bool = True, include_event_logs: bool = True) -> List[Document]:
        """
        Load all hardware data for RAG indexing.

        Args:
            include_pdfs: Whether to load and chunk DCS PDFs (slower)
            include_event_logs: Whether to query Parquet event logs (memory-intensive)
        """
        logger.info(f"Loading Diagnostic Specialist data from {self.processed_dir}")

        all_documents = []

        doc_index = self.load_documentation_index()
        all_documents.extend(doc_index)

        dicom = self.load_dicom_conformance()
        all_documents.extend(dicom)

        error_profiles = self.load_known_failure_modes()
        all_documents.extend(error_profiles)

        failure_catalog = self.load_failure_mode_catalog()
        all_documents.extend(failure_catalog)

        common_fms = self.load_common_failure_modes()
        all_documents.extend(common_fms)

        if include_pdfs:
            pdfs = self.load_mri_pdfs()
            all_documents.extend(pdfs)

        if include_event_logs:
            events = self.load_event_log_errors()
            all_documents.extend(events)

        logger.info(f"Total documents loaded: {len(all_documents)}")
        return all_documents

    def get_summary(self) -> Dict[str, Any]:
        """Get a summary of available data."""
        summary = {
            'processed_dir': str(self.processed_dir),
            'raw_pdf_dir': str(self.raw_pdf_dir),
            'parquet_dir': str(self.parquet_dir),
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

        # Count DCS PDFs
        dcs_count = 0
        for pattern in DCS_PDF_PATTERNS:
            dcs_count += len(list(self.raw_pdf_dir.glob(f"*{pattern}*.pdf")))
        summary['dcs_pdf_count'] = dcs_count

        return summary


def main():
    """Test the MRI Hardware loader."""
    logger.info("=" * 60)
    logger.info("Testing Diagnostic Specialist Data Loader")
    logger.info("=" * 60)

    try:
        loader = MRIHardwareLoader()
        summary = loader.get_summary()
        logger.info(f"\nData Summary:")
        for file, info in summary.get('files', {}).items():
            logger.info(f"  {file}: {info}")
        logger.info(f"  DCS PDFs: {summary.get('dcs_pdf_count', 0)}")

        documents = loader.load(include_pdfs=False)
        logger.info(f"\nLoaded {len(documents)} documents (excluding PDFs)")

        if documents:
            logger.info(f"\nExample: {documents[0].page_content[:300]}...")

    except Exception as e:
        logger.error(f"Test failed: {str(e)}", exc_info=True)
        raise


if __name__ == "__main__":
    main()
