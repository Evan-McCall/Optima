# Postmortem: Vendor-Contract RAG Hallucination Problem (Q1 2026)

**Owner:** priya · **Reviewers:** marcus · **Status:** ongoing
**Related experiments:** exp_001, exp_002, exp_003, exp_004, exp_005

## Summary

Our vendor-contract clause-violation checker (legal review tool) shipped to internal
beta with an unacceptable hallucination rate: it cited clause numbers that did not
exist in the retrieved contracts ~22% of the time (exp_001). For a legal product this
is a non-starter — a fabricated clause citation is worse than no answer.

## What we learned

1. **The bottleneck is generation grounding, not retrieval.** Improving chunking and
   recall (exp_002: recall 0.71 -> 0.83) barely moved hallucination (22% -> 18%).
   Reranking (exp_005) improved context precision to 0.81 but faithfulness stalled.
2. **A cheap offline eval unblocked everything.** Standing up a RAGAS faithfulness
   harness on a fixed 60-query set (exp_003) gave us a ~$3/run signal that correlates
   with manual legal review (Spearman 0.74). Faithfulness is our north-star metric.
3. **Chain-of-Verification was the single biggest win (exp_004):** hallucinated clause
   rate 22% -> 7%, faithfulness 0.62 -> 0.78, for ~30% more cost/latency.

## Open problems

- Remaining ~6-7% are *near-miss* clause-number errors (cites clause 7.2 when the real
  one is 7.3). Retrieval tuning has hit diminishing returns here (exp_005).
- We have **not** tried: constrained/grounded decoding that forces cited clause IDs to
  be copied verbatim from retrieved context, or a dedicated citation-verifier model.
- Security/PII review of the retrieval index is still outstanding.

## Recommendation to the team

Stop spending budget on retrieval ranking. Put the next lean experiment into
**generation-side grounding** (citation verification / constrained decoding) measured
on the exp_003 faithfulness harness.
