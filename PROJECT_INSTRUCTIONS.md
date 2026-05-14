PROJECT: Baba Is You LLM Experiment
====================================
Testing LLM agents playing Baba Is You puzzles via the pyBaba simulator.
Exploring whether LLMs can solve Baba Is You puzzles, and whether
chain-of-thought reasoning improves performance on meta-rule spatial
puzzles. EXPERIMENT IS COMPLETE.

Trial counts:
  deepseek-chat (non-thinking):    10 trials baba_is_you, 5 each other level
  deepseek-reasoner (CoT/thinking): 10 trials baba_is_you, 1 each other level
  Max 75 steps per trial (set in run_nonthinking.py and run_cot.py)

EXPERIMENT DESIGN
===================================
Goal: Can LLMs play Baba Is You? Does chain-of-thought reasoning
improve performance on rule-manipulation puzzles?

Comparison: deepseek-chat (non-thinking) vs deepseek-reasoner (CoT/thinking)
  Both are DeepSeek V4 Flash — same model weights, only inference mode differs.
  NOTE: Both API aliases scheduled for deprecation 2026-07-24.

Metrics per model per level:
  - Solve rate (fraction of trials won)
  - Steps to solve (when solved)
  - Steps to failure (when not solved)
  - Rule manipulation events (word block pushes that changed active rules)



ARCHITECTURE DECISION
=====================
Native GamingAgent integration (github.com/lmgame-org/GamingAgent).
GamingAgent already handles: memory, reflection, cloud LLM API calls, logging,
multi-run orchestration, and prompt structure.


GAMINGAGENT NATIVE FORMAT
====================================
GamingAgent provides:
- Cloud LLM API calls (OpenAI-compatible, Gemini, DeepSeek, Anthropic, xAI)
- MemoryModule: rolling trajectory + LLM reflection between steps
- ReasoningModule: formats prompt with game state + trajectory + reflection
- PerceptionModule: in text mode, passes textual representation through
- Logging, multi-run orchestration, config-driven setup

Files written for this project:
  gamingagent/envs/custom_07_baba_is_you/babaIsYouEnv.py
  gamingagent/envs/custom_07_baba_is_you/game_env_config.json  (active level)
  gamingagent/envs/custom_07_baba_is_you/game_env_config_baba_is_you.json
  gamingagent/envs/custom_07_baba_is_you/game_env_config_out_of_reach.json
  gamingagent/envs/custom_07_baba_is_you/game_env_config_volcano.json
  gamingagent/envs/custom_07_baba_is_you/game_env_config_off_limits.json
  gamingagent/configs/custom_07_baba_is_you/config.yaml
  gamingagent/configs/custom_07_baba_is_you/module_prompts.json
  lmgame-bench/single_agent_runner.py  (stripped to baba_is_you only)
  lmgame-bench/run_nonthinking.py  (Python runner, deepseek-chat)
  lmgame-bench/run_cot.py          (Python runner, deepseek-reasoner)
  analyze_results.py
  replay_trial.py


MODELS & ENDPOINTS
==================
Only two models used in final experiment. Both use DeepSeek API.

deepseek-chat  [NON-REASONING, DeepSeek V4 Flash non-thinking mode]
  key env var:  DEEPSEEK_API_KEY
  NOTE: API alias scheduled for deprecation 2026-07-24. Experiment completed before deprecation.

deepseek-reasoner  [REASONING/CoT, DeepSeek V4 Flash thinking mode]
  key env var:  DEEPSEEK_API_KEY
  NOTE: API alias scheduled for deprecation 2026-07-24. Experiment completed before deprecation.
  CoT overhead: ~44 s/step on baba_is_you (~7 min/trial at ~10 steps), ~4–5 min/step on complex levels (~5–6 hr/trial at 75 steps). Non-thinking: ~13 s/step on baba_is_you (~3 min/trial), ~45–60 s/step on complex levels (~55–70 min/trial).

GPT-4o mini and other models were considered but dropped — only DeepSeek
non-thinking vs CoT was used in the final experiment.


LEVELS (4 selected)
====================
Level files are pyBaba's native numerical format.
Loaded with: pyBaba.Game(full_path_to_txt_file)

Location:
  baba-is-auto/Resources/Maps/

Level files:
  baba_is_you.txt   (11×9 grid)   ← simplest, use for initial testing
  out_of_reach.txt  (22×16 grid)
  volcano.txt       (33×18 grid)
  off_limits.txt    (24×14 grid)

LEVEL CONFIG SWAP PATTERN:
  The runner always reads game_env_config.json (no suffix).
  Python runners (run_nonthinking.py / run_cot.py) copy the level-specific file via shutil.copy before each run.
  For manual single runs, copy manually:
    copy gamingagent\envs\custom_07_baba_is_you\game_env_config_baba_is_you.json
         gamingagent\envs\custom_07_baba_is_you\game_env_config.json


CRITICAL PYBABA API FACTS
===================================================================
1. OBJECT TYPE NAMING IS INVERTED:
   ObjectType.BABA      = TEXT/WORD block "BABA" (pushable, used in rules)
   ObjectType.ICON_BABA = physical BABA sprite (the character you control)
   This applies to ALL nouns. Plain = word block. ICON_ = physical sprite.

