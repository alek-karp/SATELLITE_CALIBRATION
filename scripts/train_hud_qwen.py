"""Train a HUD Gateway model fork on the local satellite-calibration taskset.

Usage:
    uv run python scripts/train_hud_qwen.py satellite-qwen3-8b

Create the trainable fork first:
    uv run hud models fork Qwen/Qwen3-8B --name satellite-qwen3-8b
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

from hud import Job, Taskset, TrainingClient
from hud.agents import create_agent

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tasks import tasks


async def train(
    model: str,
    *,
    iterations: int,
    group: int,
    max_steps: int,
    max_concurrent: int,
    learning_rate: float,
    loss_fn: str | None,
    temperature: float,
    top_p: float,
    auto_respond: bool,
    task_ids: str | None,
) -> None:
    selected_tasks = list(tasks)
    if task_ids:
        requested = [slug.strip() for slug in task_ids.split(",") if slug.strip()]
        by_slug = {task.slug: task for task in selected_tasks}
        missing = [slug for slug in requested if slug not in by_slug]
        if missing:
            raise ValueError(f"unknown task id(s): {', '.join(missing)}")
        selected_tasks = [by_slug[slug] for slug in requested]

    taskset = Taskset("satellite-calibration-local", selected_tasks)
    agent = create_agent(
        model,
        max_steps=max_steps,
        auto_respond=auto_respond,
        completion_kwargs={
            "temperature": temperature,
            "top_p": top_p,
            "extra_body": {"return_token_ids": True},
        },
    )
    trainer = TrainingClient(model)

    available_losses = await trainer.available_losses()
    selected_loss = loss_fn or ("ppo" if "ppo" in available_losses else "importance_sampling")
    if selected_loss not in available_losses:
        raise ValueError(
            f"loss_fn={selected_loss!r} is not available for {model}. "
            f"Available losses: {available_losses}"
        )

    session = await Job.start(f"{model}-satellite-training", group=group)
    print(f"training job: https://hud.ai/jobs/{session.id}")
    print(
        f"loss: {selected_loss} | group: {group} | max_steps: {max_steps} "
        f"| temperature: {temperature} | top_p: {top_p} "
        f"| auto_respond: {auto_respond} | tasks: {len(selected_tasks)}"
    )

    for step_idx in range(1, iterations + 1):
        start = len(session.runs)
        await taskset.run(
            agent,
            group=group,
            max_concurrent=max_concurrent,
            job=session,
            rollout_timeout=600,
        )
        batch = session.runs[start:]
        rewards = [run.reward or 0.0 for run in batch]
        mean_reward = sum(rewards) / len(rewards)
        reward_min = min(rewards)
        reward_max = max(rewards)
        result = await trainer.step(
            batch,
            learning_rate=learning_rate,
            loss_fn=selected_loss,
            group_size=group,
        )
        head = await trainer.head()
        head_name = head.name if head else "base"
        print(
            f"step {step_idx}/{iterations}: "
            f"rollouts={len(batch)} mean_reward={mean_reward:.3f} "
            f"range={reward_min:.3f}..{reward_max:.3f} "
            f"trainer={result} head={head_name}"
        )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("model", help="Trainable HUD model slug, e.g. satellite-qwen3-8b")
    parser.add_argument("--iterations", type=int, default=3)
    parser.add_argument("--group", type=int, default=3)
    parser.add_argument("--max-steps", type=int, default=60)
    parser.add_argument("--max-concurrent", type=int, default=3)
    parser.add_argument("--learning-rate", type=float, default=1e-5)
    parser.add_argument("--loss-fn", default=None)
    parser.add_argument("--temperature", type=float, default=0.7)
    parser.add_argument("--top-p", type=float, default=0.95)
    parser.add_argument("--no-auto-respond", action="store_true")
    parser.add_argument("--task-ids", default=None)
    args = parser.parse_args()
    asyncio.run(
        train(
            args.model,
            iterations=args.iterations,
            group=args.group,
            max_steps=args.max_steps,
            max_concurrent=args.max_concurrent,
            learning_rate=args.learning_rate,
            loss_fn=args.loss_fn,
            temperature=args.temperature,
            top_p=args.top_p,
            auto_respond=not args.no_auto_respond,
            task_ids=args.task_ids,
        )
    )


if __name__ == "__main__":
    main()
