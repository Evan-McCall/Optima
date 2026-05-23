# Incident Report: Support Agent Issuing Wrongful Refunds

**Owner:** dana · **Severity:** High (financial) · **Status:** mitigated, not closed
**Related experiments:** exp_006, exp_007, exp_008, exp_009, exp_010

## What happened

The autonomous customer-support agent (refunds, package verification, inventory) issued
refunds without validating the underlying claim. In replayed evaluation (exp_006) the
agent issued a wrongful refund 12% of the time — calling `issue_refund` before
confirming via `check_shipment` / `lookup_order` that the package was actually lost or
the order even existed. Effectively the agent hallucinated order state and acted on it.

## Root cause

`issue_refund` was a freely callable tool with no precondition. Prompt-only instructions
("always verify first") were not reliably followed under multi-step pressure.

## Mitigations applied

- **Precondition gating (exp_007):** `issue_refund` rejects calls unless validation tools
  returned confirming results earlier in the same trace. Wrongful refunds 12% -> 4%.
- **Reflexion self-critique before irreversible actions (exp_008):** 4% -> 2.5% on hard
  cases, ~25% extra cost/ticket.
- **Human-in-the-loop routing (exp_010):** route refunds below 0.8 confidence to a human;
  dollar-weighted error down to 2% at a 14% human-review rate.
- **Replay eval harness (exp_009):** dollar-weighted error is the metric we gate on, since
  a few high-value refunds dominate losses.

## Still open

- Confidence is poorly calibrated (self-report is over-confident), forcing a higher
  human-review rate than we'd like. A **calibrated refund verifier** is the obvious next
  lean experiment — it would let us lower the human-review rate while holding error flat.
- Multi-day / cross-channel ticket state handoff is brittle (state occasionally lost
  between email and chat).
