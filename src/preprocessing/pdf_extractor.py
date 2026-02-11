"""
MRI PDF Extractor - Table-aware PDF extraction for DICOM Conformance Statements

Uses pdfplumber for structured table extraction from DCS PDFs,
which contain SOP Class UID mappings critical for Agent 1 (The Specialist).

Author: Thesis Project - Agentic Infra Co-Pilot
"""

import re
import csv
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional

try:
    import pdfplumber
except ImportError:
    pdfplumber = None

from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.documents import Document

logger = logging.getLogger(__name__)


class MRIPDFExtractor:
    """Extract text and tables from Siemens MRI PDFs."""

    def __init__(self, chunk_size: int = 1000, chunk_overlap: int = 200):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            separators=["\n\n", "\n", ". ", " ", ""]
        )

    def extract_text(self, pdf_path: Path) -> List[Document]:
        """Standard text extraction using PyPDFLoader."""
        pdf_path = Path(pdf_path)
        if not pdf_path.exists():
            logger.warning(f"PDF not found: {pdf_path}")
            return []

        try:
            loader = PyPDFLoader(str(pdf_path))
            pages = loader.load()
            for page in pages:
                page.metadata['file_name'] = pdf_path.name
                page.metadata['source_type'] = 'siemens_pdf'
            return pages
        except Exception as e:
            logger.error(f"Failed to extract text from {pdf_path}: {e}")
            return []

    def extract_tables(self, pdf_path: Path) -> List[Dict[str, Any]]:
        """
        Extract tables from PDF using pdfplumber.

        Returns list of dicts with: page_number, table_index, headers, rows.
        """
        if pdfplumber is None:
            logger.warning("pdfplumber not installed. Install with: pip install pdfplumber")
            return []

        pdf_path = Path(pdf_path)
        tables = []

        try:
            with pdfplumber.open(str(pdf_path)) as pdf:
                for page_num, page in enumerate(pdf.pages, 1):
                    page_tables = page.extract_tables()
                    for table_idx, table in enumerate(page_tables):
                        if not table or len(table) < 2:
                            continue

                        # First row as headers, rest as data
                        headers = [str(h).strip() if h else f"col_{i}" for i, h in enumerate(table[0])]
                        rows = []
                        for row in table[1:]:
                            row_dict = {}
                            for i, cell in enumerate(row):
                                key = headers[i] if i < len(headers) else f"col_{i}"
                                row_dict[key] = str(cell).strip() if cell else ""
                            rows.append(row_dict)

                        tables.append({
                            'page_number': page_num,
                            'table_index': table_idx,
                            'headers': headers,
                            'rows': rows,
                            'source_file': pdf_path.name,
                        })
        except Exception as e:
            logger.error(f"Failed to extract tables from {pdf_path}: {e}")

        return tables

    def extract_dicom_sop_classes(self, dcs_pdf_path: Path) -> List[Dict[str, str]]:
        """
        Parse DICOM SOP Class UID tables from DCS (DICOM Conformance Statement) PDFs.

        Returns list of dicts with: sop_class_uid, sop_class_name, transfer_syntaxes, role, supported.
        """
        tables = self.extract_tables(dcs_pdf_path)
        sop_entries = []

        # UID pattern: digits separated by dots (e.g., 1.2.840.10008.5.1.4.1.1.4)
        uid_pattern = re.compile(r'\d+\.\d+\.\d+(?:\.\d+)+')

        for table in tables:
            headers_lower = [h.lower() for h in table['headers']]

            # Look for tables containing SOP Class UIDs
            has_uid_col = any('uid' in h or 'sop' in h for h in headers_lower)
            if not has_uid_col:
                # Check if any cell contains a UID pattern
                has_uid_data = False
                for row in table['rows'][:3]:
                    for val in row.values():
                        if uid_pattern.search(val):
                            has_uid_data = True
                            break
                    if has_uid_data:
                        break
                if not has_uid_data:
                    continue

            for row in table['rows']:
                values = list(row.values())
                # Find the cell containing a UID
                uid_val = ""
                name_val = ""
                role_val = ""

                for i, val in enumerate(values):
                    if uid_pattern.search(val):
                        uid_val = uid_pattern.search(val).group()
                    elif len(val) > 10 and not uid_val:
                        # Longest non-UID text is likely the name
                        if len(val) > len(name_val):
                            name_val = val

                if uid_val:
                    # Check for role indicators
                    row_text = " ".join(values).lower()
                    if 'scu' in row_text:
                        role_val = 'SCU'
                    elif 'scp' in row_text:
                        role_val = 'SCP'
                    elif 'both' in row_text:
                        role_val = 'SCU/SCP'

                    sop_entries.append({
                        'sop_class_uid': uid_val,
                        'sop_class_name': name_val.strip(),
                        'role': role_val,
                        'supported': 'yes',
                        'source_pdf': Path(dcs_pdf_path).name,
                        'page': table['page_number'],
                    })

        # Deduplicate by UID within same PDF
        seen = set()
        unique_entries = []
        for entry in sop_entries:
            key = (entry['sop_class_uid'], entry['source_pdf'])
            if key not in seen:
                seen.add(key)
                unique_entries.append(entry)

        logger.info(f"Extracted {len(unique_entries)} SOP Class UIDs from {Path(dcs_pdf_path).name}")
        return unique_entries

    def extract_with_chunking(
        self,
        pdf_path: Path,
        extra_metadata: Optional[Dict[str, str]] = None
    ) -> List[Document]:
        """
        Full pipeline: extract text -> chunk -> add metadata.

        Args:
            pdf_path: Path to the PDF file
            extra_metadata: Additional metadata to attach to each chunk

        Returns:
            List of chunked Documents with metadata
        """
        pages = self.extract_text(pdf_path)
        if not pages:
            return []

        # Chunk the pages
        chunks = self.text_splitter.split_documents(pages)

        # Add extra metadata
        category = self._classify_pdf(Path(pdf_path).name)
        for chunk in chunks:
            chunk.metadata['category'] = category
            chunk.metadata['chunk_size'] = self.chunk_size
            if extra_metadata:
                chunk.metadata.update(extra_metadata)

        logger.info(f"Extracted {len(chunks)} chunks from {Path(pdf_path).name}")
        return chunks

    def extract_all_from_directory(
        self,
        directory: Path,
        file_filter: Optional[List[str]] = None
    ) -> List[Document]:
        """
        Extract and chunk all PDFs from a directory.

        Args:
            directory: Directory containing PDFs
            file_filter: Optional list of filenames to include (None = all)

        Returns:
            Combined list of Document chunks from all PDFs
        """
        directory = Path(directory)
        all_chunks = []

        for pdf_file in sorted(directory.glob("*.pdf")):
            if file_filter and pdf_file.name not in file_filter:
                continue

            chunks = self.extract_with_chunking(pdf_file)
            all_chunks.extend(chunks)

        logger.info(f"Total: {len(all_chunks)} chunks from {directory}")
        return all_chunks

    def export_sop_classes_to_csv(
        self,
        dcs_pdf_paths: List[Path],
        output_path: Path
    ) -> int:
        """
        Extract DICOM SOP classes from multiple DCS PDFs and write to CSV.

        Returns number of entries written.
        """
        all_entries = []
        for pdf_path in dcs_pdf_paths:
            entries = self.extract_dicom_sop_classes(pdf_path)
            all_entries.extend(entries)

        if not all_entries:
            logger.warning("No SOP Class entries extracted from DCS PDFs")
            return 0

        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        fieldnames = ['sop_class_uid', 'sop_class_name', 'role', 'supported', 'source_pdf', 'page']
        with open(output_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(all_entries)

        logger.info(f"Exported {len(all_entries)} SOP Class entries to {output_path}")
        return len(all_entries)

    @staticmethod
    def _classify_pdf(filename: str) -> str:
        """Classify a PDF by its filename."""
        name_lower = filename.lower()
        if 'dcs' in name_lower:
            return 'dicom_conformance'
        elif 'magnetom' in name_lower or 'cspl' in name_lower:
            return 'hardware_spec'
        elif 'sop' in name_lower or 'safety' in name_lower:
            return 'safety_sop'
        elif 'mrrt' in name_lower or 'questionnaire' in name_lower:
            return 'questionnaire'
        elif 'protocol' in name_lower:
            return 'protocol_management'
        elif 'acr' in name_lower:
            return 'clinical_guidelines'
        return 'general'
