# AI Fundamentals — Complete Training Guide

**A practical guide to Artificial Intelligence concepts**

For teams with no prior AI background — Clear explanations • Visual examples • Real-world analogies

STMicroelectronics — Support & Maintenance Team — 2026

---

## Table of Contents

1. What is Artificial Intelligence?
2. Machine Learning
3. How to Train a Model — Step by Step
4. Deep Learning & Neural Networks
5. Natural Language Processing (NLP)
6. Embeddings — How AI Understands Meaning
7. Large Language Models (LLMs)
8. Specialized Chatbots — Why and How
9. RAG — Retrieval-Augmented Generation
10. Feature Engineering — The Secret Sauce
11. Agentic AI — Autonomous Intelligent Agents
12. Vector Databases
13. Computer Vision
14. Evaluation — How We Measure AI Quality
15. Data Generation — Creating Training-Ready Data
16. CI/CD for AI — Continuous Deployment
17. Advantages, Limits, and Challenges of AI
18. How Everything Connects in Our Project
19. Glossary
20. Conclusion

---

## 1. What is Artificial Intelligence?

### 1.1 Definition

Artificial Intelligence (AI) is the science of building computer systems that can perform tasks normally requiring human intelligence: understanding language, recognizing patterns, making decisions, and learning from experience.

Think of AI as a very fast assistant that never gets tired, can read thousands of documents in seconds, and remembers everything perfectly — but has no common sense and only does what it was trained to do.

### 1.2 AI is not magic

AI systems are software built on mathematics and statistics. They do not think, feel, or understand like humans. They process data, find patterns, and produce outputs based on those patterns.

An AI system is only as good as:
- The data it was trained on (garbage in = garbage out)
- The rules and algorithms it follows
- The way humans designed and evaluated it

### 1.3 Types of AI

| Type | What it does | Example |
|------|-------------|---------|
| **Narrow AI** | Performs one specific task very well | Spam filter, voice assistant, chatbot |
| **General AI** | Would perform any intellectual task like a human | Does not exist yet |
| **Super AI** | Would surpass human intelligence | Science fiction for now |

All AI systems today, including ChatGPT, are Narrow AI — they excel at specific tasks but cannot do everything.

📌 **In our project**: Our chatbot is Narrow AI: it answers STM32Cube technical questions from a knowledge base. It cannot debug your code or design a circuit.

---

## 2. Machine Learning

### 2.1 What is Machine Learning?

Machine Learning (ML) is a subset of AI where systems learn from data instead of being explicitly programmed with rules.

Traditional programming: you write the rules. Machine Learning: you give examples and the system discovers the rules.

| Traditional programming | Machine Learning |
|------------------------|-----------------|
| You write the rules yourself | The system discovers the rules from examples |
| Example: you write "IF email contains 'free money' THEN mark as spam" | Example: you show 10,000 emails labeled spam/not-spam, and the system learns to detect spam on its own |

### 2.2 The three types of Machine Learning

**Supervised Learning**

The system learns from labeled examples — input/output pairs provided by humans.

Like a teacher showing students 1,000 photos of cats and dogs with labels. After training, the student can label new photos correctly.
- Classification: assign a category (bug vs. feature request, spam vs. not spam)
- Regression: predict a number (temperature tomorrow, delivery time)

**Unsupervised Learning**

The system finds patterns in data without labels. Nobody tells it what to look for.

Like sorting a pile of 1,000 photos into groups without knowing what the groups should be. The system might discover: photos with animals, photos with buildings, photos with people.
- Clustering: group similar items together
- Dimensionality reduction: simplify complex data while keeping important patterns

**Reinforcement Learning**

The system learns by trial and error, receiving rewards for good actions and penalties for bad ones.

Like training a dog: reward for sitting, no reward for jumping. Over time, the dog learns what actions lead to treats.
- Used in: game AI, robotics, self-driving cars, recommendation systems

📌 **In our project**: Our project uses concepts from supervised learning (evaluation with known correct answers) and unsupervised learning (similarity detection between issues).

---

## 3. How to Train a Model — Step by Step

### 3.1 The training lifecycle

Training an AI model is a structured, iterative process. Here are the steps, explained simply:

```
┌─────────────────────────────────────────────────────────────────┐
│               MODEL TRAINING LIFECYCLE                            │
│                                                                   │
│  1. COLLECT DATA                                                  │
│     │  Gather raw examples (texts, images, measurements)         │
│     ▼                                                             │
│  2. PREPARE DATA (cleaning + feature engineering)                │
│     │  Clean, structure, extract useful information              │
│     ▼                                                             │
│  3. SPLIT DATA                                                    │
│     │  Training set (80%) / Validation set (10%) / Test (10%)   │
│     ▼                                                             │
│  4. CHOOSE A MODEL ARCHITECTURE                                  │
│     │  Select the right algorithm for the problem                │
│     ▼                                                             │
│  5. TRAIN                                                         │
│     │  Model reads training data thousands of times              │
│     │  Adjusts internal parameters at each pass                  │
│     ▼                                                             │
│  6. EVALUATE                                                      │
│     │  Test on data the model has NEVER seen                     │
│     │  Measure accuracy, precision, recall                       │
│     ▼                                                             │
│  7. ITERATE                                                       │
│     │  Not good enough? → adjust data, features, or model       │
│     ▼                                                             │
│  8. DEPLOY                                                        │
│     │  Put in production and monitor                             │
│     ▼                                                             │
│  9. MONITOR & RETRAIN                                             │
│        Performance drops over time → retrain with new data       │
└─────────────────────────────────────────────────────────────────┘
```

