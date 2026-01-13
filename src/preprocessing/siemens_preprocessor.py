"""
Siemens Data Preprocessor

Purpose:
- Cleans and standardizes Siemens MRRT questionnaire data
- Handles missing values and outliers
- Converts between wide and long formats
- Extracts key insights and pain points

Input: Parsed CSV DataFrames from ingestion module
Output: Cleaned data saved to data/processed/siemens/
"""

import pandas as pd
from pathlib import Path
from typing import Dict, Any, List
import logging

logger = logging.getLogger(__name__)


class SiemensPreprocessor:
    """Preprocessor for Siemens MRRT questionnaire data."""

    def __init__(self, output_dir: str = "data/processed/siemens"):
        """
        Initialize the preprocessor.

        Args:
            output_dir: Directory to save processed data
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def handle_missing_values(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Handle missing values in the dataset.

        Args:
            df: Raw DataFrame

        Returns:
            DataFrame with missing values handled
        """
        logger.info("Handling missing values")

        # Document missing data patterns
        missing_counts = df.isnull().sum()
        missing_pct = (missing_counts / len(df) * 100).round(2)

        missing_summary = pd.DataFrame({
            'missing_count': missing_counts,
            'missing_pct': missing_pct
        })
        missing_summary = missing_summary[missing_summary['missing_count'] > 0].sort_values(
            'missing_pct', ascending=False
        )

        if not missing_summary.empty:
            logger.info(f"Columns with missing values: {len(missing_summary)}")
            logger.debug(f"\n{missing_summary.head(10)}")

        # For now, keep missing values as-is (they are informative in questionnaires)
        # Optional questions legitimately have missing data
        return df

    def detect_anomalies(self, df: pd.DataFrame, format_type: str = 'long') -> pd.DataFrame:
        """
        Detect anomalies in questionnaire data (e.g., incomplete responses).

        Args:
            df: Cleaned DataFrame
            format_type: 'wide' or 'long' format

        Returns:
            DataFrame with anomaly flags
        """
        logger.info("Detecting anomalies in questionnaire data")

        if format_type == 'wide' and not df.empty:
            # Check for incomplete responses (too many missing values)
            missing_per_row = df.isnull().sum(axis=1)
            total_cols = len(df.columns)
            missing_pct = (missing_per_row / total_cols * 100).round(2)

            df['incomplete_response_flag'] = missing_pct > 50
            incomplete_count = df['incomplete_response_flag'].sum()

            if incomplete_count > 0:
                logger.warning(f"Found {incomplete_count} potentially incomplete responses (>50% missing)")

        return df

    def process(self, data: Dict[str, pd.DataFrame]) -> Dict[str, pd.DataFrame]:
        """
        Process the Siemens questionnaire data (both formats).

        Args:
            data: Dictionary with 'wide' and 'long' DataFrames

        Returns:
            Processed data dictionary
        """
        logger.info("Starting Siemens data preprocessing pipeline")

        result = {}

        # Process wide format
        if not data['wide'].empty:
            logger.info(f"Processing wide format: {len(data['wide'])} records")
            wide_df = data['wide'].copy()
            wide_df = self.handle_missing_values(wide_df)
            wide_df = self.detect_anomalies(wide_df, format_type='wide')
            result['wide'] = wide_df

            # Save processed wide format
            output_path = self.output_dir / "processed_wide_format.csv"
            wide_df.to_csv(output_path, index=False, encoding='utf-8')
            logger.info(f"Saved processed wide format to {output_path}")

        # Process long format
        if not data['long'].empty:
            logger.info(f"Processing long format: {len(data['long'])} records")
            long_df = data['long'].copy()
            long_df = self.handle_missing_values(long_df)
            long_df = self.detect_anomalies(long_df, format_type='long')
            result['long'] = long_df

            # Save processed long format
            output_path = self.output_dir / "processed_long_format.csv"
            long_df.to_csv(output_path, index=False, encoding='utf-8')
            logger.info(f"Saved processed long format to {output_path}")

        logger.info("Preprocessing pipeline complete")
        return result

    def extract_pain_points(self, long_df: pd.DataFrame) -> pd.DataFrame:
        """
        Extract pain points from long format questionnaire data.

        Args:
            long_df: Long format DataFrame

        Returns:
            DataFrame with pain point responses
        """
        if long_df.empty:
            return pd.DataFrame()

        # Filter for pain point section
        pain_points = long_df[long_df['section'] == 'pain_points'].copy()

        logger.info(f"Extracted {len(pain_points)} pain point responses")
        return pain_points

    def convert_long_to_wide(self, long_df: pd.DataFrame) -> pd.DataFrame:
        """
        Convert long format to wide format.

        Args:
            long_df: Long format DataFrame

        Returns:
            Wide format DataFrame
        """
        if long_df.empty:
            return pd.DataFrame()

        logger.info("Converting long format to wide format")

        # Pivot on response_id and field_name
        wide_df = long_df.pivot_table(
            index=['response_id', 'interviewer', 'interview_date', 'country', 'institution_name'],
            columns='field_name',
            values='response_text',
            aggfunc='first'
        ).reset_index()

        return wide_df
