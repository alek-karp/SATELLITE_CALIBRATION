import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'env'))

from satellite_env import SatelliteEnv, ACTIONS
import numpy as np

def run_random_episode(difficulty='medium', render=True):
    env = SatelliteEnv(difficulty=difficulty, render_mode='human' if render else None)
    obs, info = env.reset()

    print(f"\n{'='*70}")
    print(f"Satellite: {info['satellite']}")
    print(f"Pass duration: {info['pass_duration']}s  |  Max elevation: {info['max_elevation']:.1f}°")
    print(f"Anomalies: {info['anomalies']}")
    print(f"{'='*70}\n")

    total_reward = 0
    steps_above_threshold = 0
    steps_locked = 0
    done = False
    step = 0

    while not done:
        action = env.action_space.sample()
        obs, reward, terminated, truncated, info = env.step(action)
        done = terminated or truncated
        total_reward += reward

        if info['locked']:
            steps_locked += 1
        if info['snr_db'] > 10.0:
            steps_above_threshold += 1

        if render and step % 30 == 0:
            env.render()

        step += 1

    print(f"\n{'='*70}")
    print(f"Episode complete — {step} steps")
    print(f"Total reward:          {total_reward:.1f}")
    print(f"Steps locked:          {steps_locked}/{step} ({100*steps_locked/step:.0f}%)")
    print(f"Steps above threshold: {steps_above_threshold}/{step} ({100*steps_above_threshold/step:.0f}%)")
    print(f"{'='*70}\n")
    return total_reward


if __name__ == '__main__':
    print("=== EASY (no anomalies) ===")
    run_random_episode(difficulty='easy')

    print("\n=== MEDIUM (1 anomaly) ===")
    run_random_episode(difficulty='medium')

    print("\n=== HARD (2 anomalies) ===")
    run_random_episode(difficulty='hard')
