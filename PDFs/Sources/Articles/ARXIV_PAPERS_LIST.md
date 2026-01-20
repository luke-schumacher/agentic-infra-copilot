# arXiv Papers - Download List

This document contains direct download links for essential arXiv papers. All papers are **freely accessible** without registration.

---

## 1. GraphRAG Foundation Paper

**Title:** From Local to Global: A Graph RAG Approach to Query-Focused Summarization

**Authors:** Darren Edge, Ha Trinh, Newman Cheng, Joshua Bradley, Alex Chao, Apurva Mody, Steven Truitt, Jonathan Larson (Microsoft Research)

**arXiv ID:** 2404.16130

**Date:** Submitted April 24, 2024; Updated February 19, 2025

**Abstract:** Proposes GraphRAG, a graph-based approach to question answering over private text corpora. Uses LLMs to build a graph index in two stages: first deriving an entity knowledge graph from source documents, then pregenerating community summaries for groups of closely related entities. For global sensemaking questions over datasets in the 1 million token range, GraphRAG leads to substantial improvements over conventional RAG for both comprehensiveness and diversity of generated answers.

**Download Links:**
- **PDF**: https://arxiv.org/pdf/2404.16130
- **Abstract Page**: https://arxiv.org/abs/2404.16130
- **HTML Version**: https://arxiv.org/html/2404.16130v1

**Save As:** `Edge_2024_GraphRAG.pdf`

**BibTeX Key:** `edge2024graphrag`

**Thesis Reference:** Section 5 (Unified Architecture) - Core reference for GraphRAG implementation

---

## 2. Chain-of-Thought Prompting

**Title:** Chain-of-Thought Prompting Elicits Reasoning in Large Language Models

**Authors:** Jason Wei, Xuezhi Wang, Dale Schuurmans, Maarten Bosma, Brian Ichter, Fei Xia, Ed Chi, Quoc Le, Denny Zhou (Google Research, Brain Team)

**arXiv ID:** 2201.11903

**Date:** Submitted January 28, 2022; Last revised January 10, 2023 (v6)

**Abstract:** Explores how generating a chain of thought (a series of intermediate reasoning steps) significantly improves the ability of large language models to perform complex reasoning. Shows that reasoning abilities emerge naturally in sufficiently large language models via chain of thought prompting, where a few chain of thought demonstrations are provided as exemplars. Experiments show improved performance on arithmetic, commonsense, and symbolic reasoning tasks. For instance, prompting a 540B-parameter model with just eight chain of thought exemplars achieves state-of-the-art accuracy on the GSM8K benchmark.

**Download Links:**
- **PDF**: https://arxiv.org/pdf/2201.11903
- **Abstract Page:** https://arxiv.org/abs/2201.11903
- **HTML Version**: https://ar5iv.labs.arxiv.org/html/2201.11903

**Save As:** `Wei_2022_Chain_of_Thought.pdf`

**BibTeX Key:** `wei2022chain`

**Thesis Reference:** Section 2.2.1 (The "Chain-of-Thought" (CoT) Orchestration) - Foundational paper for CoT reasoning in agent architectures

---

## 3. ReAct: Reasoning and Acting

**Title:** ReAct: Synergizing Reasoning and Acting in Language Models

**Authors:** Shunyu Yao, Jeffrey Zhao, Dian Yu, et al.

**arXiv ID:** 2210.03629

**Date:** Submitted October 6, 2022

**Publication:** Published as a conference paper at ICLR 2023

**Abstract:** Explores the use of LLMs to generate both reasoning traces and task-specific actions in an interleaved manner, allowing for greater synergy between the two. Reasoning traces help the model induce, track, and update action plans as well as handle exceptions, while actions allow it to interface with external sources (knowledge bases or environments) to gather additional information. This approach has become influential in combining reasoning and acting capabilities in large language models.

**Download Links:**
- **PDF**: https://arxiv.org/pdf/2210.03629
- **Abstract Page**: https://arxiv.org/abs/2210.03629
- **HTML Version**: https://ar5iv.labs.arxiv.org/html/2210.03629

**Save As:** `Yao_2023_ReAct.pdf`

**BibTeX Key:** `yao2023react`

