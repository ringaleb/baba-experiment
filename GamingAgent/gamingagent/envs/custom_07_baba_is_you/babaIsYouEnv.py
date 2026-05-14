"""
BabaIsYouEnv — Baba Is You wrapped as a GamingAgent-compatible gym.Env.

Place this file at:
  GamingAgent/gamingagent/envs/custom_07_baba_is_you/babaIsYouEnv.py

Modeled on sokobanEnv.py. Uses pyBaba as the simulator backend.
Text-only observation mode (no image renderer needed).
"""

import gymnasium as gym
import numpy as np
import os
from typing import Any, Dict, Tuple, Optional, List

import pyBaba

from gamingagent.envs.gym_env_adapter import GymEnvAdapter
from gamingagent.modules.core_module import Observation
from gymnasium.spaces import Discrete, Box


# ─── OBJECT MAPS (from environment.py reference) ──────────────────────────────
# CRITICAL: pyBaba naming is INVERTED from what you'd expect:
#   ObjectType.BABA      = the TEXT/WORD block "BABA" (pushable tile)
#   ObjectType.ICON_BABA = the physical BABA sprite (the character you control)

OBJECT_NAMES = {
    # Physical sprites (ICON_ types) → plain display name
    pyBaba.ObjectType.ICON_BABA:   "BABA",
    pyBaba.ObjectType.ICON_FLAG:   "FLAG",
    pyBaba.ObjectType.ICON_ROCK:   "ROCK",
    pyBaba.ObjectType.ICON_WALL:   "WALL",
    pyBaba.ObjectType.ICON_LAVA:   "LAVA",
    pyBaba.ObjectType.ICON_WATER:  "WATER",
    pyBaba.ObjectType.ICON_SKULL:  "SKULL",
    pyBaba.ObjectType.ICON_TILE:   "TILE",
    pyBaba.ObjectType.ICON_GRASS:  "GRASS",
    pyBaba.ObjectType.ICON_FLOWER: "FLOWER",
    pyBaba.ObjectType.ICON_EMPTY:  "EMPTY",
    # Word/text blocks (plain types) → TEXT_ prefixed name
    pyBaba.ObjectType.BABA:        "TEXT_BABA",
    pyBaba.ObjectType.FLAG:        "TEXT_FLAG",
    pyBaba.ObjectType.ROCK:        "TEXT_ROCK",
    pyBaba.ObjectType.WALL:        "TEXT_WALL",
    pyBaba.ObjectType.LAVA:        "TEXT_LAVA",
    pyBaba.ObjectType.WATER:       "TEXT_WATER",
    pyBaba.ObjectType.SKULL:       "TEXT_SKULL",
    pyBaba.ObjectType.IS:          "TEXT_IS",
    pyBaba.ObjectType.YOU:         "TEXT_YOU",
    pyBaba.ObjectType.WIN:         "TEXT_WIN",
    pyBaba.ObjectType.PUSH:        "TEXT_PUSH",
    pyBaba.ObjectType.STOP:        "TEXT_STOP",
    pyBaba.ObjectType.DEFEAT:      "TEXT_DEFEAT",
    pyBaba.ObjectType.MELT:        "TEXT_MELT",
    pyBaba.ObjectType.HOT:         "TEXT_HOT",
    pyBaba.ObjectType.SINK:        "TEXT_SINK",
}

# Noun word-block types — used for rule scanning (plain ObjectType, NOT ICON_)
NOUN_TYPES = {
    pyBaba.ObjectType.BABA:  "BABA",
    pyBaba.ObjectType.FLAG:  "FLAG",
    pyBaba.ObjectType.ROCK:  "ROCK",
    pyBaba.ObjectType.WALL:  "WALL",
    pyBaba.ObjectType.LAVA:  "LAVA",
    pyBaba.ObjectType.WATER: "WATER",
    pyBaba.ObjectType.SKULL: "SKULL",
}