### 3.2 What the model actually "learns"

During training, the model adjusts millions (or billions) of internal numbers called **weights**. These weights determine how the model reacts to any input.

**Analogy**: Imagine a gigantic mixing board in a recording studio with 175 billion knobs. Training = turning all those knobs until the output sounds right. Once the knobs are in the right positions, the model produces correct answers for new inputs.

### 3.3 Key assets for training a good model

| Asset | Why it's critical | What we do in our project |
|-------|------------------|--------------------------|
| **Data quality** | "Garbage in = garbage out" — a model cannot learn from dirty data | Pipeline cleaning + schema validation |
| **Data volume** | More examples = better learning | 20+ repos, thousands of issues and files |
| **Relevant features** | The model needs discriminating information | Feature engineering: layer, severity, board, component |
| **Representative data** | Training data must reflect real cases | Diversity of repos and problem types |
| **Rigorous evaluation** | Objectively measure if the model is good | Offline/online evaluation framework |
| **Iteration speed** | Fast feedback loop = faster improvement | Automated pipeline (CI/CD) for quick regeneration |

### 3.4 Training vs. RAG — two different approaches

| | Training a model | Using RAG |
|---|---|---|
| **What you do** | Teach the model new knowledge | Give the model documents to read |
| **Time required** | Hours to weeks | Minutes to hours |
| **Cost** | Very expensive (GPU clusters) | Moderate (API calls + storage) |
| **Update frequency** | Retrain = expensive | Update KB = fast and cheap |
| **Our approach** | We do NOT train the LLM | We prepare data for RAG retrieval |

📌 **In our project**: We don't train the LLM itself — we optimize the DATA it retrieves. That's why data quality, feature engineering, and chunking are our focus.

---

## 4. Deep Learning & Neural Networks

### 4.1 What is a Neural Network?

A neural network is a computational model inspired by the human brain. It consists of layers of interconnected nodes (neurons) that process information.

Structure of a neural network:
- **Input layer**: receives the data (text, image, numbers)
- **Hidden layers**: process and transform the data (the more layers, the "deeper" the network)
- **Output layer**: produces the result (classification, prediction, generated text)

Each connection between neurons has a "weight" — a number that gets adjusted during training. Training = finding the right weights so the network produces correct outputs.

### 4.2 What makes it "Deep"?

Deep Learning simply means a neural network with many hidden layers (tens, hundreds, or even thousands). More layers allow the network to learn more complex patterns.

| Simple ML | Shallow Neural Net | Deep Learning |
|-----------|-------------------|---------------|
| Manual feature extraction | 1-2 hidden layers | 10-1000+ hidden layers |
| Works on structured data | Simple pattern recognition | Complex tasks: language, vision, speech |

### 4.3 Why Deep Learning matters

Deep Learning powers the most impressive AI systems today:
- **Large Language Models** (GPT, Claude, LLaMA) — text understanding and generation
- **Computer Vision** (image recognition, object detection, face recognition)
- **Speech recognition** (Siri, Alexa, Google Assistant)
- **Machine translation** (Google Translate, DeepL)

📌 **In our project**: The LLM inside ST ChatGPT is a Deep Learning model. We do not train it ourselves — we feed it our data through RAG.

---

## 5. Natural Language Processing (NLP)

### 5.1 What is NLP?

Natural Language Processing is the branch of AI that enables computers to understand, interpret, and generate human language — text and speech.

When you type a question to a chatbot and it understands what you mean — that is NLP at work.

### 5.2 Key NLP tasks

| Task | What it does | Example |
|------|-------------|---------|
| Tokenization | Split text into words/tokens | "Hello world" → ["Hello", "world"] |
| Named Entity Recognition | Identify names, places, dates | "STM32H7 has a DMA bug" → STM32H7=MCU, DMA=peripheral |
| Sentiment Analysis | Detect emotion/opinion in text | "This driver works perfectly" → positive |
| Text Classification | Assign categories to text | Issue → bug / feature request / question |
| Summarization | Condense long text into a short version | 10-page report → 3-sentence summary |
| Question Answering | Find the answer to a question in text | "How to init UART on H7?" → answer from docs |

### 5.3 Tokenization in detail

