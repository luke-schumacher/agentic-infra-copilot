"""
Clinical Governance Data Loader

Loads processed clinical governance data for the Governance Agent:
- Clinical protocols (RSNA RadReport templates)
- RadLex ontology terms
- Protocol categories and statistics

Uses preprocessed CSVs from data/processed/governance/ for fast RAG ingestion.

Environment Variables:
- GOVERNANCE_DATA_DIR: Path to processed governance data (default: data/processed/governance)
- RAW_TEMPLATES_DIR: Path to raw RSNA templates (default: data/raw/siemens/examination/RSNA-RAD-REPORT)

Author: Thesis Project - Healthcare MAS
"""

import os
import pandas as pd
from pathlib import Path
from typing import List, Dict, Any, Optional
import logging
from langchain_core.documents import Document

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Default paths (can be overridden via environment variables)
DEFAULT_PROCESSED_DIR = "data/processed/governance"
DEFAULT_RAW_TEMPLATES_DIR = "data/raw/siemens/examination/RSNA-RAD-REPORT"


class ClinicalGovernanceLoader:
    """Loads clinical governance data including protocols and RadLex terms."""

    def __init__(
        self,
        processed_dir: Optional[str] = None,
        raw_templates_dir: Optional[str] = None
    ):
        """
        Initialize the Clinical Governance loader.

        Args:
            processed_dir: Directory with preprocessed CSVs (env: GOVERNANCE_DATA_DIR)
            raw_templates_dir: Directory with raw RSNA templates (env: RAW_TEMPLATES_DIR)
        """
        self.processed_dir = Path(
            processed_dir or os.getenv("GOVERNANCE_DATA_DIR", DEFAULT_PROCESSED_DIR)
        )
        self.raw_templates_dir = Path(
            raw_templates_dir or os.getenv("RAW_TEMPLATES_DIR", DEFAULT_RAW_TEMPLATES_DIR)
        )

        logger.info(f"ClinicalGovernanceLoader initialized with processed_dir={self.processed_dir}")

    def load_clinical_protocols(self) -> List[Document]:
        """
        Load clinical protocols from preprocessed CSV.

        Returns:
            List of Documents with protocol information
        """
        csv_path = self.processed_dir / "clinical_protocols.csv"

        if not csv_path.exists():
            logger.warning(f"Clinical protocols not found: {csv_path}")
            return []

        logger.info(f"Loading clinical protocols: {csv_path}")

        try:
            df = pd.read_csv(csv_path, encoding='utf-8')
            documents = []

            # Group protocols by modality for better organization
            if 'modality' in df.columns:
                for modality in df['modality'].unique():
                    modality_df = df[df['modality'] == modality]

                    # Further group by body region
                    for body_region in modality_df['body_region'].unique():
                        region_df = modality_df[modality_df['body_region'] == body_region]

                        text_parts = [
                            f"CLINICAL PROTOCOLS - {modality} - {body_region}",
                            f"Total protocols: {len(region_df)}",
                            ""
                        ]

                        for _, row in region_df.iterrows():
                            text_parts.append(f"Protocol: {row['title']}")
                            if pd.notna(row.get('description')) and row['description']:
                                text_parts.append(f"  Description: {row['description']}")
                            text_parts.append(f"  Language: {row.get('language', 'en')}")
                            text_parts.append(f"  File: {row['filename']}")
                            text_parts.append("")

                        doc = Document(
                            page_content="\n".join(text_parts),
                            metadata={
                                'source_type': 'clinical_protocol',
                                'data_type': 'rsna_radreport',
                                'modality': modality,
                                'body_region': body_region,
                                'protocol_count': len(region_df),
                                'file_name': csv_path.name,
                                'agent': 'governance_agent'
                            }
                        )
                        documents.append(doc)

            else:
                # Flat structure fallback
                for _, row in df.iterrows():
                    text = (
                        f"Clinical Protocol: {row.get('title', row.get('filename', 'Unknown'))}\n"
                        f"File: {row.get('filename', 'Unknown')}"
                    )
                    doc = Document(
                        page_content=text,
                        metadata={
                            'source_type': 'clinical_protocol',
                            'data_type': 'rsna_radreport',
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
        """
        Load RadLex ontology terms from preprocessed CSV.

        Returns:
            List of Documents with RadLex terminology
        """
        csv_path = self.processed_dir / "radlex_terms.csv"

        if not csv_path.exists():
            logger.warning(f"RadLex terms not found: {csv_path}")
            return []

        logger.info(f"Loading RadLex terms: {csv_path}")

        try:
            df = pd.read_csv(csv_path, encoding='utf-8')
            documents = []

            # Group by template for context
            if 'template' in df.columns:
                grouped = df.groupby('template')

                for template, group in grouped:
                    terms = group[['code', 'meaning']].drop_duplicates()

                    text_parts = [
                        f"RADLEX TERMS - {template}",
                        f"Total terms: {len(terms)}",
                        ""
                    ]

                    for _, row in terms.iterrows():
                        text_parts.append(f"- {row['code']}: {row['meaning']}")

                    doc = Document(
                        page_content="\n".join(text_parts),
                        metadata={
                            'source_type': 'radlex_ontology',
                            'data_type': 'terminology',
                            'template': template,
                            'term_count': len(terms),
                            'file_name': csv_path.name,
                            'agent': 'governance_agent'
                        }
                    )
                    documents.append(doc)

            else:
                # Create a single document with all terms
                unique_terms = df.drop_duplicates()
                text_parts = [
                    "RADLEX ONTOLOGY TERMS",
                    f"Total unique terms: {len(unique_terms)}",
                    ""
                ]

                for _, row in unique_terms.iterrows():
                    text_parts.append(f"- {row['code']}: {row['meaning']}")

                doc = Document(
                    page_content="\n".join(text_parts),
                    metadata={
                        'source_type': 'radlex_ontology',
                        'data_type': 'terminology',
                        'term_count': len(unique_terms),
                        'file_name': csv_path.name,
                        'agent': 'governance_agent'
                    }
                )
                documents.append(doc)

            logger.info(f"Loaded {len(documents)} RadLex term groups")
            return documents

        except Exception as e:
            logger.error(f"Error loading RadLex terms: {str(e)}")
            return []

    def load_protocol_categories(self) -> List[Document]:
        """
        Load protocol category statistics.

        Returns:
            List of Documents with category information
        """
        csv_path = self.processed_dir / "protocol_categories.csv"

        if not csv_path.exists():
            logger.warning(f"Protocol categories not found: {csv_path}")
            return []

        logger.info(f"Loading protocol categories: {csv_path}")

        try:
            df = pd.read_csv(csv_path, encoding='utf-8')

            # Create summary document
            text_parts = [
                "PROTOCOL CATEGORY STATISTICS",
                f"Total categories: {len(df)}",
                ""
            ]

            total_protocols = df['count'].sum()
            text_parts.append(f"Total protocols across all categories: {total_protocols}")
            text_parts.append("")

            # Group by modality prefix
            df['modality'] = df['category'].str.split('_').str[0]

            for modality in df['modality'].unique():
                modality_df = df[df['modality'] == modality]
                modality_total = modality_df['count'].sum()
                text_parts.append(f"{modality}: {modality_total} protocols")

                for _, row in modality_df.iterrows():
                    text_parts.append(f"  - {row['category']}: {row['count']}")

                text_parts.append("")

            doc = Document(
                page_content="\n".join(text_parts),
                metadata={
                    'source_type': 'category_statistics',
                    'data_type': 'protocol_summary',
                    'total_categories': len(df),
                    'total_protocols': int(total_protocols),
                    'file_name': csv_path.name,
                    'agent': 'governance_agent'
                }
            )

            logger.info(f"Loaded protocol category statistics")
            return [doc]

        except Exception as e:
            logger.error(f"Error loading protocol categories: {str(e)}")
            return []

    def load_radlex_by_modality(self, modality: str) -> List[Document]:
        """
        Load RadLex terms filtered by modality.

        Args:
            modality: Modality to filter by (e.g., 'MRI', 'CT')

        Returns:
            List of Documents with filtered RadLex terms
        """
        protocols_path = self.processed_dir / "clinical_protocols.csv"
        radlex_path = self.processed_dir / "radlex_terms.csv"

        if not protocols_path.exists() or not radlex_path.exists():
            logger.warning("Required files not found for modality filter")
            return []

        try:
            protocols_df = pd.read_csv(protocols_path)
            radlex_df = pd.read_csv(radlex_path)

            # Get templates for the specified modality
            modality_templates = protocols_df[
                protocols_df['modality'].str.contains(modality, case=False, na=False)
            ]['filename'].tolist()

            # Filter RadLex terms to these templates
            filtered_radlex = radlex_df[radlex_df['template'].isin(modality_templates)]

            if filtered_radlex.empty:
                logger.warning(f"No RadLex terms found for modality: {modality}")
                return []

            # Group and create documents
            documents = []
            unique_terms = filtered_radlex[['code', 'meaning']].drop_duplicates()

            text_parts = [
                f"RADLEX TERMS FOR {modality.upper()}",
                f"Total unique terms: {len(unique_terms)}",
                ""
            ]

            # Organize by first letter for readability
            for _, row in unique_terms.sort_values('meaning').iterrows():
                text_parts.append(f"- {row['code']}: {row['meaning']}")

            doc = Document(
                page_content="\n".join(text_parts),
                metadata={
                    'source_type': 'radlex_ontology',
                    'data_type': 'modality_terminology',
                    'modality': modality,
                    'term_count': len(unique_terms),
                    'agent': 'governance_agent'
                }
            )
            documents.append(doc)

            logger.info(f"Loaded {len(unique_terms)} RadLex terms for {modality}")
            return documents

        except Exception as e:
            logger.error(f"Error loading RadLex by modality: {str(e)}")
            return []

    def load(self) -> List[Document]:
        """
        Load all governance data.

        Returns:
            List of all Documents
        """
        logger.info(f"Loading clinical governance data from {self.processed_dir}")

        all_documents = []

        # Load clinical protocols
        protocols = self.load_clinical_protocols()
        all_documents.extend(protocols)

        # Load RadLex terms
        radlex = self.load_radlex_terms()
        all_documents.extend(radlex)

        # Load protocol categories
        categories = self.load_protocol_categories()
        all_documents.extend(categories)

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

        # Count modalities and body regions if available
        protocols_path = self.processed_dir / "clinical_protocols.csv"
        if protocols_path.exists():
            try:
                df = pd.read_csv(protocols_path)
                if 'modality' in df.columns:
                    summary['modalities'] = df['modality'].nunique()
                if 'body_region' in df.columns:
                    summary['body_regions'] = df['body_region'].nunique()
            except Exception:
                pass

        return summary

    def get_mri_protocols(self) -> List[Dict[str, Any]]:
        """
        Get MRI-specific protocols as structured data.

        Returns:
            List of dictionaries with MRI protocol information
        """
        csv_path = self.processed_dir / "clinical_protocols.csv"

        if not csv_path.exists():
            return []

        try:
            df = pd.read_csv(csv_path)
            mri_df = df[df['modality'].str.contains('MRI', case=False, na=False)]

            return mri_df.to_dict('records')

        except Exception as e:
            logger.error(f"Error getting MRI protocols: {str(e)}")
            return []


def main():
    """Test the Clinical Governance loader."""
    logger.info("=" * 60)
    logger.info("Testing Clinical Governance Data Loader")
    logger.info("=" * 60)

    try:
        loader = ClinicalGovernanceLoader()

        # Print summary
        summary = loader.get_summary()
        logger.info(f"\nData Summary:")
        for file, info in summary.get('files', {}).items():
            logger.info(f"  {file}: {info}")
        logger.info(f"  Modalities: {summary.get('modalities', 'N/A')}")
        logger.info(f"  Body Regions: {summary.get('body_regions', 'N/A')}")

        # Load all data
        documents = loader.load()

        logger.info(f"\nLoaded {len(documents)} documents")

        if documents:
            logger.info("\n" + "=" * 60)
            logger.info("EXAMPLE DOCUMENT:")
            logger.info("=" * 60)
            print(f"\nContent:\n{documents[0].page_content[:500]}...\n")
            print(f"Metadata:\n{documents[0].metadata}\n")

        # Test MRI-specific loader
        mri_protocols = loader.get_mri_protocols()
        logger.info(f"\nMRI Protocols found: {len(mri_protocols)}")

        logger.info("\n" + "=" * 60)
        logger.info("Loader test completed!")
        logger.info("=" * 60)

    except Exception as e:
        logger.error(f"Test failed: {str(e)}", exc_info=True)
        raise


if __name__ == "__main__":
    main()
