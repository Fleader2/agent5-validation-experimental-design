# Agent 5 — Validation and Experimental Design

## Overview

Agent 5 is the fifth component of a multi-agent system for constructing scientifically
traceable, mechanistic models of microbial metabolism, and completes the first full pass of the
five-agent workflow.

Agent 5 consumes Agent 2's model metadata and Agent 4's calibration report (two separate
repositories, `agent2-antimony-builder` and `agent4-calibration-estimator`), validates the
calibrated model against held-out observations, identifies generalization and dominant-
uncertainty problems, and ranks the next most informative experiments.

**Central rule:** Agent 5 validates and prioritizes experiments; it does not recalibrate the
model, invent data, or silently change biology.

Agent 5 does **not**:

- curate literature, assemble a model, or calibrate any parameter (Agents 1/2/4's job),
- recompute Agent 3's or Agent 4's own diagnostic/identifiability logic from scratch,
- claim full Bayesian optimal experimental design — Version 1 uses a disclosed, modest,
  diagonal local-sensitivity/Fisher-information proxy,
- fabricate a validation result when no real held-out data exists.

Agent 5 consumes Agent 2's and Agent 4's output through an explicit, versioned handoff contract
(a plain, JSON-serializable dict) — it never imports any sibling package's runtime code. The
Agent 2 portion of that handoff is the one canonical `agent2-downstream-v1` shape Agent 2's own
`run_agent2_pipeline` entrypoint emits and every downstream agent consumes unchanged (Five-Agent
Workflow V1 Hardening increment).

Agent 5 completes the five-agent chain; the sibling `five-agent-integration-harness` repository
orchestrates all five agents end to end and is the canonical Version 1 release baseline (tagged
`v1.0.0`) — see its own `docs/00_five_agent_workflow_v1_architecture.md` for the full system map.

See `docs/01_agent5_responsibility_boundary.md` through `docs/06_what_agent5_does_not_do.md`
for full detail.

## Canonical workflow

```text
Agent 2 model + Agent 4 calibrated report + held-out observations
        ↓
Validation simulation (Agent 4's own fitted values, never adjusted)
        ↓
Residual / generalization analysis (train-vs-validation comparison)
        ↓
Uncertainty / sensitivity analysis (aggregates Agent 4's own identifiability findings)
        ↓
Candidate-experiment generation and scoring
        ↓
Ranked recommendations, each with a stated rationale
        ↓
Agent5Report
```

## Setup

```bash
python3 -m venv .venv
.venv/bin/pip install -e ".[dev]"
```

Dependencies: `antimony`, `libroadrunner`, `python-libsbml`, `numpy`, `scipy` — the same
simulation stack Agent 3/Agent 4 already validated. No Tellurium, no Bayesian/MCMC dependency.

## Tests

```bash
.venv/bin/python3 -m pytest tests/ -q
```