Tokenization is the first step of any NLP pipeline. It splits raw text into smaller units (tokens) that the model can process.

"HAL_UART_Init() failed on STM32H7" becomes:
["HAL", "_", "UART", "_", "Init", "()", "failed", "on", "STM32", "H7"]

Modern LLMs use subword tokenization (BPE): common words stay whole, rare words are split into pieces. This allows the model to handle any word, even ones it has never seen before.

### 5.4 TF-IDF: measuring word importance

TF-IDF (Term Frequency – Inverse Document Frequency) is a classic NLP technique that measures how important a word is in a document relative to all other documents.

- **TF** (Term Frequency): how often the word appears in THIS document
- **IDF** (Inverse Document Frequency): how rare the word is across ALL documents
- **TF-IDF = TF × IDF** — high score means the word is frequent here but rare elsewhere

If "DMA" appears 10 times in issue #487 but rarely in other issues, TF-IDF gives it a high score for issue #487 — making it easy to find when someone searches for DMA problems.

📌 **In our project**: We use TF-IDF for offline retrieval testing: before uploading to ST ChatGPT, we verify that a simple TF-IDF search on our preprocessed data can find the right documents.

---

## 6. Embeddings — How AI Understands Meaning

### 6.1 The problem: computers only understand numbers

Computers cannot read text the way humans do. They need text to be converted into numbers before they can process it. But not just any numbers — numbers that capture the MEANING of the text.

### 6.2 What is an embedding?

An embedding is a list of numbers (a vector) that represents the meaning of a piece of text. Texts with similar meanings have similar vectors.

"UART initialization error" and "USART init failure" would have very similar embeddings because they mean almost the same thing — even though the words are different.

### 6.3 How embeddings are used

- **Semantic search**: find documents related to a question based on meaning, not just keywords
- **Similarity detection**: find issues that describe the same bug in different words
- **Clustering**: group related documents together automatically
- **Recommendation**: suggest similar content

### 6.4 Cosine similarity

Once texts are converted to vectors, we measure how similar they are using cosine similarity — a number between 0 (completely different) and 1 (identical).

| Text A | Text B | Cosine similarity |
|--------|--------|-------------------|
| UART init error on H7 | USART initialization failure STM32H7 | 0.92 (very similar) |
| UART init error on H7 | How to configure SPI clock | 0.15 (very different) |

📌 **In our project**: Our pipeline uses cosine similarity in two places: linking similar issues (similarity stage) and evaluating retrieval quality (benchmark).

---

## 7. Large Language Models (LLMs)

### 7.1 What is an LLM?

A Large Language Model is a Deep Learning model trained on enormous amounts of text — books, websites, code, conversations. It learns to predict what word comes next in a sentence, and from this simple task it develops the ability to understand and generate language.

An LLM is like someone who has read every book, every website, and every forum post in the world. They can talk about anything — but they might mix things up or make things up if they are not careful.

### 7.2 How LLMs generate text

LLMs generate text one token at a time. For each new token, the model calculates the probability of every possible next word and picks one. This process repeats until the answer is complete.

- Input: "How do I initialize" → model predicts next word: "UART" (high probability)
- Then: "How do I initialize UART" → predicts: "on" (high probability)
- Then: "How do I initialize UART on" → predicts: "STM32H7" (high probability)
- And so on until the full answer is generated

### 7.3 The hallucination problem

Hallucination is when the AI generates information that sounds correct but is actually false. This is the most dangerous failure mode of any LLM-based system.

Why it happens: the model is trained to produce fluent, confident text — even when it does not have the right information. It would rather give a wrong answer confidently than say "I don't know."

| Hallucination example | Why it is dangerous |
|-----------------------|--------------------|
| "This bug was fixed in version 1.4.2" | The fix might not exist, leading to wrong firmware choices |
| "Use HAL_DMA_Start_IT() with channel 3" | Wrong channel could cause hardware damage or silent data corruption |

**This is why RAG exists**: by forcing the LLM to answer ONLY from retrieved documents, we dramatically reduce hallucination.

### 7.4 Key LLM concepts

| Concept | Explanation |
|---------|-------------|
| **Prompt** | The text you send to the model (question + context + instructions) |
| **Context window** | Maximum amount of text the model can process at once (e.g. 128K tokens) |
| **Temperature** | Controls randomness: 0 = deterministic, 1 = creative. Support chatbots use low temperature. |
| **Fine-tuning** | Additional training on domain-specific data to improve performance |
| **System prompt** | Hidden instructions that define the model's behavior and personality |

📌 **In our project**: ST ChatGPT uses a system prompt (called persona) that defines how the model should behave for STM32 support.

---

## 8. Specialized Chatbots — Why and How

### 8.1 Generalist vs. Specialized chatbot