**Thesis Reference:** Section 6 (Hypothetical Fault Scenario) - Supports the observe → plan → act cycle in autonomous fault diagnosis

---

## 4. 2025 Multi-Agent Systems Surveys

### A Survey on LLM-based Multi-Agent System: Recent Advances and New Frontiers

**Authors:** Various

**arXiv ID:** 2412.17481

**Date:** Submitted December 23, 2024; Updated January 7, 2025

**Abstract:** Provides comprehensive overview of LLM-based multi-agent systems (LLM-MAS) applications in solving complex tasks, simulating specific scenarios, and evaluating generative agents. Covers recent advances in multi-agent coordination, cooperation, and competition mechanisms. Directly relevant for understanding cross-domain fault diagnosis requiring multiple specialized agents.

**Download Links:**
- **PDF**: https://arxiv.org/pdf/2412.17481
- **Abstract Page**: https://arxiv.org/abs/2412.17481
- **HTML Version**: https://arxiv.org/html/2412.17481v2

**Save As:** `MultiAgent_LLM_Survey_2025.pdf`

**BibTeX Key:** `multi_agent_survey2025`

**Thesis Reference:** Section 2.2.1 (Multi-agent coordination), Section 6 (Fault diagnosis scenario)

---

### Multi-Agent Collaboration Mechanisms: A Survey of LLMs

**Authors:** Various

**arXiv ID:** 2501.06322

**Date:** Submitted January 10, 2025

**Abstract:** Characterizes collaboration mechanisms based on key dimensions: actors, types (cooperation, competition, or coopetition), structures (peer-to-peer, centralized, or distributed), strategies (role-based or model-based), and coordination protocols. Investigates applications across 5G/6G networks, Industry 5.0, question answering, and social settings. Directly addresses the thesis's cross-domain coordination needs.

**Download Links:**
- **PDF**: https://arxiv.org/pdf/2501.06322
- **Abstract Page**: https://arxiv.org/abs/2501.06322
- **HTML Version**: https://arxiv.org/html/2501.06322v1

**Save As:** `Agent_Collaboration_Mechanisms_2025.pdf`

**BibTeX Key:** `agent_collab2025`

**Thesis Reference:** Section 2.2 (Agent coordination), Section 5.2 (Causal linkage across domains)

---

## 5. 2025 GraphRAG & Knowledge Graph Advances

### Retrieval-Augmented Generation with Graphs (GraphRAG Survey)

**Authors:** Various

**arXiv ID:** 2501.00309

**Date:** Submitted January 2025

**Abstract:** Comprehensive survey proposing a holistic GraphRAG framework by defining key components: query processor, retriever, organizer, generator, and data source. Reviews the increasing attention on equipping RAG with Graph structures. Covers recent advances including Medical Graph RAG (CVPR 2025), HybGRAG, and HyperGraphRAG.

**Download Links:**
- **PDF**: https://arxiv.org/pdf/2501.00309
- **Abstract Page**: https://arxiv.org/abs/2501.00309

**Save As:** `GraphRAG_Comprehensive_Survey_2025.pdf`

**BibTeX Key:** `graphrag_survey2025`

**Thesis Reference:** Section 5 (Unified Architecture), Section 3.1 (Industrial Knowledge Graph integration)

---

### Knowledge Graph-Guided Retrieval Augmented Generation (KG2RAG)

**Authors:** Various

**arXiv ID:** 2502.06864

**Date:** Submitted February 2025

**Publication:** NAACL 2025 (April-May 2025)

**Abstract:** Proposes KG2RAG framework that utilizes knowledge graphs to provide fact-level relationships between chunks, improving the diversity and coherence of retrieved results. Demonstrates competitive performance with state-of-the-art GraphRAG frameworks while offering better scalability for industrial applications.

**Download Links:**
- **PDF**: https://arxiv.org/pdf/2502.06864
- **Abstract Page**: https://arxiv.org/abs/2502.06864

**Save As:** `KG2RAG_Framework_2025.pdf`

**BibTeX Key:** `kg2rag2025`

**Thesis Reference:** Section 5.1 (Translation Matrix), Section 3 (Industrial KG implementation)

