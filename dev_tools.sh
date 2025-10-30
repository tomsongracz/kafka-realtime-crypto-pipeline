#!/bin/bash

# dev_tools.sh - Narzędzie do uruchamiania testów i lintingu w projekcie
# Użycie:
#   ./dev_tools.sh test     # Uruchamia wszystkie testy (pytest)
#   ./dev_tools.sh lint     # Uruchamia linting (black + flake8)
#   ./dev_tools.sh          # Pokazuje pomoc

set -e  # Wyjście z błędem przy pierwszej błędnej komendzie

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"  # Przejdź do katalogu projektu

show_help() {
    echo "Dostępne komendy:"
    echo "  test  - Uruchamia testy (pytest tests/ -v)"
    echo "  lint  - Uruchamia linting i formatowanie (black --check + flake8)"
    echo "  help  - Pokazuje tę pomoc"
    echo ""
    echo "Przykład:"
    echo "  ./dev_tools.sh test"
}

case "$1" in
    "test")
        echo "[INFO] Uruchamianie testów..."
        pytest tests/ -v --tb=short
        echo "[SUCCESS] Testy zakończone pomyślnie!"
        ;;
    "lint")
        echo "[INFO] Uruchamianie lintingu (black + flake8)..."
        echo "[INFO] Sprawdzanie formatowania (black --check)..."
        black . --check --diff  # --check: tylko sprawdź, --diff: pokaż różnice
        echo "[INFO] Sprawdzanie błędów (flake8)..."
        flake8 . --max-line-length=200 --extend-ignore=F401 # Domyślny dla black
        echo "[SUCCESS] Linting zakończony pomyślnie! Kod jest zgodny."
        ;;
    "help"|"")
        show_help
        ;;
    *)
        echo "[ERROR] Nieznana komenda: $1"
        show_help
        exit 1
        ;;
esac