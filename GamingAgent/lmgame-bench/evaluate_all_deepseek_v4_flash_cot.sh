#!/bin/bash
# evaluate_all_deepseek_r1.sh
# Runs all 4 Baba Is You levels x 3 trials with DeepSeek V4 Flash thinking (CoT) mode.
# Run from the GamingAgent root directory:
#   bash lmgame-bench/evaluate_all_deepseek_r1.sh
#
# Prerequisites:
#   export DEEPSEEK_API_KEY=your_key
#
# NOTE: deepseek-reasoner = thinking (CoT) mode of DeepSeek V4 Flash
#       (alias deprecated 2026/07/24; switch to deepseek-v4-flash with thinking enabled after that)
#       CoT generates ~5x more output tokens. Expect ~30s per step; full run takes 2-3 hours.

LEVELS=("baba_is_you" "out_of_reach" "volcano" "off_limits")
MODEL="deepseek-reasoner"
NUM_RUNS=3
MAX_STEPS=75
ENV_DIR="gamingagent/envs/custom_07_baba_is_you"

echo "======================================================"
echo "  MODEL: DeepSeek V4 Flash thinking/CoT (deepseek-reasoner)"
echo "  Runs per level: $NUM_RUNS"
echo "  Max steps per run: $MAX_STEPS"
echo "  NOTE: CoT ~15-30s/step; episodes end early on win or stuck detection"
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
echo "  DeepSeek R1 COMPLETE — results in cache/baba_is_you/"
echo "======================================================"
