"""
Lazy Parquet Loader - Memory-efficient event log loading using Polars

Scans per-customer directories under data/raw/siemens/eventlog_txt/mr*/
Each customer directory contains:
  - mr{id}_deduplicated.parquet  (event log data)
  - mr{id}_sources.csv           (event source distribution)
  - mr{id}_summary.csv           (pre-computed event summaries)

Uses Polars lazy frames to keep memory under control for 1.4GB+ of data.
Never collects full datasets; always filters + limits before materializing.

Author: Thesis Project - Agentic Infra Co-Pilot
"""

import logging
from pathlib import Path
from typing import List, Optional, Dict, Any

import pandas as pd

try:
    import polars as pl
except ImportError:
    pl = None

logger = logging.getLogger(__name__)


class LazyParquetLoader:
    """Memory-efficient Parquet event log loading using Polars lazy frames."""

    def __init__(self, parquet_dir: str = "data/raw/siemens/eventlog_txt"):
        self.parquet_dir = Path(parquet_dir)
        if not self.parquet_dir.exists():
            logger.warning(f"Parquet directory not found: {self.parquet_dir}")

        if pl is None:
            raise ImportError("Polars is required. Install with: pip install polars")

    def list_customers(self) -> List[str]:
        """List all customer IDs from directory names."""
        if not self.parquet_dir.exists():
            return []
        return sorted([
            d.name for d in self.parquet_dir.iterdir()
            if d.is_dir() and d.name.startswith('mr')
        ])

    def has_parquet(self, customer_id: str) -> bool:
        """Check if a customer has a deduplicated parquet file."""
        parquet_path = self.parquet_dir / customer_id / f"{customer_id}_deduplicated.parquet"
        return parquet_path.exists()

    def scan_customer(self, customer_id: str) -> Optional[pl.LazyFrame]:
        """Create a lazy scan of a single customer's parquet file."""
        parquet_path = self.parquet_dir / customer_id / f"{customer_id}_deduplicated.parquet"
        if not parquet_path.exists():
            logger.warning(f"Parquet not found for {customer_id}: {parquet_path}")
            return None

        try:
            return pl.scan_parquet(str(parquet_path))
        except Exception as e:
            logger.error(f"Failed to scan {parquet_path}: {e}")
            return None

    def scan_all(self) -> Optional[pl.LazyFrame]:
        """
        Create a lazy scan across ALL customer parquet files.

        WARNING: Collecting this without filters will use significant memory.
        Always apply filters before .collect().
        """
        parquet_files = sorted(self.parquet_dir.glob("mr*/mr*_deduplicated.parquet"))
        if not parquet_files:
            logger.warning("No parquet files found")
            return None

        try:
            frames = []
            for pf in parquet_files:
                customer_id = pf.parent.name
                lf = pl.scan_parquet(str(pf)).with_columns(
                    pl.lit(customer_id).alias("customer_id")
                )
                frames.append(lf)

            return pl.concat(frames)
        except Exception as e:
            logger.error(f"Failed to scan parquet files: {e}")
            return None

    def query_events_for_customer(
        self,
        customer_id: str,
        severity: Optional[str] = None,
        source_filter: Optional[str] = None,
        limit: int = 1000
    ) -> Optional[pl.DataFrame]:
        """
        Query events for a specific customer with optional filters.

        Args:
            customer_id: Customer ID (e.g., 'mr200103')
            severity: Filter by level: 'E' (error), 'W' (warning), 'I' (info)
            source_filter: Filter by source containing this string
            limit: Max rows to return

        Returns:
            DataFrame with matching events, or None if no data
        """
        lf = self.scan_customer(customer_id)
        if lf is None:
            return None

        try:
            if severity:
                lf = lf.filter(pl.col("level") == severity)

            if source_filter:
                lf = lf.filter(pl.col("source").str.contains(source_filter, literal=False))

            return lf.head(limit).collect()
        except Exception as e:
            logger.error(f"Query failed for {customer_id}: {e}")
            return None

    def find_dicom_errors(
        self,
        customer_id: Optional[str] = None,
        limit: int = 500
    ) -> Optional[pl.DataFrame]:
        """
        Find events mentioning DICOM, SOP, transfer syntax, or UID.

        Args:
            customer_id: Specific customer, or None for all customers
            limit: Max rows to return
        """
        if customer_id:
            lf = self.scan_customer(customer_id)
        else:
            lf = self.scan_all()

        if lf is None:
            return None

        dicom_pattern = r"(?i)(dicom|sop|transfer.?syntax|uid|association|pacs|storage.?commit)"

        try:
            return (
                lf
                .filter(pl.col("masked_description").str.contains(dicom_pattern, literal=False))
                .head(limit)
                .collect()
            )
        except Exception as e:
            logger.error(f"DICOM error search failed: {e}")
            return None

    def get_error_summary(self, customer_id: str) -> Dict[str, Any]:
        """
        Get aggregated error counts for a customer.

        Prefers loading from pre-computed *_summary.csv when available,
        falling back to scanning the parquet file.
        """
        summary_path = self.parquet_dir / customer_id / f"{customer_id}_summary.csv"
        if summary_path.exists():
            try:
                df = pd.read_csv(summary_path)
                total_events = len(df)
                error_rows = df[df['level'] == 'E'] if 'level' in df.columns else pd.DataFrame()
                warning_rows = df[df['level'] == 'W'] if 'level' in df.columns else pd.DataFrame()

                return {
                    'customer_id': customer_id,
                    'source': 'summary_csv',
                    'total_unique_patterns': total_events,
                    'error_patterns': len(error_rows),
                    'warning_patterns': len(warning_rows),
                    'top_errors': (
                        error_rows.nlargest(10, 'occurrence_count')[
                            ['source', 'event_id', 'masked_description', 'occurrence_count']
                        ].to_dict('records')
                        if not error_rows.empty else []
                    ),
                }
            except Exception as e:
                logger.warning(f"Failed to load summary CSV for {customer_id}: {e}")

        # Fallback: scan parquet
        lf = self.scan_customer(customer_id)
        if lf is None:
            return {'customer_id': customer_id, 'source': 'not_found'}

        try:
            error_df = (
                lf
                .filter(pl.col("level") == "E")
                .group_by(["source", "event_id"])
                .agg(pl.col("occurrence_count").sum())
                .sort("occurrence_count", descending=True)
                .head(10)
                .collect()
            )
            return {
                'customer_id': customer_id,
                'source': 'parquet_scan',
                'top_errors': error_df.to_dicts(),
            }
        except Exception as e:
            logger.error(f"Error summary scan failed for {customer_id}: {e}")
            return {'customer_id': customer_id, 'source': 'error', 'error': str(e)}

    def get_source_distribution(self, customer_id: str) -> Optional[pd.DataFrame]:
        """Load the event source distribution from *_sources.csv."""
        sources_path = self.parquet_dir / customer_id / f"{customer_id}_sources.csv"
        if not sources_path.exists():
            return None
        try:
            return pd.read_csv(sources_path)
        except Exception as e:
            logger.error(f"Failed to load sources for {customer_id}: {e}")
            return None

    def get_temporal_patterns(
        self,
        customer_id: str,
        time_column: str = "timestamp",
        limit: int = 1000
    ) -> Optional[pl.DataFrame]:
        """
        Detect temporal clustering of error events.

        Groups errors by hour to find peak error periods.
        """
        lf = self.scan_customer(customer_id)
        if lf is None:
            return None

        try:
            # Get column names to check what's available
            schema = lf.collect_schema()
            columns = schema.names()

            if time_column not in columns:
                # Try common alternatives
                for alt in ['date', 'time', 'event_time', 'log_time']:
                    if alt in columns:
                        time_column = alt
                        break
                else:
                    logger.warning(f"No time column found for {customer_id}. Columns: {columns}")
                    return None

            result = (
                lf
                .filter(pl.col("level") == "E")
                .select([time_column, "source", "event_id", "occurrence_count"])
                .head(limit)
                .collect()
            )
            return result
        except Exception as e:
            logger.error(f"Temporal pattern query failed for {customer_id}: {e}")
            return None

    def get_customer_overview(self) -> Optional[pd.DataFrame]:
        """Load the master all_customers_overview.csv."""
        overview_path = self.parquet_dir / "all_customers_overview.csv"
        if not overview_path.exists():
            logger.warning(f"Overview not found: {overview_path}")
            return None
        try:
            return pd.read_csv(overview_path)
        except Exception as e:
            logger.error(f"Failed to load overview: {e}")
            return None

    def get_parquet_schema(self, customer_id: str) -> Optional[Dict[str, str]]:
        """Get the schema (column names and types) of a customer's parquet file."""
        lf = self.scan_customer(customer_id)
        if lf is None:
            return None
        try:
            schema = lf.collect_schema()
            return {name: str(dtype) for name, dtype in schema.items()}
        except Exception as e:
            logger.error(f"Schema read failed for {customer_id}: {e}")
            return None

    def get_stats(self) -> Dict[str, Any]:
        """Get overall statistics about available data."""
        customers = self.list_customers()
        customers_with_parquet = [c for c in customers if self.has_parquet(c)]

        overview = self.get_customer_overview()
        total_events = 0
        total_errors = 0
        if overview is not None:
            total_events = int(overview['total_events'].sum())
            total_errors = int(overview['errors'].sum())

        return {
            'total_customers': len(customers),
            'customers_with_parquet': len(customers_with_parquet),
            'customers_missing_parquet': [c for c in customers if not self.has_parquet(c)],
            'total_events': total_events,
            'total_errors': total_errors,
        }
