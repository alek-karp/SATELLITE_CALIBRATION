"""Eval Protocol wrapper for the satellite Fireworks RFT remote rollout server.

The remote server owns the episode and reports the real reward via tracing.
This evaluator exists so `eval-protocol upload` can register a remote rollout
processor for Fireworks RFT.
"""

from eval_protocol import EvaluateResult, EvaluationRow, RemoteRolloutProcessor, evaluation_test


@evaluation_test(
    input_dataset=["data/rft_seed.jsonl"],
    completion_params=[{"model": "accounts/fireworks/models/gemma-3-27b-it"}],
    rollout_processor=RemoteRolloutProcessor(timeout_seconds=900),
    max_dataset_rows=1,
    max_concurrent_rollouts=1,
)
def satellite_eval(row: EvaluationRow) -> EvaluationRow:
    """Pass through the score emitted by the remote satellite rollout."""
    extra_info = row.rollout_status.get_extra_info() or {}
    score = float(extra_info.get("score", 0.0))
    row.evaluation_result = EvaluateResult(
        score=score,
        is_score_valid="score" in extra_info,
        reason="remote satellite rollout score" if "score" in extra_info else "remote rollout did not report a score",
    )
    return row
