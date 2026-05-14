#!/bin/bash
# evaluate_all.sh
# Runs all 4 Baba Is You levels x 2 models x N trials each.
# Run from the GamingAgent root directory:
#   bash lmgame-bench/evaluate_all.sh
#
# Prerequisites:
#   export DEEPSEEK_API_KEY=your_key

LEVELS=("baba_is_you" "out_of_reach" "volcano" "off_limits")
MAX_STEPS=150
ENV_DIR="gamingagent/envs/custom_07_baba_is_you"

# Trial counts: 5 for non-thinking, 3 for CoT (output tokens are expensive)
declare -A MODEL_RUNS
MODEL_RUNS["deepseek-chat"]=5
MODEL_RUNS["deepseek-reasoner"]=3

MODELS=("deepseek-chat" "deepseek-reasoner")

for LEVEL in "${LEVELS[@]}"; do
    echo ""
    echo "======================================================"
    echo "  LEVEL: $LEVEL"
    echo "======================================================"

    cp "${ENV_DIR}/game_env_config_${LEVEL}.json" "${ENV_DIR}/game_env_config.json"

    for MODEL in "${MODELS[@]}"; do
        NUM_RUNS=${MODEL_RUNS[$MODEL]}
        echo ""
        echo "  Model: $MODEL (${NUM_RUNS} trials)"
        echo "------------------------------------------------------"

        python lmgame-bench/single_agent_runner.py \
            --game_name baba_is_you \
            --model_name "$MODEL" \
            --observation_mode text \
            --num_runs $NUM_RUNS \
            --max_steps_per_episode $MAX_STEPS \
            --use_perception false \
            --use_reflection true

        echo "  Done: $MODEL on $LEVEL"
    done
done

echo ""
echo "======================================================"
echo "  ALL RUNS COMPLETE"
echo "  Results are in: cache/baba_is_you/"
echo "======================================================"