2. CORRECT METHOD IS HasType(), NOT HasObject():
   cell.HasType(pyBaba.ObjectType.BABA)  ← correct
   cell.HasObject(...)                   ← AttributeError

3. PLAY STATE: pyBaba.PlayState.WON (not .WIN), pyBaba.PlayState.LOST

4. CELL ACCESS:
   map_obj = game.GetMap()
   cell = map_obj.At(x, y)   # x=col, y=row, (0,0)=top-left
   cell.GetTypes()            # returns list of ObjectTypes

5. MOVE: game.MovePlayer(pyBaba.Direction.UP)  # returns None (binding bug)
         Use game.GetPlayState() after each move to check WON/LOST/PLAYING

6. OBJECT TYPES IN EXPERIMENT LEVELS:
   Physical (ICON_): ICON_BABA, ICON_FLAG, ICON_ROCK, ICON_WALL, ICON_LAVA,
                     ICON_WATER, ICON_SKULL, ICON_TILE, ICON_GRASS,
                     ICON_FLOWER, ICON_EMPTY
   Word/noun blocks: BABA, FLAG, ROCK, WALL, LAVA, WATER, SKULL
   Property/verb:    IS, YOU, WIN, PUSH, STOP, DEFEAT, MELT, HOT, SINK

7. ICON_EMPTY is real but should render blank in grid display.


CONFIRMED ADAPTER METHOD SIGNATURES
=====================================
Verified by reading gym_env_adapter.py (create_agent_observation ~line 172, log_step_data ~line 213).

create_agent_observation(
    img_path=None,
    text_representation=None,
    background_info=None,
    max_memory=10
) -> Observation

log_step_data(
    agent_action_str,
    thought_process,
    reward,
    info,
    terminated,
    truncated,
    time_taken_s,
    perf_score,
    agent_observation,
    reasoning_trace=None   # CoT scratchpad, optional
)

BabaIsYouEnv.step() returns:
    (agent_observation, reward, terminated, truncated, info_dict, perf_score)

BabaIsYouEnv.reset() returns:
    (Observation, info_dict)


PROMPT FORMAT (module_prompts.json)
=====================================
Modeled on 2048 and Sokoban prompt patterns. Key requirements:
- Format enforcement in BOTH system_prompt AND end of user prompt
- Concrete thought:/move: examples in reasoning_module prompt
- "IMPORTANT — FORMAT YOUR RESPONSE EXACTLY LIKE THIS:" at end of prompts
- Reflection capped at 80 words explicitly
- base_module prompt is NEVER sent in harness mode (harness: true) — only reasoning_module prompt is used

Valid actions: "up", "down", "left", "right" (exact lowercase strings)
The adapter does case-insensitive matching via .lower() so "UP" works too,
but prompts should enforce lowercase for safety.


KNOWN BUGS & FIXES (ALL RESOLVED)
==================================
1. NUMPY BUG — broke log writing:
   `np.float_` was removed in NumPy 2.0; step logging silently failed.
   Fixed: install numpy<2.0 (pip install "numpy<2.0").

2. REASONING_EFFORT BUG — broke gpt-4o-mini calls:
   GamingAgent passed reasoning_effort=high to gpt-4o-mini which doesn't
   support that parameter (only o-series models do).
   Fixed: reasoning_effort key removed entirely from config.yaml.
   Setting to null was NOT sufficient — key had to be absent.
   Does not affect DeepSeek models (different code path in api_providers.py).

3. HARNESS MODE ACTION UNPACKING BUG:
   In harness mode, agent.get_action() returns (action_dict, updated_observation)
   NOT (action_str, thought_str) as in non-harness mode.
   action_dict has keys: 'action', 'thought', 'raw_response_str', 'reasoning_trace'
   The updated_observation must be kept for the next step.
   Fixed: in single_agent_runner.py run_game_episode().

4. RETRO/CANDY CRUSH IMPORT BUG — broke startup on Windows:
   Original single_agent_runner.py imported all game environments including
   stable-retro (requires C++ compiler on Windows) and tile_match_gym.
   Fixed: stripped single_agent_runner.py to import only BabaIsYouEnv.

5. ZAI-SDK BUG — wrong package installed:
   The correct PyPI package for DeepSeek is 'zai-sdk', not 'zai'.
   The 'zai' package is a dummy placeholder with wrong API.
   Fixed: pip uninstall zai && pip install zai-sdk (one-time setup).

6. GEMINI RATE LIMIT (not applicable — Gemini was dropped):
   AI Studio free tier hits rate limits almost immediately (20 req/day,
   ~25 calls per 10-step trial). Gemini was dropped from the experiment;
   only DeepSeek models were used.

7. ANALYZE_RESULTS.PY LEVEL DETECTION:
   Script reads level_file from agent_config.json in each run folder and uses
   os.path.basename() to look it up in LEVEL_NAME_MAP — so even hardcoded absolute
   paths in archived logs resolve correctly. Confirmed working in final experiment.

