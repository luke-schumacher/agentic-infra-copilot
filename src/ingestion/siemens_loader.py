"""
Siemens Loader - RAG Ingestion Layer

Converts Siemens MRRT questionnaire CSV data into natural language text chunks
for RAG-based query answering.

Purpose:
- Load CSV questionnaire data
- Convert each institution's response into readable text
- Enable queries like "Which hospitals have issues with coil weight?"

Author: Thesis Project - Agentic Infra Co-Pilot
"""

import pandas as pd
from pathlib import Path
from typing import List, Dict, Any
import logging
from langchain_core.documents import Document

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class SiemensLoader:
    """Loads and converts Siemens questionnaire data to natural language chunks."""

    def __init__(self, csv_path: str = "data/raw/siemens/sample_processed_wide_format.csv"):
        """
        Initialize the Siemens loader.

        Args:
            csv_path: Path to the wide format CSV file
        """
        self.csv_path = Path(csv_path)

    def _safe_get(self, row: pd.Series, column: str, default: str = "Not specified") -> str:
        """
        Safely get a value from a row, handling NaN values.

        Args:
            row: Pandas Series (row)
            column: Column name
            default: Default value for missing data

        Returns:
            String value or default
        """
        if column not in row.index:
            return default
        value = row[column]
        if pd.isna(value):
            return default
        return str(value)

    def _determine_org_type(self, row: pd.Series) -> str:
        """
        Determine organization type from multiple org type columns.

        Args:
            row: Pandas Series containing org type columns

        Returns:
            Organization type description
        """
        org_types = []

        if self._safe_get(row, 'org_type_private', 'No') == 'Yes':
            org_types.append('private')
        if self._safe_get(row, 'org_type_public', 'No') == 'Yes':
            org_types.append('public')
        if self._safe_get(row, 'org_type_academic', 'No') == 'Yes':
            org_types.append('academic')
        if self._safe_get(row, 'org_type_cancer_center', 'No') == 'Yes':
            org_types.append('cancer center')
        if self._safe_get(row, 'org_type_rt_center', 'No') == 'Yes':
            org_types.append('RT center')

        if org_types:
            return ', '.join(org_types)
        return 'healthcare'

    def _convert_row_to_text(self, row: pd.Series) -> str:
        """
        Convert a single CSV row to natural language text.

        Args:
            row: Pandas Series representing one institution

        Returns:
            Natural language description
        """
        # Basic institution info
        institution = self._safe_get(row, 'institution_name')
        country = self._safe_get(row, 'country')
        org_type = self._determine_org_type(row)

        # Equipment
        num_linacs = self._safe_get(row, 'num_linacs')
        num_ct = self._safe_get(row, 'num_ct_simulators')

        # MR usage
        pct_mr = self._safe_get(row, 'pct_patients_planned_with_mr')

        # Pain points
        positioning_pains = self._safe_get(row, 'positioning_exchange_pains')
        coil_pains = self._safe_get(row, 'brain_headneck_coil_pains')

        # MR vendors
        mr_vendor1 = self._safe_get(row, 'mr_vendor_1')
        mr_model1 = self._safe_get(row, 'mr_model_1')

        # Pricing
        pricing_bargain = self._safe_get(row, 'pricing_bargain')
        pricing_expensive = self._safe_get(row, 'pricing_expensive')

        # Build natural language text
        text_parts = [
            f"Institution: {institution}",
            f"Location: {country}",
            f"Type: {org_type} facility",
            f"Equipment: {num_linacs} LINACs, {num_ct} CT simulators",
            f"MR Imaging Usage: {pct_mr}% of patients planned with MR images",
        ]

        if mr_vendor1 != "Not specified":
            text_parts.append(f"MR Equipment: {mr_vendor1} {mr_model1}")

        if positioning_pains != "Not specified":
            text_parts.append(f"Positioning Pain Points: {positioning_pains}")

        if coil_pains != "Not specified":
            text_parts.append(f"Coil Setup Pain Points: {coil_pains}")

        if pricing_bargain != "Not specified" and pricing_expensive != "Not specified":
            text_parts.append(f"Pricing Sensitivity: Bargain price {pricing_bargain}, Expensive at {pricing_expensive}")

        return ". ".join(text_parts) + "."

    def load(self) -> List[Document]:
        """
        Load CSV data and convert to LangChain Documents.

        Returns:
            List of Document objects with natural language text
        """
        logger.info(f"Loading Siemens data from {self.csv_path}")

        if not self.csv_path.exists():
            logger.error(f"CSV file not found: {self.csv_path}")
            raise FileNotFoundError(f"CSV file not found: {self.csv_path}")

        # Read CSV with error handling for malformed lines
        df = pd.read_csv(
            self.csv_path,
            encoding='utf-8',
            on_bad_lines='warn',  # Warn but continue on malformed lines
            engine='python'  # More flexible parser
        )
        logger.info(f"Loaded {len(df)} rows from CSV")

        documents = []

        # Convert each row to a Document
        for idx, row in df.iterrows():
            response_id = self._safe_get(row, 'response_id', f'RESP_{idx}')
            text = self._convert_row_to_text(row)

            # Create LangChain Document with metadata
            doc = Document(
                page_content=text,
                metadata={
                    'source': 'siemens_questionnaire',
                    'response_id': response_id,
                    'institution': self._safe_get(row, 'institution_name'),
                    'country': self._safe_get(row, 'country'),
                    'data_type': 'questionnaire_response'
                }
            )
            documents.append(doc)

        logger.info(f"Created {len(documents)} Document objects")
        return documents


def main():
    """Test the Siemens loader."""
    logger.info("=" * 60)
    logger.info("Testing Siemens Loader")
    logger.info("=" * 60)

    try:
        loader = SiemensLoader()
        documents = loader.load()

        logger.info(f"\nSuccessfully loaded {len(documents)} documents")

        # Display first document as example
        if documents:
            logger.info("\n" + "=" * 60)
            logger.info("EXAMPLE DOCUMENT:")
            logger.info("=" * 60)
            print(f"\nContent:\n{documents[0].page_content}\n")
            print(f"Metadata:\n{documents[0].metadata}\n")

            # Display second document if available
            if len(documents) > 1:
                logger.info("\n" + "=" * 60)
                logger.info("SECOND DOCUMENT:")
                logger.info("=" * 60)
                print(f"\nContent:\n{documents[1].page_content}\n")
                print(f"Metadata:\n{documents[1].metadata}\n")

        logger.info("=" * 60)
        logger.info("Test completed successfully!")
        logger.info("=" * 60)

    except Exception as e:
        logger.error(f"Test failed: {str(e)}", exc_info=True)
        raise


if __name__ == "__main__":
    main()
