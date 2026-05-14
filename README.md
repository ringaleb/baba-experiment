# LLM Puzzle Solving: Chain-of-Thought vs. Standard Generation on Baba Is You

An experiment exploring whether large language models can solve *Baba Is You* puzzles, and whether chain-of-thought reasoning improves performance over standard text generation.

**Question:** Does DeepSeek V4 Flash in thinking mode (chain-of-thought) outperform DeepSeek V4 Flash in non-thinking mode on a puzzle game that requires multi-step rule inference?

---

## Key Results

| Level | Grid | DeepSeek V4 Flash | DeepSeek V4 Flash (CoT) |
|-------|------|:-----------------:|:-----------------------:|
| Baba Is You | 11×9 | **10/10** (100%) | **10/10** (100%) |
| Out of Reach | 22×16 | 0/5 (0%) | 0/1 (0%) |
| Volcano | 33×18 | 0/5 (0%) | 0/1 (0%) |
| Off Limits | 24×14 | 0/5 (0%) | 0/1 (0%) |

Both models solved the simplest level perfectly and failed all harder levels. CoT produced slightly fewer steps on the easy level (10.0 vs 11.9 mean) and fewer coordinate errors, but neither model attempted the rule manipulation required to solve harder levels. Full per-trial summaries are in [baba_is_you_old_cache_2/experiment_summaries.md](baba_is_you_old_cache_2/experiment_summaries.md).

---

## Repository Structure

```
baba-experiment/
├── baba-is-auto/                  C++ Baba Is You simulator + Python bindings
│   ├── pyBaba.cp311-win_amd64.pyd Pre-compiled Python extension (Python 3.11, Windows x64)
│   ├── Sources/baba-is-auto/      Core game logic (Game.cpp, Map.cpp, etc.)
│   ├── Includes/baba-is-auto/     Headers
│   ├── Extensions/
│   │   ├── BabaPython/            pybind11 Python bindings source
│   │   ├── BabaGUI/               pygame GUI (play.py, replay_gui.py, and more)
│   │   └── BabaRL/                reinforcement learning extensions (unused in this project)
│   ├── Resources/Maps/            4 level files (.txt)
│   └── Libraries/                 pybind11, doctest (vendored)
│
├── GamingAgent/                   Custom fork of GamingAgent framework
│   ├── lmgame-bench/
│   │   ├── run_nonthinking.py     Runs all non-thinking trials
│   │   ├── run_cot.py             Runs all CoT trials
│   │   └── single_agent_runner.py Low-level runner (used by above)
│   ├── gamingagent/
│   │   ├── agents/base_agent.py   Harness: perception → memory → reasoning
│   │   ├── envs/custom_07_baba_is_you/
│   │   │   ├── babaIsYouEnv.py    Game environment wrapper
│   │   │   └── game_env_config*.json   Per-level configs
│   │   └── configs/custom_07_baba_is_you/
│   │       ├── config.yaml        Agent settings
│   │       └── module_prompts.json   All LLM prompts
│   ├── tools/serving/api_providers.py   LLM API calls
│   ├── analyze_results.py         Post-run analysis → CSV + JSON files + terminal tables
│   ├── replay_trial.py            Terminal step-by-step replay
│   ├── credentials.example.sh     API key template (copy → credentials.sh)
│   └── cache/                     Trial logs (gitignored by GamingAgent/.gitignore)
│
├── baba_is_you_old_cache_1/       Pilot/debug runs (all 4 levels, bare-timestamp folders)
├── baba_is_you_old_cache_2/       Final experiment data
│   ├── deepseek_chat/             Non-thinking results (10 baba_is_you + 5 each harder level)
│   ├── deepseek_reason/           CoT results (10 baba_is_you + 1 each harder level)
│   ├── experiment_summaries.md    Step-by-step readable summaries per trial (609 lines)
│   └── results/                   analyze_results.py output (CSV + JSON)
│
├── CLAUDE.md                      Developer notes for Claude Code
└── PROJECT_INSTRUCTIONS.md        Detailed internal implementation notes
```

---

## Prerequisites

