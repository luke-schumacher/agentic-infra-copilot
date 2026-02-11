"""
MRRT Questionnaire Parser

Parses MRRT questionnaire data (from CSV or PDF) to extract institution profiles.
The primary input is the already-parsed sample_processed_long_format.csv which
contains structured questionnaire responses.

For PDFs, falls back to PyPDFLoader text extraction.

Author: Thesis Project - Agentic Infra Co-Pilot
"""

import logging
from pathlib import Path
from typing import List, Dict, Any, Optional

import pandas as pd

logger = logging.getLogger(__name__)


class MRRTQuestionnaireParser:
    """Parse MRRT questionnaire data to extract institution profiles."""

    def __init__(self, raw_siemens_dir: str = "data/raw/siemens"):
        self.raw_dir = Path(raw_siemens_dir)
        self.long_format_path = self.raw_dir / "sample_processed_long_format.csv"
        self.wide_format_path = self.raw_dir / "sample_processed_wide_format.csv"
        self.questionnaire_dir = self.raw_dir / "RT_Study_MTTI"

    def load_long_format(self) -> Optional[pd.DataFrame]:
        """Load the pre-parsed long format questionnaire data."""
        if not self.long_format_path.exists():
            logger.warning(f"Long format CSV not found: {self.long_format_path}")
            return None
        return pd.read_csv(self.long_format_path)

    def build_institution_profiles(self) -> pd.DataFrame:
        """
        Build institution profiles from questionnaire data.

        Returns a DataFrame with one row per institution containing:
        - Basic info: name, country, type
        - Equipment: MRI models, LINAC count
        - Workload: patients/year, % MR planning
        - Pain points: from questionnaire responses
        """
        long_df = self.load_long_format()
        if long_df is None or long_df.empty:
            logger.warning("No questionnaire data available")
            return pd.DataFrame()

        profiles = []

        for response_id in long_df['response_id'].unique():
            resp = long_df[long_df['response_id'] == response_id]

            profile = {
                'response_id': response_id,
                'institution_name': resp['institution_name'].iloc[0],
                'country': resp['country'].iloc[0],
                'interviewer': resp['interviewer'].iloc[0],
                'interview_date': resp['interview_date'].iloc[0],
            }

            # Extract key fields by field_name
            field_map = dict(zip(resp['field_name'], resp['response_value']))
            text_map = dict(zip(resp['field_name'], resp['response_text']))

            # Organization type
            profile['org_type'] = field_map.get('org_type', '')
            profile['institution_type'] = self._classify_institution(
                field_map.get('org_type', '')
            )

            # Equipment
            profile['num_linacs'] = self._safe_int(field_map.get('num_linacs', ''))
            profile['num_ct_simulators'] = self._safe_int(field_map.get('num_ct_simulators', ''))
            profile['has_dedicated_mr'] = field_map.get('dedicated_mr', '')
            profile['mr_vendor_1'] = text_map.get('mr_vendor_1', '')
            profile['mr_model_1'] = text_map.get('mr_model_1', '')
            profile['mr_vendor_2'] = text_map.get('mr_vendor_2', '')
            profile['mr_model_2'] = text_map.get('mr_model_2', '')

            # Workload
            profile['patients_per_year'] = field_map.get('patients_per_year', '')
            profile['pct_mr_planning'] = self._safe_float(
                field_map.get('pct_mr_planning', '')
            )

            # Network status
            profile['network_type'] = field_map.get('network_type', '')

            # Clinical sites treated
            treating_fields = resp[resp['field_name'].str.endswith('_treating')]
            treated_sites = treating_fields[
                treating_fields['response_value'] == 'true'
            ]['field_name'].tolist()
            profile['clinical_sites_treated'] = ', '.join(
                s.replace('_treating', '') for s in treated_sites
            )
            profile['num_clinical_sites'] = len(treated_sites)

            # Pain points (from pain_points section if available)
            pain_section = resp[resp['section'] == 'pain_points']
            if not pain_section.empty:
                pain_texts = pain_section['response_text'].dropna().tolist()
                pain_values = pain_section['response_value'].dropna().tolist()
                profile['pain_points'] = '; '.join(
                    [t for t in pain_texts + pain_values if t and str(t).strip()]
                )
            else:
                profile['pain_points'] = ''

            profiles.append(profile)

        df = pd.DataFrame(profiles)
        logger.info(f"Built {len(df)} institution profiles")
        return df

    def export_profiles(self, output_path: str = "data/processed/governance/institution_profiles.csv") -> int:
        """Export institution profiles to CSV."""
        output = Path(output_path)
        output.parent.mkdir(parents=True, exist_ok=True)

        profiles_df = self.build_institution_profiles()
        if profiles_df.empty:
            logger.warning("No profiles to export")
            return 0

        profiles_df.to_csv(output, index=False, encoding='utf-8')
        logger.info(f"Exported {len(profiles_df)} profiles to {output}")
        return len(profiles_df)

    def get_scanner_models(self) -> List[Dict[str, str]]:
        """Extract all MRI scanner models mentioned in questionnaires."""
        profiles = self.build_institution_profiles()
        if profiles.empty:
            return []

        models = []
        for _, row in profiles.iterrows():
            if row.get('mr_model_1'):
                models.append({
                    'institution': row['institution_name'],
                    'vendor': row.get('mr_vendor_1', ''),
                    'model': row['mr_model_1'],
                })
            if row.get('mr_model_2'):
                models.append({
                    'institution': row['institution_name'],
                    'vendor': row.get('mr_vendor_2', ''),
                    'model': row['mr_model_2'],
                })
        return models

    @staticmethod
    def _classify_institution(org_type: str) -> str:
        """Classify institution type from organization type string."""
        if not org_type:
            return 'unknown'
        org_lower = str(org_type).lower()
        if 'academic' in org_lower or 'university' in org_lower:
            return 'academic'
        elif 'private' in org_lower:
            return 'private'
        elif 'cancer' in org_lower:
            return 'cancer_center'
        elif 'public' in org_lower:
            return 'public'
        return 'other'

    @staticmethod
    def _safe_int(val: str) -> Optional[int]:
        """Safely convert to int."""
        try:
            return int(val)
        except (ValueError, TypeError):
            return None

    @staticmethod
    def _safe_float(val: str) -> Optional[float]:
        """Safely convert to float."""
        try:
            return float(val)
        except (ValueError, TypeError):
            return None
