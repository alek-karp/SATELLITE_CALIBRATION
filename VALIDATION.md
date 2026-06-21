# Validation Checklist

Run these questions before implementing any new training loop, reward signal, or environment change.

## Environment

- [ ] Can a competent agent actually solve this? Run a sanity check episode before collecting baseline data.
- [ ] Are the physics parameters calibrated to reality? (beamwidth, drift rate, tracking leak)
- [ ] Does the anomaly severity allow recovery within the decision interval?

## Reward Signal

- [ ] Is one score per episode dense enough for GRPO to attribute credit to individual decisions?
- [ ] What does the model actually need to learn — and is that learnable from the reward we defined?
- [ ] Does the reward distinguish between lucky recoveries and good strategy?

## Base Model

- [ ] What are the failure modes of the base model before designing the training loop?
- [ ] Is the model failing due to lack of knowledge, or due to noisy observations it can't control?
- [ ] Run at least one full episode per anomaly type and document the behaviour before training.

## Post-Training

- [ ] What does a post-RFT episode log need to look like to prove improvement?
- [ ] Define success criteria before running RFT, not after.
