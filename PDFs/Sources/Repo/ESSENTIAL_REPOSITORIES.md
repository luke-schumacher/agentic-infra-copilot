# Essential Code Repositories for Thesis Research

This document catalogs the essential open-source repositories supporting the thesis research on "Agentic Web Approaches for Automated Fault Diagnosis: A Cross-Domain Technical Case Study."

---

## 1. LLM Agents & Agentic Architectures

### microsoft/graphrag
- **URL**: https://github.com/microsoft/graphrag
- **Description**: Microsoft's official GraphRAG implementation provides a data pipeline and transformation suite that extracts meaningful, structured data from unstructured text using LLMs. It implements a graph-based approach to Retrieval-Augmented Generation (RAG) using knowledge graph memory structures to enhance LLM reasoning capabilities.
- **Thesis Relevance**: **Section 5 (Unified Architecture)** - Core implementation of the Graph RAG framework referenced throughout the thesis. Directly supports the semantic translation and knowledge graph-based middleware concepts.
- **Key Features**:
  - Graph-based RAG system with knowledge graph memory structures
  - Modular architecture for customization and extension
  - CLI interface for initialization and configuration
  - Prompt tuning support for dataset-specific optimization
  - Production-ready with 29.6k GitHub stars
- **Technical Specs**: Python (96.1%), MIT License, Active development with 415 commits
- **BibTeX Key**: `microsoft_graphrag`

### langchain-ai/langgraph
- **URL**: https://github.com/langchain-ai/langgraph
- **Description**: A low-level orchestration framework for constructing, managing, and deploying long-running, stateful agents. Provides durable execution, human-in-the-loop capabilities, and comprehensive memory management for building graph-based workflows with customizable control flow, branching, and subgraph patterns.
- **Thesis Relevance**: **Section 2.2 (Chain-of-Thought Orchestration)** - Demonstrates the agent orchestration patterns and graph-based workflows essential for implementing the "observe → plan → act" cycle described in the fault diagnosis scenario.
- **Key Features**:
  - Durable execution with failure recovery and resume capabilities
  - Human-in-the-loop state inspection and modification
  - Short-term working memory and long-term persistent memory
  - Production-ready deployment infrastructure
  - LangSmith integration for execution tracing and metrics
- **Technical Specs**: Python (99.3%), MIT License, 21.9k stars, 436 releases
- **BibTeX Key**: `langgraph`