| | Generalist chatbot | Specialized chatbot |
|---|---|---|
| **Knowledge** | Broad but shallow | Deep in one domain |
| **Accuracy** | Risk of hallucinations | Answers verified by a knowledge base |
| **Example** | ChatGPT in free mode | Our STM32 chatbot |
| **Data** | The entire internet | GitHub issues + STM32 docs specifically |

### 8.2 Why specialize a chatbot?

A generalist LLM does NOT know:
- The specific bugs of HAL STM32H7 v1.11.0
- The exact DMA configuration for an SPI transfer
- The workarounds validated by the firmware team

→ You must **provide the right information at the right time** = that's the role of RAG.

### 8.3 Three approaches to specialize a chatbot

| Approach | Principle | Advantages | Disadvantages |
|----------|-----------|-----------|---------------|
| **Fine-tuning** | Re-train the model on your data | Deeply integrated knowledge | Expensive, risk of catastrophic forgetting |
| **RAG** | Provide relevant documents in context | Flexible, traceable, updateable | Depends on retrieval quality |
| **Prompt Engineering** | Precise instructions to the model | Quick to set up | Limited by context window |

### 8.4 Why we chose RAG

- Our data changes frequently (new issues, new releases)
- We need traceability (every answer must cite its source)
- Fine-tuning would require re-training every time data changes = too expensive
- RAG lets us update the knowledge base in minutes without touching the model

📌 **In our project**: We use RAG — the most adapted approach for technical data that evolves frequently. Our pipeline is 100% focused on producing the best possible data for RAG retrieval.

---

## 9. RAG — Retrieval-Augmented Generation

### 9.1 The problem RAG solves

Standard LLMs answer from their training data — which is frozen at a point in time, generic, and may contain errors. For technical support, we need answers from OUR specific, up-to-date data.

| Standard LLM | LLM with RAG |
|--------------|-------------|
| Answers from general training data | Answers from YOUR specific documents |
| May be outdated | Uses latest uploaded data |
| Cannot cite sources | Every answer traces back to a source document |
| Higher hallucination risk | Hallucination reduced by grounding in real data |

### 9.2 How RAG works — step by step

```
┌─────────────────────────────────────────────────────────────────┐
│                      RAG FLOW                                    │
│                                                                  │
│  User: "How to configure DMA on STM32H7?"                       │
│       │                                                          │
│       ▼                                                          │
│  ┌──────────────┐     ┌────────────────────┐                    │
│  │  RETRIEVAL   │────▶│  Knowledge Base     │                    │
│  │  (search)    │     │  (our data)         │                    │
│  └──────────────┘     └────────────────────┘                    │
│       │                                                          │
│       │ Top-k relevant documents found                           │
│       ▼                                                          │
│  ┌──────────────┐                                                │
│  │     LLM      │ = User question + Retrieved documents          │
│  │ (generation) │                                                │
│  └──────────────┘                                                │
│       │                                                          │
│       ▼                                                          │
│  Precise, sourced answer                                         │
└─────────────────────────────────────────────────────────────────┘
```

**In summary**: RAG = "Search first in the knowledge base, then give the LLM the right documents so it generates a precise answer."

### 9.3 Why data quality is CRITICAL for RAG

The RAG can only answer correctly if:
1. **The right data exists** in the Knowledge Base (Data Generation)
2. **The data is well structured** to be found (Feature Engineering + Chunking)
3. **The retrieval finds the right documents** (Similarity + Evaluation)

→ **This is exactly the role of our pipeline**: transform raw data into optimized data so that RAG works well.

### 9.4 Chunking strategies for RAG

Documents must be split into chunks before indexing. The chunking strategy directly impacts retrieval quality:

| Strategy | How it works | Pros / Cons |
|----------|-------------|------------|
| **Full document** | 1 chunk = entire document | Simple but noisy for large docs |
| **Paragraph** | Split on natural paragraph boundaries | Clean, preserves meaning |
| **Sliding window** | Fixed-size windows with overlap | Uniform size, but cuts meaning |
| **Section-based** | Split on headers (##, ###) | Great for structured docs |
| **Parent-child** | Children indexed for search, parents returned for context | Best for generation quality |

📌 **In our project**: ST ChatGPT uses the parent-child strategy. Our preprocessing pipeline is entirely designed to produce data that works well with this strategy.

### 9.5 Reverse-engineering a production RAG (black box)

When working with a proprietary RAG platform, you cannot see the code. You must **reverse-engineer its behavior** by:

1. **Testing different data formats** → observe which ones get retrieved
2. **Varying chunk sizes** → identify the sweet spot
3. **Adding/removing metadata** → see what improves scoring
4. **Comparing offline vs online results** → understand platform-side processing
5. **Building a second RAG** → compare strategies on known data

This is what we did: we studied the black box RAG to understand its strengths and weaknesses, then designed our preprocessing to exploit its strengths and compensate for its weaknesses.

---

## 10. Feature Engineering — The Secret Sauce

### 10.1 What is Feature Engineering?

Feature Engineering is the art of **extracting and creating structured information** from raw data to help an AI system work better.

**Analogy**: You have a pile of 5,000 paper CVs. Feature Engineering = reading each CV and filling an Excel spreadsheet with columns: "Years of experience", "Main language", "Industry sector", "Education level". This structured table is far more exploitable than the raw CVs.

### 10.2 Why it's the most impactful step

In any AI/ML project, feature engineering typically delivers more improvement than changing algorithms. A simple algorithm with great features outperforms a complex algorithm with poor features.

```
Raw text: "HAL_SPI_Transmit returns HAL_TIMEOUT on NUCLEO-H743ZI 
           when DMA is used with buffer size > 65535 bytes"

Feature Engineering extracts:
  ├── layer = "HAL"           (detected from HAL_ prefix)
  ├── component = "SPI"       (detected from function name)
  ├── board = "NUCLEO-H743ZI" (detected from pattern)
  ├── severity = "high"       (timeout = functional failure)
  ├── issue_kind = "bug_report" (labeled as bug)
  ├── keywords = ["DMA", "buffer size", "65535", "timeout"]
  └── evidence_strength = "high" (specific, reproducible)
```

### 10.3 Concrete examples in our project

| Raw data | Extracted feature | How | Utility for RAG |
|----------|------------------|-----|-----------------|
| Issue text: "HAL_SPI_Transmit returns HAL_TIMEOUT" | `layer = "HAL"` | Pattern detection "HAL_" | Filter by software layer |
| GitHub labels: ["bug", "STM32H7"] | `severity = "high"`, `board = "STM32H7"` | Label mapping | Prioritization and filtering |
| Long issue with 12 comments | `evidence_strength = "high"` | Score based on technical richness | Prioritize rich content |
| Attached image (screenshot) | `image_description = "Oscilloscope trace showing..."` | LLM Vision | Make image searchable by text |

### 10.4 Why it's critical for RAG

Without feature engineering: RAG searches in raw unstructured text → mediocre results.
With feature engineering: RAG can filter, weight, and target → relevant results.

📌 **In our project**: Our enrichment stage performs heavy feature engineering — extracting layer, severity, board, component, issue_kind, keywords, and evidence strength from every issue and file.

---

## 11. Agentic AI — Autonomous Intelligent Agents

### 11.1 What is an AI Agent?

An **AI agent** is an autonomous program that:
1. **Receives an objective** (not just a simple instruction)
2. **Plans** the steps to achieve that objective
3. **Executes** actions (call APIs, read files, make decisions)
4. **Observes** the results
5. **Adapts** if something fails (retries, alternative plan)

**The key difference with a simple LLM call:**

```
Simple LLM call:      Question → Answer (one shot)
Agentic AI:           Objective → Planning → Action 1 → Observation → Action 2 → ... → Final result
```

### 11.2 Analogy

- **Simple LLM** = A consultant you ask ONE question and they answer.
- **AI Agent** = An autonomous intern given ONE mission. They plan their steps, execute, handle problems, and come back with the final result.

### 11.3 Components of an AI Agent

```
┌─────────────────────────────────────────────────┐
│                 AI AGENT                          │
│                                                   │
│  ┌──────────┐       ┌──────────────────┐         │
│  │   LLM    │       │     Tools        │         │
│  │ (brain)  │       │ (APIs, files,    │         │
│  └──────────┘       │  databases,      │         │
│       │             │  web search)     │         │
│       ▼             └──────────────────┘         │
│  ┌──────────┐                                     │
│  │  Memory  │  (context of past actions)          │
│  └──────────┘                                     │
│       │                                           │
│       ▼                                           │
│  ┌─────────────────┐                             │
│  │  Execution Loop │  Plan → Act → Observe →     │
│  │                 │  Adapt → Repeat until done   │
│  └─────────────────┘                             │
└─────────────────────────────────────────────────┘
```

### 11.4 Types of AI Agents

| Type | Behavior | Example |
|------|----------|---------|
| **Reactive** | Responds to stimuli, no planning | Simple chatbot with if/else rules |
| **Deliberative** | Plans before acting | Our image enrichment agent |
| **Multi-agent** | Several agents collaborate | One agent collects data, another evaluates quality |

### 11.5 In our project: the image enrichment agent

**Objective given to the agent**: "For each GitHub issue containing images, generate a textual description of each image."

**What the agent does autonomously**:
1. Scans all issues with images
2. Extracts image URLs
3. Calls the LLM Vision API to analyze each image
4. If an image is inaccessible → handles the error, moves to the next
5. If the API rate limit is hit → waits and retries
6. Inserts the generated description into the correct document field
7. Verifies coherence of the final result

→ **Autonomy + error handling + orchestration** = that's Agentic AI.

### 11.6 Why Agentic AI matters for industry

AI Agents allow **automating complex workflows** that previously required human intervention at every step. This is the next wave of AI adoption in enterprises:
- Process automation at scale (thousands of documents)
- Intelligent data pipelines
- Self-healing systems that detect and fix issues
- Multi-step research and analysis tasks

📌 **In our project**: Our Vision agent enriches thousands of images autonomously, handling errors, retries, and incremental updates without manual intervention.

---

## 12. Vector Databases

### 12.1 What is a vector database?

A vector database is a specialized storage system designed to store and search embeddings efficiently. Instead of searching by keywords (like a traditional database), it searches by meaning (similarity).

Traditional database: "Find all documents containing the word UART."
Vector database: "Find all documents that are ABOUT UART problems, even if they use different words."

### 12.2 How vector search works

- Step 1: All documents are converted to embeddings and stored in the vector database
- Step 2: When a query arrives, it is also converted to an embedding
- Step 3: The database finds the stored embeddings closest to the query embedding
- Step 4: Returns the top-k most similar documents

### 12.3 Popular vector databases

| Database | Type | Used for |
|----------|------|----------|
| ChromaDB | Open source, local | Prototyping, local experiments |
| Pinecone | Cloud managed | Production RAG systems |
| Weaviate | Open source, cloud or local | Enterprise applications |
| FAISS | Facebook library | Research, high-performance search |

📌 **In our project**: Our RAG benchmark uses ChromaDB locally. The ST ChatGPT platform uses its own internal vector database (black box).

---

## 13. Computer Vision

### 13.1 What is Computer Vision?

Computer Vision is the field of AI that enables machines to interpret and understand images and videos. It allows computers to "see" and extract information from visual content.

### 13.2 Key Computer Vision tasks

| Task | What it does | Example |
|------|-------------|---------|
| Image Classification | Assign a label to an entire image | "This is a circuit diagram" |
| Object Detection | Find and locate objects in an image | "There is a capacitor at position X,Y" |
| OCR | Extract text from images | Read register values from a screenshot |
| Image Segmentation | Identify every pixel's category | Separate foreground from background |
| Image Description | Generate text describing image content | "Oscilloscope trace showing signal at 50MHz" |

📌 **In our project**: Our Vision Agent uses Computer Vision (via LLM Vision) to describe technical images extracted from STM32Cube issues, converting visual information into searchable text for RAG.

---

## 14. Evaluation — How We Measure AI Quality

### 14.1 Why evaluation matters

"If you cannot measure it, you cannot improve it." — Lord Kelvin

An AI system without evaluation is like a car without a speedometer — you have no idea if it is working correctly. Evaluation tells us: is the system answering correctly? Is it hallucinating? Is it improving over time?

### 14.2 Key metrics for RAG systems

| Metric | What it measures | Good score |
|--------|-----------------|-----------|
| **P@k** (Precision at k) | Of the top k retrieved documents, how many are actually relevant? | 1.0 = all relevant |
| **MRR** | Mean Reciprocal Rank: how early does the first relevant document appear? | 1.0 = first result is relevant |
| **Recall** | Of all relevant documents, how many did we find? | 1.0 = found everything |
| **F1 Score** | Balance between precision and recall | Closer to 1.0 = better |
| **Latency** | How fast the system responds | < 2 seconds for chatbots |

### 14.3 Offline vs. Online evaluation

| Offline evaluation | Online evaluation |
|-------------------|-------------------|
| Test on your local machine | Test on the live platform |
| Fast, repeatable, no cost | Real conditions, real model |
| Uses TF-IDF, local embeddings | Uses the actual RAG engine |
| Catches data quality issues | Catches integration issues |

### 14.4 The data-driven iteration loop

```
   ┌──────────────┐
   │  Modify the  │
   │   pipeline   │
   └──────┬───────┘
          │
          ▼
   ┌──────────────┐
   │  Regenerate  │
   │   the data   │
   └──────┬───────┘
          │
          ▼
   ┌──────────────┐
   │   Evaluate   │◄────── Are metrics improving?
   │   (tests)    │           YES → Deploy
   └──────┬───────┘           NO  → Go back to step 1
          │
          ▼
   ┌──────────────┐
   │   Measure    │
   │   impact     │
   └──────────────┘
```

📌 **In our project**: We run both: offline TF-IDF tests on chunked JSONs + online 30Q/50Q benchmarks on the ST ChatGPT platform.

---

## 15. Data Generation — Creating Training-Ready Data

### 15.1 What is Data Generation?

Data Generation is the process of **creating structured, usable data** from raw, unstructured sources that cannot be directly consumed by an AI system.

**Analogy**: Imagine you have 50,000 handwritten customer complaint letters (some in bad handwriting, some torn, some with coffee stains). Data Generation = reading each one, typing it into a computer, fixing spelling errors, extracting key info (date, product, complaint type), and producing a clean spreadsheet.

### 15.2 Why raw data is NOT ready for AI

| Raw data problem | Why AI cannot use it | Our solution |
|-----------------|---------------------|--------------|
| Unstructured text (free-form GitHub issues) | No consistent format to search | Enrichment: extract structured fields |
| Mixed languages and formats | Noise dilutes signal | Cleaning: normalize and filter |
| Images without text description | RAG cannot search images | LLM Vision: generate text descriptions |
| Duplicate/invalid content | Pollutes search results | Validation: is_valid flag + rescue mechanism |
| Missing metadata | Cannot filter or prioritize | Feature engineering: extract layer, board, severity |

### 15.3 Our Data Generation pipeline

```
RAW SOURCES                    PIPELINE STAGES                 RAG-READY DATA
─────────────                  ───────────────                 ──────────────
GitHub API      ─┐             1. INGESTION                   Structured JSON
  Issues         │                 (fetch all data)            with metadata,
  PRs            │             2. CLEANING                    features,
  Commits        ├───────────▶     (normalize, filter)  ────▶ descriptions,
Technical docs   │             3. ENRICHMENT                  chunked text,
  README         │                 (feature engineering)      ready for
  Release Notes  │             4. CHUNKING                    vector indexing
  PDF files     ─┘                 (split for retrieval)
                               5. DELIVERY
                                   (format for KB)
```

### 15.4 Scale of our data generation

- 20+ GitHub repositories processed
- Thousands of issues, PRs, and commits
- Hundreds of technical files (README, Release Notes, PDFs)
- All transformed into structured, searchable, RAG-optimized documents

📌 **In our project**: Our entire pipeline IS a data generation system. Everything from ingestion to delivery is designed to produce data that makes the RAG chatbot answer correctly.

---

## 16. CI/CD for AI — Continuous Deployment

### 16.1 What is CI/CD?

CI/CD (Continuous Integration / Continuous Deployment) is the practice of **automatically building, testing, and deploying** software whenever changes are made.

**Analogy**: Instead of manually baking bread every morning (mix, knead, bake, package, deliver), you build a factory that does it all automatically. You just add ingredients (data) and quality-check the output.

### 16.2 Why CI/CD matters for AI data pipelines

Without CI/CD:
- Manual updates = human errors
- Slow iterations = slow improvement
- No audit trail = no traceability

With CI/CD:
- Automatic execution on every change
- Consistent, repeatable process
- Full traceability (who changed what, when)

### 16.3 Our CI/CD workflow

```
NEW DATA AVAILABLE (new issues, new releases)
        │
        ▼
┌─────────────────────────────┐
│  AUTOMATED PIPELINE (CI/CD)  │
│                              │
│  1. Fetch new data           │
│  2. Clean & enrich           │
│  3. Run quality tests        │
│  4. If tests pass → deliver  │
│  5. Upload to Knowledge Base │
└─────────────────────────────┘
        │
        ▼
KNOWLEDGE BASE UPDATED
(chatbot immediately has new answers)
```

📌 **In our project**: GitHub Actions + PowerShell scripts run the full pipeline and upload results to the Knowledge Base automatically, supporting 20+ data sources with zero manual intervention.

---

## 17. Advantages, Limits, and Challenges of AI

### 17.1 Advantages

- **Speed**: processes thousands of documents in seconds
- **Consistency**: same input always gets the same processing (no human fatigue or mood)
- **Scalability**: once built, works on any volume of data
- **Pattern discovery**: finds connections humans might miss
- **24/7 availability**: works anytime without breaks

### 17.2 Limits

- **No common sense**: AI does not truly understand — it matches patterns
- **Data dependency**: garbage in = garbage out
- **Hallucination**: can generate confident but wrong answers
- **Bias**: reflects biases present in training data
- **Explainability**: hard to know WHY the model gave a specific answer
- **Cost**: training large models requires massive compute resources

### 17.3 Ethical considerations

- **Privacy**: AI systems may process sensitive data
- **Fairness**: models must not discriminate
- **Transparency**: users should know when they are interacting with AI
- **Accountability**: who is responsible when AI makes a mistake?

AI is a tool. Like any tool, its impact depends on how responsibly it is designed, deployed, and monitored.

---

## 18. How Everything Connects in Our Project

### 18.1 Architecture overview

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    COMPLETE PROJECT ARCHITECTURE                          │
│                                                                           │
│  RAW SOURCES               OUR PIPELINE                    CHATBOT       │
│  ┌──────────────┐         ┌─────────────────────┐        ┌────────────┐│
│  │ GitHub API   │         │                     │        │            ││
│  │  • Issues    │──┐      │  1. Ingestion       │        │  RAG       ││
│  │  • PRs       │  │      │  2. Cleaning        │        │  Engine    ││
│  │  • Commits   │  │      │  3. Feature Eng.    │        │            ││
│  ├──────────────┤  ├─────▶│  4. Similarity      │───────▶│  LLM +    ││
│  │ Technical    │  │      │  5. Chunking        │        │  Knowledge ││
│  │  • README    │  │      │  6. Evaluation      │        │  Base      ││
│  │  • PDF       │──┘      │  7. Delivery        │        │            ││
│  │  • Images    │         └─────────────────────┘        └────────────┘│
│  └──────────────┘                  │                          │         │
│                                    │                          │         │
│                        ┌───────────┴──────────┐              │         │
│                        │   AI AGENTS           │              ▼         │
│                        │   (LLM Vision)        │         End Users      │
│                        │   Enrich images       │         ask questions  │
│                        │   autonomously        │                        │
│                        └──────────────────────┘                         │
│                                                                          │
│  ┌────────────────────────────────────────────────────────────────────┐ │
│  │  CI/CD (GitHub Actions) — runs everything automatically on schedule  │ │
│  └────────────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────────┘
```

### 18.2 Summary in one sentence

> Our pipeline transforms unusable raw data into an optimized knowledge base that the RAG chatbot uses to answer thousands of STM32 technical questions precisely and reliably.

### 18.3 The value chain

| Step | Input | Output | AI concept used |
|------|-------|--------|----------------|
| Ingestion | GitHub API, files | Raw JSON | Data collection |
| Cleaning | Raw JSON | Clean, normalized data | NLP preprocessing |
| Enrichment | Clean data | Data + features | Feature Engineering |
| Similarity | Enriched docs | Docs with related links | Cosine similarity, TF-IDF |
| Chunking | Full documents | Optimized chunks | Chunking strategies |
| Agent enrichment | Images | Text descriptions | Agentic AI, Computer Vision |
| Evaluation | Pipeline outputs | Quality metrics | Evaluation framework |
| Delivery | Chunks + metadata | KB-ready JSON | Data formatting |
| Upload | JSON files | Updated Knowledge Base | CI/CD automation |

---

## 19. Glossary

| Term | Definition |
|------|-----------|
| **AI** | Artificial Intelligence — systems that perform tasks requiring human intelligence |
| **ML** | Machine Learning — learning from data instead of explicit rules |
| **DL** | Deep Learning — ML with multi-layer neural networks |
| **NLP** | Natural Language Processing — AI for understanding text and speech |
| **LLM** | Large Language Model — AI trained on massive text data to understand and generate language |
| **RAG** | Retrieval-Augmented Generation — search then answer from your own data |
| **Embedding** | Numerical representation of text that captures meaning |
| **Chunking** | Splitting documents into smaller pieces for processing |
| **Vector DB** | Database optimized for storing and searching embeddings by similarity |
| **TF-IDF** | Term Frequency-Inverse Document Frequency — measures word importance |
| **Cosine similarity** | Mathematical measure of similarity between two vectors (0 to 1) |
| **Hallucination** | When AI generates false information that sounds correct |
| **Prompt** | The input text sent to an LLM (question + context + instructions) |
| **Fine-tuning** | Additional training of a model on domain-specific data |
| **Token** | Smallest unit of text processed by an LLM (word, subword, or character) |
| **P@k** | Precision at rank k — fraction of top-k results that are relevant |
| **MRR** | Mean Reciprocal Rank — how early the first relevant result appears |
| **Feature Engineering** | Extracting structured information from raw data to improve AI performance |
| **Data Generation** | Creating structured, usable data from raw unstructured sources |
| **Agentic AI** | AI systems that act autonomously — plan, execute, observe, adapt |
| **AI Agent** | Autonomous program that pursues objectives using tools and reasoning |
| **CI/CD** | Continuous Integration / Continuous Deployment — automated build and deploy |
| **Pipeline** | Chain of automated processing steps executed sequentially |
| **Knowledge Base (KB)** | Structured collection of documents feeding a RAG system |
| **Black box** | System whose internal workings are not visible — only inputs/outputs |
| **Reverse engineering** | Studying a system's behavior to understand its internal logic |

---

## 20. Conclusion

### Key takeaways

- **AI is not magic** — it is software built on mathematics and data
- **Machine Learning** lets systems learn from examples instead of explicit rules
- **Deep Learning** enables complex tasks like language understanding and image recognition
- **NLP** is what allows AI to understand and generate human text
- **LLMs** are powerful but can hallucinate — they need guardrails
- **RAG** solves hallucination by grounding answers in your own documents
- **Feature Engineering** is often more impactful than the algorithm itself
- **Agentic AI** enables autonomous, multi-step workflows at scale
- **Data Generation** transforms raw chaos into structured knowledge
- **Evaluation** is not optional — you must measure to improve
- **CI/CD** enables continuous improvement without manual effort
- **Data quality drives everything** — better data = better AI

### The bottom line

AI is a tool that amplifies human capability. It does not replace expertise — it makes experts faster and more effective.

Our project demonstrates this: we don't build the LLM, we don't train the neural network. We **engineer the data** that makes the AI useful. The quality of the chatbot's answers depends entirely on the quality of the data we provide — and that's what our pipeline ensures.
