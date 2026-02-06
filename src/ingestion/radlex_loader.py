"""
RadLex Knowledge Base Loader - Medical Terminology Ingestion

Parses RSNA RadReport templates containing RadLex ontology terms.
Standardizes medical imaging terminology for the Hardware Agent.

Template Format: HTML with embedded XML containing RadLex coding:
    <coding_scheme name="RadLex" designator="2.16.840.1.113883.6.256" />
    <term>
        <code meaning="brain" value="RID6434" scheme="RadLex">
    </term>

Author: Thesis Project - Agentic Infra Co-Pilot
"""

import re
from pathlib import Path
from typing import List, Dict, Any, Optional, Set
from pydantic import BaseModel, Field
from langchain_core.documents import Document
from bs4 import BeautifulSoup
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class RadLexTerm(BaseModel):
    """RadLex ontology term."""
    code: str = Field(description="RadLex identifier (e.g., RID6434)")
    meaning: str = Field(description="Human-readable meaning (e.g., 'brain')")
    scheme: str = Field(default="RadLex", description="Coding scheme")


class TemplateField(BaseModel):
    """Field from a radiology report template."""
    field_id: str
    field_name: str
    default_value: Optional[str] = None
    radlex_terms: List[RadLexTerm] = Field(default_factory=list)


class ExaminationTemplate(BaseModel):
    """Parsed RSNA RadReport template."""
    template_id: str = Field(description="Template identifier from URL")
    title: str = Field(description="Template title (e.g., 'CT Brain')")
    procedure_type: str = Field(description="Imaging modality: CT, MRI, Xray, etc.")
    body_region: str = Field(description="Primary body region")
    description: Optional[str] = None
    publisher: str = Field(default="RSNA")
    language: str = Field(default="en")

    # Template structure
    sections: List[str] = Field(default_factory=list)
    fields: List[TemplateField] = Field(default_factory=list)

    # Ontology terms
    radlex_terms: List[RadLexTerm] = Field(default_factory=list)

    @property
    def all_radlex_codes(self) -> Set[str]:
        """Get all unique RadLex codes in template."""
        codes = {t.code for t in self.radlex_terms}
        for field in self.fields:
            codes.update(t.code for t in field.radlex_terms)
        return codes