### microsoft/autogen
- **URL**: https://github.com/microsoft/autogen
- **Description**: A Microsoft-maintained framework for building multi-agent AI applications capable of autonomous operation or human collaboration. Features event-driven agent design, cross-language support (Python and .NET), and model-agnostic architecture supporting various LLM providers.
- **Thesis Relevance**: **Section 2.2.1 (TM Forum Autonomous Networks Level 4)** - Demonstrates multi-agent collaboration patterns relevant to the "Agent" concept in autonomous network management and the coordination between multiple specialized agents.
- **Key Features**:
  - Multi-agent orchestration with message-passing architecture
  - Event-driven design supporting local and distributed runtimes
  - Cross-language support (Python 3.10+ and .NET/C#)
  - AutoGen Studio GUI for no-code prototyping
  - AgentChat API for rapid high-level development
- **Technical Specs**: Python/.NET, Dual license (CC-BY-4.0/MIT), 52.4k stars
- **BibTeX Key**: `microsoft_autogen`
- **Note**: Maintenance mode - receiving bug fixes but new users directed to Microsoft Agent Framework

---

## 2. ETSI ZSM & Intent-Based Networking

### tmforum-apis
- **URL**: https://github.com/tmforum-apis
- **Description**: GitHub organization maintaining TM Forum Open APIs under Apache 2.0 license, providing open telecommunications standards. Contains 93 repositories including the TMF921 Intent Management API specification referenced extensively in the thesis.
- **Thesis Relevance**: **Section 2.3 (TMF921 Intent Management API)** - Official source for the TMF921 API specification that defines the Intent Management Entity (IME) and intent lifecycle management described in the thesis.
- **Key Features**:
  - 93 repositories covering telecommunications management domains
  - OpenAPI 3.0 specifications for REST APIs
  - TMF921 Intent Management API repository
  - Apache 2.0 license for industry-wide adoption
  - Official TM Forum standard implementations
- **Technical Specs**: JavaScript/Java, OpenAPI 3.0, Apache 2.0 License
- **BibTeX Key**: `tmforum_apis`
- **Key Repository**: TMF921 Intent Management API

---

## 3. Knowledge Graphs & Semantic Interoperability

### RDFLib/rdflib
- **URL**: https://github.com/RDFLib/rdflib
- **Description**: A pure Python package for working with RDF that provides comprehensive tools for semantic web development and knowledge graph operations. Includes parsers/serializers for multiple RDF formats and full SPARQL 1.1 query/update support.
- **Thesis Relevance**: **Section 3.1 (Industrial Knowledge Graph)** - Essential for understanding RDF triple-based representation and SPARQL queries referenced in the fault scenario (Section 6, Phase 3).
- **Key Features**:
  - Parsers and serializers for RDF/XML, N3, NTriples, Turtle, JSON-LD, and more
  - Full SPARQL 1.1 query and update statement support
  - In-memory, persistent Berkeley DB, and remote SPARQL endpoint storage
  - Triple-based RDF representation (Subject-Predicate-Object)
  - Namespace management with built-in vocabularies (FOAF, RDFS, OWL)
- **Technical Specs**: Python (95.9%), Stable release v7.5.0, 189 contributors, 25.7k dependents
- **BibTeX Key**: `rdflib`

### iofoundry/Core
- **URL**: https://github.com/iofoundry/Core
- **Description**: The IOF Core Ontology, the top-level ontology in the Industrial Ontologies Foundry suite. Built on Basic Formal Ontology (BFO) to support digital manufacturing by facilitating cross-system data integration within factories and across enterprises.
- **Thesis Relevance**: **Section 3.1.1 (IKG Ontology and Standards)** - Provides the IOF (Industrial Ontologies Foundry) ontology explicitly referenced in the thesis for semantic mapping of industrial error codes.
- **Key Features**:
  - Based on Basic Formal Ontology (BFO) for logical consistency
  - Developed using first-order logic and OWL 2 (Web Ontology Language)
  - Common mid-level ontology for manufacturing domains
  - Supports cross-system data integration in Industry 4.0
  - Viewable with Protégé open-source tool
- **Technical Specs**: OWL/RDF, Part of OAGi (Open Applications Group)
- **BibTeX Key**: `iof_core`
- **Organization**: https://github.com/iofoundry (7 repositories)

---

## 4. OCPP & Industrial Edge Integration

### mobilityhouse/ocpp
- **URL**: https://github.com/mobilityhouse/ocpp
- **Description**: A Python package implementing the JSON version of the Open Charge Point Protocol (OCPP), enabling communication between EV charging stations and central management systems. Supports OCPP 1.6, 2.0.1 (Edition 2 and Edition 3 errata).
- **Thesis Relevance**: **Section 4 (The Evidence: Illigo/Energy Logs and OCPP 2.0.1)** - Demonstrates practical implementation of OCPP 2.0.1 protocol including the NotifyEventRequest message structure used in the fault scenario.
- **Key Features**:
  - Support for OCPP 1.6, 2.0.1 Edition 2 (2022-12-15), and Edition 3 errata (2024-11)
  - Server and client framework implementations
  - JSON-based protocol implementation
  - Comprehensive documentation on ReadTheDocs
  - Active community with 45 contributors and 217 dependents
- **Technical Specs**: Python (99.5%), MIT License, 969 stars, 30+ releases
- **BibTeX Key**: `mobilityhouse_ocpp`

### gijzelaerr/python-snap7
- **URL**: https://github.com/gijzelaerr/python-snap7
- **Description**: A Python wrapper for Snap7, an open-source, multi-platform Ethernet communication suite for interfacing natively with Siemens S7 PLCs. Enables programmatic access to Siemens S7-300, S7-1200, S7-1500 controllers.
- **Thesis Relevance**: **Section 3.2 (Simatic S7-1500 Web API)** - Provides practical implementation reference for Siemens PLC communication, complementing the JSON-RPC Web API approach described in the thesis.
- **Key Features**:
  - Native communication with Siemens S7 PLCs (S7-300, S7-1200, S7-1500, Vipa)
  - Cross-platform support (Windows, Linux, OS X)
  - Python 3.9+ compatibility
  - Available on PyPI for easy installation
  - Active community with multiple forks for specialized use cases
- **Technical Specs**: Python wrapper for C library, Open source, Tested with Python 3.9+
- **BibTeX Key**: `python_snap7`
- **Alternative**: Can be used alongside or instead of official Siemens Web API

---

## Quick Reference Table

| Repository | Primary Domain | Language | Stars | Status | Thesis Section |
|------------|---------------|----------|-------|--------|---------------|
| microsoft/graphrag | GraphRAG Implementation | Python | 29.6k | Active | Section 5 |
| langchain-ai/langgraph | Agent Orchestration | Python | 21.9k | Active | Section 2.2 |
| microsoft/autogen | Multi-Agent Systems | Python/.NET | 52.4k | Maintenance | Section 2.2.1 |
| tmforum-apis | Intent Management APIs | JavaScript/Java | - | Active | Section 2.3 |
| RDFLib/rdflib | RDF/SPARQL/Knowledge Graphs | Python | - | Active | Section 3.1 |
| iofoundry/Core | Industrial Ontology | OWL/RDF | - | Active | Section 3.1.1 |
| mobilityhouse/ocpp | OCPP 2.0.1 Implementation | Python | 969 | Active | Section 4 |
| gijzelaerr/python-snap7 | Siemens PLC Communication | Python | - | Active | Section 3.2 |

---

## Alternative & Related Repositories

### Other OCPP Implementations:
- **EVerest/libocpp** (C++) - OCA-certified OCPP 2.0.1 implementation
- **c-jimenez/open-ocpp** (C++) - Open source OCPP 1.6 and 2.0.1
- **MrMaydo/OCPP** (Java) - Java implementation of OCPP 2.0.1

### IOF Related:
- **iofoundry/ontology** - Main IOF ontology repository
- **NCOR-US/IOF-BFO** - IOF files with BFO integration

### Additional TM Forum Repositories:
- **TMF620_ProductCatalog** - Product catalog management
- **TMF641_ServiceOrder** - Service order processing API

---

## Usage Notes

**Citation in Thesis:**
When citing these repositories in the thesis, use the BibTeX keys provided in the `refs.bib` file. For example:
- GraphRAG implementation is described in the microsoft/graphrag repository \cite{microsoft_graphrag}.

**Code Examples:**
These repositories can be referenced when explaining implementation details or providing code examples in the thesis appendices.

**Architecture References:**
Repository documentation and architecture diagrams can support the technical explanations in Chapters 2-5.

---

**Last Updated**: December 2025
**Total Repositories**: 8 core + 6 alternatives = 14 repositories documented
