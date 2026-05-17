# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Experiment exploring whether LLMs can solve Baba Is You puzzles, and whether chain-of-thought reasoning (DeepSeek V4 Flash thinking mode) improves performance over standard generation (DeepSeek V4 Flash non-thinking mode). Baba Is You requires multi-step rule inference and consequence tracking, which chain-of-thought is designed for.

**Model note:** `deepseek-chat` = non-thinking mode of DeepSeek V4 Flash. `deepseek-reasoner` = thinking (CoT) mode of DeepSeek V4 Flash. Both aliases scheduled for deprecation by DeepSeek on 2026-07-24.

**Stack:** Python 3.11, GamingAgent framework (custom fork), pyBaba C++/Python simulator

## Setup & Installation

Install pyBaba (from `baba-experiment/`):

```powershell
$dest = python -c "import sysconfig; print(sysconfig.get_path('purelib'))"
copy baba-is-auto\pyBaba.cp311-win_amd64.pyd $dest
```

Install Python deps (from `GamingAgent/`):

```bash
pip install -e . --no-deps   # --no-deps skips stable-retro/vizdoom/etc. which need C++ compilation
pip install anthropic openai pyyaml gym gymnasium tiktoken opencv-python pygame==2.6.1 google-generativeai google-genai psutil pyautogui PyGetWindow mss together protobuf
pip install "numpy<2.0"   # CRITICAL — NumPy 2.0 removes np.float_, breaking step logging
pip install zai-sdk grpcio aiohttp
```

Set API key before running:
```powershell
$env:DEEPSEEK_API_KEY="sk-..."
```

## Running Experiments

**Quick debug (10 steps, single trial):**
```powershell
# From GamingAgent/
copy gamingagent\envs\custom_07_baba_is_you\game_env_config_baba_is_you.json `
     gamingagent\envs\custom_07_baba_is_you\game_env_config.json

python lmgame-bench/single_agent_runner.py `
  --game_name baba_is_you --model_name deepseek-chat `
  --observation_mode text --num_runs 1 `
  --max_steps_per_episode 10 --use_perception false --level_name baba_is_you
```

**Full experiment:**
```powershell
# From GamingAgent/ — run each in a separate PowerShell window
python lmgame-bench\run_nonthinking.py   # deepseek-chat, 10 trials baba_is_you / 5 trials harder levels, 75 steps max
python lmgame-bench\run_cot.py           # deepseek-reasoner, 10 trials baba_is_you / 1 trial harder levels, 75 steps max
```

**Analyze results:**
```powershell
# From GamingAgent/
python analyze_results.py
# Output: results/baba_is_you_analysis/ (CSV + JSON); tables also printed to terminal
```

**Replay a trial for debugging:**
```powershell
# From GamingAgent/
python replay_trial.py                                        # most recent
python replay_trial.py --model deepseek_chat --episode 2     # specific (use deepseek_reason for CoT)
python replay_trial.py --grid                                 # show ASCII grid per step
```

## Architecture

### Data Flow

```
pyBaba C++ game state
    → BabaIsYouEnv (gamingagent/envs/custom_07_baba_is_you/babaIsYouEnv.py)
        Converts game state to text observation:
          - ASCII grid (one object shown per cell)
          - Full coordinate list of all physical objects
          - Full coordinate list of all word blocks
          - Active rules
          - All player positions (all YOU-controlled sprites across all active YOU rules)
    → GymEnvAdapter (gamingagent/envs/gym_env_adapter.py)
        Wraps gym env for agent; handles action mapping, logging, stuck detection
    → BaseAgent (gamingagent/agents/base_agent.py)
        Runs harness mode (harness: true in config.yaml):
        1. PerceptionModule — DISABLED (use_perception: false)
        2. MemoryModule — stores last 10 steps; generates reflection via separate LLM call (thinking=False in code; irrelevant for DeepSeek — CoT is set by the model alias, not this flag)
        3. ReasoningModule — calls LLM with game state + trajectory + reflection (thinking=True in code; irrelevant for DeepSeek — deepseek-reasoner alias already implies CoT for all calls including memory)
        NOTE: base_module prompt is never used in harness mode — only reasoning_module prompt is sent
    → Returns action string parsed by regex matching "move:" or "action:" (case insensitive)
    → Results logged to cache/baba_is_you/{model_folder}/{level}_{timestamp}/episode_NNN_log.jsonl
```

