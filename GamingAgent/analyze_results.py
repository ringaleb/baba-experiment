"""
analyze_results.py
==================
Reads all GamingAgent logs from cache/baba_is_you/ and produces
the tables and metrics for the experiment.

Run from the GamingAgent root directory:
    python analyze_results.py

Output files written to: results/baba_is_you_analysis/
"""

import os
import json
import glob
from collections import defaultdict

# ── CONFIG ────────────────────────────────────────────────────────────────────

CACHE_ROOT   = "cache/baba_is_you"
OUTPUT_DIR   = "results/baba_is_you_analysis"

# Map folder name prefixes to clean model names for display
# deepseek-chat = non-thinking mode of DeepSeek V4 Flash
# deepseek-reasoner = thinking (CoT) mode of DeepSeek V4 Flash
# Both aliases scheduled for deprecation by DeepSeek on 2026-07-24
MODEL_NAME_MAP = {
    "deepseek_chat":      "DeepSeek V4 Flash",
    "deepseek_reason":    "DeepSeek V4 Flash (CoT)",  # folder name truncated to 15 chars by runner
}

# Map game_env_config level_file basenames to clean level names
LEVEL_NAME_MAP = {
    "baba_is_you.txt":  "Baba Is You",
    "out_of_reach.txt": "Out of Reach",
    "volcano.txt":      "Volcano",
    "off_limits.txt":   "Off Limits",
}

# ── HELPERS ───────────────────────────────────────────────────────────────────

def model_display_name(folder_name: str) -> str:
    for prefix, display in MODEL_NAME_MAP.items():
        if folder_name.startswith(prefix):
            return display
    return folder_name

def safe_mean(values):
    return sum(values) / len(values) if values else None

def safe_std(values):
    if not values or len(values) < 2:
        return 0.0
    m = safe_mean(values)
    return (sum((x - m) ** 2 for x in values) / len(values)) ** 0.5

# ── PARSE LOGS ────────────────────────────────────────────────────────────────

