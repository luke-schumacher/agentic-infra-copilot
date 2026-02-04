"""
Siemens Technician Data Loader

Processes Siemens MRRT questionnaire CSV data for RAG-based querying:
- Equipment specifications (MR scanners, LINACs, CT simulators)
- Institution pain points and challenges
- Vendor and pricing information

Migrated from src/ingestion/siemens_loader.py for agent-specific ownership.

Author: Thesis Project - Agentic Infra Co-Pilot
"""

import pandas as pd
from pathlib import Path
from typing import List, Dict, Any, Optional
import logging
from langchain_core.documents import Document

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class SiemensLoader:
    """Loads and converts Siemens questionnaire data to LangChain Documents."""

    def __init__(
        self,
        data_dir: str = "data/raw/siemens",
        chunk_overlap: int = 0
    ):
        """
        Initialize the Siemens loader.

        Args:
            data_dir: Directory containing Siemens CSV files
            chunk_overlap: Overlap between documents (not used for structured data)
        """
        self.data_dir = Path(data_dir)
        self.chunk_overlap = chunk_overlap

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

    def _load_wide_format(self, csv_path: Path) -> List[Document]:
        """
        Load wide format CSV where each row is an institution response.

        Args:
            csv_path: Path to CSV file

        Returns:
            List of Document objects
        """
        logger.info(f"Loading wide format CSV: {csv_path}")

        df = pd.read_csv(
            csv_path,
            encoding='utf-8',
            on_bad_lines='warn',
            engine='python'
        )
        logger.info(f"Loaded {len(df)} rows from {csv_path.name}")

        documents = []

        for idx, row in df.iterrows():
            response_id = self._safe_get(row, 'response_id', f'RESP_{idx}')
            text = self._convert_row_to_text(row)

            doc = Document(
                page_content=text,
                metadata={
                    'source_type': 'siemens_questionnaire',
                    'data_type': 'equipment_survey',
                    'response_id': response_id,
                    'institution': self._safe_get(row, 'institution_name'),
                    'country': self._safe_get(row, 'country'),
                    'file_name': csv_path.name,
                    'agent': 'siemens_technician'
                }
            )
            documents.append(doc)

        return documents

    def _load_long_format(self, csv_path: Path) -> List[Document]:
        """
        Load long format CSV where each row is a question-answer pair.

        Args:
            csv_path: Path to CSV file

        Returns:
            List of Document objects grouped by response_id
        """
        logger.info(f"Loading long format CSV: {csv_path}")

        df = pd.read_csv(
            csv_path,
            encoding='utf-8',
            on_bad_lines='warn',
            engine='python'
        )
        logger.info(f"Loaded {len(df)} rows from {csv_path.name}")

        # Group by response_id and create one document per response
        documents = []

        if 'response_id' in df.columns:
            grouped = df.groupby('response_id')

            for response_id, group in grouped:
                text_parts = [f"Survey Response ID: {response_id}"]

                for _, row in group.iterrows():
                    question = self._safe_get(row, 'question_text', 'Unknown question')
                    answer = self._safe_get(row, 'answer_value', 'No answer')
                    category = self._safe_get(row, 'category', 'General')

                    text_parts.append(f"{category} - {question}: {answer}")

                doc = Document(
                    page_content="\n".join(text_parts),
                    metadata={
                        'source_type': 'siemens_questionnaire',
                        'data_type': 'equipment_survey_long',
                        'response_id': str(response_id),
                        'file_name': csv_path.name,
                        'agent': 'siemens_technician'
                    }
                )
                documents.append(doc)
        else:
            # Fallback: treat each row as a document
            for idx, row in df.iterrows():
                text = " | ".join([f"{col}: {row[col]}" for col in df.columns if pd.notna(row[col])])
                doc = Document(
                    page_content=text,
                    metadata={
                        'source_type': 'siemens_questionnaire',
                        'data_type': 'equipment_survey_row',
                        'row_index': idx,
                        'file_name': csv_path.name,
                        'agent': 'siemens_technician'
                    }
                )
                documents.append(doc)

        return documents

    def load_equipment_specifications(self) -> List[Document]:
        """
        Load Versicharge equipment specifications from CSV.

        Returns:
            List of Documents with equipment specifications
        """
        csv_path = self.data_dir / "versicharge_specifications.csv"

        if not csv_path.exists():
            logger.warning(f"Equipment specifications not found: {csv_path}")
            return []

        logger.info(f"Loading equipment specifications: {csv_path}")

        try:
            df = pd.read_csv(csv_path, encoding='utf-8')
            documents = []

            # Group by category for better context
            for category in df['category'].unique():
                category_df = df[df['category'] == category]
                specs_text = [f"EQUIPMENT SPECIFICATIONS - {category}"]

                for _, row in category_df.iterrows():
                    specs_text.append(
                        f"- {row['parameter']}: {row['value']} {row['unit']} "
                        f"({row['description']})"
                    )
                    if pd.notna(row.get('fault_relevance')) and row['fault_relevance'] != 'N/A':
                        specs_text.append(f"  Fault Relevance: {row['fault_relevance']}")

                doc = Document(
                    page_content="\n".join(specs_text),
                    metadata={
                        'source_type': 'equipment_specification',
                        'data_type': 'versicharge_specs',
                        'category': category,
                        'spec_count': len(category_df),
                        'file_name': csv_path.name,
                        'agent': 'siemens_technician'
                    }
                )
                documents.append(doc)

            logger.info(f"Loaded {len(documents)} equipment specification groups")
            return documents

        except Exception as e:
            logger.error(f"Error loading equipment specifications: {str(e)}")
            return []

    def load_failure_modes(self) -> List[Document]:
        """
        Load common failure modes from CSV.

        Returns:
            List of Documents with failure mode information
        """
        csv_path = self.data_dir / "common_failure_modes.csv"

        if not csv_path.exists():
            logger.warning(f"Failure modes not found: {csv_path}")
            return []

        logger.info(f"Loading failure modes: {csv_path}")

        try:
            df = pd.read_csv(csv_path, encoding='utf-8')
            documents = []

            for _, row in df.iterrows():
                text = (
                    f"FAILURE MODE: {row['failure_id']} - {row['failure_mode']}\n"
                    f"Component: {row['component']}\n"
                    f"Symptom: {row['symptom']}\n"
                    f"Root Cause: {row['root_cause']}\n"
                    f"Detection Method: {row['detection_method']}\n"
                    f"Severity: {row['severity']}\n"
                    f"Mean Time to Repair: {row['mttr_hours']} hours\n"
                    f"Repair Action: {row['repair_action']}\n"
                    f"Spare Parts Required: {row['spare_parts_required']}\n"
                    f"Preventive Maintenance: {row['preventive_maintenance']}"
                )

                doc = Document(
                    page_content=text,
                    metadata={
                        'source_type': 'failure_mode',
                        'data_type': 'diagnostic_guide',
                        'failure_id': row['failure_id'],
                        'component': row['component'],
                        'severity': row['severity'],
                        'mttr_hours': row['mttr_hours'],
                        'file_name': csv_path.name,
                        'agent': 'siemens_technician'
                    }
                )
                documents.append(doc)

            logger.info(f"Loaded {len(documents)} failure modes")
            return documents

        except Exception as e:
            logger.error(f"Error loading failure modes: {str(e)}")
            return []

    def load(self) -> List[Document]:
        """
        Load all CSV files from the Siemens directory.

        Automatically detects wide vs long format based on filename.
        Also loads equipment specifications and failure modes.

        Returns:
            List of LangChain Documents
        """
        logger.info(f"Loading Siemens data from {self.data_dir}")

        if not self.data_dir.exists():
            logger.warning(f"Directory not found: {self.data_dir}. Creating it.")
            self.data_dir.mkdir(parents=True, exist_ok=True)
            logger.warning("Directory created but no CSVs found. Returning empty list.")
            return []

        all_documents = []

        # Load equipment specifications (new)
        spec_docs = self.load_equipment_specifications()
        all_documents.extend(spec_docs)

        # Load failure modes (new)
        failure_docs = self.load_failure_modes()
        all_documents.extend(failure_docs)

        # Find questionnaire CSV files (original functionality)
        csv_files = list(self.data_dir.glob("*format*.csv"))

        logger.info(f"Found {len(csv_files)} questionnaire CSV files to process")

        for csv_file in csv_files:
            try:
                # Determine format based on filename
                if 'wide' in csv_file.name.lower():
                    docs = self._load_wide_format(csv_file)
                elif 'long' in csv_file.name.lower():
                    docs = self._load_long_format(csv_file)
                else:
                    # Default to long format for unknown files
                    docs = self._load_long_format(csv_file)

                all_documents.extend(docs)
                logger.info(f"  Created {len(docs)} documents from {csv_file.name}")

            except Exception as e:
                logger.error(f"Error processing {csv_file.name}: {str(e)}")
                continue

        logger.info(f"Total documents created: {len(all_documents)}")
        return all_documents

    def load_single_csv(self, csv_path: str) -> List[Document]:
        """
        Load a single CSV file.

        Args:
            csv_path: Path to a specific CSV file

        Returns:
            List of LangChain Documents
        """
        csv_file = Path(csv_path)

        if not csv_file.exists():
            logger.error(f"CSV file not found: {csv_path}")
            raise FileNotFoundError(f"CSV file not found: {csv_path}")

        if 'wide' in csv_file.name.lower():
            return self._load_wide_format(csv_file)
        else:
            return self._load_long_format(csv_file)


def main():
    """Test the Siemens loader."""
    logger.info("=" * 60)
    logger.info("Testing Siemens Technician Data Loader")
    logger.info("=" * 60)

    try:
        loader = SiemensLoader()
        documents = loader.load()

        logger.info(f"\nSuccessfully loaded {len(documents)} documents")

        if not documents:
            logger.warning("\nNo documents were loaded.")
            logger.info("\nTo test with actual data:")
            logger.info("1. Place CSV files in data/raw/siemens/")
            logger.info("2. Run this script again")
        else:
            # Display first document as example
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
