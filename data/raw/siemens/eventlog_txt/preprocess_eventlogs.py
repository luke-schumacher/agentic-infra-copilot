"""
Bulk Eventlog Preprocessor — Siemens MRI Event Logs (Portable)

Recursively discovers directories containing .txt eventlog files,
parses them into structured Parquet/CSV and deduplicated Parquet/CSV,
then optionally deletes originals after verified writes.

Memory-safe: streams one .txt file at a time (~40 MB peak), never loads
an entire folder into RAM. Safe for 16 GB machines processing 15 GB folders.

Dependencies: pip install pandas pyarrow tqdm

Output per group (one per mr* folder):
    {name}_structured.parquet   — full parsed events, zstd compressed
    {name}_deduplicated.parquet — masked descriptions + occurrence count
    {name}_structured.csv       — (with --csv) same as parquet, universal format
    {name}_deduplicated.csv     — (with --csv) same as parquet, universal format

Usage:
    # Drop this script anywhere and point it at your Eventlog folder:
    python preprocess_eventlogs.py /path/to/Eventlog --dry-run
    python preprocess_eventlogs.py /path/to/Eventlog --skip-delete --csv
    python preprocess_eventlogs.py /path/to/Eventlog --output-dir ./processed
    python preprocess_eventlogs.py /path/to/Eventlog   # full run, deletes .txt after

Expected structure:
    Eventlog/
      mr200103/
        MR200103_EvtLog_20251210.txt
        MR200103_EvtLog_20251211.txt
      mr155687/
        MR155687_EvtLog_20251210.txt
"""

import argparse
import gc
import logging
import re
import sys
import time
from collections import defaultdict
from pathlib import Path

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
from tqdm import tqdm

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

# --------------------------------------------------------------------------- #
#  Constants                                                                    #
# --------------------------------------------------------------------------- #

COLUMNS = ["level", "date", "time", "source", "event_id", "description"]

