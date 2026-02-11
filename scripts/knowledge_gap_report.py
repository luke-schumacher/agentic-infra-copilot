"""
Knowledge Gap Report

Analyzes customer_mapping.csv to identify which customers lack
event logs, questionnaire data, or technical documentation.

Run: python scripts/knowledge_gap_report.py
Output: data/processed/knowledge_gap_report.csv

Author: Thesis Project - Agentic Infra Co-Pilot
"""

import csv
import logging
from pathlib import Path

import pandas as pd

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).parent.parent
PROCESSED_DIR = BASE_DIR / "data" / "processed"


def generate_report():
    """Generate knowledge gap report from customer mapping."""
    mapping_path = PROCESSED_DIR / "customer_mapping.csv"
    if not mapping_path.exists():
        logger.error(f"Customer mapping not found: {mapping_path}")
        logger.error("Run build_customer_mapping.py first.")
        return

    df = pd.read_csv(mapping_path)
    logger.info(f"Loaded {len(df)} customers from mapping")

    # Compute gaps
    rows = []
    for _, customer in df.iterrows():
        gaps = []

        if not customer.get('has_parquet', False):
            gaps.append('missing_parquet')
        if not customer.get('has_event_logs', False):
            gaps.append('missing_event_logs')
        if not customer.get('has_questionnaire', False):
            gaps.append('missing_questionnaire')
        if not customer.get('has_dcs_docs', False):
            gaps.append('missing_dcs_docs')
        if customer.get('mapping_status') == 'unmatched':
            gaps.append('unmatched_institution')

        rows.append({
            'customer_id': customer['customer_id'],
            'institution_name': customer.get('institution_name', ''),
            'has_event_logs': customer.get('has_event_logs', False),
            'has_parquet': customer.get('has_parquet', False),
            'has_questionnaire': customer.get('has_questionnaire', False),
            'has_dcs_docs': customer.get('has_dcs_docs', False),
            'total_events': customer.get('total_events', 0),
            'error_count': customer.get('error_count', 0),
            'gap_count': len(gaps),
            'gaps': '; '.join(gaps) if gaps else 'none',
            'data_completeness_pct': round(
                (4 - len([g for g in gaps if g != 'unmatched_institution'])) / 4 * 100, 1
            ),
        })

    # Sort by gap count (most gaps first)
    rows.sort(key=lambda r: (-r['gap_count'], r['customer_id']))

    # Save report
    output_path = PROCESSED_DIR / "knowledge_gap_report.csv"
    fieldnames = list(rows[0].keys()) if rows else []
    with open(output_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    logger.info(f"Knowledge gap report saved: {output_path}")

    # Print summary
    total = len(rows)
    no_parquet = sum(1 for r in rows if not r['has_parquet'])
    no_questionnaire = sum(1 for r in rows if not r['has_questionnaire'])
    unmatched = sum(1 for r in rows if 'unmatched_institution' in r['gaps'])
    fully_complete = sum(1 for r in rows if r['gap_count'] == 0)

    logger.info(f"\n--- KNOWLEDGE GAP SUMMARY ---")
    logger.info(f"Total customers: {total}")
    logger.info(f"Fully complete: {fully_complete}")
    logger.info(f"Missing parquet: {no_parquet}")
    logger.info(f"Missing questionnaire: {no_questionnaire}")
    logger.info(f"Unmatched institutions: {unmatched}")

    if no_parquet > 0:
        missing = [r['customer_id'] for r in rows if not r['has_parquet']]
        logger.info(f"Customers missing parquet: {missing}")


def main():
    logger.info("=" * 60)
    logger.info("KNOWLEDGE GAP REPORT")
    logger.info("=" * 60)
    generate_report()


if __name__ == "__main__":
    main()
