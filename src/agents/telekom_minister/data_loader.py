"""
Telekom Minister Data Loader

Processes Telekom infrastructure documentation for RAG-based querying:
- ETSI standards (PDF)
- Service Level Agreements (SLAs) - CSV
- Network Intent policies - CSV
- OCPP protocol reference data - CSV
- Fault-SLA mappings - CSV
- Troubleshooting procedures

Migrated from src/ingestion/telekom_loader.py for agent-specific ownership.

Author: Thesis Project - Agentic Infra Co-Pilot
"""

import pandas as pd
from pathlib import Path
from typing import List
import logging
from langchain_core.documents import Document
from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class TelekomLoader:
    """Loads and chunks Telekom PDF documentation for the Minister agent."""

    def __init__(
        self,
        pdf_dir: str = "data/raw/telekom",
        chunk_size: int = 1000,
        chunk_overlap: int = 200
    ):
        """
        Initialize the Telekom loader.

        Args:
            pdf_dir: Directory containing Telekom PDF files
            chunk_size: Size of text chunks in characters
            chunk_overlap: Overlap between chunks in characters
        """
        self.pdf_dir = Path(pdf_dir)
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    def load(self) -> List[Document]:
        """
        Load all PDF files from the Telekom directory and split into chunks.

        Returns:
            List of LangChain Documents with chunked text
        """
        logger.info(f"Loading Telekom PDFs from {self.pdf_dir}")

        if not self.pdf_dir.exists():
            logger.warning(f"Directory not found: {self.pdf_dir}. Creating it.")
            self.pdf_dir.mkdir(parents=True, exist_ok=True)
            logger.warning("Directory created but no PDFs found. Returning empty list.")
            return []

        # Find all PDF files
        pdf_files = list(self.pdf_dir.glob("*.pdf"))

        if not pdf_files:
            logger.warning(f"No PDF files found in {self.pdf_dir}")
            return []

        logger.info(f"Found {len(pdf_files)} PDF files to process")

        all_documents = []

        # Initialize text splitter
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=self.chunk_size,
            chunk_overlap=self.chunk_overlap,
            length_function=len,
            separators=["\n\n", "\n", ". ", " ", ""]
        )

        # Process each PDF
        for pdf_file in pdf_files:
            try:
                logger.info(f"Processing: {pdf_file.name}")

                # Load PDF using LangChain PyPDFLoader
                loader = PyPDFLoader(str(pdf_file))
                documents = loader.load()

                logger.info(f"  Loaded {len(documents)} pages from {pdf_file.name}")

                # Split documents into chunks
                chunks = text_splitter.split_documents(documents)

                logger.info(f"  Created {len(chunks)} chunks")

                # Enhance metadata for Minister-specific context
                for chunk in chunks:
                    chunk.metadata.update({
                        'source_type': 'telekom_documentation',
                        'data_type': 'network_intent',
                        'file_name': pdf_file.name,
                        'content_type': 'pdf_document',
                        'agent': 'telekom_minister'
                    })

                all_documents.extend(chunks)

            except Exception as e:
                logger.error(f"Error processing {pdf_file.name}: {str(e)}")
                continue

        logger.info(f"Total documents created: {len(all_documents)}")
        return all_documents

    def load_single_pdf(self, pdf_path: str) -> List[Document]:
        """
        Load a single PDF file and split into chunks.

        Args:
            pdf_path: Path to a specific PDF file

        Returns:
            List of LangChain Documents
        """
        pdf_file = Path(pdf_path)

        if not pdf_file.exists():
            logger.error(f"PDF file not found: {pdf_path}")
            raise FileNotFoundError(f"PDF file not found: {pdf_path}")

        logger.info(f"Loading single PDF: {pdf_file.name}")

        # Load PDF
        loader = PyPDFLoader(str(pdf_file))
        documents = loader.load()

        logger.info(f"Loaded {len(documents)} pages")

        # Split into chunks
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=self.chunk_size,
            chunk_overlap=self.chunk_overlap,
            length_function=len,
            separators=["\n\n", "\n", ". ", " ", ""]
        )

        chunks = text_splitter.split_documents(documents)

        logger.info(f"Created {len(chunks)} chunks")

        # Enhance metadata
        for chunk in chunks:
            chunk.metadata.update({
                'source_type': 'telekom_documentation',
                'data_type': 'network_intent',
                'file_name': pdf_file.name,
                'content_type': 'pdf_document',
                'agent': 'telekom_minister'
            })

        return chunks

    def load_sla_definitions(self) -> List[Document]:
        """
        Load SLA definitions from CSV.

        Returns:
            List of Documents with SLA information
        """
        csv_path = self.pdf_dir / "processed" / "sla_definitions.csv"

        if not csv_path.exists():
            logger.warning(f"SLA definitions not found: {csv_path}")
            return []

        logger.info(f"Loading SLA definitions: {csv_path}")

        try:
            df = pd.read_csv(csv_path, encoding='utf-8')
            documents = []

            for _, row in df.iterrows():
                text = (
                    f"SLA Code: {row['sla_code']}\n"
                    f"Name: {row['sla_name']}\n"
                    f"Category: {row['category']}\n"
                    f"Threshold: {row['threshold_value']} {row['threshold_unit']}\n"
                    f"Severity: {row['severity']}\n"
                    f"Description: {row['description']}\n"
                    f"Violation Action: {row['violation_action']}\n"
                    f"Applicable Stations: {row['applicable_stations']}"
                )

                doc = Document(
                    page_content=text,
                    metadata={
                        'source_type': 'sla_definition',
                        'data_type': 'sla',
                        'sla_code': row['sla_code'],
                        'category': row['category'],
                        'severity': row['severity'],
                        'file_name': csv_path.name,
                        'agent': 'telekom_minister'
                    }
                )
                documents.append(doc)

            logger.info(f"Loaded {len(documents)} SLA definitions")
            return documents

        except Exception as e:
            logger.error(f"Error loading SLA definitions: {str(e)}")
            return []

    def load_fault_sla_mapping(self) -> List[Document]:
        """
        Load fault-to-SLA mappings from CSV.

        Returns:
            List of Documents with fault-SLA relationships
        """
        csv_path = self.pdf_dir / "processed" / "fault_sla_mapping.csv"

        if not csv_path.exists():
            logger.warning(f"Fault-SLA mapping not found: {csv_path}")
            return []

        logger.info(f"Loading fault-SLA mappings: {csv_path}")

        try:
            df = pd.read_csv(csv_path, encoding='utf-8')
            documents = []

            for _, row in df.iterrows():
                text = (
                    f"Fault Code: {row['fault_code']}\n"
                    f"Fault Name: {row['fault_name']}\n"
                    f"Category: {row['fault_category']}\n"
                    f"Related SLAs: {row['related_sla_codes']}\n"
                    f"Risk Level: {row['risk_level']}\n"
                    f"Typical Cause: {row['typical_cause']}\n"
                    f"Detection Method: {row['detection_method']}\n"
                    f"Auto Remediation: {row['auto_remediation']}\n"
                    f"Manual Intervention Required: {row['manual_intervention_required']}"
                )

                doc = Document(
                    page_content=text,
                    metadata={
                        'source_type': 'fault_sla_mapping',
                        'data_type': 'fault_mapping',
                        'fault_code': row['fault_code'],
                        'risk_level': row['risk_level'],
                        'related_slas': row['related_sla_codes'],
                        'file_name': csv_path.name,
                        'agent': 'telekom_minister'
                    }
                )
                documents.append(doc)

            logger.info(f"Loaded {len(documents)} fault-SLA mappings")
            return documents

        except Exception as e:
            logger.error(f"Error loading fault-SLA mappings: {str(e)}")
            return []

    def load_network_intent_policies(self) -> List[Document]:
        """
        Load network intent policies from CSV.

        Returns:
            List of Documents with intent policies
        """
        csv_path = self.pdf_dir / "processed" / "network_intent_policies.csv"

        if not csv_path.exists():
            logger.warning(f"Network intent policies not found: {csv_path}")
            return []

        logger.info(f"Loading network intent policies: {csv_path}")

        try:
            df = pd.read_csv(csv_path, encoding='utf-8')
            documents = []

            for _, row in df.iterrows():
                text = (
                    f"Intent ID: {row['intent_id']}\n"
                    f"Name: {row['intent_name']}\n"
                    f"Type: {row['intent_type']}\n"
                    f"Priority: {row['priority']}\n"
                    f"Condition: {row['condition']}\n"
                    f"Action: {row['action']}\n"
                    f"Target Components: {row['target_components']}\n"
                    f"Enforcement Level: {row['enforcement_level']}\n"
                    f"Description: {row['description']}"
                )

                doc = Document(
                    page_content=text,
                    metadata={
                        'source_type': 'network_intent',
                        'data_type': 'intent_policy',
                        'intent_id': row['intent_id'],
                        'intent_type': row['intent_type'],
                        'priority': row['priority'],
                        'enforcement_level': row['enforcement_level'],
                        'file_name': csv_path.name,
                        'agent': 'telekom_minister'
                    }
                )
                documents.append(doc)

            logger.info(f"Loaded {len(documents)} intent policies")
            return documents

        except Exception as e:
            logger.error(f"Error loading intent policies: {str(e)}")
            return []

    def load_ocpp_reference_data(self) -> List[Document]:
        """
        Load OCPP protocol reference data from CSVs.

        Returns:
            List of Documents with OCPP reference information
        """
        processed_dir = self.pdf_dir / "processed"

        if not processed_dir.exists():
            logger.warning(f"Processed directory not found: {processed_dir}")
            return []

        documents = []

        # Load security events
        security_csv = processed_dir / "security_events.csv"
        if security_csv.exists():
            try:
                df = pd.read_csv(security_csv, encoding='utf-8', sep=';')
                for _, row in df.iterrows():
                    text = (
                        f"OCPP Security Event: {row.get('Security Event', 'Unknown')}\n"
                        f"Description: {row.get('Description', 'No description')}\n"
                        f"Critical: {row.get('Critical', 'Unknown')}"
                    )
                    doc = Document(
                        page_content=text,
                        metadata={
                            'source_type': 'ocpp_reference',
                            'data_type': 'security_event',
                            'event_name': row.get('Security Event', ''),
                            'critical': row.get('Critical', ''),
                            'file_name': security_csv.name,
                            'agent': 'telekom_minister'
                        }
                    )
                    documents.append(doc)
                logger.info(f"Loaded {len(df)} security events")
            except Exception as e:
                logger.warning(f"Error loading security events: {e}")

        # Load reason codes
        reason_csv = processed_dir / "reason_codes.csv"
        if reason_csv.exists():
            try:
                df = pd.read_csv(reason_csv, encoding='utf-8', sep=';')
                for _, row in df.iterrows():
                    if pd.notna(row.get('Reason code')):
                        text = (
                            f"OCPP Reason Code: {row.get('Reason code', '')}\n"
                            f"Group: {row.get('Group', 'General')}\n"
                            f"Description: {row.get('Description', 'No description')}\n"
                            f"Used For: {row.get('Typically used for', 'Various')}"
                        )
                        doc = Document(
                            page_content=text,
                            metadata={
                                'source_type': 'ocpp_reference',
                                'data_type': 'reason_code',
                                'reason_code': row.get('Reason code', ''),
                                'group': row.get('Group', ''),
                                'file_name': reason_csv.name,
                                'agent': 'telekom_minister'
                            }
                        )
                        documents.append(doc)
                logger.info(f"Loaded reason codes from {reason_csv.name}")
            except Exception as e:
                logger.warning(f"Error loading reason codes: {e}")

        # Load components
        components_csv = processed_dir / "components.csv"
        if components_csv.exists():
            try:
                df = pd.read_csv(components_csv, encoding='utf-8', sep=';')
                for _, row in df.iterrows():
                    component = row.get('Component', '')
                    if pd.notna(component) and component.strip():
                        text = (
                            f"OCPP Component: {component}\n"
                            f"Description: {row.get('Description', 'No description')}"
                        )
                        doc = Document(
                            page_content=text,
                            metadata={
                                'source_type': 'ocpp_reference',
                                'data_type': 'component',
                                'component_name': component,
                                'file_name': components_csv.name,
                                'agent': 'telekom_minister'
                            }
                        )
                        documents.append(doc)
                logger.info(f"Loaded components from {components_csv.name}")
            except Exception as e:
                logger.warning(f"Error loading components: {e}")

        # Load cross-domain fault resolution guide
        cross_domain_csv = processed_dir / "cross_domain_fault_resolution.csv"
        if cross_domain_csv.exists():
            try:
                df = pd.read_csv(cross_domain_csv, encoding='utf-8')
                for _, row in df.iterrows():
                    text = (
                        f"Cross-Domain Resolution: {row['resolution_id']}\n"
                        f"Fault Scenario: {row['fault_scenario']}\n"
                        f"Primary Domain: {row['primary_domain']}\n"
                        f"Secondary Domains: {row['secondary_domains']}\n"
                        f"Telekom Assessment: {row['telekom_assessment']}\n"
                        f"Siemens Diagnosis: {row['siemens_diagnosis']}\n"
                        f"Illigo Findings: {row['illigo_findings']}\n"
                        f"Integrated Resolution: {row['integrated_resolution']}\n"
                        f"SLA Impact: {row['sla_impact']}\n"
                        f"Risk Level: {row['risk_level']}"
                    )
                    doc = Document(
                        page_content=text,
                        metadata={
                            'source_type': 'cross_domain_resolution',
                            'data_type': 'resolution_guide',
                            'resolution_id': row['resolution_id'],
                            'primary_domain': row['primary_domain'],
                            'risk_level': row['risk_level'],
                            'file_name': cross_domain_csv.name,
                            'agent': 'telekom_minister'
                        }
                    )
                    documents.append(doc)
                logger.info(f"Loaded {len(df)} cross-domain resolution guides")
            except Exception as e:
                logger.warning(f"Error loading cross-domain resolutions: {e}")

        logger.info(f"Total OCPP reference documents: {len(documents)}")
        return documents

    def load(self) -> List[Document]:
        """
        Load all Telekom data: PDFs and CSVs.

        Returns:
            List of LangChain Documents
        """
        logger.info(f"Loading Telekom data from {self.pdf_dir}")

        if not self.pdf_dir.exists():
            logger.warning(f"Directory not found: {self.pdf_dir}. Creating it.")
            self.pdf_dir.mkdir(parents=True, exist_ok=True)
            return []

        all_documents = []

        # Load PDF documents (original functionality)
        pdf_docs = self._load_pdfs()
        all_documents.extend(pdf_docs)
        logger.info(f"Loaded {len(pdf_docs)} PDF document chunks")

        # Load SLA definitions
        sla_docs = self.load_sla_definitions()
        all_documents.extend(sla_docs)

        # Load fault-SLA mappings
        fault_docs = self.load_fault_sla_mapping()
        all_documents.extend(fault_docs)

        # Load network intent policies
        intent_docs = self.load_network_intent_policies()
        all_documents.extend(intent_docs)

        # Load OCPP reference data
        ocpp_docs = self.load_ocpp_reference_data()
        all_documents.extend(ocpp_docs)

        logger.info(f"Total documents created: {len(all_documents)}")
        return all_documents

    def _load_pdfs(self) -> List[Document]:
        """
        Load all PDF files from the Telekom directory and split into chunks.

        Returns:
            List of LangChain Documents with chunked text
        """
        # Find all PDF files recursively
        pdf_files = list(self.pdf_dir.glob("**/*.pdf"))

        if not pdf_files:
            logger.warning(f"No PDF files found in {self.pdf_dir}")
            return []

        logger.info(f"Found {len(pdf_files)} PDF files to process")

        all_documents = []

        # Initialize text splitter
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=self.chunk_size,
            chunk_overlap=self.chunk_overlap,
            length_function=len,
            separators=["\n\n", "\n", ". ", " ", ""]
        )

        # Process each PDF
        for pdf_file in pdf_files:
            try:
                logger.info(f"Processing: {pdf_file.name}")

                # Load PDF using LangChain PyPDFLoader
                loader = PyPDFLoader(str(pdf_file))
                documents = loader.load()

                logger.info(f"  Loaded {len(documents)} pages from {pdf_file.name}")

                # Split documents into chunks
                chunks = text_splitter.split_documents(documents)

                logger.info(f"  Created {len(chunks)} chunks")

                # Enhance metadata for Minister-specific context
                for chunk in chunks:
                    chunk.metadata.update({
                        'source_type': 'telekom_documentation',
                        'data_type': 'network_intent',
                        'file_name': pdf_file.name,
                        'content_type': 'pdf_document',
                        'agent': 'telekom_minister'
                    })

                all_documents.extend(chunks)

            except Exception as e:
                logger.error(f"Error processing {pdf_file.name}: {str(e)}")
                continue

        return all_documents


def main():
    """Test the Telekom loader."""
    logger.info("=" * 60)
    logger.info("Testing Telekom Minister Data Loader")
    logger.info("=" * 60)

    try:
        loader = TelekomLoader()
        documents = loader.load()

        logger.info(f"\nSuccessfully loaded {len(documents)} document chunks")

        if not documents:
            logger.warning("\nNo documents were loaded.")
            logger.info("\nTo test with actual data:")
            logger.info("1. Place PDF files in data/raw/telekom/")
            logger.info("2. Run this script again")
        else:
            # Display first chunk as example
            logger.info("\n" + "=" * 60)
            logger.info("EXAMPLE DOCUMENT CHUNK:")
            logger.info("=" * 60)
            print(f"\nContent (first 300 chars):\n{documents[0].page_content[:300]}...\n")
            print(f"Metadata:\n{documents[0].metadata}\n")

        logger.info("\n" + "=" * 60)
        logger.info("Loader test completed!")
        logger.info("=" * 60)

    except Exception as e:
        logger.error(f"Test failed: {str(e)}", exc_info=True)
        raise


if __name__ == "__main__":
    main()