---

### Large Language Models for Knowledge Graph Embedding: A Survey

**Authors:** Various

**arXiv ID:** 2501.07766

**Date:** Submitted January 14, 2025; Updated April 8, 2025

**Abstract:** Survey on LLM-based knowledge graph embedding techniques. Covers how LLMs can be used to create and maintain semantic embeddings for knowledge graph entities and relationships. Particularly relevant for the semantic translation challenge between network, industrial, and energy domains.

**Download Links:**
- **PDF**: https://arxiv.org/pdf/2501.07766
- **Abstract Page**: https://arxiv.org/abs/2501.07766

**Save As:** `LLM_KG_Embedding_Survey_2025.pdf`

**BibTeX Key:** `llm_kg_embed2025`

**Thesis Reference:** Section 3.1 (IKG semantic context), Section 5.1 (Translation Matrix)

---

## 6. Autonomous LLM Agents Fundamentals

### Fundamentals of Building Autonomous LLM Agents

**Authors:** Various

**arXiv ID:** 2510.09244

**Date:** Submitted October 2024

**Abstract:** Foundational paper on the principles and architectures for building autonomous LLM agents. Covers perception systems, reasoning mechanisms, memory architectures, and execution systems. Provides the theoretical foundation for implementing Level 4 autonomy as described in the TM Forum framework.

**Download Links:**
- **PDF**: https://arxiv.org/pdf/2510.09244
- **Abstract Page**: https://arxiv.org/abs/2510.09244

**Save As:** `Autonomous_LLM_Agents_Fundamentals_2024.pdf`

**BibTeX Key:** `autonomous_agents_fund2024`

**Thesis Reference:** Section 2.2.1 (Level 4 Autonomy), Section 6 (Autonomous remediation)

---

### Autonomous Control Leveraging LLMs: An Agentic Framework for Industrial Automation

**Authors:** Various

**arXiv ID:** 2507.07115

**Date:** Submitted July 2025

**Abstract:** Agentic framework specifically designed for next-generation industrial automation. Addresses how LLM agents can interact with industrial control systems (PLCs, SCADA) and make autonomous decisions. Directly applicable to the Siemens Industrial Edge integration in the thesis.

**Download Links:**
- **PDF**: https://arxiv.org/pdf/2507.07115
- **Abstract Page**: https://arxiv.org/abs/2507.07115
- **HTML Version**: https://arxiv.org/html/2507.07115

**Save As:** `Agentic_Industrial_Automation_2025.pdf`

**BibTeX Key:** `agentic_industrial2025`

**Thesis Reference:** Section 3 (The Hands - Industrial Domain), Section 3.2 (Siemens S7-1500 Web API)

---

## Download Instructions

### Method 1: Direct Download
1. Click the PDF link for each paper
2. Save the file with the specified filename
3. Place in: `C:\Users\lukis\My Drive\University\AISS\Thesis\Sources\Articles\`

### Method 2: Using a Download Manager
If you prefer batch downloading:
```bash
# Core Papers (2022-2024)
wget https://arxiv.org/pdf/2404.16130 -O Edge_2024_GraphRAG.pdf
wget https://arxiv.org/pdf/2201.11903 -O Wei_2022_Chain_of_Thought.pdf
wget https://arxiv.org/pdf/2210.03629 -O Yao_2023_ReAct.pdf

# 2025 Multi-Agent Systems
wget https://arxiv.org/pdf/2412.17481 -O MultiAgent_LLM_Survey_2025.pdf
wget https://arxiv.org/pdf/2501.06322 -O Agent_Collaboration_Mechanisms_2025.pdf

# 2025 GraphRAG & Knowledge Graphs
wget https://arxiv.org/pdf/2501.00309 -O GraphRAG_Comprehensive_Survey_2025.pdf
wget https://arxiv.org/pdf/2502.06864 -O KG2RAG_Framework_2025.pdf
wget https://arxiv.org/pdf/2501.07766 -O LLM_KG_Embedding_Survey_2025.pdf

