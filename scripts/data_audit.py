"""
Siemens Data Audit & Discovery Script

Scans data/raw/siemens/ to produce a comprehensive inventory:
- Classifies files by category (DCS, SOP, Questionnaire, Event Log, etc.)
- Flags duplicates and non-MRI files
- Reports unindexed files and coverage gaps

Run: python scripts/data_audit.py
Output: data/audit/data_audit_report.json
"""

import json
import hashlib
from pathlib import Path
from typing import Dict, List, Any
from collections import defaultdict
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).parent.parent
RAW_SIEMENS = BASE_DIR / "data" / "raw" / "siemens"
AUDIT_DIR = BASE_DIR / "data" / "audit"

# Classification rules: keyword -> category
FILE_CATEGORIES = {
    'DCS': 'DICOM Conformance Statement',
    'MAGNETOM': 'Hardware Specification',
    'CSPL': 'Hardware Specification',
    'SOP': 'Safety/SOP',
    'Safety': 'Safety/SOP',
    'MRRT': 'Questionnaire',
    'Questionnaire': 'Questionnaire',
    'Protocol': 'Protocol Management',
    'Dot Cockpit': 'Protocol Management',
    'ACR': 'Clinical Guidelines',
    'Appropriateness': 'Clinical Guidelines',
    'Radiologist': 'Clinical Interpretation',
    'Interpretation': 'Clinical Interpretation',
    'versicharge': 'Non-MRI (Wallbox)',
    'wallbox': 'Non-MRI (Wallbox)',
}

# Agent assignment rules
AGENT_ASSIGNMENTS = {
    'DICOM Conformance Statement': 'hardware_agent (The Specialist)',
    'Hardware Specification': 'hardware_agent (The Specialist)',
    'Safety/SOP': 'telemetry_agent (The Auditor)',
    'Questionnaire': 'governance_agent (The Anthropologist)',
    'Clinical Guidelines': 'telemetry_agent (The Auditor)',
    'Clinical Interpretation': 'hardware_agent (The Specialist)',
    'Protocol Management': 'hardware_agent (The Specialist)',
    'Non-MRI (Wallbox)': 'EXCLUDE',
}


def classify_file(filename: str) -> str:
    """Classify a file by its name."""
    name_lower = filename.lower()
    for keyword, category in FILE_CATEGORIES.items():
        if keyword.lower() in name_lower:
            return category
    return 'Uncategorized'


def get_file_hash(filepath: Path, block_size: int = 65536) -> str:
    """Compute MD5 hash of first 64KB for duplicate detection."""
    hasher = hashlib.md5()
    try:
        with open(filepath, 'rb') as f:
            buf = f.read(block_size)
            hasher.update(buf)
    except (IOError, PermissionError):
        return "unreadable"
    return hasher.hexdigest()


