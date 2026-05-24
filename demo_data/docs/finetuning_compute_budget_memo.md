# Memo: Compute Budget Policy for Model Fine-Tuning

**Owner:** sofia · **Audience:** ML team + eng leadership · **Status:** active policy
**Related experiments:** exp_011, exp_012, exp_013, exp_014, exp_015

## Why this memo exists

In January we attempted a full-parameter fine-tune of Llama-3-8B on the ~2TB proprietary
finance tabular corpus (exp_011). We aborted at 40% of the first epoch having already
spent **~$24,000** on 8x A100s. Optimizer state for an 8B model plus the data volume made
full fine-tuning economically impossible at our budget.

## Policy (effective immediately)

1. **No full-parameter fine-tunes** without explicit leadership sign-off and a costed plan.
2. **Default to parameter-efficient fine-tuning (PEFT).** Our results:
   - LoRA (exp_012): 0.81 portfolio-update accuracy, **~$110**, <1% of params trained.
   - QLoRA (exp_013): **0.83** accuracy on 5x more data, 22GB peak memory (fits one 40GB
     card), **~$96**. Current recommended default for scaling.
   - DoRA (exp_015): 0.85 accuracy for +18% train time — use when accuracy is the priority.
3. **Always run a cheap non-LLM baseline first.** XGBoost (exp_014) hit 0.79 at ~$3 on the
   pure numeric task. The LLM only earns its cost on the language-heavy slice (free-text
   client instructions, rationale generation). Don't pay for an LLM where trees suffice.

## Open questions

- DoRA + 4-bit quantization together is untested (exp_015 note) — potential best-of-both.
- Optimal LoRA rank for the full corpus not yet swept; exp_012/013 used r=16.
