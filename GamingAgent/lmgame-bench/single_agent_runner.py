import argparse
import os
import json
import datetime
import time
import numpy as np
import yaml
from typing import Any, Dict
import sys
import re
import random

# Force UTF-8 output so Unicode game-state characters don't crash on Windows cp1252
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

import gymnasium as gym

from gamingagent.agents.base_agent import BaseAgent
from gamingagent.modules import PerceptionModule, ReasoningModule
from tools.utils import draw_grid_on_image

# Baba Is You only — all other game imports removed
from gamingagent.envs.custom_07_baba_is_you.babaIsYouEnv import BabaIsYouEnv

game_config_mapping = {
    "baba_is_you": "custom_07_baba_is_you",
}

def str_to_bool(v):
    if isinstance(v, bool):
        return v
    if v.lower() in ('yes', 'true', 't', 'y', '1'):
        return True
    elif v.lower() in ('no', 'false', 'f', 'n', '0'):
        return False
    else:
        raise argparse.ArgumentTypeError('Boolean value expected.')

def parse_arguments(defaults_map=None, argv_to_parse=None):
    parser = argparse.ArgumentParser(description="Run GamingAgent for Baba Is You.")
    parser.add_argument("--game_name", type=str, default=None)
    parser.add_argument("--config_root_dir", type=str, default="gamingagent/configs")
    parser.add_argument("--model_name", type=str, default="gemini-2.5-flash")
    parser.add_argument("--harness", action="store_true")
    parser.add_argument("--multiagent_arg", type=str, default="single", choices=["single", "multi"])
    parser.add_argument("--num_runs", type=int, default=1)
    parser.add_argument("--observation_mode", type=str, default="text", choices=["vision", "text", "both"])
    parser.add_argument("--max_memory", type=int, default=10)
    parser.add_argument("--use_reflection", type=str_to_bool, default=True)
    parser.add_argument("--use_perception", type=str_to_bool, default=False)
    parser.add_argument("--use_summary", type=str_to_bool, default=False)
    parser.add_argument("--token_limit", type=int, default=4096)
    parser.add_argument("--max_steps_per_episode", type=int, default=150)
    parser.add_argument("--use_custom_prompt", action="store_true")
    parser.add_argument("--scaffolding", type=str, default=None)
    parser.add_argument("--seed", type=int, default=None)
    parser.add_argument("--modal_url", type=str, default=None)
    parser.add_argument("--vllm_url", type=str, default=None)
    parser.add_argument("--level_name", type=str, default=None)

    if argv_to_parse:
        args = parser.parse_args(argv_to_parse)
    else:
        args = parser.parse_args()

    args._cli_values = {}
    for action in parser._actions:
        if action.dest != 'help':
            args._cli_values[action.dest] = getattr(args, action.dest)

    args._yaml_defaults = defaults_map if defaults_map else {}

    if defaults_map:
        for param_name, yaml_value in defaults_map.items():
            if yaml_value is not None:
                argv_to_check = argv_to_parse if argv_to_parse is not None else sys.argv
                param_on_cli = (f"--{param_name.replace('_', '-')}" in argv_to_check
                                or f"--{param_name}" in argv_to_check)
                if not param_on_cli:
                    if param_name == "model_name":
                        continue
                    cli_value = getattr(args, param_name)
                    if cli_value != yaml_value:
                        setattr(args, param_name, yaml_value)

    return args

def create_environment(game_name_arg: str,
                       obs_mode_arg: str,
                       config_dir_name_for_env_cfg: str,
                       cache_dir_for_adapter: str,
                       harness: bool = False,
                       multiagent_arg: str = "single"):
    """Creates and returns the Baba Is You environment."""

    env_specific_config_path = os.path.join(
        "gamingagent/envs", config_dir_name_for_env_cfg, "game_env_config.json"
    )
    env_init_params = {}

    assert multiagent_arg == "single", "This script only supports single-agent games."

    if not os.path.exists(env_specific_config_path):
        print(f"ERROR: Config file not found at {env_specific_config_path}")
        return None

    if game_name_arg == "baba_is_you":
        with open(env_specific_config_path, 'r') as f:
            env_specific_config = json.load(f)
            env_init_kwargs = env_specific_config.get('env_init_kwargs', {})
            env_init_params['level_file'] = env_specific_config.get('level_file', '')
            env_init_params['max_steps_episode'] = env_init_kwargs.get('max_steps_episode', 150)
            env_init_params['max_stuck_steps_for_adapter'] = env_specific_config.get('max_unchanged_steps_for_termination', 20)

        print(f"Initializing environment: {game_name_arg} with params: {env_init_params}")
        env = BabaIsYouEnv(
            level_file=env_init_params.get('level_file'),
            max_steps_episode=env_init_params.get('max_steps_episode'),
            game_name_for_adapter=game_name_arg,
            observation_mode_for_adapter=obs_mode_arg,
            agent_cache_dir_for_adapter=cache_dir_for_adapter,
            game_specific_config_path_for_adapter=env_specific_config_path,
            max_stuck_steps_for_adapter=env_init_params.get('max_stuck_steps_for_adapter'),
        )
        return env
    else:
        print(f"ERROR: Game '{game_name_arg}' is not supported in this runner.")
        return None

