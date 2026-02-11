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

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DEFAULT_PROCESSED_DIR = "data/processed/governance"
DEFAULT_PROCESSED_BASE = "data/processed"
DEFAULT_RAW_DIR = "data/raw/siemens"


class ClinicalGovernanceLoader:
    """Loads institution profiles, workload patterns, and customer feedback for RAG."""

    def __init__(
        self,
        processed_dir: Optional[str] = None,
        processed_base: Optional[str] = None,
        raw_dir: Optional[str] = None
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

    def load(self) -> List[Document]:
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

        documents = loader.load()
        logger.info(f"\nLoaded {len(documents)} documents")

        if documents:
            logger.info(f"\nExample: {documents[0].page_content[:300]}...")

    except Exception as e:
        logger.error(f"Test failed: {str(e)}", exc_info=True)
        raise


if __name__ == "__main__":
    main()