class RadLexLoader:
    """
    Loader for RSNA RadReport templates with RadLex terminology.

    Extracts:
    - Template metadata (title, modality, body region)
    - RadLex ontology terms for standardization
    - Report field structure for protocol understanding
    """

    # Modality keywords for classification
    MODALITY_KEYWORDS = {
        'CT': ['ct', 'computed tomography', 'scan'],
        'MRI': ['mri', 'mr ', 'magnetic resonance'],
        'Xray': ['xray', 'x-ray', 'radiograph', 'chest film'],
        'Ultrasound': ['ultrasound', 'us ', 'sonograph'],
        'PET': ['pet', 'positron'],
        'Nuclear': ['nuclear', 'scintigraphy'],
        'Fluoroscopy': ['fluoro', 'fluoroscopy'],
        'Mammography': ['mammo', 'mammograph']
    }

    # Body region keywords
    BODY_REGION_KEYWORDS = {
        'Head': ['head', 'brain', 'skull', 'cranial', 'cerebr'],
        'Neck': ['neck', 'cervical', 'thyroid', 'larynx'],
        'Chest': ['chest', 'thorax', 'lung', 'pulmonary', 'cardiac', 'heart'],
        'Abdomen': ['abdomen', 'abdominal', 'liver', 'kidney', 'pancrea', 'spleen'],
        'Pelvis': ['pelvis', 'pelvic', 'bladder', 'prostate', 'uterus', 'ovary'],
        'Spine': ['spine', 'spinal', 'lumbar', 'thoracic', 'vertebr'],
        'Extremity': ['extremity', 'arm', 'leg', 'hand', 'foot', 'ankle', 'wrist', 'knee', 'hip', 'shoulder'],
        'Whole Body': ['whole body', 'total body', 'bone survey']
    }

    def __init__(self, template_dir: str = "data/raw/siemens/examination/RSNA-RAD-REPORT"):
        """
        Initialize RadLex loader.

        Args:
            template_dir: Directory containing RSNA RadReport templates
        """
        self.template_dir = Path(template_dir)

    def _extract_modality(self, title: str, content: str) -> str:
        """
        Determine imaging modality from template.

        Args:
            title: Template title
            content: Full template content

        Returns:
            Modality string
        """
        text = f"{title} {content}".lower()

        for modality, keywords in self.MODALITY_KEYWORDS.items():
            if any(kw in text for kw in keywords):
                return modality

        return "Other"

    def _extract_body_region(self, title: str, radlex_terms: List[RadLexTerm]) -> str:
        """
        Determine primary body region from template.

        Args:
            title: Template title
            radlex_terms: Extracted RadLex terms

        Returns:
            Body region string
        """
        text = title.lower()

        # Check title first
        for region, keywords in self.BODY_REGION_KEYWORDS.items():
            if any(kw in text for kw in keywords):
                return region

        # Check RadLex terms
        term_text = ' '.join(t.meaning.lower() for t in radlex_terms)
        for region, keywords in self.BODY_REGION_KEYWORDS.items():
            if any(kw in term_text for kw in keywords):
                return region

        return "General"

    def _extract_radlex_terms(self, xml_content: str) -> List[RadLexTerm]:
        """
        Extract RadLex terms from template XML.

        Args:
            xml_content: XML string containing term definitions

        Returns:
            List of RadLexTerm objects
        """
        terms = []

        # Pattern for RadLex code elements
        # <code meaning="brain" value="RID6434" scheme="RadLex">
        code_pattern = re.compile(
            r'<code\s+meaning="([^"]+)"\s+value="([^"]+)"\s+scheme="([^"]+)"',
            re.IGNORECASE
        )

        for match in code_pattern.finditer(xml_content):
            meaning = match.group(1)
            value = match.group(2)
            scheme = match.group(3)

            if scheme.lower() == 'radlex' and value.startswith('RID'):
                terms.append(RadLexTerm(
                    code=value,
                    meaning=meaning,
                    scheme=scheme
                ))

        return terms

    def _extract_fields(self, soup: BeautifulSoup) -> List[TemplateField]:
        """
        Extract form fields from template HTML.

        Args:
            soup: BeautifulSoup object of template

        Returns:
            List of TemplateField objects
        """
        fields = []

        # Find input and textarea elements
        for input_elem in soup.find_all(['input', 'textarea']):
            field_id = input_elem.get('id', '')
            field_name = input_elem.get('name', '')
            default_value = input_elem.get('value', '')

            if input_elem.name == 'textarea':
                default_value = input_elem.get_text(strip=True)

            if field_id or field_name:
                fields.append(TemplateField(
                    field_id=field_id,
                    field_name=field_name,
                    default_value=default_value if default_value else None
                ))

        return fields

    def _extract_sections(self, soup: BeautifulSoup) -> List[str]:
        """
        Extract section names from template.

        Args:
            soup: BeautifulSoup object

        Returns:
            List of section names
        """
        sections = []

        for section in soup.find_all('section'):
            section_name = section.get('data-section-name', '')
            if section_name:
                sections.append(section_name)

        return sections

    def parse_template(self, path: Path) -> Optional[ExaminationTemplate]:
        """
        Parse a single RadReport template file.

        Args:
            path: Path to template file

        Returns:
            ExaminationTemplate or None if parse fails
        """
        try:
            with open(path, 'r', encoding='utf-8', errors='replace') as f:
                content = f.read()

            soup = BeautifulSoup(content, 'html.parser')

            # Extract title
            title_meta = soup.find('meta', attrs={'name': 'dcterms.title'})
            title = title_meta.get('content', path.stem) if title_meta else path.stem

            # Extract description
            desc_meta = soup.find('meta', attrs={'name': 'dcterms.description'})
            description = desc_meta.get('content') if desc_meta else None

            # Extract template ID
            id_meta = soup.find('meta', attrs={'name': 'dcterms.identifier'})
            template_id = id_meta.get('content', path.stem) if id_meta else path.stem

            # Extract language
            lang_meta = soup.find('meta', attrs={'name': 'dcterms.language'})
            language = lang_meta.get('content', 'en') if lang_meta else 'en'

            # Extract RadLex terms from script block
            script = soup.find('script', type='text/xml')
            radlex_terms = []
            if script:
                radlex_terms = self._extract_radlex_terms(script.get_text())

            # Extract fields and sections
            fields = self._extract_fields(soup)
            sections = self._extract_sections(soup)

            # Determine modality and body region
            procedure_type = self._extract_modality(title, content)
            body_region = self._extract_body_region(title, radlex_terms)

            return ExaminationTemplate(
                template_id=template_id,
                title=title,
                procedure_type=procedure_type,
                body_region=body_region,
                description=description,
                language=language,
                sections=sections,
                fields=fields,
                radlex_terms=radlex_terms
            )

        except Exception as e:
            logger.warning(f"Failed to parse template {path.name}: {e}")
            return None

    def build_terminology_index(self) -> Dict[str, RadLexTerm]:
        """
        Build index of all RadLex terms across templates.

        Returns:
            Dictionary mapping code to RadLexTerm
        """
        index = {}

        for template_file in self.template_dir.glob("*.txt"):
            template = self.parse_template(template_file)
            if template:
                for term in template.radlex_terms:
                    index[term.code] = term

        logger.info(f"Built terminology index with {len(index)} unique RadLex terms")
        return index

    def to_documents(self, templates: List[ExaminationTemplate]) -> List[Document]:
        """
        Convert templates to LangChain Documents.

        Args:
            templates: List of parsed templates

        Returns:
            List of Document objects
        """
        documents = []

        for template in templates:
            # Build document content
            text_parts = [
                f"Medical Imaging Protocol: {template.title}",
                f"Modality: {template.procedure_type}",
                f"Body Region: {template.body_region}",
            ]

            if template.description:
                text_parts.append(f"Description: {template.description}")

            if template.sections:
                text_parts.append(f"Report Sections: {', '.join(template.sections)}")

            if template.radlex_terms:
                term_text = ', '.join(
                    f"{t.meaning} ({t.code})" for t in template.radlex_terms[:10]
                )
                text_parts.append(f"Key Medical Terms: {term_text}")

            if template.fields:
                field_names = [f.field_name for f in template.fields if f.field_name][:10]
                text_parts.append(f"Report Fields: {', '.join(field_names)}")

            doc = Document(
                page_content='\n'.join(text_parts),
                metadata={
                    'source': 'rsna_radreport',
                    'template_id': template.template_id,
                    'title': template.title,
                    'procedure_type': template.procedure_type,
                    'body_region': template.body_region,
                    'language': template.language,
                    'radlex_count': len(template.radlex_terms),
                    'data_type': 'protocol_template'
                }
            )
            documents.append(doc)

        logger.info(f"Created {len(documents)} Documents from templates")
        return documents

    def load(self) -> List[Document]:
        """
        Load all templates and convert to Documents.

        Returns:
            List of Document objects
        """
        logger.info(f"Loading RadLex templates from {self.template_dir}")

        if not self.template_dir.exists():
            logger.warning(f"Template directory not found: {self.template_dir}")
            return []

        template_files = list(self.template_dir.glob("*.txt"))
        logger.info(f"Found {len(template_files)} template files")

        templates = []
        for template_file in template_files:
            template = self.parse_template(template_file)
            if template:
                templates.append(template)

        logger.info(f"Successfully parsed {len(templates)} templates")
        return self.to_documents(templates)

    def get_modality_summary(self) -> Dict[str, int]:
        """
        Get summary of templates by modality.

        Returns:
            Dictionary of modality -> count
        """
        summary: Dict[str, int] = {}

        for template_file in self.template_dir.glob("*.txt"):
            template = self.parse_template(template_file)
            if template:
                modality = template.procedure_type
                summary[modality] = summary.get(modality, 0) + 1

        return summary