# Property word-block types — used for rule scanning
PROPERTY_TYPES = {
    pyBaba.ObjectType.YOU:    "YOU",
    pyBaba.ObjectType.WIN:    "WIN",
    pyBaba.ObjectType.PUSH:   "PUSH",
    pyBaba.ObjectType.STOP:   "STOP",
    pyBaba.ObjectType.DEFEAT: "DEFEAT",
    pyBaba.ObjectType.MELT:   "MELT",
    pyBaba.ObjectType.HOT:    "HOT",
    pyBaba.ObjectType.SINK:   "SINK",
}

# Short display labels for ASCII grid (padded to 5 chars)
DISPLAY_NAMES = {
    pyBaba.ObjectType.ICON_BABA:   "BABA",
    pyBaba.ObjectType.ICON_FLAG:   "FLAG",
    pyBaba.ObjectType.ICON_ROCK:   "ROCK",
    pyBaba.ObjectType.ICON_WALL:   "WALL",
    pyBaba.ObjectType.ICON_LAVA:   "LAVA",
    pyBaba.ObjectType.ICON_WATER:  "WATR",
    pyBaba.ObjectType.ICON_SKULL:  "SKUL",
    pyBaba.ObjectType.ICON_TILE:   "TILE",
    pyBaba.ObjectType.ICON_GRASS:  "GRSS",
    pyBaba.ObjectType.ICON_FLOWER: "FLWR",
    pyBaba.ObjectType.ICON_EMPTY:  "",
    pyBaba.ObjectType.BABA:        "[BAB]",
    pyBaba.ObjectType.FLAG:        "[FLG]",
    pyBaba.ObjectType.ROCK:        "[RCK]",
    pyBaba.ObjectType.WALL:        "[WLL]",
    pyBaba.ObjectType.LAVA:        "[LAV]",
    pyBaba.ObjectType.WATER:       "[WTR]",
    pyBaba.ObjectType.SKULL:       "[SKL]",
    pyBaba.ObjectType.IS:          "[IS] ",
    pyBaba.ObjectType.YOU:         "[YOU]",
    pyBaba.ObjectType.WIN:         "[WIN]",
    pyBaba.ObjectType.PUSH:        "[PSH]",
    pyBaba.ObjectType.STOP:        "[STP]",
    pyBaba.ObjectType.DEFEAT:      "[DFT]",
    pyBaba.ObjectType.MELT:        "[MLT]",
    pyBaba.ObjectType.HOT:         "[HOT]",
    pyBaba.ObjectType.SINK:        "[SNK]",
}

# Maps action integer index → pyBaba.Direction
DIRECTION_MAP = {
    0: pyBaba.Direction.UP,
    1: pyBaba.Direction.DOWN,
    2: pyBaba.Direction.LEFT,
    3: pyBaba.Direction.RIGHT,
}

# Maps noun name → physical ICON_ type (for player position lookup)
NOUN_TO_ICON = {
    "BABA":  pyBaba.ObjectType.ICON_BABA,
    "FLAG":  pyBaba.ObjectType.ICON_FLAG,
    "ROCK":  pyBaba.ObjectType.ICON_ROCK,
    "WALL":  pyBaba.ObjectType.ICON_WALL,
    "LAVA":  pyBaba.ObjectType.ICON_LAVA,
    "WATER": pyBaba.ObjectType.ICON_WATER,
    "SKULL": pyBaba.ObjectType.ICON_SKULL,
}


# ─── PYBA API HELPERS ─────────────────────────────────────────────────────────