# Order matters: GUIDs before dates (GUIDs contain date-like hex sequences)
MASK_PATTERNS = [
    (re.compile(r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}"), "<GUID>"),
    (re.compile(r"\d{4}-\d{2}-\d{2}"), "<DATE>"),
    (re.compile(r"\d{2}:\d{2}:\d{2}"), "<TIME>"),
    (re.compile(r"0x[0-9a-fA-F]+"), "<HEX>"),
    (re.compile(r"PID=\d+"), "PID=<PID>"),
    (re.compile(r"ExitCode=\d+"), "ExitCode=<CODE>"),
    (re.compile(r"\bDev#[0-9a-fA-F]+"), "Dev#<DEV_ID>"),
    (re.compile(r"#[0-9a-fA-F]{4,}"), "#<HEX_ID>"),
    (re.compile(r"(?<![a-zA-Z_])\d{5,}(?![a-zA-Z])"), "<NUM_ID>"),
]

# PyArrow schema for structured parquet (defined once, reused for all writers)
STRUCTURED_SCHEMA = pa.schema([
    ("level", pa.string()),
    ("date", pa.string()),
    ("time", pa.string()),
    ("source", pa.string()),
    ("event_id", pa.string()),
    ("description", pa.string()),
    ("source_file", pa.string()),
])


# --------------------------------------------------------------------------- #
#  Encoding detection                                                           #
# --------------------------------------------------------------------------- #

def detect_encoding(file_path: Path) -> str:
    """Check BOM, then validate first line parses as tab-delimited."""
    with open(file_path, "rb") as f:
        bom = f.read(4)
    if bom[:2] == b"\xff\xfe":
        return "utf-16-le"
    if bom[:2] == b"\xfe\xff":
        return "utf-16-be"

    for enc in ("utf-8", "utf-16-le"):
        try:
            with open(file_path, "r", encoding=enc, errors="strict") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    if len(line.split("\t")) >= 6:
                        return enc
                    break
        except (UnicodeDecodeError, UnicodeError):
            continue
    return "utf-8"


# --------------------------------------------------------------------------- #
#  File parsing                                                                 #
# --------------------------------------------------------------------------- #

def read_eventlog_file(file_path: Path, encoding: str = None) -> pd.DataFrame:
    """Parse a tab-delimited eventlog into structured columns."""
    enc = encoding or detect_encoding(file_path)
    rows = []
    skipped = 0

    with open(file_path, "r", encoding=enc, errors="replace") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            parts = line.split("\t")
            if len(parts) < 6:
                skipped += 1
                continue
            rows.append({
                "level": parts[0],
                "date": parts[1],
                "time": parts[2],
                "source": parts[3],
                "event_id": parts[4],
                "description": "\t".join(parts[5:]),
            })

    if skipped:
        logger.debug("%s: skipped %d unparseable lines", file_path.name, skipped)

    return pd.DataFrame(rows, columns=COLUMNS)


# --------------------------------------------------------------------------- #
#  Masking                                                                      #
# --------------------------------------------------------------------------- #

def mask_dynamic_values(description: str) -> str:
    """Replace timestamps, hex IDs, GUIDs, PIDs, numeric IDs with placeholders."""
    for pattern, replacement in MASK_PATTERNS:
        description = pattern.sub(replacement, description)
    return description


# --------------------------------------------------------------------------- #
#  Discovery                                                                    #
# --------------------------------------------------------------------------- #

def discover_groups(root: Path) -> dict[str, list[Path]]:
    """
    Recursively find all .txt files under root and group by parent directory.

    Returns dict mapping group name (relative path from root) to .txt file list.
    For files directly in root, group name is the filename prefix (e.g. "MR176571").
    """
    groups: dict[str, list[Path]] = defaultdict(list)

    for txt_file in sorted(root.rglob("*.txt")):
        if not txt_file.is_file():
            continue
        if txt_file.stat().st_size < 100:
            continue

        parent = txt_file.parent
        if parent == root:
            prefix = txt_file.stem.split("_")[0] if "_" in txt_file.stem else txt_file.stem
            groups[prefix].append(txt_file)
        else:
            rel = parent.relative_to(root)
            group_name = str(rel).replace("\\", "/")
            groups[group_name].append(txt_file)

    return dict(groups)


# --------------------------------------------------------------------------- #
#  Processing (chunked / streaming)                                             #
# --------------------------------------------------------------------------- #

def process_group(
    group_name: str,
    txt_files: list[Path],
    output_dir: Path,
    args: argparse.Namespace,
) -> dict:
    """
    Process one group (one mr* folder) of .txt files using streaming I/O.

    Memory strategy:
      - Structured parquet: stream one .txt file at a time via ParquetWriter
      - Structured CSV: append one .txt file at a time
      - Deduplicated: read structured parquet back one row group at a time,
        mask + accumulate counts in a dict, write once at the end
      - Peak RAM ≈ size of one .txt file (~40 MB typical)
    """
    txt_size = sum(f.stat().st_size for f in txt_files)
    safe_name = group_name.replace("/", "_").replace("\\", "_")

    stats = {
        "group": group_name,
        "txt_files": len(txt_files),
        "txt_size_mb": round(txt_size / (1024 * 1024), 1),
        "rows_structured": 0,
        "rows_deduplicated": 0,
        "parquet_structured_mb": 0.0,
        "parquet_dedup_mb": 0.0,
        "csv_structured_mb": 0.0,
        "csv_dedup_mb": 0.0,
        "skipped_files": 0,
        "status": "ok",
    }

    if args.dry_run:
        stats["status"] = "dry-run"
        logger.info(
            "[DRY-RUN] %s: %d files (%.1f MB)",
            group_name, len(txt_files), stats["txt_size_mb"],
        )
        return stats

    # Check for resume: skip if output parquets already exist
    output_dir.mkdir(parents=True, exist_ok=True)
    structured_pq = output_dir / f"{safe_name}_structured.parquet"
    dedup_pq = output_dir / f"{safe_name}_deduplicated.parquet"

    if structured_pq.exists() and dedup_pq.exists():
        existing_rows = pq.read_metadata(structured_pq).num_rows
        stats["status"] = "skipped-exists"
        stats["rows_structured"] = existing_rows
        logger.info(
            "%s: SKIPPED (parquets already exist, %d rows). "
            "Delete them to reprocess.",
            group_name, existing_rows,
        )
        return stats

    # ── Step 1: Stream .txt files into structured parquet (+ CSV) ────────────
    enc = args.encoding
    writer = None
    csv_path = output_dir / f"{safe_name}_structured.csv" if args.csv else None
    csv_first = True
    total_rows = 0

    for txt_file in txt_files:
        try:
            df = read_eventlog_file(txt_file, encoding=enc)
            if df.empty:
                logger.warning("  %s: 0 parseable rows, skipping", txt_file.name)
                stats["skipped_files"] += 1
                continue

            df["source_file"] = txt_file.name
            file_rows = len(df)
            total_rows += file_rows

            # Write to parquet (one row group per .txt file)
            table = pa.Table.from_pandas(df, schema=STRUCTURED_SCHEMA, preserve_index=False)
            if writer is None:
                writer = pq.ParquetWriter(
                    structured_pq,
                    STRUCTURED_SCHEMA,
                    compression="zstd",
                    compression_level=args.compression_level,
                )
            writer.write_table(table)

            # Append to CSV
            if csv_path:
                df.to_csv(
                    csv_path,
                    mode="w" if csv_first else "a",
                    header=csv_first,
                    index=False,
                )
                csv_first = False

            logger.info(
                "  %s: %d rows (%.1f MB)",
                txt_file.name, file_rows,
                txt_file.stat().st_size / (1024 * 1024),
            )

            del df, table
            gc.collect()

        except Exception as e:
            logger.error("  %s: FAILED to read (%s), skipping", txt_file.name, e)
            stats["skipped_files"] += 1
            continue

    if writer is not None:
        writer.close()

    if total_rows == 0:
        stats["status"] = "no-data"
        # Clean up empty parquet if writer was opened then nothing written
        if structured_pq.exists():
            structured_pq.unlink()
        return stats

    stats["rows_structured"] = total_rows
    stats["parquet_structured_mb"] = round(
        structured_pq.stat().st_size / (1024 * 1024), 2
    )
    if csv_path and csv_path.exists():
        stats["csv_structured_mb"] = round(
            csv_path.stat().st_size / (1024 * 1024), 2
        )

    # ── Step 2: Build dedup by reading structured parquet row-group by row-group
    #    Each row group = one original .txt file. Mask + count per chunk,
    #    accumulate into a dict. Peak RAM = one row group.
    dedup_counts: dict[tuple, int] = {}

    pf = pq.ParquetFile(structured_pq)
    for i in range(pf.metadata.num_row_groups):
        chunk = pf.read_row_group(i).to_pandas()
        chunk["masked_description"] = chunk["description"].apply(mask_dynamic_values)
        grouped = chunk.groupby(
            ["level", "source", "event_id", "masked_description"]
        ).size()
        for key, cnt in grouped.items():
            dedup_counts[key] = dedup_counts.get(key, 0) + cnt
        del chunk, grouped
        gc.collect()

    # Convert accumulated counts to DataFrame
    dedup_rows = [
        {
            "level": k[0],
            "source": k[1],
            "event_id": k[2],
            "masked_description": k[3],
            "occurrence_count": v,
        }
        for k, v in dedup_counts.items()
    ]
    del dedup_counts
    gc.collect()

    deduplicated = pd.DataFrame(dedup_rows)
    del dedup_rows
    gc.collect()

    stats["rows_deduplicated"] = len(deduplicated)

    deduplicated.to_parquet(
        dedup_pq,
        engine="pyarrow",
        compression="zstd",
        compression_level=args.compression_level,
        index=False,
    )
    stats["parquet_dedup_mb"] = round(
        dedup_pq.stat().st_size / (1024 * 1024), 2
    )

    if args.csv:
        dedup_csv = output_dir / f"{safe_name}_deduplicated.csv"
        deduplicated.to_csv(dedup_csv, index=False)
        stats["csv_dedup_mb"] = round(
            dedup_csv.stat().st_size / (1024 * 1024), 2
        )

    del deduplicated
    gc.collect()

    # ── Step 3: Verify via parquet metadata (no re-read) ─────────────────────
    meta_s = pq.read_metadata(structured_pq)
    meta_d = pq.read_metadata(dedup_pq)

    if meta_s.num_rows != stats["rows_structured"]:
        stats["status"] = "VERIFY-FAIL-structured"
        logger.error(
            "%s: structured parquet row mismatch (%d on disk vs %d expected)",
            group_name, meta_s.num_rows, stats["rows_structured"],
        )
        return stats

    if meta_d.num_rows != stats["rows_deduplicated"]:
        stats["status"] = "VERIFY-FAIL-dedup"
        logger.error(
            "%s: dedup parquet row mismatch (%d on disk vs %d expected)",
            group_name, meta_d.num_rows, stats["rows_deduplicated"],
        )
        return stats

    # ── Step 4: Delete originals ─────────────────────────────────────────────
    if not args.skip_delete:
        for txt_file in txt_files:
            txt_file.unlink()
        logger.info(
            "%s: deleted %d .txt files (%.1f MB freed)",
            group_name, len(txt_files), stats["txt_size_mb"],
        )

    return stats


# --------------------------------------------------------------------------- #
#  Main                                                                         #
# --------------------------------------------------------------------------- #

def main():
    parser = argparse.ArgumentParser(
        description="Bulk preprocess Siemens MRI eventlog .txt → Parquet/CSV.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""Examples:
  python preprocess_eventlogs.py D:\\Eventlog --dry-run
  python preprocess_eventlogs.py D:\\Eventlog --skip-delete --csv
  python preprocess_eventlogs.py D:\\Eventlog --output-dir D:\\processed
  python preprocess_eventlogs.py .   # process current directory

Resumable: if parquets already exist for a group, that group is skipped.
Delete existing parquets to force reprocessing.""",
    )
    parser.add_argument(
        "root",
        nargs="?",
        default=".",
        help="Root directory to scan for eventlog .txt files (default: current dir).",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default=None,
        help="Write all output to this directory (default: alongside originals).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Discover and report sizes only; no reads or writes.",
    )
    parser.add_argument(
        "--skip-delete",
        action="store_true",
        help="Write output files but keep original .txt files.",
    )
    parser.add_argument(
        "--csv",
        action="store_true",
        help="Also output CSV files (in addition to Parquet).",
    )
    parser.add_argument(
        "--encoding",
        type=str,
        default=None,
        help="Force encoding (e.g. utf-16-le, utf-8). Default: auto-detect.",
    )
    parser.add_argument(
        "--compression-level",
        type=int,
        default=3,
        help="Zstandard compression level for Parquet (1-22). Default: 3.",
    )
    args = parser.parse_args()

    root = Path(args.root).resolve()
    if not root.is_dir():
        logger.error("Root directory does not exist: %s", root)
        sys.exit(1)

    logger.info("Root directory: %s", root)
    logger.info("Scanning for .txt files...")

    groups = discover_groups(root)
    if not groups:
        logger.warning("No .txt eventlog files found under %s", root)
        sys.exit(0)

    total_files = sum(len(files) for files in groups.values())
    total_size_mb = sum(
        f.stat().st_size for files in groups.values() for f in files
    ) / (1024 * 1024)
    logger.info(
        "Found %d groups (mr* folders), %d .txt files, %.1f GB total",
        len(groups), total_files, total_size_mb / 1024,
    )

    output_base = Path(args.output_dir).resolve() if args.output_dir else None

    total_start = time.time()
    all_stats = []

    for group_name, txt_files in tqdm(
        sorted(groups.items()), desc="Groups", unit="group"
    ):
        if output_base:
            out_dir = output_base
        else:
            out_dir = txt_files[0].parent

        try:
            stats = process_group(group_name, txt_files, out_dir, args)
        except Exception as e:
            logger.error("%s: UNEXPECTED ERROR: %s", group_name, e)
            stats = {
                "group": group_name,
                "txt_files": len(txt_files),
                "txt_size_mb": round(
                    sum(f.stat().st_size for f in txt_files) / (1024 * 1024), 1
                ),
                "rows_structured": 0,
                "rows_deduplicated": 0,
                "parquet_structured_mb": 0.0,
                "parquet_dedup_mb": 0.0,
                "csv_structured_mb": 0.0,
                "csv_dedup_mb": 0.0,
                "skipped_files": 0,
                "status": f"ERROR: {e}",
            }

        all_stats.append(stats)

        if stats["status"] == "ok":
            line = (
                f"{group_name}: {stats['rows_structured']:,} rows "
                f"→ pq {stats['parquet_structured_mb']:.1f}+"
                f"{stats['parquet_dedup_mb']:.1f} MB"
            )
            if args.csv:
                line += (
                    f", csv {stats['csv_structured_mb']:.1f}+"
                    f"{stats['csv_dedup_mb']:.1f} MB"
                )
            logger.info(line)

    # Summary
    elapsed = time.time() - total_start
    total_txt = sum(s["txt_size_mb"] for s in all_stats)
    total_struct_pq = sum(s["parquet_structured_mb"] for s in all_stats)
    total_dedup_pq = sum(s["parquet_dedup_mb"] for s in all_stats)
    total_struct_csv = sum(s["csv_structured_mb"] for s in all_stats)
    total_dedup_csv = sum(s["csv_dedup_mb"] for s in all_stats)
    total_rows = sum(s["rows_structured"] for s in all_stats)
    total_skipped = sum(s.get("skipped_files", 0) for s in all_stats)
    ok_count = sum(1 for s in all_stats if s["status"] == "ok")
    skip_count = sum(1 for s in all_stats if s["status"] == "skipped-exists")
    fail_count = sum(
        1 for s in all_stats if "FAIL" in s["status"] or "ERROR" in s["status"]
    )

    logger.info("=" * 65)
    logger.info("SUMMARY")
    logger.info("=" * 65)
    logger.info(
        "Groups:       %d total (%d ok, %d skipped/resumed, %d failed)",
        len(all_stats), ok_count, skip_count, fail_count,
    )
    logger.info("Total rows:   %s", f"{total_rows:,}")
    if total_skipped:
        logger.info("Skipped files: %d (corrupted/unreadable)", total_skipped)
    logger.info("Input .txt:   %.1f MB (%.1f GB)", total_txt, total_txt / 1024)
    logger.info(
        "Parquet out:  %.1f MB structured + %.1f MB dedup = %.1f MB total",
        total_struct_pq, total_dedup_pq, total_struct_pq + total_dedup_pq,
    )
    if args.csv:
        logger.info(
            "CSV out:      %.1f MB structured + %.1f MB dedup = %.1f MB total",
            total_struct_csv, total_dedup_csv, total_struct_csv + total_dedup_csv,
        )
    if total_txt > 0:
        pq_total = total_struct_pq + total_dedup_pq
        logger.info(
            "Compression:  %.1f%% smaller than .txt (parquet)",
            (1 - pq_total / total_txt) * 100,
        )
    if output_base:
        logger.info("Output dir:   %s", output_base)
    logger.info(
        "Elapsed:      %.1f sec (%.0f rows/sec)",
        elapsed, total_rows / max(elapsed, 0.01),
    )
    logger.info("=" * 65)

    if fail_count:
        logger.error(
            "%d groups had failures — originals NOT deleted for those groups",
            fail_count,
        )
        sys.exit(1)


if __name__ == "__main__":
    main()
