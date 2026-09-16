#!/bin/bash
set -euo pipefail
cd -- "$(dirname -- "$0")"
exec .venv/bin/gym_super_mario_bros \
  --env SuperMarioBros-1-1-v0 --mode human --actionspace simple