def main():
    """Test the RadLex loader."""
    logger.info("=" * 60)
    logger.info("Testing RadLex Knowledge Base Loader")
    logger.info("=" * 60)

    loader = RadLexLoader()

    # Load all templates
    documents = loader.load()
    logger.info(f"\nLoaded {len(documents)} documents")

    # Show modality summary
    summary = loader.get_modality_summary()
    logger.info("\nModality Summary:")
    for modality, count in sorted(summary.items(), key=lambda x: -x[1]):
        logger.info(f"  {modality}: {count}")

    # Build terminology index
    term_index = loader.build_terminology_index()
    logger.info(f"\nUnique RadLex terms: {len(term_index)}")

    # Show example document
    if documents:
        logger.info("\n" + "=" * 60)
        logger.info("Example Document:")
        logger.info("=" * 60)
        print(f"\nContent:\n{documents[0].page_content}")
        print(f"\nMetadata: {documents[0].metadata}")

        # Show MRI-specific documents
        mri_docs = [d for d in documents if d.metadata.get('procedure_type') == 'MRI']
        logger.info(f"\nMRI-specific templates: {len(mri_docs)}")

        if mri_docs:
            logger.info("\nExample MRI template:")
            print(mri_docs[0].page_content)

    logger.info("\n" + "=" * 60)
    logger.info("RadLex loader test complete")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
