"""
replay_trial.py
===============
Prints a clean, readable step-by-step replay of a single trial.

Usage (run from GamingAgent root):
    python replay_trial.py                               # auto-finds most recent trial
    python replay_trial.py --log path/to/episode_001_log.jsonl
    python replay_trial.py --model deepseek_chat         # most recent trial for this model
    python replay_trial.py --model deepseek_chat --episode 2  # specific episode number

Options:
    --log       Direct path to a .jsonl log file
    --model     Model folder name prefix (e.g. deepseek_chat, deepseek_reason)
                Note: deepseek-reasoner folder is truncated to "deepseek_reason" (15 chars)
    --episode   Episode number to show (default: 1)
    --grid      Show full ASCII grid each step (default: False, grids are long)
    --thought   Show full thought text (default: truncated to 300 chars)
"""

import sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

import os
import json
import glob
import argparse


CACHE_ROOT = "cache/baba_is_you"


def find_log_file(model_prefix=None, episode_num=1):
    """Find the most recent log file matching the criteria."""
    if model_prefix:
        model_dirs = [
            d for d in os.listdir(CACHE_ROOT)
            if d.startswith(model_prefix) and os.path.isdir(os.path.join(CACHE_ROOT, d))
        ]
    else:
        model_dirs = [
            d for d in os.listdir(CACHE_ROOT)
            if os.path.isdir(os.path.join(CACHE_ROOT, d))
        ]

    if not model_dirs:
        print(f"No model folders found in {CACHE_ROOT}")
        return None

    # For each model dir, find all timestamp run folders
    all_runs = []
    for model_dir in model_dirs:
        model_path = os.path.join(CACHE_ROOT, model_dir)
        run_folders = [
            d for d in os.listdir(model_path)
            if os.path.isdir(os.path.join(model_path, d))
        ]
        for run_folder in run_folders:
            all_runs.append((model_dir, run_folder, os.path.join(model_path, run_folder)))

    if not all_runs:
        print("No run folders found.")
        return None

    # Sort by timestamp (run_folder name) — most recent last
    all_runs.sort(key=lambda x: x[1])
    most_recent = all_runs[-1]
    run_path = most_recent[2]

    log_file = os.path.join(run_path, f"episode_{episode_num:03d}_log.jsonl")
    if not os.path.exists(log_file):
        # Try episode 1 as fallback
        log_file = os.path.join(run_path, "episode_001_log.jsonl")

    if not os.path.exists(log_file):
        print(f"No log file found at {log_file}")
        return None

    return log_file, most_recent[0], most_recent[1]


