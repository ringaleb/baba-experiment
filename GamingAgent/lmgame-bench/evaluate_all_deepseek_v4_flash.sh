#!/bin/bash
# evaluate_all_deepseek_v4_flash.sh
# Runs all 4 Baba Is You levels x 5 trials with DeepSeek V4 Flash non-thinking mode.
# Run from the GamingAgent root directory:
#   bash lmgame-bench/evaluate_all_deepseek_v4_flash.sh
#
# Prerequisites:
#   export DEEPSEEK_API_KEY=your_key
#
# NOTE: deepseek-chat = non-thinking mode of DeepSeek V4 Flash
#       (alias deprecated 2026/07/24; switch to deepseek-v4-flash after that)

LEVELS=("baba_is_you" "out_of_reach" "volcano" "off_limits")
MODEL="deepseek-chat"
NUM_RUNS=5
MAX_STEPS=75
ENV_DIR="gamingagent/envs/custom_07_baba_is_you"

echo "======================================================"
echo "  MODEL: DeepSeek V4 Flash non-thinking (deepseek-chat)"
echo "  Runs per level: $NUM_RUNS"
echo "  Max steps per run: $MAX_STEPS"
echo "  NOTE: episodes end early on win or 20-step stuck detection"
echo "======================================================"

for LEVEL in "${LEVELS[@]}"; do
    echo ""
    echo "  LEVEL: $LEVEL"
    echo "------------------------------------------------------"

    cp "${ENV_DIR}/game_env_config_${LEVEL}.json" "${ENV_DIR}/game_env_config.json"

    cmd //c python lmgame-bench/single_agent_runner.py \
        --game_name baba_is_you \
        --model_name "$MODEL" \
        --observation_mode text \
        --num_runs $NUM_RUNS \
        --max_steps_per_episode $MAX_STEPS \
        --use_perception false \
        --use_reflection true

    echo "  Done: $LEVEL"
done

echo ""
echo "======================================================"
echo "  DeepSeek V3 COMPLETE — results in cache/baba_is_you/"
echo "======================================================"
