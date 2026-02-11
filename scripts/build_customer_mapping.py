"""
Customer Mapping Builder

Maps the 35 Customer IDs (from event log directories) to institution information
from MRRT questionnaires and computes data coverage per customer.

Run: python scripts/build_customer_mapping.py
Output: data/processed/customer_mapping.csv

Author: Thesis Project - Agentic Infra Co-Pilot
"""

import csv
import logging
from pathlib import Path
from typing import Dict, List, Any

import pandas as pd

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).parent.parent
RAW_SIEMENS = BASE_DIR / "data" / "raw" / "siemens"
EVENTLOG_DIR = RAW_SIEMENS / "eventlog_txt"
PROCESSED_DIR = BASE_DIR / "data" / "processed"

# DCS PDFs that apply to specific scanner software versions
DCS_COVERAGE = {
    'DCS_MR_XA50.pdf': 'XA50',
    'DCS_MR_XA51A-V03.pdf': 'XA51A',
    'DCS_MR_XA60.pdf': 'XA60',
}


def get_customer_directories() -> List[Dict[str, Any]]:
    """Scan eventlog_txt for customer directories and check completeness."""
    if not EVENTLOG_DIR.exists():
        logger.error(f"Event log directory not found: {EVENTLOG_DIR}")
        return []

    customers = []
    for d in sorted(EVENTLOG_DIR.iterdir()):
        if not d.is_dir() or not d.name.startswith('mr'):
            continue

        cid = d.name
        parquet_path = d / f"{cid}_deduplicated.parquet"
        summary_path = d / f"{cid}_summary.csv"
        sources_path = d / f"{cid}_sources.csv"

        customers.append({
            'customer_id': cid,
            'has_parquet': parquet_path.exists(),
            'has_summary': summary_path.exists(),
            'has_sources': sources_path.exists(),
            'parquet_size_mb': round(parquet_path.stat().st_size / (1024 * 1024), 2) if parquet_path.exists() else 0.0,
        })

    return customers


def load_overview_stats() -> Dict[str, Dict[str, Any]]:
    """Load aggregate stats from all_customers_overview.csv."""
    overview_path = EVENTLOG_DIR / "all_customers_overview.csv"
    if not overview_path.exists():
        logger.warning("all_customers_overview.csv not found")
        return {}

    df = pd.read_csv(overview_path)
    stats = {}
    for _, row in df.iterrows():
        stats[row['customer']] = {
            'total_events': int(row['total_events']),
            'mri_events': int(row['mri_events']),
            'mri_pct': float(row['mri_pct']),
            'errors': int(row['errors']),
            'warnings': int(row['warnings']),
        }
    return stats


def load_questionnaire_profiles() -> List[Dict[str, Any]]:
    """Load institution profiles from the questionnaire CSV."""
    long_format = RAW_SIEMENS / "sample_processed_long_format.csv"
    if not long_format.exists():
        logger.warning("Questionnaire CSV not found")
        return []

    df = pd.read_csv(long_format)
    profiles = []

    for rid in df['response_id'].unique():
        resp = df[df['response_id'] == rid]
        field_map = dict(zip(resp['field_name'], resp['response_value']))
        text_map = dict(zip(resp['field_name'], resp['response_text']))

        profiles.append({
            'response_id': rid,
            'institution_name': resp['institution_name'].iloc[0],
            'country': resp['country'].iloc[0],
            'org_type': field_map.get('org_type', ''),
            'mr_vendor_1': text_map.get('mr_vendor_1', ''),
            'mr_model_1': text_map.get('mr_model_1', ''),
        })

    return profiles


def check_dcs_coverage() -> List[str]:
    """Check which DCS PDFs exist."""
    available = []
    for pdf_name in DCS_COVERAGE:
        if (RAW_SIEMENS / pdf_name).exists():
            available.append(pdf_name)
    return available


def build_mapping():
    """Build the customer mapping and save to CSV."""
    logger.info("Building customer mapping...")

    # Get customer directories
    customers = get_customer_directories()
    logger.info(f"Found {len(customers)} customer directories")

    # Load overview stats
    stats = load_overview_stats()

    # Load questionnaire data
    profiles = load_questionnaire_profiles()
    logger.info(f"Found {len(profiles)} questionnaire profiles")

    # Check DCS coverage
    dcs_pdfs = check_dcs_coverage()
    logger.info(f"DCS PDFs available: {dcs_pdfs}")

    # Build mapping rows
    # Note: We cannot automatically map customer IDs to questionnaire institutions
    # without explicit linking data. We create the mapping structure with
    # 'unmatched' status for customers that need manual linking.
    rows = []
    for cust in customers:
        cid = cust['customer_id']
        cust_stats = stats.get(cid, {})

        row = {
            'customer_id': cid,
            'institution_name': '',  # needs manual mapping
            'country': '',
            'scanner_model': '',
            'institution_type': '',
            'has_questionnaire': False,
            'has_event_logs': cust['has_parquet'] or cust['has_summary'],
            'has_parquet': cust['has_parquet'],
            'parquet_size_mb': cust['parquet_size_mb'],
            'total_events': cust_stats.get('total_events', 0),
            'mri_events': cust_stats.get('mri_events', 0),
            'mri_pct': cust_stats.get('mri_pct', 0.0),
            'error_count': cust_stats.get('errors', 0),
            'warning_count': cust_stats.get('warnings', 0),
            'has_dcs_docs': len(dcs_pdfs) > 0,  # DCS PDFs apply globally to all customers
            'mapping_status': 'unmatched',
        }
        rows.append(row)

    # Save mapping
    output_path = PROCESSED_DIR / "customer_mapping.csv"
    output_path.parent.mkdir(parents=True, exist_ok=True)

    fieldnames = list(rows[0].keys()) if rows else []
    with open(output_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    logger.info(f"Customer mapping saved: {output_path} ({len(rows)} customers)")

    # Also save questionnaire profiles separately for reference
    if profiles:
        profiles_path = PROCESSED_DIR / "questionnaire_institutions.csv"
        pd.DataFrame(profiles).to_csv(profiles_path, index=False, encoding='utf-8')
        logger.info(f"Questionnaire institutions saved: {profiles_path}")

    # Print summary
    has_parquet = sum(1 for r in rows if r['has_parquet'])
    total_events = sum(r['total_events'] for r in rows)
    total_errors = sum(r['error_count'] for r in rows)

    logger.info(f"\n--- SUMMARY ---")
    logger.info(f"Total customers: {len(rows)}")
    logger.info(f"With parquet data: {has_parquet}")
    logger.info(f"Without parquet: {len(rows) - has_parquet}")
    logger.info(f"Total events across all: {total_events:,}")
    logger.info(f"Total errors across all: {total_errors:,}")
    logger.info(f"Questionnaire profiles available: {len(profiles)}")
    logger.info(f"DCS PDFs available: {len(dcs_pdfs)}")
    logger.info(f"\nNOTE: Customer-to-institution mapping requires manual linking.")
    logger.info(f"Edit {output_path} to fill in institution_name and scanner_model.")


def main():
    logger.info("=" * 60)
    logger.info("CUSTOMER MAPPING BUILDER")
    logger.info("=" * 60)
    build_mapping()


if __name__ == "__main__":
    main()