def load_steps(log_path):
    steps = []
    with open(log_path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    steps.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    return steps


def replay(log_path, show_grid=False, show_full_thought=False):
    steps = load_steps(log_path)
    if not steps:
        print("No steps found in log file.")
        return

    print(f"\n{'='*70}")
    print(f"TRIAL REPLAY: {log_path}")
    print(f"Total steps logged: {len(steps)}")

    # Episode summary from last step
    last = steps[-1]
    info = last.get("info", {})
    won = info.get("won", False)
    total_steps = info.get("num_env_steps", len(steps))
    rule_changes = info.get("word_block_push_events", 0)
    outcome = "WON" if won else ("TRUNCATED (step limit)" if last.get("truncated") else "LOST")

    print(f"Outcome:       {outcome}")
    print(f"Steps taken:   {total_steps}")
    print(f"Rule changes:  {rule_changes}")
    print(f"{'='*70}\n")

    invalid_count = 0

    for step in steps:
        step_num       = step.get("step", "?")
        action         = step.get("agent_action", "None")
        thought        = step.get("thought", "") or ""
        reasoning_trace = step.get("reasoning_trace") or ""
        reward         = step.get("reward", 0.0)
        terminated     = step.get("terminated", False)
        truncated      = step.get("truncated", False)
        time_s         = step.get("time_taken_s", 0.0)
        info           = step.get("info", {})

        won_step     = info.get("won", False)
        active_rules = info.get("active_rules", [])
        player_pos   = info.get("player_position", None)

        is_valid = action in ("up", "down", "left", "right")
        if not is_valid:
            invalid_count += 1

        valid_marker = "" if is_valid else " ← INVALID"

        print(f"--- Step {step_num:>3} {'-'*50}")
        print(f"  Action:   {action}{valid_marker}")
        print(f"  Position: {player_pos}   Rules: {active_rules}")
        print(f"  Reward:   {reward:+.2f}   Time: {time_s:.1f}s")

        if thought:
            if show_full_thought:
                # Clean up the thought — remove nested JSON if present
                if thought.startswith("{") or "textual_representation" in thought:
                    print(f"  Thought:  [complex object — use --thought flag]")
                else:
                    print(f"  Thought:  {thought}")
            else:
                # Show first 300 chars, skip if it looks like a raw JSON dump
                if "textual_representation" in thought or thought.startswith("{"):
                    print(f"  Thought:  [memory object — run with --thought to see raw]")
                else:
                    preview = thought[:300]
                    suffix = "..." if len(thought) > 300 else ""
                    print(f"  Thought:  {preview}{suffix}")

        if reasoning_trace:
            if show_full_thought:
                print(f"  R1 Chain: {reasoning_trace}")
            else:
                preview = reasoning_trace[:300]
                suffix = "..." if len(reasoning_trace) > 300 else ""
                print(f"  R1 Chain: {preview}{suffix}")

        if show_grid:
            obs_raw = step.get("agent_observation", "")
            obs_str = obs_raw
            if isinstance(obs_raw, str):
                try:
                    obs_obj = json.loads(obs_raw)
                    obs_str = obs_obj.get("textual_representation", obs_raw) or obs_raw
                except (json.JSONDecodeError, AttributeError):
                    pass
            if "VISUAL GRID" in obs_str:
                start = obs_str.find("VISUAL GRID")
                end   = obs_str.find("PHYSICAL OBJECTS")
                if start != -1 and end != -1:
                    print("\n" + obs_str[start:end].strip() + "\n")

        if terminated:
            if won_step:
                print(f"\n  *** LEVEL SOLVED at step {step_num}! ***")
            else:
                print(f"\n  *** Episode terminated at step {step_num} ***")
        elif truncated:
            print(f"\n  *** Step limit reached at step {step_num} ***")

        print()

    print(f"{'='*70}")
    print(f"SUMMARY: {outcome} | {total_steps} steps | "
          f"{rule_changes} rule changes | "
          f"{invalid_count} invalid actions "
          f"({invalid_count/max(len(steps),1)*100:.0f}% invalid rate)")
    print(f"{'='*70}\n")


def list_available_runs():
    """Print all available runs to help user find what they want."""
    print(f"\nAvailable runs in {CACHE_ROOT}:")
    print(f"{'─'*60}")

    if not os.path.exists(CACHE_ROOT):
        print("  Cache directory not found. Run the experiment first.")
        return

    for model_dir in sorted(os.listdir(CACHE_ROOT)):
        model_path = os.path.join(CACHE_ROOT, model_dir)
        if not os.path.isdir(model_path):
            continue

        run_folders = sorted([
            d for d in os.listdir(model_path)
            if os.path.isdir(os.path.join(model_path, d))
        ])

        for run_folder in run_folders:
            run_path = os.path.join(model_path, run_folder)
            episodes = sorted(glob.glob(os.path.join(run_path, "episode_*_log.jsonl")))
            n_eps = len(episodes)

            # Get level name from agent_config
            level = "?"
            config_path = os.path.join(run_path, "agent_config.json")
            if os.path.exists(config_path):
                try:
                    with open(config_path) as f:
                        cfg = json.load(f)
                    lf = cfg.get("level_file", "")
                    level = os.path.basename(str(lf)).replace(".txt", "")
                except Exception:
                    pass

            print(f"  model: {model_dir}")
            print(f"  run:   {run_folder}")
            print(f"  level: {level}   episodes: {n_eps}")
            print(f"  log:   {run_path}/episode_001_log.jsonl")
            print()


def main():
    parser = argparse.ArgumentParser(description="Replay a Baba Is You trial step by step.")
    parser.add_argument("--log",     type=str, default=None, help="Direct path to episode log file")
    parser.add_argument("--model",   type=str, default=None, help="Model folder name prefix")
    parser.add_argument("--episode", type=int, default=1,    help="Episode number (default: 1)")
    parser.add_argument("--grid",    action="store_true",    help="Show ASCII grid each step")
    parser.add_argument("--thought", action="store_true",    help="Show full thought text")
    parser.add_argument("--list",    action="store_true",    help="List all available runs and exit")
    args = parser.parse_args()

    if args.list:
        list_available_runs()
        return

    if args.log:
        log_path = args.log
        if not os.path.exists(log_path):
            print(f"Log file not found: {log_path}")
            return
        replay(log_path, show_grid=args.grid, show_full_thought=args.thought)
        return

    if not os.path.exists(CACHE_ROOT):
        print(f"Cache directory not found: {CACHE_ROOT}")
        print("Run the experiment first.")
        return

    result = find_log_file(model_prefix=args.model, episode_num=args.episode)
    if not result:
        list_available_runs()
        return

    log_path, model_dir, run_folder = result
    print(f"Model:  {model_dir}")
    print(f"Run:    {run_folder}")
    replay(log_path, show_grid=args.grid, show_full_thought=args.thought)


if __name__ == "__main__":
    main()
