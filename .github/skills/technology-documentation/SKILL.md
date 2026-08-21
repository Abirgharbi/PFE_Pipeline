---
name: technology-documentation
description: "Use when: documenting technologies used in the project, explaining selection rationale, producing technology comparison tables, or writing the État de l'Art / Architecture sections that justify technical choices."
---

# Purpose

Document and explain the technology stack of the STM32Cube Preprocessing Pipeline. Every technology mention in the report should answer: What? Why? What alternatives? What contribution?

# When to Use

- Writing or updating the "Technologies Utilisées" section
- Justifying a tool choice in the architecture chapter
- Comparing alternatives (e.g., "why TF-IDF not BERT?")
- Adding a new technology to the stack
- Responding to jury questions about tool choices

# Technology Categories

## 1. Data Processing & NLP
| Tech | Role | Justification |
|------|------|---------------|
| Python 3.14 | Core runtime | Industry standard for data pipelines, rich NLP ecosystem |
| scikit-learn | TF-IDF similarity | Lightweight, no GPU dependency, sufficient for sparse text matching |
| jsonschema | Validation | Declarative contracts between pipeline stages, automatic enforcement |
| pypdf + PyMuPDF | PDF extraction | pypdf for text, PyMuPDF for page rendering (figure detection needs bitmap) |
| OpenCV | Figure detection | Contour analysis on rendered PDF pages to isolate diagrams |

## 2. AI & RAG Platform
| Tech | Role | Justification |
|------|------|---------------|
| Azure OpenAI GPT-5.1 | LLM | ST-approved enterprise model, high accuracy, function calling |
| Unstructured KB (Hybrid) | Retrieval | Combines semantic embeddings + full-text search, citation support |
| Alfred Vision API | Image understanding | Multimodal analysis of PDF figures and issue screenshots |
| NovaX | Fallback | Handles edge-case queries when KB retrieval is empty |

## 3. Infrastructure & Automation
| Tech | Role | Justification |
|------|------|---------------|
| GitHub REST API | Data source | Direct access to issues, PRs, commits, file trees |
| Jenkins | CI/CD | ST enterprise standard, Groovy pipeline-as-code |
| PowerShell | Scripts | Windows-native, JSON-native, parallel execution support |
| Git | Version control | Standard, plus data source via local clone scanning |

## 4. Reporting & Visualization
| Tech | Role | Justification |
|------|------|---------------|
| LaTeX + TikZ | Report | Academic standard, precise typesetting, vector diagrams |
| Mermaid | Quick diagrams | Fast iteration in VS Code, convertible to images |

# Output Format (for report sections)

```latex
\subsection{Choix Technologiques}

\paragraph{Python et scikit-learn}
Le pipeline repose sur \textbf{Python 3.14} pour l'ensemble du traitement de données.
Le choix de \texttt{scikit-learn} pour le calcul de similarité TF-IDF se justifie par
sa légèreté (pas de GPU requis), sa maturité, et sa suffisance pour la correspondance
lexicale entre issues techniques. Les alternatives considérées (sentence-transformers,
FAISS) ont été écartées car elles introduisent une dépendance GPU non disponible
dans l'infrastructure Jenkins de ST.
```

# Decision Framework

For each technology choice, the documentation must answer:
1. **What problem does it solve?**
2. **Why this specific tool?** (not just "it's popular")
3. **What alternatives were evaluated?**
4. **Why were alternatives rejected?** (cost, complexity, ST policy, performance)
5. **What measurable benefit does it provide?**

# Rules

- Never document a technology without its justification
- Always name at least one rejected alternative
- Connect each choice to a project objective or constraint
- Use French academic register for report sections
- Include version numbers for reproducibility