def run_game_episode(agent: BaseAgent, game_env: gym.Env, episode_id: int, args: argparse.Namespace):
    """Run a single episode of the game."""
    agent_observation, last_info = game_env.reset(
        max_memory=args.max_memory, seed=args.seed, episode_id=episode_id
    )
    if args.seed is not None:
        args.seed += 1

    total_reward_for_episode = 0.0
    total_perf_score_for_episode = 0.0
    final_step_num = 0

    for step_num in range(args.max_steps_per_episode):
        final_step_num = step_num + 1
        game_env.render()

        step_start_time = time.time()
        action_result = agent.get_action(agent_observation)
        time_taken_s = time.time() - step_start_time

        # Harness mode returns (action_dict, updated_observation)
        # Non-harness mode returns (action_str, thought_str)
        reasoning_trace = None
        if isinstance(action_result, tuple) and len(action_result) == 2:
            first, second = action_result
            if isinstance(first, dict):
                # Harness mode: first is action dict, second is updated observation
                agent_action_str = first.get('action', '')
                thought_process = first.get('thought', '')
                reasoning_trace = first.get('reasoning_trace', None)
                agent_observation = second  # update observation for next step
            else:
                # Non-harness mode: first is action string, second is thought
                agent_action_str = first
                thought_process = second
        elif isinstance(action_result, dict):
            agent_action_str = action_result.get('action', '')
            thought_process = action_result.get('thought', '')
            reasoning_trace = action_result.get('reasoning_trace', None)
        else:
            agent_action_str = str(action_result)
            thought_process = ''

        print(f"\n--- Episode {episode_id}, Step {final_step_num} ---")
        print(f"  Action: {agent_action_str}")
        if thought_process:
            thought_str = str(thought_process) if not isinstance(thought_process, str) else thought_process
            preview = thought_str[:300]
            print(f"  Thought: {preview}{'...' if len(thought_str) > 300 else ''}")

        agent_observation, reward, terminated, truncated, last_info, current_step_perf_score = game_env.step(
            agent_action_str, thought_process, time_taken_s, reasoning_trace
        )

        total_reward_for_episode += reward
        total_perf_score_for_episode += current_step_perf_score

        won = last_info.get('won', False)
        rules = last_info.get('active_rules', [])
        print(f"  Reward: {reward:.2f} | Won: {won} | Rules: {rules}")

        if terminated or truncated:
            result = "WON" if won else ("TRUNCATED" if truncated else "LOST")
            print(f"\n  Episode {episode_id} ended: {result} after {final_step_num} steps")
            break

    final_score = 1.0 if last_info.get('won', False) else 0.0

    if hasattr(game_env, 'adapter') and game_env.adapter:
        game_env.adapter.record_episode_result(
            episode_id=episode_id,
            score=final_score,
            steps=final_step_num,
            total_reward=total_reward_for_episode,
            total_perf_score=total_perf_score_for_episode,
        )
    return

