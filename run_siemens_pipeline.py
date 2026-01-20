"""
Siemens MRRT Questionnaire Data Pipeline

This script runs the complete data ingestion and preprocessing pipeline
for Siemens MRRT questionnaire data.

Usage:
    python run_siemens_pipeline.py
"""

import logging
import sys
from pathlib import Path

# Ensure logs directory exists
Path("logs").mkdir(exist_ok=True)

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from src.ingestion.csv_parser import SiemensCSVParser
from src.preprocessing.siemens_preprocessor import SiemensPreprocessor

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('logs/siemens_pipeline.log')
    ]
)

logger = logging.getLogger(__name__)


def main():
    """Run the Siemens data pipeline."""
    logger.info("=" * 60)
    logger.info("Starting Siemens MRRT Questionnaire Data Pipeline")
    logger.info("=" * 60)

    try:
        # Step 1: Parse CSV files
        logger.info("\n[Step 1/3] Parsing CSV files...")
        parser = SiemensCSVParser(input_dir="data/raw/siemens")
        parsed_data = parser.parse_all()

        # Report parsing results
        if not parsed_data['wide'].empty:
            logger.info(f"Wide format: {len(parsed_data['wide'])} rows")
        if not parsed_data['long'].empty:
            logger.info(f"Long format: {len(parsed_data['long'])} rows")

        # Step 2: Preprocess data
        logger.info("\n[Step 2/3] Preprocessing data...")
        preprocessor = SiemensPreprocessor(output_dir="data/processed/siemens")
        processed_data = preprocessor.process(parsed_data)

        # Step 3: Extract insights
        logger.info("\n[Step 3/3] Extracting insights...")
        if not processed_data.get('long', pd.DataFrame()).empty:
            pain_points = preprocessor.extract_pain_points(processed_data['long'])
            if not pain_points.empty:
                logger.info(f"Extracted {len(pain_points)} pain point responses")

                # Save pain points separately
                pain_points_path = Path("data/processed/siemens/pain_points_extracted.csv")
                pain_points.to_csv(pain_points_path, index=False, encoding='utf-8')
                logger.info(f"Saved pain points to {pain_points_path}")

        logger.info("\n" + "=" * 60)
        logger.info("Pipeline completed successfully!")
        logger.info("=" * 60)

        # Print summary
        print("\nPipeline Summary:")
        print(f"  - Parsed files: {len(parsed_data['wide']) + len(parsed_data['long']) if parsed_data else 0} total rows")
        print(f"  - Wide format: {len(processed_data.get('wide', []))} rows")
        print(f"  - Long format: {len(processed_data.get('long', []))} rows")
        print(f"  - Output directory: data/processed/siemens/")
        print(f"  - Log file: logs/siemens_pipeline.log")

    except Exception as e:
        logger.error(f"Pipeline failed with error: {str(e)}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    # Import pandas here to avoid import errors in logging setup
    import pandas as pd

    main()