- **Python 3.11** (the compiled `.pyd` binary is version-locked to 3.11)
- **Windows x64** (the pre-compiled binary targets `win_amd64`; other platforms need a rebuild — see below)
- **CMake 3.31.6+** and **Visual Studio 2022** (only needed if rebuilding pyBaba)
- A **DeepSeek API key** from [platform.deepseek.com](https://platform.deepseek.com) (only needed to run new experiments)

---

## Installation

### 1. Install Python dependencies

Run all commands from `GamingAgent/`:

```powershell
pip install -e . --no-deps
pip install anthropic openai pyyaml gym gymnasium tiktoken opencv-python pygame==2.6.1 google-generativeai google-genai psutil pyautogui PyGetWindow mss together protobuf
pip install "numpy<2.0"
pip install zai-sdk grpcio aiohttp
```

> **Note:** `--no-deps` skips packages in the upstream `pyproject.toml` that require C++ compilation on Windows (stable-retro, vizdoom, etc.) and are not needed for this experiment. The second line manually installs everything that is needed.
>
> `numpy<2.0` is required — NumPy 2.0 removes `np.float_`, which breaks step logging.

### 2. Set your API key

```powershell
# PowerShell (recommended on Windows)
$env:DEEPSEEK_API_KEY = "sk-..."
```

`credentials.example.sh` is a template you can copy to `credentials.sh` and fill in. `credentials.sh` is gitignored. Note: `.sh` files use `export VAR=value` syntax and must be sourced in bash/WSL/Git Bash — they cannot be dot-sourced in PowerShell.

### 3. Install pyBaba

The pre-compiled extension for Windows Python 3.11 is included in the repo. Install it by copying it into site-packages:

```powershell
# From baba-experiment/
$dest = python -c "import sysconfig; print(sysconfig.get_path('purelib'))"
copy baba-is-auto\pyBaba.cp311-win_amd64.pyd $dest
```

If you are on a different OS or Python version, you need to build from source — see [Rebuilding pyBaba](#rebuilding-pybaba) below.

---

## Running Experiments

All commands run from `GamingAgent/`.

### Quick test (single trial, 10 steps)

```powershell
copy gamingagent\envs\custom_07_baba_is_you\game_env_config_baba_is_you.json `
     gamingagent\envs\custom_07_baba_is_you\game_env_config.json

python lmgame-bench\single_agent_runner.py `
  --game_name baba_is_you `
  --model_name deepseek-chat `
  --observation_mode text `
  --num_runs 1 `
  --max_steps_per_episode 10 `
  --use_perception false `
  --level_name baba_is_you
```

### Full experiment (reproduces all results)

**Run both in parallel** — open two separate PowerShell windows and launch one in each. They write to different output folders and do not interfere with each other.

```powershell
# Window 1 — Non-thinking: 10 trials on baba_is_you, 5 trials each on harder levels, 75 steps max
python lmgame-bench\run_nonthinking.py
```

```powershell
# Window 2 — CoT: 10 trials on baba_is_you, 1 trial each on harder levels, 75 steps max
python lmgame-bench\run_cot.py
```

> **Time estimates (from actual runs):** Non-thinking ~3 min/trial on baba_is_you (~13 s/step), ~55–70 min/trial on complex levels (~45–60 s/step at 75 steps). CoT ~7 min/trial on baba_is_you (~44 s/step), ~5–6 hr/trial on complex levels (~4–5 min/step at 75 steps). Full non-thinking run ≈ 12 hr; full CoT run ≈ 18 hr.

> **Model alias deprecation:** `deepseek-chat` and `deepseek-reasoner` are scheduled for deprecation by DeepSeek on 2026-07-24. The experiment was completed before that date. To re-run after deprecation, use `deepseek-v4-flash` as the model name — but note that `deepseek-v4-flash` **defaults to thinking mode enabled**. The current code sends no `extra_body` to the API, so: for the non-thinking run you would need to add `extra_body={"thinking": {"type": "disabled"}}` to `deepseek_text_reasoning_completion` in `tools/serving/api_providers.py`; for the CoT run you can omit `extra_body` (thinking is on by default). The `model_name` flag in `run_nonthinking.py` / `run_cot.py` is where to change the model alias. **This project has only been tested with `deepseek-chat` and `deepseek-reasoner` — other aliases or models are untested.**
>
> **Prompt version note:** The prompts in `gamingagent/configs/custom_07_baba_is_you/module_prompts.json` reflect post-experiment corrections (DEFEAT property description fixed, KEY PROPERTIES block added to the reasoning prompt). The archived experiment data in `baba_is_you_old_cache_2/` was collected with an earlier version of the prompts before these corrections were applied. Re-running with the current prompts may produce different results.

Results are written to `cache/baba_is_you/{model}/{level}_{timestamp}/` (e.g. `deepseek_chat/baba_is_you_20260509_221619/`).

---

## Analyzing Results

From `GamingAgent/`:

```powershell
python analyze_results.py
```

Reads everything in `cache/baba_is_you/` and outputs to `results/baba_is_you_analysis/`:

- `results_summary.csv` — solve rate, steps, rule changes, invalid action rate per model/level
- `full_metrics.json` — nested per-episode metrics

Also prints four formatted tables to the terminal.

---

## Replaying a Trial (Terminal)

> **Prefer the GUI replay** (`replay_gui.py` in `baba-is-auto/Extensions/BabaGUI/`) — it shows the actual game board and is much easier to follow. The terminal replay is useful when you want to inspect thought text or pipe output for scripting.

From `GamingAgent/`:

```powershell
python replay_trial.py                              # most recent trial
python replay_trial.py --list                       # list all available runs
python replay_trial.py --model deepseek_chat --episode 2
python replay_trial.py --model deepseek_reason --episode 1 --grid --thought
python replay_trial.py --log path\to\episode_001_log.jsonl
```

Flags:
- `--grid` — show ASCII grid at each step
- `--thought` — show full thought text (default truncates to 300 chars)

---

## Archived Experiment Data

Two sets of cached runs are included in this repository.

> **Note on prompts:** Both caches were run before post-experiment corrections were applied to `module_prompts.json`. The current file reflects fixes made after all runs completed — the DEFEAT property description was incorrect and the KEY PROPERTIES block was missing from the reasoning prompt during all runs. Neither cache used the corrected prompts.

### baba_is_you_old_cache_1/ — Pilot runs

Early development and debug runs collected while the prompt and environment were still being tuned. Run folders use bare timestamps (no level prefix) because `--level_name` was not yet being passed to the runner. All four levels are present.

| Model | Runs |
|-------|------|
| `deepseek_chat` | 4 run folders, 5 episodes each (all four levels) |
| `deepseek_reason` | 4 run folders, 1–3 episodes each (all four levels) |

### baba_is_you_old_cache_2/ — Final experiment data

The complete final experiment run. Run folders include the level name prefix (e.g. `baba_is_you_20260509_221619`). This is the data the Key Results table is drawn from.

| Model | baba_is_you | out_of_reach | volcano | off_limits |
|-------|:-----------:|:------------:|:-------:|:----------:|
| `deepseek_chat` | 10 episodes | 5 episodes | 5 episodes | 5 episodes |
| `deepseek_reason` | 10 episodes | 1 episode | 1 episode | 1 episode |

Also contains:
- `experiment_summaries.md` — 609-line step-by-step readable summary of every trial
- `results/baba_is_you_analysis/results_summary.csv` — solve rate, steps, rule changes, invalid action rate per model/level
- `results/baba_is_you_analysis/full_metrics.json` — nested per-episode metrics

---

## GUI Tools

All commands run from `baba-is-auto/Extensions/BabaGUI/`.

### Interactive play

```powershell
python play.py                                              # default: out_of_reach
python play.py ../../Resources/Maps/baba_is_you.txt        # simplest level
python play.py ../../Resources/Maps/volcano.txt
python play.py ../../Resources/Maps/off_limits.txt
```

Controls: arrow keys to move, **R** to restart, **Escape** to quit.

### GUI replay of a recorded trial

```powershell
# Example from archived experiment data
python replay_gui.py ../../../baba_is_you_old_cache_2/deepseek_chat/baba_is_you_20260509_221619/episode_002_log.jsonl

# General form
python replay_gui.py <path_to_episode_log.jsonl>
```

Controls: **Space** to pause/resume, **R** to restart, **Escape** to quit. Replays at 5 steps/second.

---

## Levels

| File | Grid | Difficulty | Notes |
|------|------|-----------|-------|
| `baba_is_you.txt` | 11×9 | Simple | Both models solved 100%. Straightforward path to FLAG IS WIN. |
| `out_of_reach.txt` | 22×16 | Complex | Requires pushing a rock into water (ROCK IS SINK interaction). |
| `volcano.txt` | 33×18 | Complex | BABA IS MELT + LAVA IS HOT active. Must manipulate word blocks to survive. |
| `off_limits.txt` | 24×14 | Complex | SKULL IS DEFEAT hazards. Requires creative rule changes to reach flag. |

---

## Rebuilding pyBaba

Only needed if you're on a different OS, Python version, or have modified the C++ source.

**Requirements:** CMake 3.31.6+, Visual Studio 2022 (Windows), or GCC/Clang (Linux/Mac).

```powershell
# From baba-is-auto/
cmake -B build -S . -DPYTHON_EXECUTABLE="C:\Path\To\python.exe"
cmake --build build --config Release --target pyBaba

# Copy the built extension to where the scripts expect it
copy build\lib\Release\pyBaba.cp311-win_amd64.pyd pyBaba.cp311-win_amd64.pyd
```

On Linux/Mac the output file will be `pyBaba.cpython-311-x86_64-linux-gnu.so` or similar — copy that to `baba-is-auto/` and the GUI scripts will find it automatically (they prepend `baba-is-auto/` to `sys.path`).

---

## Architecture Notes

### Data flow

```
pyBaba C++ game state
  → BabaIsYouEnv          Converts to text: ASCII grid + object coords + active rules
  → GymEnvAdapter         Action mapping, stuck detection, step logging
  → BaseAgent (harness)
      MemoryModule         Stores last 10 steps; reflection via separate LLM call (thinking=False — irrelevant for DeepSeek; CoT is set by the model alias, not this flag)
      ReasoningModule      Main LLM call (thinking=True — irrelevant for DeepSeek; deepseek-reasoner alias already implies CoT)
  → Action string parsed by regex ("move:" or "action:")
  → Logged to cache/{model}/{level}_{timestamp}/episode_NNN_log.jsonl
```

### Prompt architecture

All prompts are in `gamingagent/configs/custom_07_baba_is_you/module_prompts.json`. Four modules are defined, but only two are active per step:

- **`reasoning_module`** — the only prompt actually sent for move decisions. `harness: true` in `config.yaml` means `base_module` is never used.
- **`memory_module` (reflection)** — a separate LLM call made before the main reasoning call; produces a brief reflection on recent steps that is injected into the reasoning prompt.
- **`base_module`** — never sent in harness mode; present in the file for non-harness debugging only.
- **`perception_module`** — defined but not instantiated (`use_perception: false`); its output placeholder `{processed_visual_description}` is always filled with "N/A".

The reasoning prompt receives four substitution fields: `{textual_representation}` (current game state), `{game_trajectory}` (last 10 steps), `{reflection}` (memory module output), and `{processed_visual_description}` (always N/A).

### pyBaba naming convention (inverted from intuition)

```python
pyBaba.ObjectType.BABA      # the TEXT/WORD block "BABA" — pushable, forms rules
pyBaba.ObjectType.ICON_BABA # the physical BABA sprite — the controllable character
```

### Key implementation files

| File | Purpose |
|------|---------|
| `baba-is-auto/Sources/baba-is-auto/Games/Game.cpp` | Move logic, HOT/MELT, SINK semantics, NOUN IS NOUN, rule parsing |
| `gamingagent/envs/custom_07_baba_is_you/babaIsYouEnv.py` | Gym environment, text observation builder |
| `gamingagent/configs/custom_07_baba_is_you/module_prompts.json` | All LLM prompts |
| `tools/serving/api_providers.py` | DeepSeek API calls; `max_tokens` set to 32768 minimum for CoT token budget |

---

## Modifications to Upstream Codebases

This project is built on two upstream projects, both modified for this experiment. Here is what changed from the originals.

### baba-is-auto (upstream: [utilforever/baba-is-auto](https://github.com/utilforever/baba-is-auto))

The original simulator was missing several game mechanics and had no Python GUI. The following were added:

**C++ engine changes:**

| File | Change |
|------|--------|
| `Sources/baba-is-auto/Games/Game.cpp` | Added `ApplyNounIsNoun()` — transforms all icon sprites when a NOUN IS NOUN rule is active (e.g. ROCK IS FLAG turns all rock sprites into flags). Called at end of `ParseRules()`. |
| `Sources/baba-is-auto/Games/Game.cpp` | Added HOT/MELT destruction logic in `ProcessMove()` — MELT objects are destroyed on contact with HOT objects and vice versa. PUSH on either object overrides destruction (the object is pushed instead). |
| `Sources/baba-is-auto/Games/Game.cpp` | Fixed SINK semantics in `ProcessMove()` — the original combined SINK and DEFEAT into one branch that only removed the mover. Fixed to separate the two: SINK now also removes the SINK object at the destination (both objects are consumed), while DEFEAT only removes the mover. |
| `Sources/baba-is-auto/Games/Game.cpp` | Added self-HOT+MELT check in `CheckPlayState()` — objects that are simultaneously HOT and MELT destroy themselves when rules change. |
| `Sources/baba-is-auto/Rules/RuleManager.cpp` | Fixed `HasProperty()` to skip text/word block types — in the original, rules like `WALL IS STOP` also applied STOP to the `[WALL]` word block itself, making it impossible to push. Fixed by adding an early `continue` for any type where `IsTextType()` is true before looking up rules. |
| `Sources/baba-is-auto/Rules/RuleManager.cpp` / `.hpp` | Added `GetAllRules()` — exposes the full rule list, needed by `ApplyNounIsNoun`. |
| `Includes/baba-is-auto/Games/Game.hpp` | Added `ApplyNounIsNoun()` declaration. |

**BabaGUI — extended for this project:**

The upstream repo includes `Extensions/BabaGUI/` with `main.py`, `config.py`, `sprites.py`, `action.txt`, and the `sprites/` asset folder. Changes made for this project:

| File | Change |
|------|--------|
| `main.py` | Changed hardcoded level from `off_limits_bug.txt` → `off_limits.txt` |
| `play.py` | **Added** — interactive player; load any level via CLI arg, arrow keys to move, R to restart, win/lose overlay, render-priority pass ordering |
| `replay_gui.py` | **Added** — GUI replay of recorded agent trials from JSONL logs; Space to pause/resume, R to restart |

`config.py` and `sprites.py` are unchanged from upstream.

All BabaGUI scripts prepend `baba-is-auto/` to `sys.path` so they pick up the locally built `pyBaba.pyd` rather than any globally installed version.

---

### GamingAgent (upstream: [lmgame-org/GamingAgent](https://github.com/lmgame-org/GamingAgent))

All Baba Is You integration was written from scratch on top of the existing agent harness.

**Files written for this project:**

| File | Purpose |
|------|---------|
| `gamingagent/envs/custom_07_baba_is_you/babaIsYouEnv.py` | Full gym environment: wraps pyBaba, builds text observations, detects win/lose |
| `gamingagent/envs/custom_07_baba_is_you/game_env_config_*.json` | Per-level configs with level file path and action mapping |
| `gamingagent/configs/custom_07_baba_is_you/config.yaml` | Agent configuration (harness mode, memory, token limit) |
| `gamingagent/configs/custom_07_baba_is_you/module_prompts.json` | All LLM prompts for all four agent modules |
| `lmgame-bench/run_nonthinking.py` | Runs full non-thinking experiment (all levels, all trials) |
| `lmgame-bench/run_cot.py` | Runs full CoT experiment |
| `analyze_results.py` | Post-run analysis pipeline → CSV + JSON files; summary tables printed to terminal |
| `replay_trial.py` | Terminal step-by-step trial replay with optional ASCII grid |
| `credentials.example.sh` | API key template (copy to `credentials.sh`, which is gitignored) |

**Modifications to existing upstream files:**

| File | Change |
|------|--------|
| `lmgame-bench/single_agent_runner.py` | Stripped all non-Baba game imports (Retro, Candy Crush) that caused import errors on Windows; added `sys.stdout.reconfigure(encoding='utf-8', errors='replace')` to prevent crashes on Unicode game-state output |
| `tools/serving/api_providers.py` | Fixed `deepseek_text_reasoning_completion` to use `max(token_limit, 32768)` — original cap of 8192 left no budget for the answer after a long reasoning trace |

---

## Known Issues / Gotchas

- **NumPy 2.0 breaks logging** — `np.float_` was removed. Use `pip install "numpy<2.0"`.
- **`MovePlayer` returns None** — the pybind11 binding doesn't return `PlayState`. Always call `game.GetPlayState()` after moving.
- **`game.GetMap()` returns a reference** (not a copy) — the `Map` object exposes `AddObject`, `RemoveObject`, and `Reset` in the Python binding, so mutations are reflected in the game state. These bypass rule evaluation and play-state updates. Never mutate the map directly; use `game.MovePlayer()` for gameplay.
- **Windows UTF-8** — the terminal must support UTF-8 or some observation output will be garbled. `single_agent_runner.py` handles this with `sys.stdout.reconfigure(encoding='utf-8', errors='replace')`.
- **CoT token budget** — `deepseek-reasoner` reasoning traces can be 50k+ chars. The API call uses `max_tokens=32768` minimum to leave room for the final answer.

---

## Credits

- **baba-is-auto** C++ simulator by [Chris Ohk (utilforever)](https://github.com/utilforever/baba-is-auto)
- **GamingAgent** framework ([lmgame-org/GamingAgent](https://github.com/lmgame-org/GamingAgent)) — base harness for LLM game agents
- *Baba Is You* game by [Arvi Teikari (Hempuli)](https://hempuli.com/)
- Documentation written with [Claude Code](https://claude.ai/code)
