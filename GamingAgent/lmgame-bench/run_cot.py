"""
run_cot.py
Runs all 4 Baba Is You levels with DeepSeek V4 Flash thinking (CoT) mode.
baba_is_you: 10 trials. Harder levels: 1 trial each (CoT is ~44 s/step on baba_is_you, ~4-5 min/step on complex levels).

Usage (from GamingAgent/):
    python lmgame-bench/run_cot.py
"""

import subprocess
import shutil
import sys

MODEL = "deepseek-reasoner"
MAX_STEPS = 75
ENV_DIR = "gamingagent/envs/custom_07_baba_is_you"

LEVEL_RUNS = {
    "baba_is_you":  10,
    "out_of_reach":  1,
    "volcano":       1,
    "off_limits":    1,
}

print("=" * 54)
print(f"  MODEL: DeepSeek V4 Flash thinking/CoT ({MODEL})")
print(f"  Max steps: {MAX_STEPS}")
print("=" * 54)

for level, num_runs in LEVEL_RUNS.items():
    print(f"\n=== LEVEL: {level} ({num_runs} trial(s)) ===")
    shutil.copy(
        f"{ENV_DIR}/game_env_config_{level}.json",
        f"{ENV_DIR}/game_env_config.json",
    )
    subprocess.run([
        sys.executable, "lmgame-bench/single_agent_runner.py",
        "--game_name",            "baba_is_you",
        "--model_name",           MODEL,
        "--observation_mode",     "text",
        "--num_runs",             str(num_runs),
        "--max_steps_per_episode", str(MAX_STEPS),
        "--use_perception",       "false",
        "--use_reflection",       "true",
        "--level_name",           level,
    ])
    print(f"  Done: {level}")

print("\n" + "=" * 54)
print("  CoT COMPLETE — results in cache/baba_is_you/")
print("=" * 54)