def parse_episode_log(jsonl_path: str) -> dict:
    """Parse a single episode_XXX_log.jsonl file into a summary dict."""
    steps = []
    try:
        with open(jsonl_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    steps.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    except Exception as e:
        print(f"  Warning: Could not read {jsonl_path}: {e}")
        return None

    if not steps:
        return None

    last = steps[-1]
    info = last.get("info", {})

    won       = info.get("won", False)
    num_steps = info.get("num_env_steps", len(steps))
    rule_changes = info.get("word_block_push_events", 0)

    # Count invalid actions
    invalid_actions = sum(
        1 for s in steps
        if s.get("agent_action") not in ("up", "down", "left", "right")
    )

    # Collect thought lengths as a proxy for reasoning depth
    thought_lengths = [
        len(s.get("thought", "") or "")
        for s in steps
    ]

    return {
        "won":             won,
        "steps":           num_steps,
        "rule_changes":    rule_changes,
        "invalid_actions": invalid_actions,
        "total_steps_logged": len(steps),
        "avg_thought_len": safe_mean(thought_lengths),
        "terminated":      last.get("terminated", False),
        "truncated":       last.get("truncated", False),
    }

def parse_run_summary(summary_path: str) -> dict:
    """Parse gym_run_summary.json."""
    try:
        with open(summary_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return {}

def get_level_from_summary(summary_path: str) -> str:
    """Extract level name from gym_run_summary.json settings."""
    try:
        with open(summary_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        # Level file path is in agent_config.json in the same directory
        run_dir = os.path.dirname(summary_path)
        config_path = os.path.join(run_dir, "agent_config.json")
        if os.path.exists(config_path):
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
            # Look for level_file in config
            level_file = config.get("level_file", "")
            basename = os.path.basename(level_file)
            return LEVEL_NAME_MAP.get(basename, basename)
    except Exception:
        pass
    return "Unknown Level"

def get_level_from_env_config() -> str:
    """Read current game_env_config.json to find level name."""
    config_path = "gamingagent/envs/custom_07_baba_is_you/game_env_config.json"
    try:
        with open(config_path, 'r') as f:
            data = json.load(f)
        level_file = data.get("level_file", "")
        basename = os.path.basename(level_file)
        return LEVEL_NAME_MAP.get(basename, basename)
    except Exception:
        return "Unknown Level"

# ── COLLECT ALL RESULTS ───────────────────────────────────────────────────────

def collect_all_results():
    """
    Walk cache/baba_is_you/ and collect all episode results.
    
    Directory structure:
        cache/baba_is_you/{model_folder}/{timestamp}/episode_XXX_log.jsonl
        cache/baba_is_you/{model_folder}/{timestamp}/gym_run_summary.json
        cache/baba_is_you/{model_folder}/{timestamp}/agent_config.json
    
    Returns:
        dict: {model_name: {level_name: [episode_result, ...]}}
    """
    results = defaultdict(lambda: defaultdict(list))

    if not os.path.exists(CACHE_ROOT):
        print(f"ERROR: Cache directory not found: {CACHE_ROOT}")
        print("Run the experiment first, then re-run this script.")
        return results

    # Find all model folders
    model_folders = [
        d for d in os.listdir(CACHE_ROOT)
        if os.path.isdir(os.path.join(CACHE_ROOT, d))
    ]

    for model_folder in sorted(model_folders):
        model_name = model_display_name(model_folder)
        model_path = os.path.join(CACHE_ROOT, model_folder)

        # Find all timestamp run folders
        run_folders = [
            d for d in os.listdir(model_path)
            if os.path.isdir(os.path.join(model_path, d))
        ]

        for run_folder in sorted(run_folders):
            run_path = os.path.join(model_path, run_folder)

            # Determine which level this run used
            level_name = "Unknown Level"
            agent_config_path = os.path.join(run_path, "agent_config.json")
            if os.path.exists(agent_config_path):
                try:
                    with open(agent_config_path, 'r') as f:
                        agent_config = json.load(f)
                    level_file = agent_config.get("level_file", "")
                    basename = os.path.basename(str(level_file))
                    level_name = LEVEL_NAME_MAP.get(basename, basename or "Unknown Level")
                except Exception:
                    pass

            # Find all episode log files
            log_files = sorted(glob.glob(os.path.join(run_path, "episode_*_log.jsonl")))
            for log_file in log_files:
                episode_result = parse_episode_log(log_file)
                if episode_result:
                    episode_result["model"]       = model_name
                    episode_result["level"]       = level_name
                    episode_result["run_folder"]  = run_folder
                    episode_result["log_file"]    = log_file
                    results[model_name][level_name].append(episode_result)

    return results

# ── COMPUTE METRICS ───────────────────────────────────────────────────────────

def compute_metrics(episodes: list) -> dict:
    """Compute metrics from a list of episode results."""
    if not episodes:
        return {
            "n_trials":          0,
            "solve_rate":        None,
            "steps_mean":        None,
            "steps_std":         None,
            "steps_when_solved": None,
            "steps_when_failed": None,
            "rule_changes_mean": None,
            "rule_changes_std":  None,
            "invalid_action_rate": None,
        }

    won_episodes    = [e for e in episodes if e["won"]]
    failed_episodes = [e for e in episodes if not e["won"]]

    solve_rate = len(won_episodes) / len(episodes)

    steps_all    = [e["steps"] for e in episodes]
    steps_won    = [e["steps"] for e in won_episodes]
    steps_failed = [e["steps"] for e in failed_episodes]
    rule_changes = [e["rule_changes"] for e in episodes]
    invalid_rates = [
        e["invalid_actions"] / max(e["total_steps_logged"], 1)
        for e in episodes
    ]

    return {
        "n_trials":            len(episodes),
        "solve_rate":          solve_rate,
        "steps_mean":          safe_mean(steps_all),
        "steps_std":           safe_std(steps_all),
        "steps_when_solved":   safe_mean(steps_won),
        "steps_when_failed":   safe_mean(steps_failed),
        "rule_changes_mean":   safe_mean(rule_changes),
        "rule_changes_std":    safe_std(rule_changes),
        "invalid_action_rate": safe_mean(invalid_rates),
    }

# ── PRINT TABLES ──────────────────────────────────────────────────────────────

def fmt(val, decimals=2, pct=False, na="N/A"):
    if val is None:
        return na
    if pct:
        return f"{val * 100:.0f}%"
    return f"{val:.{decimals}f}"

def print_solve_rate_table(all_metrics: dict, levels: list, models: list):
    print("\n" + "="*70)
    print("RESULTS - Solve Rate (fraction of trials won)")
    print("="*70)
    col_w = 18
    header = f"{'Level':<20}" + "".join(f"{m:<{col_w}}" for m in models)
    print(header)
    print("-"*70)
    for level in levels:
        row = f"{level:<20}"
        for model in models:
            m = all_metrics.get(model, {}).get(level)
            row += f"{fmt(m['solve_rate'] if m else None, pct=True):<{col_w}}"
        print(row)

def print_steps_table(all_metrics: dict, levels: list, models: list):
    print("\n" + "="*70)
    print("RESULTS - Mean Steps per Episode (all trials)")
    print("="*70)
    col_w = 18
    header = f"{'Level':<20}" + "".join(f"{m:<{col_w}}" for m in models)
    print(header)
    print("-"*70)
    for level in levels:
        row = f"{level:<20}"
        for model in models:
            m = all_metrics.get(model, {}).get(level)
            if m and m["steps_mean"] is not None:
                row += f"{fmt(m['steps_mean'])} ± {fmt(m['steps_std']):<{col_w - 8}}"
            else:
                row += f"{'N/A':<{col_w}}"
        print(row)

def print_rule_changes_table(all_metrics: dict, levels: list, models: list):
    print("\n" + "="*70)
    print("RESULTS - Mean Rule Manipulation Events per Episode")
    print("="*70)
    col_w = 18
    header = f"{'Level':<20}" + "".join(f"{m:<{col_w}}" for m in models)
    print(header)
    print("-"*70)
    for level in levels:
        row = f"{level:<20}"
        for model in models:
            m = all_metrics.get(model, {}).get(level)
            if m and m["rule_changes_mean"] is not None:
                row += f"{fmt(m['rule_changes_mean'])} ± {fmt(m['rule_changes_std']):<{col_w - 8}}"
            else:
                row += f"{'N/A':<{col_w}}"
        print(row)

def print_invalid_action_table(all_metrics: dict, levels: list, models: list):
    print("\n" + "="*70)
    print("RESULTS - Invalid Action Rate")
    print("="*70)
    col_w = 18
    header = f"{'Level':<20}" + "".join(f"{m:<{col_w}}" for m in models)
    print(header)
    print("-"*70)
    for level in levels:
        row = f"{level:<20}"
        for model in models:
            m = all_metrics.get(model, {}).get(level)
            row += f"{fmt(m['invalid_action_rate'] if m else None, pct=True):<{col_w}}"
        print(row)

def print_episode_detail(results: dict, models: list, levels: list):
    print("\n" + "="*70)
    print("EPISODE DETAIL — Individual trial outcomes")
    print("="*70)
    for model in models:
        for level in levels:
            episodes = results.get(model, {}).get(level, [])
            if not episodes:
                continue
            print(f"\n  {model} | {level}:")
            for i, ep in enumerate(episodes):
                outcome = "WON" if ep["won"] else "LOST"
                print(f"    Trial {i+1}: {outcome} in {ep['steps']} steps | "
                      f"rule changes: {ep['rule_changes']} | "
                      f"invalid actions: {ep['invalid_actions']}")

# ── SAVE CSV ──────────────────────────────────────────────────────────────────

def save_csv(all_metrics: dict, levels: list, models: list, output_dir: str):
    os.makedirs(output_dir, exist_ok=True)
    csv_path = os.path.join(output_dir, "results_summary.csv")

    rows = []
    rows.append("model,level,n_trials,solve_rate,steps_mean,steps_std,"
                "steps_when_solved,steps_when_failed,"
                "rule_changes_mean,rule_changes_std,invalid_action_rate")

    for model in models:
        for level in levels:
            m = all_metrics.get(model, {}).get(level)
            if not m:
                continue
            rows.append(
                f"{model},{level},"
                f"{m['n_trials']},"
                f"{fmt(m['solve_rate'])},"
                f"{fmt(m['steps_mean'])},"
                f"{fmt(m['steps_std'])},"
                f"{fmt(m['steps_when_solved'])},"
                f"{fmt(m['steps_when_failed'])},"
                f"{fmt(m['rule_changes_mean'])},"
                f"{fmt(m['rule_changes_std'])},"
                f"{fmt(m['invalid_action_rate'])}"
            )

    with open(csv_path, 'w') as f:
        f.write("\n".join(rows))

    print(f"\nCSV saved to: {csv_path}")

# ── MAIN ──────────────────────────────────────────────────────────────────────

def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    print("Reading experiment logs from:", CACHE_ROOT)
    results = collect_all_results()

    if not results:
        print("\nNo results found. Have you run the experiment yet?")
        print(f"Expected logs in: {CACHE_ROOT}/{{model}}/{{timestamp}}/episode_XXX_log.jsonl")
        return

    # Determine which models and levels are present
    models = sorted(results.keys())
    levels_seen = set()
    for model_data in results.values():
        levels_seen.update(model_data.keys())

    # Sort levels in a sensible order
    level_order = list(LEVEL_NAME_MAP.values())
    levels = [l for l in level_order if l in levels_seen]
    levels += sorted(l for l in levels_seen if l not in level_order)

    print(f"\nModels found: {models}")
    print(f"Levels found: {levels}")

    # Compute metrics for every model × level combination
    all_metrics = {}
    for model in models:
        all_metrics[model] = {}
        for level in levels:
            episodes = results[model].get(level, [])
            all_metrics[model][level] = compute_metrics(episodes)
            n = len(episodes)
            won = sum(1 for e in episodes if e["won"])
            print(f"  {model} | {level}: {n} trials, {won} solved")

    # Print tables
    print_solve_rate_table(all_metrics, levels, models)
    print_steps_table(all_metrics, levels, models)
    print_rule_changes_table(all_metrics, levels, models)
    print_invalid_action_table(all_metrics, levels, models)
    print_episode_detail(results, models, levels)

    # Save CSV
    save_csv(all_metrics, levels, models, OUTPUT_DIR)

    # Save full JSON for further analysis
    json_path = os.path.join(OUTPUT_DIR, "full_metrics.json")
    with open(json_path, 'w') as f:
        json.dump(all_metrics, f, indent=2)
    print(f"Full metrics JSON saved to: {json_path}")

    print("\nDone.")

if __name__ == "__main__":
    main()
