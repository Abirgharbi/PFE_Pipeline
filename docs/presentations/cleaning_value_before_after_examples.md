# Cleaning Value - Before/After Examples for Defense

## Goal of this slide
The key message is:
- cleaning is not formatting,
- cleaning is signal extraction,
- and signal extraction directly improves retrieval quality.

Use this one-line narrative:
- "We remove high-volume technical noise and keep evidence that can answer support questions faster and with fewer false matches."

---

## Why type-aware cleaning creates value
A single strategy for all file types is suboptimal.
The pipeline uses one strategy per file type:
- Release Notes HTML -> strip_html
- README Markdown -> clean_markdown
- Source headers C/H -> strip_license
- CMSIS giant headers -> filter_cmsis
- Other -> passthrough

Operational impact shown in project results:
- Release notes: about -33%
- README: about -15%
- Source files: about -10%
- CMSIS giant headers: about -96%

---

## Defense point: "If V3 is good, why remove content?"
Short answer for jury:
- "We do not remove knowledge from the project; we remove retrieval noise from the RAG view."

What this means concretely:
- Raw files are still available in repository artifacts.
- Cleaning V3 creates a retrieval-optimized representation.
- The objective is not compression for its own sake, but relevance per token.

Why removal is technically justified:
- RAG has a strict context budget: each useless token displaces potentially useful evidence.
- Repeated boilerplate and generated patterns distort ranking (false lexical matches).
- Keeping everything equally leads to lower precision and slower troubleshooting.

Decision rule used by V3:
- Keep content that can answer a support question.
- Remove content that is mostly repetitive, decorative, legal, or structurally noisy.
- Measure impact with before/after stats and retrieval behavior.

Risk acknowledgment and control:
- Yes, aggressive filtering can hide some low-level details (for example specific CMSIS bit macros).
- This is handled by guardrails: selective keep rules, rescue logic, and optional fallback sources for deep debug queries.

One sentence to close objections:
- "V3 is not data deletion; it is evidence prioritization for faster and more reliable answers."

---

## Example 1 - CMSIS header (high-value case)
Source file:
- Include/stm32h743xx.h in cmsis_device_h7

Observed before (very large technical boilerplate):
```c
/**
 * @file    stm32h743xx.h
 * @brief   CMSIS STM32H743xx Device Peripheral Access Layer Header File.
 */

typedef enum {
  NonMaskableInt_IRQn = -14,
  HardFault_IRQn = -13,
  ...
} IRQn_Type;

/* Then thousands of register bit position and mask defines */
#define XXXXX_Pos (...)
#define XXXXX_Msk (...)
```

After type-aware cleaning (what V3 keeps):
```c
/* CMSIS Device Header - Filtered for RAG relevance */
/* Kept: IRQ enum, peripheral BASE addresses, TypeDef register structs */

typedef enum { ... } IRQn_Type;
#define PERIPH_BASE ...
#define GPIOA_BASE ...
...

typedef struct { ... } GPIO_TypeDef;
typedef struct { ... } RCC_TypeDef;
```

Value to explain:
- We keep troubleshooting anchors (IRQ names, base addresses, register layouts).
- We drop bulk bit-mask noise that creates irrelevant token matches.
- Concrete measured impact used in the project: 1,458,301 chars -> 52,140 chars (-96.4%).

What to say to jury:
- "Without filtering, one CMSIS file dominates retrieval context. With filtering, the same file becomes compact evidence instead of context pollution."

CMSIS-specific clarification (.h and .c): what is repetitive/non-informative?

In CMSIS `.h` files, repetitive/non-informative usually means:
- thousands of near-identical `#define XXX_Pos` / `#define XXX_Msk` patterns repeated across peripherals,
- long comment banners and legal boilerplate repeated in many files,
- generated macro blocks that share naming templates but add little value for most support intents.

In CMSIS `.c` files (or startup/system C files), repetitive/non-informative usually means:
- repeated weak handler stubs and default loops (`while(1)` style) duplicated across families,
- long init scaffolding patterns with low diagnostic specificity,
- comments that restate obvious control flow instead of adding troubleshooting evidence.

What remains informative and should be kept:
- IRQ enum names and interrupt vectors,
- peripheral base addresses and register struct layouts (`*_TypeDef`),
- function/constant anchors frequently used in support queries,
- versioned, component-specific technical lines tied to concrete behavior.

Decision test used in defense:
- If removing a block does not reduce our ability to answer "what peripheral/API/interrupt/register is involved?", it is likely retrieval noise.
- If a block is required to answer precise bit-level questions, it must be kept via selective rules or fallback indexing.

---

## Example 2 - Release Notes HTML
Source file:
- Release_Notes.html in stm32h7xx-hal-driver

Observed before:
```html
<!DOCTYPE html>
<html ...>
<head>
  <meta charset="utf-8" />
  <style type="text/css"> ... </style>
</head>
<body>
<h1>Release Notes for STM32H7xx HAL Drivers</h1>
<p>Copyright ...</p>
<li>Fix typos in GPIO MODER bit naming definitions...</li>
```

After strip_html:
```text
Release Notes for STM32H7xx HAL Drivers
Update History
V1.11.x
Main Changes
- Fix typos in GPIO MODER bit naming definitions
- Add ...
```

Value to explain:
- HTML/CSS/DOM noise is removed.
- Remaining text is directly searchable by technical change keywords.
- This reduces false matches on HTML tokens and improves chunk density.

---

## Example 3 - README Markdown (badges and image noise)
Source file:
- README.md in stm32h7xx-hal-driver

Observed before:
```md
# STM32CubeH7 HAL Driver MCU Component
![tag](https://img.shields.io/badge/tag-v1.11.6-brightgreen.svg)
## Overview
...
```

After clean_markdown:
```md
# STM32CubeH7 HAL Driver MCU Component
## Overview
...
```

Value to explain:
- Badge URLs and decorative images are not support evidence.
- Removing them prevents retrieval from ranking visual/marketing tokens.
- Technical overview remains intact.

---

## Example 4 - HAL header source (.h)
Source file:
- Inc/stm32h7xx_hal.h in stm32h7xx-hal-driver

Observed before:
```c
/**
 * Copyright (c) 2017 STMicroelectronics.
 * All rights reserved.
 * This software is licensed ...
 */

#ifndef STM32H7xx_HAL_H
#define STM32H7xx_HAL_H
#include "stm32h7xx_hal_conf.h"
```

After strip_license:
```c
#ifndef STM32H7xx_HAL_H
#define STM32H7xx_HAL_H
#include "stm32h7xx_hal_conf.h"
```

Value to explain:
- Legal boilerplate is repetitive and semantically low for troubleshooting.
- Removing it reduces token duplication across hundreds of files.
- API-relevant content is unchanged.

---

## Business value summary (to say in 20 seconds)
- Same data source, better signal quality.
- Less noise -> fewer irrelevant retrieval hits.
- Smaller, denser chunks -> better context budget for the LLM.
- Better grounding -> higher answer quality and fewer hallucination risks.

---

## One-slide structure recommendation
Use this 4-block layout:
1. CMSIS before/after (main proof)
2. Release notes before/after
3. README before/after
4. Source header before/after

Footer line:
- "Type-aware cleaning converts raw repository text into retrieval-grade technical evidence."
