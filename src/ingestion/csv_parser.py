"""
CSV Parser for Siemens Hardware Scan Data

Purpose:
- Processes 500+ Siemens hardware scan CSV files
- Standardizes column names and data formats
- Handles missing values and data quality issues

Input: Raw CSV files from data/raw/siemens/
Output: Cleaned DataFrames ready for preprocessing
"""

from pathlib import Path
from typing import List, Dict, Any
import pandas as pd
import logging

logger = logging.getLogger(__name__)


class SiemensCSVParser:
    """Parser for Siemens hardware scan CSV files."""

    def __init__(self, input_dir: str = "data/raw/siemens"):
        """
        Initialize the CSV parser.

        Args:
            input_dir: Directory containing raw Siemens CSV files
        """
        self.input_dir = Path(input_dir)

    def parse_csv(self, csv_path: Path) -> pd.DataFrame:
        """
        Parse a single CSV file.

        Args:
            csv_path: Path to the CSV file

        Returns:
            DataFrame containing the parsed CSV data
        """
        logger.info(f"Parsing CSV: {csv_path.name}")

        try:
            # Read CSV with UTF-8 encoding, handle missing values
            # Use error_bad_lines=False for Python < 3.10, on_bad_lines='skip' for >= 3.10
            df = pd.read_csv(
                csv_path,
                encoding='utf-8',
                na_values=['', 'NA', 'N/A', 'null', 'None'],
                keep_default_na=True,
                on_bad_lines='warn',  # Warn but continue on malformed lines
                engine='python'  # More flexible parser
            )

            # Add source file tracking
            df['source_file'] = csv_path.name

            # Detect format based on column structure
            if 'section' in df.columns and 'question_id' in df.columns:
                df['format_type'] = 'long'
                logger.info(f"Detected long format: {len(df)} rows")
            else:
                df['format_type'] = 'wide'
                logger.info(f"Detected wide format: {len(df)} rows, {len(df.columns)} columns")

            return df

        except Exception as e:
            logger.error(f"Error parsing {csv_path.name}: {str(e)}")
            raise

    def parse_all(self) -> Dict[str, pd.DataFrame]:
        """
        Parse all CSV files and return them organized by format type.

        Returns:
            Dictionary with keys 'wide' and 'long', each containing a DataFrame
        """
        csv_files = list(self.input_dir.glob("*.csv"))
        logger.info(f"Found {len(csv_files)} CSV files to parse")

        if not csv_files:
            logger.warning(f"No CSV files found in {self.input_dir}")
            return {"wide": pd.DataFrame(), "long": pd.DataFrame()}

        wide_dfs = []
        long_dfs = []

        for csv_file in csv_files:
            try:
                df = self.parse_csv(csv_file)

                # Separate by format type
                if df['format_type'].iloc[0] == 'long':
                    long_dfs.append(df)
                else:
                    wide_dfs.append(df)

            except Exception as e:
                logger.error(f"Skipping {csv_file.name} due to error: {str(e)}")
                continue

        # Combine dataframes by type
        result = {
            'wide': pd.concat(wide_dfs, ignore_index=True) if wide_dfs else pd.DataFrame(),
            'long': pd.concat(long_dfs, ignore_index=True) if long_dfs else pd.DataFrame()
        }

        logger.info(f"Parsed {len(wide_dfs)} wide format files, {len(long_dfs)} long format files")
        if not result['wide'].empty:
            logger.info(f"Wide format: {len(result['wide'])} total rows")
        if not result['long'].empty:
            logger.info(f"Long format: {len(result['long'])} total rows")

        return result