8. MISSING DEPENDENCIES (not in pyproject.toml):
   These must be installed manually after pip install -e .:
   pip install zai-sdk grpcio aiohttp opencv-python tiktoken pygame==2.6.1
   Also: pip install "numpy<2.0"  (must be after the above; NumPy 2.0 breaks step logging)
   Note: pip install -e . will show build errors for stable-retro, vizdoom, tile_match_gym, etc.
   Those are upstream GamingAgent packages not needed for this experiment — safe to ignore.


HOW TO RUN
==========
IMPORTANT: Always run from GamingAgent ROOT directory, not from lmgame-bench/.
All relative paths in config files and scripts resolve from the root.

Set API key (Windows PowerShell):
  $env:DEEPSEEK_API_KEY="sk-..."

Debug trial (10 steps, baba_is_you level):
  [First copy the level config:]
  copy gamingagent\envs\custom_07_baba_is_you\game_env_config_baba_is_you.json
       gamingagent\envs\custom_07_baba_is_you\game_env_config.json

  python lmgame-bench/single_agent_runner.py \
    --game_name baba_is_you \
    --model_name deepseek-chat \
    --observation_mode text \
    --num_runs 1 \
    --max_steps_per_episode 10 \
    --use_perception false \
    --level_name baba_is_you

Full experiment (from PowerShell):
  python lmgame-bench\run_nonthinking.py   # deepseek-chat
  python lmgame-bench\run_cot.py           # deepseek-reasoner

Analyze results after experiment:
  python analyze_results.py

Replay a trial step by step:
  python replay_trial.py --list                              # see available runs
  python replay_trial.py                                     # most recent trial
  python replay_trial.py --model deepseek_chat --episode 2  # non-thinking
  python replay_trial.py --model deepseek_reason --episode 2 # CoT (folder truncated to 15 chars)


INSTALLATION REQUIREMENTS
==========================
Environment: Python 3.11 (currently using system Python, not conda)
GamingAgent install: pip install -e . --no-deps from GamingAgent root
  (--no-deps required on Windows — pyproject.toml includes stable-retro/vizdoom which have no pre-built wheels)
  Then manually: pip install anthropic openai pyyaml gym gymnasium tiktoken opencv-python pygame==2.6.1 google-generativeai google-genai psutil pyautogui PyGetWindow mss together protobuf zai-sdk grpcio aiohttp
  And: pip install "numpy<2.0"  (must be last — overrides any numpy 2.x that was pulled in)
pyBaba: copy baba-is-auto\pyBaba.cp311-win_amd64.pyd to site-packages
  $dest = python -c "import sysconfig; print(sysconfig.get_path('purelib'))"
  copy baba-is-auto\pyBaba.cp311-win_amd64.pyd $dest

Confirmed working (pre-experiment):
  python -c "import pyBaba; print('ok')"          → ok
  python -c "from gamingagent.envs.gym_env_adapter import GymEnvAdapter; print('ok')" → ok
  DEEPSEEK_API_KEY env var                         → set and used


CURRENT STATE (as of May 2026)
==============================
EXPERIMENT COMPLETE. All trials run and logged.
Results in: GamingAgent/cache/baba_is_you/{model_folder}/{level}_{timestamp}/
Analysis output in: GamingAgent/results/baba_is_you_analysis/

Note: Prompt corrections were made post-experiment and do not affect logged data:
  - DEFEAT property description corrected
  - Player positions now returns all YOU-controlled sprites (not just first)
  - KEY PROPERTIES added to reasoning_module prompt (was missing from actual sent prompt)


FILES IN THIS PROJECT
=====================
GamingAgent core (read before modifying anything):
  gamingagent/envs/gym_env_adapter.py
  gamingagent/envs/custom_02_sokoban/sokobanEnv.py  (implementation template)
  gamingagent/agents/base_agent.py
  gamingagent/modules/core_module.py
  gamingagent/modules/memory_module.py
  gamingagent/modules/reasoning_module.py
  lmgame-bench/single_agent_runner.py

Baba Is You specific (the files we wrote):
  gamingagent/envs/custom_07_baba_is_you/babaIsYouEnv.py
  gamingagent/envs/custom_07_baba_is_you/game_env_config.json
  gamingagent/configs/custom_07_baba_is_you/config.yaml
  gamingagent/configs/custom_07_baba_is_you/module_prompts.json

Analysis scripts:
  analyze_results.py   (reads all logs, outputs CSV + JSON; prints 4 tables to terminal)
  replay_trial.py      (step-by-step readable replay of a trial)

Experiment runners (from GamingAgent root, PowerShell):
  lmgame-bench/run_nonthinking.py
  lmgame-bench/run_cot.py

Level files (pyBaba format, do not edit):
  baba-is-auto/Resources/Maps/baba_is_you.txt
  baba-is-auto/Resources/Maps/out_of_reach.txt
  baba-is-auto/Resources/Maps/volcano.txt
  baba-is-auto/Resources/Maps/off_limits.txt
