#!/bin/bash
set -e

# folder z docker-compose.yaml
COMPOSE_FILE="./kafka/docker-compose.yaml"

echo "[INFO] Zatrzymywanie istniejących kontenerów..."
docker compose -f $COMPOSE_FILE down -v

if [[ "$1" == "--build" ]]; then
    echo "[INFO] Budowanie obrazów i uruchamianie..."
    docker compose -f $COMPOSE_FILE up --build -d
else
    echo "[INFO] Uruchamianie kontenerów..."
    docker compose -f $COMPOSE_FILE up -d
fi

echo "[INFO] Wszystkie usługi działają. Sprawdź 'docker ps'."