# Autonomous LLM Agents
wget https://arxiv.org/pdf/2510.09244 -O Autonomous_LLM_Agents_Fundamentals_2024.pdf
wget https://arxiv.org/pdf/2507.07115 -O Agentic_Industrial_Automation_2025.pdf
```

### Method 3: arXiv Mobile App
- Download the arXiv app for iOS/Android
- Search by arXiv ID
- Save papers for offline reading

---

## BibTeX Entries (Preview)

Add these to `refs.bib`:

```bibtex
@article{edge2024graphrag,
  author = {Edge, Darren and Trinh, Ha and Cheng, Newman and Bradley, Joshua and Chao, Alex and Mody, Apurva and Truitt, Steven and Larson, Jonathan},
  title = {From Local to Global: A Graph RAG Approach to Query-Focused Summarization},
  journal = {arXiv preprint arXiv:2404.16130},
  year = {2024},
  url = {https://arxiv.org/abs/2404.16130}
}

@article{wei2022chain,
  author = {Wei, Jason and Wang, Xuezhi and Schuurmans, Dale and Bosma, Maarten and Ichter, Brian and Xia, Fei and Chi, Ed and Le, Quoc and Zhou, Denny},
  title = {Chain-of-Thought Prompting Elicits Reasoning in Large Language Models},
  journal = {arXiv preprint arXiv:2201.11903},
  year = {2022},
  url = {https://arxiv.org/abs/2201.11903}
}

@inproceedings{yao2023react,
  author = {Yao, Shunyu and Zhao, Jeffrey and Yu, Dian and others},
  title = {ReAct: Synergizing Reasoning and Acting in Language Models},
  booktitle = {Proceedings of the 11th International Conference on Learning Representations (ICLR)},
  year = {2023},
  url = {https://arxiv.org/abs/2210.03629}
}
```

---

## Paper Status

| Paper | arXiv ID | Date | Status | Size (approx) |
|-------|----------|------|--------|---------------|
| **Core Papers (2022-2024)** |
| GraphRAG | 2404.16130 | Apr 2024 | Available | ~1.5 MB |
| Chain-of-Thought | 2201.11903 | Jan 2022 | Available | ~2 MB |
| ReAct | 2210.03629 | Oct 2022 | Available | ~1 MB |
| **2025 Multi-Agent Systems** |
| Multi-Agent LLM Survey | 2412.17481 | Jan 2025 | Available | ~2 MB |
| Agent Collaboration | 2501.06322 | Jan 2025 | Available | ~1.5 MB |
| **2025 GraphRAG & KG** |
| GraphRAG Survey | 2501.00309 | Jan 2025 | Available | ~2 MB |
| KG2RAG | 2502.06864 | Feb 2025 | Available | ~1.5 MB |
| LLM KG Embedding | 2501.07766 | Jan 2025 | Available | ~1.5 MB |
| **Autonomous Agents** |
| Autonomous Agents Fund | 2510.09244 | Oct 2024 | Available | ~1.5 MB |
| Agentic Industrial | 2507.07115 | Jul 2025 | Available | ~1.5 MB |

### Neurosymbolic & Debate (The Interaction Layer)
| Paper | arXiv ID | Date | Status | Size |
|-------|----------|------|--------|------|
| Improving Factuality (Debate) | 2305.14325 | May 2023 | Available | ~1 MB |
| Divergent Thinking (MAD) | 2305.19118 | May 2023 | Available | ~1 MB |
| ChatEval (Evaluation) | 2308.07201 | Aug 2023 | Available | ~1 MB |
| Neuro-Symbolic State of Art | 2105.05330 | May 2021 | Available | ~1 MB |

---

**Total Papers**: 14 core arXiv papers (3 foundational + 7 new 2025 + 4 NeSy/Debate)
**Total Download Size**: ~16 MB
**Access**: All freely available, no registration required
**Update**: Added 7 papers from 2024-2025 to reflect latest research advances

---

## Sources

- [GraphRAG on arXiv](https://arxiv.org/abs/2404.16130)
- [Chain-of-Thought on arXiv](https://arxiv.org/abs/2201.11903)
- [ReAct on arXiv](https://arxiv.org/abs/2210.03629)
- [Microsoft Research - GraphRAG Project](https://www.microsoft.com/en-us/research/project/graphrag/)
