"""
Safety Auditor Data Loader

Loads processed data for The Auditor (Agent 3 - Safety & Compliance):
- MRI safety procedures from MRI-SOP.pdf
- Safety zone definitions (Zone I-IV)
- Personnel requirements (Level 1/Level 2 MR Personnel)
- Safety-relevant event flags from event logs
- Safety PDF documents (MRI-SOP, Safety Training, ACR Criteria)

Environment Variables:
- TELEMETRY_DATA_DIR: Path to processed telemetry data (default: data/processed/telemetry)
- RAW_PDF_DIR: Path to raw MRI PDFs (default: data/raw/siemens)

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

DEFAULT_PROCESSED_DIR = "data/processed/telemetry"
DEFAULT_RAW_PDF_DIR = "data/raw/siemens"

# Safety-related PDFs for The Auditor
SAFETY_PDF_PATTERNS = [
    'MRI-SOP', 'SOP-MRI-Safety', 'SOP_MRI_Safety',
    'ACRAppropriateness', 'ACR_Appropriateness'
]


class MRITelemetryLoader:
    """Loads MRI safety procedures, zone definitions, and compliance data for RAG."""

    def __init__(
        self,
        data_dir: Optional[str] = None,
        raw_dir: Optional[str] = None,
        chunk_size: int = 1000,
        chunk_overlap: int = 200
    ):
        self.data_dir = Path(
            data_dir or os.getenv("TELEMETRY_DATA_DIR", DEFAULT_PROCESSED_DIR)
        )
        self.raw_dir = Path(
            raw_dir or os.getenv("RAW_PDF_DIR", DEFAULT_RAW_PDF_DIR)
        )
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

        logger.info(f"MRITelemetryLoader initialized: data={self.data_dir}, pdfs={self.raw_dir}")

    def load_safety_procedures(self) -> List[Document]:
        """Load MRI safety procedures extracted from MRI-SOP.pdf."""
        csv_path = self.data_dir / "safety_procedures.csv"

        if not csv_path.exists():
            logger.warning(f"Safety procedures not found: {csv_path}")
            return []

        logger.info(f"Loading safety procedures: {csv_path}")

        try:
            df = pd.read_csv(csv_path, encoding='utf-8')
            documents = []

            # Group by section/category if available
            group_col = None
            for col in ['section', 'category', 'procedure_type']:
                if col in df.columns:
                    group_col = col
                    break

            if group_col:
                for section, group in df.groupby(group_col):
                    text_parts = [
                        f"MRI SAFETY PROCEDURE - {section}",
                        f"Items: {len(group)}",
                        ""
                    ]

                    for _, row in group.iterrows():
                        for col in group.columns:
                            if col != group_col and pd.notna(row[col]):
                                text_parts.append(f"  {col}: {row[col]}")
                        text_parts.append("")

                    doc = Document(
                        page_content="\n".join(text_parts),
                        metadata={
                            'source_type': 'safety_procedure',
                            'data_type': 'mri_sop',
                            'section': str(section),
                            'item_count': len(group),
                            'file_name': csv_path.name,
                            'agent': 'telemetry_agent'
                        }
                    )
                    documents.append(doc)
            else:
                # Single document with all procedures
                text_parts = ["MRI SAFETY PROCEDURES", f"Total entries: {len(df)}", ""]
                for _, row in df.iterrows():
                    text_parts.append(" | ".join(str(v) for v in row.values if pd.notna(v)))
                    text_parts.append("")

                doc = Document(
                    page_content="\n".join(text_parts),
                    metadata={
                        'source_type': 'safety_procedure',
                        'data_type': 'mri_sop',
                        'entry_count': len(df),
                        'file_name': csv_path.name,
                        'agent': 'telemetry_agent'
                    }
                )
                documents.append(doc)

            logger.info(f"Loaded {len(documents)} safety procedure documents")
            return documents

        except Exception as e:
            logger.error(f"Error loading safety procedures: {str(e)}")
            return []

    def load_safety_zones(self) -> List[Document]:
        """Load MRI safety zone definitions (Zone I-IV)."""
        csv_path = self.data_dir / "safety_zones.csv"

        if not csv_path.exists():
            logger.warning(f"Safety zones not found: {csv_path}")
            return []

        logger.info(f"Loading safety zones: {csv_path}")

        try:
            df = pd.read_csv(csv_path, encoding='utf-8')
            documents = []

            for _, row in df.iterrows():
                zone = row.get('zone', row.get('zone_name', 'Unknown'))
                text_parts = [f"MRI SAFETY ZONE: {zone}"]

                for col in df.columns:
                    if pd.notna(row[col]):
                        label = col.replace('_', ' ').title()
                        text_parts.append(f"{label}: {row[col]}")

                doc = Document(
                    page_content="\n".join(text_parts),
                    metadata={
                        'source_type': 'safety_zone',
                        'data_type': 'zone_definition',
                        'zone': str(zone),
                        'file_name': csv_path.name,
                        'agent': 'telemetry_agent'
                    }
                )
                documents.append(doc)

            logger.info(f"Loaded {len(documents)} safety zone definitions")
            return documents

        except Exception as e:
            logger.error(f"Error loading safety zones: {str(e)}")
            return []

    def load_personnel_requirements(self) -> List[Document]:
        """Load minimum personnel requirements from SOP data."""
        # Personnel requirements may be in safety_procedures or a dedicated file
        csv_path = self.data_dir / "personnel_requirements.csv"

        if not csv_path.exists():
            # Try extracting from safety procedures
            proc_path = self.data_dir / "safety_procedures.csv"
            if proc_path.exists():
                return self._extract_personnel_from_procedures(proc_path)
            logger.warning(f"Personnel requirements not found")
            return []

        logger.info(f"Loading personnel requirements: {csv_path}")

        try:
            df = pd.read_csv(csv_path, encoding='utf-8')

            text_parts = [
                "MRI PERSONNEL REQUIREMENTS",
                f"Total requirement entries: {len(df)}",
                ""
            ]

            for _, row in df.iterrows():
                for col in df.columns:
                    if pd.notna(row[col]):
                        label = col.replace('_', ' ').title()
                        text_parts.append(f"{label}: {row[col]}")
                text_parts.append("")

            doc = Document(
                page_content="\n".join(text_parts),
                metadata={
                    'source_type': 'personnel_requirements',
                    'data_type': 'staffing_requirements',
                    'entry_count': len(df),
                    'file_name': csv_path.name,
                    'agent': 'telemetry_agent'
                }
            )

            logger.info(f"Loaded personnel requirements")
            return [doc]

        except Exception as e:
            logger.error(f"Error loading personnel requirements: {str(e)}")
            return []

    def _extract_personnel_from_procedures(self, proc_path: Path) -> List[Document]:
        """Extract personnel info from safety procedures file."""
        try:
            df = pd.read_csv(proc_path, encoding='utf-8')
            # Filter for personnel-related entries
            personnel_keywords = ['personnel', 'staff', 'level 1', 'level 2', 'supervision', 'training']
            mask = df.apply(
                lambda row: any(
                    kw in str(v).lower() for v in row.values for kw in personnel_keywords
                ), axis=1
            )
            personnel_df = df[mask]

            if personnel_df.empty:
                return []

            text_parts = [
                "MRI PERSONNEL REQUIREMENTS (from SOP)",
                f"Relevant entries: {len(personnel_df)}",
                ""
            ]

            for _, row in personnel_df.iterrows():
                text_parts.append(" | ".join(str(v) for v in row.values if pd.notna(v)))
                text_parts.append("")

            doc = Document(
                page_content="\n".join(text_parts),
                metadata={
                    'source_type': 'personnel_requirements',
                    'data_type': 'sop_personnel_extract',
                    'entry_count': len(personnel_df),
                    'agent': 'telemetry_agent'
                }
            )
            return [doc]

        except Exception as e:
            logger.error(f"Error extracting personnel from procedures: {e}")
            return []

    def load_safety_event_flags(self) -> List[Document]:
        """Load safety-relevant event flags from event logs."""
        csv_path = self.data_dir / "safety_event_flags.csv"

        if not csv_path.exists():
            logger.warning(f"Safety event flags not found: {csv_path}")
            return []

        logger.info(f"Loading safety event flags: {csv_path}")

        try:
            df = pd.read_csv(csv_path, encoding='utf-8')
            documents = []

            group_col = 'customer_id' if 'customer_id' in df.columns else df.columns[0]
            for customer_id, group in df.groupby(group_col):
                text_parts = [
                    f"SAFETY EVENT FLAGS - Customer {customer_id}",
                    f"Flagged events: {len(group)}",
                    ""
                ]

                for _, row in group.iterrows():
                    source = row.get('source', '')
                    desc = str(row.get('description', row.get('masked_description', '')))[:150]
                    keyword = row.get('safety_keyword', '')
                    text_parts.append(f"- [{source}] {desc}")
                    if keyword:
                        text_parts.append(f"  Keyword: {keyword}")

                doc = Document(
                    page_content="\n".join(text_parts[:100]),
                    metadata={
                        'source_type': 'safety_events',
                        'data_type': 'safety_event_flags',
                        'customer_id': str(customer_id),
                        'event_count': len(group),
                        'file_name': csv_path.name,
                        'agent': 'telemetry_agent'
                    }
                )
                documents.append(doc)

            logger.info(f"Loaded {len(documents)} safety event flag documents")
            return documents

        except Exception as e:
            logger.error(f"Error loading safety event flags: {str(e)}")
            return []

    def load_safety_pdfs(self) -> List[Document]:
        """Load and chunk MRI safety PDFs (MRI-SOP, Safety Training, ACR Criteria)."""
        pdf_files = []
        for pattern in SAFETY_PDF_PATTERNS:
            found = list(self.raw_dir.glob(f"*{pattern}*"))
            pdf_files.extend([f for f in found if f.suffix.lower() == '.pdf'])

        # Deduplicate
        seen_stems = set()
        unique_pdfs = []
        for pdf in pdf_files:
            stem = pdf.stem.split(' (')[0]
            if stem not in seen_stems:
                seen_stems.add(stem)
                unique_pdfs.append(pdf)

        if not unique_pdfs:
            logger.warning("No safety PDFs found")
            return []

        logger.info(f"Loading {len(unique_pdfs)} safety PDFs")

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
                        'source_type': 'safety_documentation',
                        'data_type': 'safety_pdf',
                        'file_name': pdf_path.name,
                        'agent': 'telemetry_agent'
                    })

                all_documents.extend(chunks)
                logger.info(f"  Created {len(chunks)} chunks from {len(documents)} pages")

            except Exception as e:
                logger.error(f"Error processing {pdf_path.name}: {str(e)}")
                continue

        logger.info(f"Total safety PDF chunks: {len(all_documents)}")
        return all_documents

    def load(self, include_pdfs: bool = True) -> List[Document]:
        """Load all safety data for RAG indexing."""
        logger.info(f"Loading Safety Auditor data from {self.data_dir}")

        all_documents = []

        procedures = self.load_safety_procedures()
        all_documents.extend(procedures)

        zones = self.load_safety_zones()
        all_documents.extend(zones)

        personnel = self.load_personnel_requirements()
        all_documents.extend(personnel)

        safety_flags = self.load_safety_event_flags()
        all_documents.extend(safety_flags)

        if include_pdfs:
            pdfs = self.load_safety_pdfs()
            all_documents.extend(pdfs)

        logger.info(f"Total documents loaded: {len(all_documents)}")
        return all_documents

    def get_summary(self) -> Dict[str, Any]:
        """Get a summary of available data."""
        summary = {
            'data_dir': str(self.data_dir),
            'raw_dir': str(self.raw_dir),
            'files': {}
        }

        for csv_file in self.data_dir.glob("*.csv"):
            try:
                df = pd.read_csv(csv_file)
                summary['files'][csv_file.name] = {
                    'rows': len(df),
                    'columns': list(df.columns)
                }
            except Exception as e:
                summary['files'][csv_file.name] = {'error': str(e)}

        # Count safety PDFs
        safety_count = 0
        for pattern in SAFETY_PDF_PATTERNS:
            safety_count += len(list(self.raw_dir.glob(f"*{pattern}*.pdf")))
        summary['safety_pdf_count'] = safety_count

        return summary


def main():
    """Test the Safety Auditor loader."""
    logger.info("=" * 60)
    logger.info("Testing Safety Auditor Data Loader")
    logger.info("=" * 60)

    try:
        loader = MRITelemetryLoader()
        summary = loader.get_summary()
        logger.info(f"\nData Summary:")
        for file, info in summary.get('files', {}).items():
            logger.info(f"  {file}: {info}")
        logger.info(f"  Safety PDFs: {summary.get('safety_pdf_count', 0)}")

        documents = loader.load(include_pdfs=False)
        logger.info(f"\nLoaded {len(documents)} documents (excluding PDFs)")

        if documents:
            logger.info(f"\nExample: {documents[0].page_content[:300]}...")

    except Exception as e:
        logger.error(f"Test failed: {str(e)}", exc_info=True)
        raise


if __name__ == "__main__":
    main()