def main():
    prelim_parser = argparse.ArgumentParser(add_help=False)
    prelim_parser.add_argument("--game_name", type=str, required=True)
    prelim_parser.add_argument("--config_root_dir", type=str, default="gamingagent/configs")
    pre_args, remaining_argv = prelim_parser.parse_known_args()

    config_dir_name = game_config_mapping.get(pre_args.game_name.lower())

    if not config_dir_name:
        print(f"ERROR: '{pre_args.game_name}' not in game_config_mapping. Only 'baba_is_you' is supported.")
        sys.exit(1)

    defaults_from_yaml = {}
    if pre_args.game_name:
        defaults_from_yaml['game_name'] = pre_args.game_name

    config_file_path = os.path.join(pre_args.config_root_dir, config_dir_name, "config.yaml")
    if os.path.exists(config_file_path):
        try:
            with open(config_file_path, 'r') as f:
                loaded_yaml = yaml.safe_load(f)
                if loaded_yaml:
                    if loaded_yaml.get('game_env'):
                        game_env_config_yaml = loaded_yaml['game_env']
                        defaults_from_yaml['num_runs'] = game_env_config_yaml.get('num_runs')
                        defaults_from_yaml['max_steps_per_episode'] = game_env_config_yaml.get('max_steps')
                        defaults_from_yaml['seed'] = game_env_config_yaml.get('seed')
                    if loaded_yaml.get('agent'):
                        agent_config_yaml = loaded_yaml['agent']
                        defaults_from_yaml['token_limit'] = agent_config_yaml.get('token_limit')
                        defaults_from_yaml['harness'] = agent_config_yaml.get('harness', False)
                        defaults_from_yaml['model_name'] = agent_config_yaml.get('model_name')
                        defaults_from_yaml['observation_mode'] = agent_config_yaml.get('observation_mode')
                        defaults_from_yaml['use_custom_prompt'] = agent_config_yaml.get('use_custom_prompt')
                        defaults_from_yaml['use_reflection'] = agent_config_yaml.get('use_reflection')
                        defaults_from_yaml['use_perception'] = agent_config_yaml.get('use_perception')
                        defaults_from_yaml['use_summary'] = agent_config_yaml.get('use_summary')
                        defaults_from_yaml['scaffolding'] = agent_config_yaml.get('scaffolding')
                        if agent_config_yaml.get('modules'):
                            if agent_config_yaml['modules'].get('memory_module'):
                                defaults_from_yaml['max_memory'] = agent_config_yaml['modules']['memory_module'].get('max_memory')
                    defaults_from_yaml = {k: v for k, v in defaults_from_yaml.items() if v is not None}
        except Exception as e:
            print(f"Warning: Could not load config from {config_file_path}: {e}")
    else:
        print(f"Info: Config file {config_file_path} not found. Using CLI args and built-in defaults.")

    args = parse_arguments(defaults_map=defaults_from_yaml, argv_to_parse=remaining_argv)

    if not args.game_name:
        print("ERROR: game_name is missing.")
        sys.exit(2)

    custom_modules_for_agent = None
    if args.harness:
        print("Initializing agent in HARNESS mode.")
        custom_modules_for_agent = {
            "perception_module": PerceptionModule,
            "reasoning_module": ReasoningModule,
        }
    else:
        print("Initializing agent in NON-HARNESS (BaseModule) mode.")

    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    folder_name = f"{args.level_name}_{timestamp}" if args.level_name else timestamp
    runner_log_dir_base = os.path.join(
        "cache", args.game_name,
        args.model_name.replace("-", "_")[:15],
        folder_name
    )
    os.makedirs(runner_log_dir_base, exist_ok=True)
    print(f"Cache directory: {runner_log_dir_base}")

    agent_prompts_config_path = os.path.join(
        args.config_root_dir, config_dir_name, "module_prompts.json"
    )
    if not os.path.isfile(agent_prompts_config_path):
        print(f"Warning: module_prompts.json not found at {agent_prompts_config_path}. Using default prompts.")
        agent_prompts_config_path = None

    agent = BaseAgent(
        game_name=args.game_name,
        model_name=args.model_name,
        config_path=agent_prompts_config_path,
        harness=args.harness,
        use_custom_prompt=args.use_custom_prompt,
        max_memory=args.max_memory,
        use_reflection=args.use_reflection,
        use_perception=args.use_perception,
        use_summary=args.use_summary,
        custom_modules=custom_modules_for_agent,
        observation_mode=args.observation_mode,
        scaffolding=None,
        cache_dir=runner_log_dir_base,
        vllm_url=args.vllm_url,
        modal_url=args.modal_url,
        token_limit=args.token_limit,
    )

    game_env = create_environment(
        game_name_arg=args.game_name,
        obs_mode_arg=args.observation_mode,
        config_dir_name_for_env_cfg=config_dir_name,
        cache_dir_for_adapter=runner_log_dir_base,
        harness=args.harness,
        multiagent_arg=args.multiagent_arg,
    )

    if game_env is None:
        print("Failed to create game environment. Exiting.")
        return

    # Patch level_file into agent_config.json (needed by analyze_results.py)
    agent_config_path = os.path.join(runner_log_dir_base, "agent_config.json")
    env_config_path = os.path.join("gamingagent/envs", config_dir_name, "game_env_config.json")
    if os.path.exists(agent_config_path) and os.path.exists(env_config_path):
        with open(env_config_path) as _f:
            _env_cfg = json.load(_f)
        with open(agent_config_path) as _f:
            _agent_cfg = json.load(_f)
        _agent_cfg['level_file'] = _env_cfg.get('level_file', '')
        with open(agent_config_path, 'w') as _f:
            json.dump(_agent_cfg, _f, indent=2)

    for i in range(args.num_runs):
        run_id = i + 1
        run_game_episode(agent, game_env, run_id, args)
        if i < args.num_runs - 1:
            print("Cooldown for 1 second before next run...")
            time.sleep(1)

    overall_stat_summary = {}
    if hasattr(game_env, 'adapter') and game_env.adapter:
        overall_stat_summary = game_env.adapter.finalize_and_save_summary(vars(args))
    else:
        print("Warning: game_env.adapter not found. Cannot finalize summary.")

    game_env.close()

    print("\n" + "="*30 + " Overall Summary " + "="*30)
    print(f"Game: {args.game_name} | Model: {args.model_name} | Runs: {args.num_runs}")
    if overall_stat_summary:
        for key, stats in overall_stat_summary.items():
            key_title = key.replace("_", " ").title()
            if stats["mean"] is not None:
                print(f"  {key_title}: mean={stats['mean']:.2f}, std={stats['std']:.2f}, min={stats['min']:.2f}, max={stats['max']:.2f}")
            else:
                print(f"  {key_title}: N/A")
    else:
        print("No summary data available.")

if __name__ == "__main__":
    main()