### Key Configuration Files

| File / Location | What to change |
|------|---------------|
| `lmgame-bench/run_nonthinking.py` / `run_cot.py` — `MODEL` | Model alias: `deepseek-chat` (non-thinking) or `deepseek-reasoner` (CoT) |
| `lmgame-bench/run_nonthinking.py` / `run_cot.py` — `MAX_STEPS` | Outer harness step limit — to change the step budget, update this and `max_steps_episode` in each level config to the same value; if they differ, the lower one takes effect |
| `lmgame-bench/run_nonthinking.py` / `run_cot.py` — `LEVEL_RUNS` | Which levels to run and how many trials each (e.g. remove levels or reduce trial counts to run a subset) |
| `gamingagent/configs/custom_07_baba_is_you/config.yaml` — `token_limit` | Max tokens per LLM response (default 4096); increase if model responses are being cut off |
| `gamingagent/configs/custom_07_baba_is_you/config.yaml` — `max_memory` | Steps of trajectory history sent to the model per turn (default 10) |
| `gamingagent/configs/custom_07_baba_is_you/config.yaml` | `agent.model_name` comment is ignored by the runner (explicitly skipped, line 80 of single_agent_runner.py); model is set via `MODEL` in the run scripts |
| `gamingagent/configs/custom_07_baba_is_you/module_prompts.json` | System + user prompts for all 4 modules |
| `gamingagent/envs/custom_07_baba_is_you/game_env_config.json` | **Active** level config (copied from `game_env_config_{level}.json` by Python runners via shutil.copy) |
| `gamingagent/envs/custom_07_baba_is_you/game_env_config_{level}.json` — `env_init_kwargs.max_steps_episode` | Env's internal truncation limit — to change the step budget, update this and `MAX_STEPS` in the run script to the same value; if they differ, the lower one takes effect |
| `gamingagent/envs/custom_07_baba_is_you/game_env_config_{level}.json` — `max_unchanged_steps_for_termination` | Stuck detection threshold (default 20): if the game state hash is identical for this many consecutive steps the episode is terminated early (`terminated=True` in logs, distinct from step-limit truncation) |

### 4 Test Levels (in `baba-is-auto/Resources/Maps/`)

| Level | Grid Size | Notes |
|-------|-----------|-------|
| `baba_is_you.txt` | 11×9 | Simplest; use for initial debugging |
| `out_of_reach.txt` | 22×16 | |
| `volcano.txt` | 33×18 | Largest |
| `off_limits.txt` | 24×14 | |

### 2 Models Compared

| `model_name` in config | Actual model | Type | Est. Time per Trial |
|------------------------|-------------|------|---------------------|
| `deepseek-chat` | DeepSeek V4 Flash (non-thinking) | Non-reasoning | ~3 min/trial (simple); ~55–70 min/trial (complex, 75 steps) |
| `deepseek-reasoner` | DeepSeek V4 Flash (thinking/CoT) | Chain-of-thought | ~7 min/trial (simple, ~44 s/step); ~5–6 hr/trial (complex, ~4–5 min/step) |

## pyBaba API — Critical Gotchas

Object type naming is **inverted** from what you'd expect:
- `ObjectType.BABA` = the TEXT/WORD block "BABA" (pushable, used to form rules)
- `ObjectType.ICON_BABA` = the physical BABA sprite (controllable character)

Correct API usage:
```python
game = pyBaba.Game("path/to/level.txt")
cell = game.GetMap().At(x, y)   # (0,0) = top-left
cell.HasType(pyBaba.ObjectType.BABA)   # ✓ correct
cell.HasObject(...)                    # ✗ AttributeError
game.MovePlayer(pyBaba.Direction.UP)   # returns None (binding bug — ignore return value)
play_state = game.GetPlayState()       # ✓ use this to check WON/LOST/PLAYING
# pyBaba.PlayState.WON (not .WIN), pyBaba.PlayState.LOST
```