def _get_active_rules(game: pyBaba.Game) -> List[str]:
    """
    Scans the grid for NOUN + IS + PROPERTY sequences (horizontal and vertical).
    Returns a list of rule strings like ["BABA IS YOU", "FLAG IS WIN"].
    Uses plain ObjectType (not ICON_) for noun/property word blocks.
    """
    map_obj = game.GetMap()
    width  = map_obj.GetWidth()
    height = map_obj.GetHeight()
    rules  = []

    def cell_match(x, y, type_dict):
        if x < 0 or y < 0 or x >= width or y >= height:
            return None
        cell = map_obj.At(x, y)
        for obj_type, name in type_dict.items():
            try:
                if cell.HasType(obj_type):
                    return name
            except Exception:
                pass
        return None

    def cell_has_is(x, y):
        try:
            return map_obj.At(x, y).HasType(pyBaba.ObjectType.IS)
        except Exception:
            return False

    # Horizontal: NOUN at (x,y), IS at (x+1,y), PROPERTY at (x+2,y)
    for y in range(height):
        for x in range(width - 2):
            noun = cell_match(x,     y, NOUN_TYPES)
            prop = cell_match(x + 2, y, PROPERTY_TYPES)
            if noun and prop and cell_has_is(x + 1, y):
                rules.append(f"{noun} IS {prop}")

    # Vertical: NOUN at (x,y), IS at (x,y+1), PROPERTY at (x,y+2)
    for y in range(height - 2):
        for x in range(width):
            noun = cell_match(x, y,     NOUN_TYPES)
            prop = cell_match(x, y + 2, PROPERTY_TYPES)
            if noun and prop and cell_has_is(x, y + 1):
                rules.append(f"{noun} IS {prop}")

    return list(set(rules))


def _get_player_position(game: pyBaba.Game, active_rules: List[str]) -> List[Tuple[int, int]]:
    """
    Returns list of (x, y) positions for all YOU-controlled objects.
    Multiple nouns can be YOU simultaneously (e.g. BABA IS YOU and ROCK IS YOU).
    """
    you_nouns = [rule.replace(" IS YOU", "") for rule in active_rules if rule.endswith(" IS YOU")]
    if not you_nouns:
        return []

    map_obj = game.GetMap()
    width  = map_obj.GetWidth()
    height = map_obj.GetHeight()
    positions = []

    for you_noun in you_nouns:
        icon_type = NOUN_TO_ICON.get(you_noun)
        if icon_type is None:
            continue
        for y in range(height):
            for x in range(width):
                try:
                    if map_obj.At(x, y).HasType(icon_type):
                        positions.append((x, y))
                except Exception:
                    pass

    return positions


def _get_objects_by_position(game: pyBaba.Game) -> Dict[Tuple[int, int], List[str]]:
    """Returns dict mapping (x, y) → list of object name strings."""
    map_obj = game.GetMap()
    width  = map_obj.GetWidth()
    height = map_obj.GetHeight()
    result = {}
    for y in range(height):
        for x in range(width):
            cell = map_obj.At(x, y)
            names = []
            for obj_type, name in OBJECT_NAMES.items():
                try:
                    if cell.HasType(obj_type):
                        names.append(name)
                except Exception:
                    pass
            if names:
                result[(x, y)] = names
    return result


# ─── ENVIRONMENT CLASS ────────────────────────────────────────────────────────

