# ST Quality Index 50Q Corrective Plan

Source: user-provided ST Tool Quality Index (50 questions, pasted manually in chat).

## 1) Score Distribution

- Total questions: 50
- Critical (<= 40): 19
- Medium risk (50 to 70): 8
- Acceptable/Good (>= 80): 23

## 2) Priority Buckets

### P0 - Immediate (score 0 to 40)

Questions:

- Q02, Q10, Q11, Q14, Q16, Q17, Q19, Q20, Q21, Q24, Q25, Q26, Q29, Q42, Q44, Q46, Q48
- Q45 (30)
- Q15 (40)

Main failure patterns:

- Missing or wrong domain retrieval (USB, Ethernet, FDCAN, I2C, ADC, timers)
- Policy and uncertainty handling gaps (open issue/no PR, unknown release date)
- Evidence formatting gaps (no explicit issue/PR/commit/release-note references)
- Scope mismatch handling (non-H7 query)

### P1 - Stabilization (score 50 to 70)

Questions:

- Q35
- Q05, Q09, Q38, Q39, Q43, Q50

Main failure patterns:

- Partially correct diagnosis but weak prioritization/order of checks
- Workaround guidance not explicitly separated from verified fix status

## 3) Corrective Actions

### A) Prompt/Behavior Guardrails (implemented)

Implemented in:

- [pipeline_Automation/Chat_With_Persona_KB.py](pipeline_Automation/Chat_With_Persona_KB.py)

Added rules:

- H7 scope check with clarification for out-of-scope queries
- Contradiction check (board/MCU/version mismatch)
- No "merged/fixed" claim without explicit evidence
- Open issue/no linked PR -> unconfirmed status + workaround path
- Unknown exact release date -> state unknown + where to verify
- Mandatory evidence-oriented answer structure

CLI toggle:

- Guardrails enabled by default
- Disable with `--no-quality-guardrails`

### B) Retrieval Intent Expansion (next step)

Add intent keyword clusters for weak topics:

- USB FS/HS/ULPI/CDC/RTOS
- Ethernet lwIP throughput/link up-down
- FDCAN receive/bus-off recovery
- I2C timing/bus stuck low
- ADC high-impedance sampling and injected/regular coexistence
- Encoder high-speed misses

Targeted questions: Q11, Q15, Q16, Q17, Q19, Q20, Q21, Q24, Q25, Q26, Q29.

### C) KB Corrective Cards (next step)

Create short corrective cards for each P0 question family:

- Symptom signature
- Verified evidence (issue/PR/commit/release-note)
- Safe workaround now
- Verification checklist
- Confidence label (confirmed vs unconfirmed)

### D) Response Contract (next step)

Enforce this output contract in evaluation runs:

- Diagnosis
- Evidence
- Action
- Confidence

This directly targets Q44, Q45, Q46, Q48 weaknesses.

## 4) Execution Plan

1. Run with current guardrails enabled and re-evaluate only P0 questions first.
2. Apply retrieval intent expansion for failed P0 questions.
3. Add corrective cards for remaining P0 failures.
4. Re-run full 50Q and compare score deltas by question.

## 5) Acceptance Targets

- P0 questions: minimum score >= 70
- Q44/Q45/Q46/Q48: minimum score >= 80
- Global target: no zero scores on 50Q set
