"""
Workflow Anthropologist Data Loader

Loads processed data for The Anthropologist (Agent 2 - Workflow & Context):
- Institution profiles from MRRT questionnaire data
- Customer feedback and pain points
- Workload patterns from event log statistics
- Customer-to-institution mapping

Environment Variables:
- GOVERNANCE_DATA_DIR: Path to processed governance data (default: data/processed/governance)
- PROCESSED_BASE_DIR: Path to processed data root (default: data/processed)

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

DEFAULT_PROCESSED_DIR = "data/processed/governance"
DEFAULT_PROCESSED_BASE = "data/processed"
DEFAULT_RAW_DIR = "data/raw/siemens"

# Clinical/protocol PDFs for the Governance Agent
GOVERNANCE_PDF_PATTERNS = [
    'MRI-PROTOCOLS-COMPLETE', 'Radiologist MRI Interpretation Manual',
    'Siemens-Dot-Cockpit'
]


class ClinicalGovernanceLoader:
    """Loads institution profiles, workload patterns, and customer feedback for RAG."""

    def __init__(
        self,
        processed_dir: Optional[str] = None,
        processed_base: Optional[str] = None,
        raw_dir: Optional[str] = None,
        chunk_size: int = 1000,
        chunk_overlap: int = 200
    ):
        self.processed_dir = Path(
            processed_dir or os.getenv("GOVERNANCE_DATA_DIR", DEFAULT_PROCESSED_DIR)
        )
        self.processed_base = Path(
            processed_base or os.getenv("PROCESSED_BASE_DIR", DEFAULT_PROCESSED_BASE)
        )
        self.raw_dir = Path(
            raw_dir or os.getenv("RAW_DATA_DIR", DEFAULT_RAW_DIR)
        )
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

        logger.info(f"ClinicalGovernanceLoader initialized: {self.processed_dir}")

    def load_institution_profiles(self) -> List[Document]:
        """Load institution profiles from preprocessed questionnaire data."""
        csv_path = self.processed_dir / "institution_profiles.csv"

        if not csv_path.exists():
            logger.warning(f"Institution profiles not found: {csv_path}")
            return []

        logger.info(f"Loading institution profiles: {csv_path}")

        try:
            df = pd.read_csv(csv_path, encoding='utf-8')
            documents = []

            for _, row in df.iterrows():
                institution = row.get('institution_name', 'Unknown')
                country = row.get('country', 'Unknown')
                org_type = row.get('institution_type', row.get('org_type', 'Unknown'))

                text_parts = [
                    f"INSTITUTION PROFILE - {institution}",
                    f"Country: {country}",
                    f"Type: {org_type}",
                ]

                # Add available fields
                for field in ['equipment', 'scanner_model', 'patients_per_year',
                              'pct_mr_planning', 'clinical_sites_treated', 'pain_points']:
                    val = row.get(field)
                    if pd.notna(val) and str(val).strip():
                        label = field.replace('_', ' ').title()
                        text_parts.append(f"{label}: {val}")

                doc = Document(
                    page_content="\n".join(text_parts),
                    metadata={
                        'source_type': 'institution_profile',
                        'data_type': 'questionnaire_profile',
                        'institution_name': str(institution),
                        'country': str(country),
                        'institution_type': str(org_type),
                        'file_name': csv_path.name,
                        'agent': 'governance_agent'
                    }
                )
                documents.append(doc)

            logger.info(f"Loaded {len(documents)} institution profiles")
            return documents

        except Exception as e:
            logger.error(f"Error loading institution profiles: {str(e)}")
            return []

    def load_customer_feedback(self) -> List[Document]:
        """Load customer feedback and pain points from questionnaire responses."""
        # Try long format first (more detail)
        long_path = self.raw_dir / "sample_processed_long_format.csv"
        if not long_path.exists():
            long_path = self.processed_base / "sample_processed_long_format.csv"

        if not long_path.exists():
            logger.warning(f"Questionnaire data not found")
            return []

        logger.info(f"Loading customer feedback: {long_path}")

        try:
            df = pd.read_csv(long_path, encoding='utf-8')
            documents = []

            if 'response_id' not in df.columns:
                logger.warning("No response_id column in questionnaire data")
                return []

            for response_id, group in df.groupby('response_id'):
                institution = group[group['field_name'] == 'institution_name']['response_value'].values
                institution_name = institution[0] if len(institution) > 0 else f"Response {response_id}"

                text_parts = [f"CUSTOMER FEEDBACK - {institution_name}"]

                # Extract pain points and relevant feedback
                for _, row in group.iterrows():
                    q_text = row.get('question_text', '')
                    r_value = row.get('response_value', '')
                    r_text = row.get('response_text', '')
                    r_comment = row.get('response_comment', '')

                    if pd.notna(r_value) and str(r_value).strip():
                        text_parts.append(f"Q: {q_text}")
                        text_parts.append(f"A: {r_value}")
                        if pd.notna(r_text) and str(r_text).strip():
                            text_parts.append(f"   Detail: {r_text}")
                        if pd.notna(r_comment) and str(r_comment).strip():
                            text_parts.append(f"   Comment: {r_comment}")
                        text_parts.append("")

                doc = Document(
                    page_content="\n".join(text_parts[:200]),  # Cap length
                    metadata={
                        'source_type': 'customer_feedback',
                        'data_type': 'questionnaire_response',
                        'response_id': str(response_id),
                        'institution_name': str(institution_name),
                        'file_name': long_path.name,
                        'agent': 'governance_agent'
                    }
                )
                documents.append(doc)

            logger.info(f"Loaded {len(documents)} customer feedback documents")
            return documents

        except Exception as e:
            logger.error(f"Error loading customer feedback: {str(e)}")
            return []

    def load_workload_patterns(self) -> List[Document]:
        """Load workload patterns from event log statistics."""
        csv_path = self.processed_dir / "workload_patterns.csv"

        if not csv_path.exists():
            logger.warning(f"Workload patterns not found: {csv_path}")
            return []

        logger.info(f"Loading workload patterns: {csv_path}")

        try:
            df = pd.read_csv(csv_path, encoding='utf-8')
            documents = []

            group_col = 'customer_id' if 'customer_id' in df.columns else df.columns[0]
            for customer_id, group in df.groupby(group_col):
                text_parts = [
                    f"WORKLOAD PATTERN - Customer {customer_id}",
                ]

                for _, row in group.iterrows():
                    for col in group.columns:
                        if col != group_col and pd.notna(row[col]):
                            label = col.replace('_', ' ').title()
                            text_parts.append(f"{label}: {row[col]}")

                doc = Document(
                    page_content="\n".join(text_parts),
                    metadata={
                        'source_type': 'workload_pattern',
                        'data_type': 'event_statistics',
                        'customer_id': str(customer_id),
                        'file_name': csv_path.name,
                        'agent': 'governance_agent'
                    }
                )
                documents.append(doc)

            logger.info(f"Loaded {len(documents)} workload pattern documents")
            return documents

        except Exception as e:
            logger.error(f"Error loading workload patterns: {str(e)}")
            return []

    def load_customer_mapping(self) -> List[Document]:
        """Load customer-to-institution mapping."""
        csv_path = self.processed_base / "customer_mapping.csv"

        if not csv_path.exists():
            logger.warning(f"Customer mapping not found: {csv_path}")
            return []

        logger.info(f"Loading customer mapping: {csv_path}")

        try:
            df = pd.read_csv(csv_path, encoding='utf-8')

            text_parts = [
                "CUSTOMER MAPPING OVERVIEW",
                f"Total customers: {len(df)}",
                ""
            ]

            for _, row in df.iterrows():
                cid = row.get('customer_id', '')
                institution = row.get('institution_name', 'Unknown')
                has_parquet = row.get('has_parquet', False)
                total_events = row.get('total_events', 0)
                error_count = row.get('error_count', 0)
                text_parts.append(
                    f"- {cid}: {institution} | Events: {total_events} | Errors: {error_count} | Parquet: {has_parquet}"
                )

            doc = Document(
                page_content="\n".join(text_parts),
                metadata={
                    'source_type': 'customer_mapping',
                    'data_type': 'customer_overview',
                    'customer_count': len(df),
                    'file_name': csv_path.name,
                    'agent': 'governance_agent'
                }
            )

            logger.info(f"Loaded customer mapping with {len(df)} entries")
            return [doc]

        except Exception as e:
            logger.error(f"Error loading customer mapping: {str(e)}")
            return []

    def load_clinical_protocols(self) -> List[Document]:
        """Load clinical protocol templates from RSNA RadReport data."""
        csv_path = self.processed_dir / "clinical_protocols.csv"

        if not csv_path.exists():
            logger.warning(f"Clinical protocols not found: {csv_path}")
            return []

        logger.info(f"Loading clinical protocols: {csv_path}")

        try:
            df = pd.read_csv(csv_path, encoding='utf-8')
            documents = []

            # Group by modality to create manageable document chunks
            group_col = 'modality' if 'modality' in df.columns else df.columns[0]
            for modality, group in df.groupby(group_col):
                text_parts = [
                    f"CLINICAL PROTOCOLS - {modality}",
                    f"Total templates: {len(group)}",
                    ""
                ]

                for _, row in group.iterrows():
                    title = row.get('title', row.get('filename', ''))
                    body_region = row.get('body_region', '')
                    desc = row.get('description', '')
                    lang = row.get('language', '')
                    line = f"- {title}"
                    if body_region:
                        line += f" [{body_region}]"
                    if lang and lang != 'en':
                        line += f" ({lang})"
                    text_parts.append(line)
                    if pd.notna(desc) and str(desc).strip():
                        text_parts.append(f"  {desc}")

                doc = Document(
                    page_content="\n".join(text_parts),
                    metadata={
                        'source_type': 'clinical_protocol',
                        'data_type': 'radreport_template',
                        'modality': str(modality),
                        'template_count': len(group),
                        'file_name': csv_path.name,
                        'agent': 'governance_agent'
                    }
                )
                documents.append(doc)

            logger.info(f"Loaded {len(documents)} clinical protocol groups")
            return documents

        except Exception as e:
            logger.error(f"Error loading clinical protocols: {str(e)}")
            return []

    def load_radlex_terms(self) -> List[Document]:
        """Load RadLex terminology grouped by template category."""
        csv_path = self.processed_dir / "radlex_terms.csv"

        if not csv_path.exists():
            logger.warning(f"RadLex terms not found: {csv_path}")
            return []

        logger.info(f"Loading RadLex terms: {csv_path}")

        try:
            df = pd.read_csv(csv_path, encoding='utf-8')
            documents = []

            # Group by unique RadLex code to create a terminology reference
            # Deduplicate meanings per code
            if 'code' in df.columns and 'meaning' in df.columns:
                terms = df.drop_duplicates(subset=['code', 'meaning'])
                unique_terms = terms.groupby('code')['meaning'].first().reset_index()

                # Create chunks of ~50 terms each to stay manageable
                chunk_size = 50
                for i in range(0, len(unique_terms), chunk_size):
                    chunk = unique_terms.iloc[i:i + chunk_size]
                    text_parts = [
                        f"RADLEX TERMINOLOGY (terms {i+1}-{i+len(chunk)})",
                        f"Total terms in this chunk: {len(chunk)}",
                        ""
                    ]
                    for _, row in chunk.iterrows():
                        text_parts.append(f"- {row['code']}: {row['meaning']}")

                    doc = Document(
                        page_content="\n".join(text_parts),
                        metadata={
                            'source_type': 'radlex_terminology',
                            'data_type': 'radlex_terms',
                            'chunk_index': i // chunk_size,
                            'term_count': len(chunk),
                            'file_name': csv_path.name,
                            'agent': 'governance_agent'
                        }
                    )
                    documents.append(doc)
            else:
                # Fallback: single document
                text_parts = ["RADLEX TERMINOLOGY", f"Total entries: {len(df)}", ""]
                for _, row in df.head(200).iterrows():
                    text_parts.append(" | ".join(str(v) for v in row.values if pd.notna(v)))
                doc = Document(
                    page_content="\n".join(text_parts),
                    metadata={
                        'source_type': 'radlex_terminology',
                        'data_type': 'radlex_terms',
                        'entry_count': len(df),
                        'file_name': csv_path.name,
                        'agent': 'governance_agent'
                    }
                )
                documents.append(doc)

            logger.info(f"Loaded {len(documents)} RadLex term documents")
            return documents

        except Exception as e:
            logger.error(f"Error loading RadLex terms: {str(e)}")
            return []

    def load_governance_pdfs(self) -> List[Document]:
        """Load and chunk clinical protocol and interpretation PDFs."""
        pdf_files = []
        for pattern in GOVERNANCE_PDF_PATTERNS:
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
            logger.warning("No governance PDFs found")
            return []

        logger.info(f"Loading {len(unique_pdfs)} governance PDFs")

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
                        'source_type': 'clinical_documentation',
                        'data_type': 'protocol_pdf',
                        'file_name': pdf_path.name,
                        'agent': 'governance_agent'
                    })

                all_documents.extend(chunks)
                logger.info(f"  Created {len(chunks)} chunks from {len(documents)} pages")

            except Exception as e:
                logger.error(f"Error processing {pdf_path.name}: {str(e)}")
                continue

        logger.info(f"Total governance PDF chunks: {len(all_documents)}")
        return all_documents

    def load_protocol_categories(self) -> List[Document]:
        """Load protocol category taxonomy for template classification."""
        csv_path = self.processed_dir / "protocol_categories.csv"

        if not csv_path.exists():
            logger.warning(f"Protocol categories not found: {csv_path}")
            return []

        logger.info(f"Loading protocol categories: {csv_path}")

        try:
            df = pd.read_csv(csv_path, encoding='utf-8')
            text_parts = ["PROTOCOL CATEGORIES - Template Taxonomy", ""]

            for _, row in df.iterrows():
                category = row.get('category', '')
                count = row.get('count', 0)
                text_parts.append(f"- {category}: {count} templates")

            doc = Document(
                page_content="\n".join(text_parts),
                metadata={
                    'source_type': 'clinical_protocol',
                    'data_type': 'protocol_category',
                    'category_count': len(df),
                    'file_name': csv_path.name,
                    'agent': 'governance_agent'
                }
            )

            logger.info(f"Loaded {len(df)} protocol categories")
            return [doc]

        except Exception as e:
            logger.error(f"Error loading protocol categories: {str(e)}")
            return []

    def load(self, include_pdfs: bool = True) -> List[Document]:
        """Load all governance data for RAG indexing."""
        logger.info(f"Loading Workflow Anthropologist data from {self.processed_dir}")

        all_documents = []

        profiles = self.load_institution_profiles()
        all_documents.extend(profiles)

        feedback = self.load_customer_feedback()
        all_documents.extend(feedback)

        workload = self.load_workload_patterns()
        all_documents.extend(workload)

        mapping = self.load_customer_mapping()
        all_documents.extend(mapping)

        protocols = self.load_clinical_protocols()
        all_documents.extend(protocols)

        categories = self.load_protocol_categories()
        all_documents.extend(categories)

        radlex = self.load_radlex_terms()
        all_documents.extend(radlex)

        if include_pdfs:
            pdfs = self.load_governance_pdfs()
            all_documents.extend(pdfs)

        logger.info(f"Total documents loaded: {len(all_documents)}")
        return all_documents

    def get_summary(self) -> Dict[str, Any]:
        """Get a summary of available data."""
        summary = {
            'processed_dir': str(self.processed_dir),
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

        # Check customer mapping
        mapping_path = self.processed_base / "customer_mapping.csv"
        if mapping_path.exists():
            try:
                df = pd.read_csv(mapping_path)
                summary['customer_mapping'] = {'rows': len(df)}
            except Exception:
                pass

        return summary


def main():
    """Test the Workflow Anthropologist loader."""
    logger.info("=" * 60)
    logger.info("Testing Workflow Anthropologist Data Loader")
    logger.info("=" * 60)

    try:
        loader = ClinicalGovernanceLoader()
        summary = loader.get_summary()
        logger.info(f"\nData Summary:")
        for file, info in summary.get('files', {}).items():
            logger.info(f"  {file}: {info}")

        documents = loader.load(include_pdfs=False)
        logger.info(f"\nLoaded {len(documents)} documents (excluding PDFs)")

        if documents:
            logger.info(f"\nExample: {documents[0].page_content[:300]}...")

    except Exception as e:
        logger.error(f"Test failed: {str(e)}", exc_info=True)
        raise


if __name__ == "__main__":
    main()