class BabaIsYouEnv(gym.Env):
    """
    Baba Is You as a GamingAgent gym environment.

    action_space:  Discrete(4) — up, down, left, right
    observation:   Observation object (text representation, text-only mode)
    """

    metadata = {'render_modes': [], 'render_fps': 0}

    def __init__(
        self,
        level_file: str,
        max_steps_episode: int = 150,
        game_name_for_adapter: str = "baba_is_you",
        observation_mode_for_adapter: str = "text",
        agent_cache_dir_for_adapter: str = "cache/baba_is_you/default_run",
        game_specific_config_path_for_adapter: str = (
            "gamingagent/envs/custom_07_baba_is_you/game_env_config.json"
        ),
        max_stuck_steps_for_adapter: Optional[int] = 20,
    ):
        self.level_file         = level_file
        self.max_steps_episode  = max_steps_episode
        self.render_mode        = None

        # pyBaba game object — set in reset()
        self.game: Optional[pyBaba.Game] = None

        # Episode tracking
        self.num_env_steps            = 0
        self.current_reward_last_step = 0.0
        self.won_this_episode         = False
        self.word_block_push_events   = 0   # rule manipulation event counter

        # Discrete(4): 0=up, 1=down, 2=left, 3=right
        self.action_space = Discrete(4)

        # Placeholder — adapter returns Observation objects, not raw arrays.
        # Actual grid shape is determined at runtime from the level file.
        self.observation_space = Box(low=0, high=255, shape=(1,), dtype=np.uint8)

        # GymEnvAdapter — handles logging, stuck detection, observation packaging
        self.adapter = GymEnvAdapter(
            game_name=game_name_for_adapter,
            observation_mode=observation_mode_for_adapter,
            agent_cache_dir=agent_cache_dir_for_adapter,
            game_specific_config_path=game_specific_config_path_for_adapter,
            max_steps_for_stuck=max_stuck_steps_for_adapter,
        )

    # ── RESET ─────────────────────────────────────────────────────────────────

    def reset(
        self,
        *,
        seed: Optional[int] = None,
        options: Optional[Dict[str, Any]] = None,
        max_memory: Optional[int] = 10,
        episode_id: int = 1,
    ) -> Tuple[Observation, Dict[str, Any]]:
        super().reset(seed=seed)

        # Load the level fresh from disk
        if not os.path.exists(self.level_file):
            raise FileNotFoundError(
                f"[BabaIsYouEnv] Level file not found: {self.level_file}"
            )
        self.game = pyBaba.Game(self.level_file)

        # Reset episode state
        self.num_env_steps            = 0
        self.current_reward_last_step = 0.0
        self.won_this_episode         = False
        self.word_block_push_events   = 0

        self.adapter.reset_episode(episode_id)

        text_repr = self._build_text_representation()
        agent_observation = self.adapter.create_agent_observation(
            img_path=None,
            text_representation=text_repr,
            max_memory=max_memory,
        )

        info_dict = self._get_info()
        return agent_observation, info_dict

    # ── STEP ──────────────────────────────────────────────────────────────────

    def step(
        self,
        agent_action_str: Optional[str],
        thought_process: str = "",
        time_taken_s: float = 0.0,
        reasoning_trace: Optional[str] = None,
    ) -> Tuple[Observation, float, bool, bool, Dict[str, Any], float]:
        self.adapter.increment_step()

        # Capture pre-step rules for rule-change detection
        pre_rules = set(_get_active_rules(self.game))

        # Map string action ("up" / "down" / "left" / "right") → int index
        env_action_idx = self.adapter.map_agent_action_to_env_action(agent_action_str)

        reward     = -0.1   # small step penalty to encourage efficiency
        terminated = False
        truncated  = False

        if env_action_idx is not None and self.action_space.contains(env_action_idx):
            direction  = DIRECTION_MAP[env_action_idx]
            self.game.MovePlayer(direction)
            play_state = self.game.GetPlayState()  # MovePlayer binding returns None; use GetPlayState()

            if play_state == pyBaba.PlayState.WON:
                reward               = 10.0
                terminated           = True
                self.won_this_episode = True
            elif play_state == pyBaba.PlayState.LOST:
                reward     = -10.0
                terminated = True
        else:
            print(f"[BabaIsYouEnv] Invalid/unrecognised action: '{agent_action_str}'")

        self.num_env_steps += 1
        truncated = self.num_env_steps >= self.max_steps_episode

        # Detect rule-manipulation events (word blocks were pushed)
        post_rules = set(_get_active_rules(self.game))
        if pre_rules != post_rules:
            self.word_block_push_events += 1

        self.current_reward_last_step = reward

        info_dict          = self._get_info()
        current_perf_score = self.calculate_perf_score(reward, info_dict)

        text_repr = self._build_text_representation()
        agent_observation = self.adapter.create_agent_observation(
            img_path=None,
            text_representation=text_repr,
        )

        final_terminated, final_truncated = self.adapter.verify_termination(
            agent_observation, terminated, truncated
        )

        self.adapter.log_step_data(
            agent_action_str=agent_action_str,
            thought_process=thought_process,
            reasoning_trace=reasoning_trace,
            reward=reward,
            info=info_dict,
            terminated=final_terminated,
            truncated=final_truncated,
            time_taken_s=time_taken_s,
            perf_score=current_perf_score,
            agent_observation=agent_observation,
        )

        return agent_observation, reward, final_terminated, final_truncated, info_dict, current_perf_score

    # ── HELPERS ───────────────────────────────────────────────────────────────

    def _build_text_representation(self) -> str:
        """
        Builds the full text description of the current game state.
        This is what the LLM sees as its primary observation.
        """
        if self.game is None:
            return "Game not initialised."

        map_obj = self.game.GetMap()
        width   = map_obj.GetWidth()
        height  = map_obj.GetHeight()

        active_rules  = _get_active_rules(self.game)
        player_pos    = _get_player_position(self.game, active_rules)
        objects_by_xy = _get_objects_by_position(self.game)

        # ── ASCII grid ──────────────────────────────────────────────────────
        cell_w = 6
        # Column header
        grid_lines = [""]
        header = "     " + "".join(f"{x:<{cell_w+1}}" for x in range(width))
        grid_lines.append(header)
        grid_lines.append("     " + "-" * (width * (cell_w + 1)))

        for y in range(height):
            row = f"  {y:<3}"
            for x in range(width):
                cell  = map_obj.At(x, y)
                label = ""
                for obj_type, name in DISPLAY_NAMES.items():
                    try:
                        if cell.HasType(obj_type):
                            label = name.strip()
                            break
                    except Exception:
                        pass
                row += "|" + label.center(cell_w)
            row += "|"
            grid_lines.append(row)

        grid_str = "\n".join(grid_lines)

        # ── Physical objects & word blocks lists ────────────────────────────
        word_blocks     = {}
        physical_objects = {}
        for (x, y), names in sorted(objects_by_xy.items()):
            words     = [n for n in names if n.startswith("TEXT_")]
            physicals = [n for n in names if not n.startswith("TEXT_") and n != "EMPTY"]
            if words:
                word_blocks[(x, y)] = words
            if physicals:
                physical_objects[(x, y)] = physicals

        phys_lines = []
        for (x, y), names in sorted(physical_objects.items()):
            phys_lines.append(f"  ({x},{y}): {', '.join(names)}")

        word_lines = []
        for (x, y), names in sorted(word_blocks.items()):
            word_lines.append(f"  ({x},{y}): {', '.join(names)}")

        rules_text = (
            "\n".join(f"  - {r}" for r in sorted(active_rules))
            if active_rules else "  (none — you cannot move!)"
        )

        player_text = (
            ", ".join(f"({x}, {y})" for x, y in player_pos) if player_pos
            else "Unknown — check if any X IS YOU rule is active"
        )

        text = f"""=== BABA IS YOU — CURRENT GAME STATE ===
Grid: {width} cols × {height} rows  |  col=x (right+), row=y (down+)

VISUAL GRID ([] = word/text block, plain = physical sprite, blank = empty):
{grid_str}

PHYSICAL OBJECTS (sprites you walk into, push, or need to reach):
{chr(10).join(phys_lines) if phys_lines else "  (none)"}

WORD BLOCKS (pushable text tiles that form rules):
{chr(10).join(word_lines) if word_lines else "  (none)"}

ACTIVE RULES (word blocks currently forming valid NOUN IS PROPERTY lines):
{rules_text}

YOUR CONTROLLED OBJECT (IS YOU) is at: {player_text}
Rule changes this episode: {self.word_block_push_events}
"""
        return text

    def _get_info(self) -> Dict[str, Any]:
        active_rules = _get_active_rules(self.game) if self.game else []
        player_pos   = _get_player_position(self.game, active_rules) if self.game else None
        return {
            "num_env_steps":         self.num_env_steps,
            "active_rules":          active_rules,
            "player_position":       player_pos,
            "won":                   self.won_this_episode,
            "word_block_push_events": self.word_block_push_events,
            "reward_last_step":      self.current_reward_last_step,
        }

    def calculate_perf_score(self, reward: float, info: Dict[str, Any]) -> float:
        """
        Performance score for this episode:
          1.0 if the level has been won (regardless of step count)
          0.0 otherwise
        This is the primary solve_rate metric.
        """
        return 1.0 if self.won_this_episode else 0.0

    # ── GYM BOILERPLATE ───────────────────────────────────────────────────────

    def render(self):
        # Text-only mode — no graphical renderer implemented.
        return None

    def close(self):
        self.adapter.close_log_file()
        print("[BabaIsYouEnv] Closed.")