def scan_directory() -> Dict[str, Any]:
    """Scan the siemens data directory and produce an audit report."""
    if not RAW_SIEMENS.exists():
        logger.error(f"Siemens data directory not found: {RAW_SIEMENS}")
        return {}

    report = {
        'scan_root': str(RAW_SIEMENS),
        'files': [],
        'summary': defaultdict(lambda: {'count': 0, 'total_size_mb': 0.0, 'files': []}),
        'duplicates': [],
        'excluded': [],
        'customer_directories': [],
        'parquet_files': [],
        'warnings': [],
    }

    # Track hashes for duplicate detection
    hash_to_files: Dict[str, List[str]] = defaultdict(list)

    # Scan all files
    for filepath in sorted(RAW_SIEMENS.rglob('*')):
        if filepath.is_dir():
            continue

        rel_path = str(filepath.relative_to(RAW_SIEMENS))
        size_mb = round(filepath.stat().st_size / (1024 * 1024), 2)
        ext = filepath.suffix.lower()
        category = classify_file(filepath.name)
        agent = AGENT_ASSIGNMENTS.get(category, 'unassigned')

        file_entry = {
            'path': rel_path,
            'name': filepath.name,
            'extension': ext,
            'size_mb': size_mb,
            'category': category,
            'assigned_agent': agent,
        }

        # Track by category
        cat_key = category
        report['summary'][cat_key]['count'] += 1
        report['summary'][cat_key]['total_size_mb'] = round(
            report['summary'][cat_key]['total_size_mb'] + size_mb, 2
        )
        report['summary'][cat_key]['files'].append(rel_path)

        # Track parquet files
        if ext == '.parquet':
            report['parquet_files'].append(file_entry)

        # Track PDFs for duplicate detection
        if ext == '.pdf':
            file_hash = get_file_hash(filepath)
            hash_to_files[file_hash].append(rel_path)

        # Flag non-MRI files
        if category == 'Non-MRI (Wallbox)':
            report['excluded'].append(file_entry)

        report['files'].append(file_entry)

    # Detect duplicates
    for file_hash, paths in hash_to_files.items():
        if len(paths) > 1:
            report['duplicates'].append({
                'hash': file_hash,
                'files': paths,
                'recommendation': f'Keep {paths[0]}, remove {paths[1:]}'
            })

    # Scan customer directories (event log data)
    eventlog_dir = RAW_SIEMENS / "eventlog_txt"
    if eventlog_dir.exists():
        for customer_dir in sorted(eventlog_dir.iterdir()):
            if customer_dir.is_dir() and customer_dir.name.startswith('mr'):
                customer_id = customer_dir.name
                has_parquet = (customer_dir / f"{customer_id}_deduplicated.parquet").exists()
                has_sources = (customer_dir / f"{customer_id}_sources.csv").exists()
                has_summary = (customer_dir / f"{customer_id}_summary.csv").exists()

                parquet_size = 0.0
                if has_parquet:
                    parquet_size = round(
                        (customer_dir / f"{customer_id}_deduplicated.parquet").stat().st_size / (1024 * 1024), 2
                    )

                entry = {
                    'customer_id': customer_id,
                    'has_parquet': has_parquet,
                    'has_sources_csv': has_sources,
                    'has_summary_csv': has_summary,
                    'parquet_size_mb': parquet_size,
                    'complete': has_parquet and has_sources and has_summary,
                }

                if not has_parquet:
                    report['warnings'].append(
                        f"Customer {customer_id}: missing _deduplicated.parquet file"
                    )

                report['customer_directories'].append(entry)

    # Generate summary statistics
    total_customers = len(report['customer_directories'])
    complete_customers = sum(1 for c in report['customer_directories'] if c['complete'])
    total_parquet_mb = sum(c['parquet_size_mb'] for c in report['customer_directories'])

    report['statistics'] = {
        'total_files': len(report['files']),
        'total_customers': total_customers,
        'complete_customers': complete_customers,
        'incomplete_customers': total_customers - complete_customers,
        'total_parquet_size_mb': round(total_parquet_mb, 2),
        'total_duplicates_found': len(report['duplicates']),
        'total_excluded_files': len(report['excluded']),
        'categories': {k: v['count'] for k, v in report['summary'].items()},
    }

    # Convert defaultdict to regular dict for JSON serialization
    report['summary'] = dict(report['summary'])

    return report


def main():
    """Run the data audit and save report."""
    logger.info("=" * 60)
    logger.info("SIEMENS DATA AUDIT & DISCOVERY")
    logger.info("=" * 60)

    report = scan_directory()

    if not report:
        logger.error("Audit failed - no data found")
        return

    # Save report
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    output_path = AUDIT_DIR / "data_audit_report.json"

    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(report, f, indent=2, default=str)

    logger.info(f"\nAudit report saved: {output_path}")

    # Print summary
    stats = report['statistics']
    logger.info(f"\n--- SUMMARY ---")
    logger.info(f"Total files scanned: {stats['total_files']}")
    logger.info(f"Customer directories: {stats['total_customers']} ({stats['complete_customers']} complete)")
    logger.info(f"Total Parquet data: {stats['total_parquet_size_mb']} MB")
    logger.info(f"Duplicates found: {stats['total_duplicates_found']}")
    logger.info(f"Non-MRI files excluded: {stats['total_excluded_files']}")

    logger.info(f"\nCategories:")
    for cat, count in sorted(stats['categories'].items(), key=lambda x: -x[1]):
        logger.info(f"  {cat}: {count} files")

    if report['warnings']:
        logger.info(f"\nWarnings:")
        for w in report['warnings']:
            logger.warning(f"  {w}")

    if report['duplicates']:
        logger.info(f"\nDuplicates:")
        for d in report['duplicates']:
            logger.info(f"  {d['files']}")


if __name__ == "__main__":
    main()