## Results Location

```
GamingAgent/cache/baba_is_you/{model_folder}/{level}_{timestamp}/
    episode_NNN_log.jsonl     — one JSON line per step (state, action, reward, thought, reasoning_trace)
    agent_config.json         — full config snapshot (must include level_file for analyze_results.py)
    gym_run_summary.json      — high-level stats across all runs
    memory_module.json        — JSON array of per-step reflection prompts + LLM responses
    reasoning_module.json     — JSON array of per-step reasoning prompts + full LLM responses (~1MB for 10 episodes)
    observations/             — always empty in text mode; created by GymEnvAdapter on init (stores observation images in vision mode only)

model_folder uses underscores: deepseek_chat, deepseek_reason (truncated to 15 chars)
run folder format: `{level_name}_{YYYYMMDD_HHMMSS}` when `--level_name` is passed (as experiment runners do), else just `{YYYYMMDD_HHMMSS}`
```

## Prompt Architecture Notes

- **Only reasoning_module prompt is sent** — `harness: true` in config means base_module prompt is never used
- **Memory module reflection call** passes `thinking=False`; reasoning module passes `thinking=True` — but both are dead code for DeepSeek. Neither our fork nor the original upstream `deepseek_text_reasoning_completion` sends any `extra_body` or thinking-control parameter; only `model`, `messages`, `stream`, and `max_tokens` are sent. CoT is determined entirely by the model alias: `deepseek-reasoner` forces CoT on for all calls (including memory reflections); `deepseek-chat` forces it off. **Post-deprecation note (after 2026-07-24):** `deepseek-v4-flash` defaults to thinking **enabled** per DeepSeek API docs — re-running the non-thinking experiment would require adding `extra_body={"thinking": {"type": "disabled"}}` to the API call, which the current code does not do.
- **Reasoning prompt fields**: `{textual_representation}` (current state), `{game_trajectory}` (last 10 steps), `{reflection}` (LLM summary), `{processed_visual_description}` (always N/A)
- **Player position limitation**: `_get_player_position` now returns all YOU-controlled sprite positions, but the ASCII grid still only shows one object per cell when objects overlap

## Known Issues Fixed

- **NumPy 2.0**: `np.float_` removed → no logs written. Fixed: `pip install "numpy<2.0"`
- **Retro/Candy game imports**: Stripped from `single_agent_runner.py` — don't re-add
- **`zai-sdk`**: The PyPI package is `zai-sdk` (not `zai`)
- **`MovePlayer` returns None**: pyBaba Python binding returns `None` instead of `PlayState`. Fixed in `babaIsYouEnv.py` to call `game.GetPlayState()` after each move — without this, wins are never detected
- **Windows UTF-8 crash**: Game state and replay output contain Unicode characters that crash Windows cp1252 console. Fixed by `sys.stdout.reconfigure(encoding='utf-8', errors='replace')` at top of `single_agent_runner.py` and `replay_trial.py`
- **Thinking mode token limit**: `deepseek_text_reasoning_completion` capped `max_tokens` at 8192; reasoning traces can use 50k+ chars leaving no budget for the final answer. Fixed to `max(token_limit, 32768)` in `tools/serving/api_providers.py`
- **DEFEAT description wrong**: `module_prompts.json` base_module said "loses the level" — corrected to "destroys your controlled object" in base_module, and correct definition included when KEY PROPERTIES were added to reasoning_module
- **Player position single-only**: `_get_player_position` previously returned only the first YOU-controlled sprite. Fixed to return all positions across all active YOU rules as a list
- **KEY PROPERTIES missing from actual prompt**: base_module KEY PROPERTIES were never sent (harness mode skips base_module). Added full property definitions to reasoning_module prompt's Key mechanics reminders section
