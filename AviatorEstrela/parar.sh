#!/bin/bash
# Para o servio em background

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PID_FILE="$SCRIPT_DIR/aviator_service.pid"
XVFB_PID_FILE="$SCRIPT_DIR/xvfb.pid"

cd "$SCRIPT_DIR"

echo "Parando Aviator ML Intelligence..."

# Parar servio Python
if [ -f "$PID_FILE" ]; then
    PID=$(cat "$PID_FILE")
    if ps -p "$PID" > /dev/null 2>&1; then
        echo "  Parando processo $PID..."
        kill "$PID" 2>/dev/null
        sleep 2

        # Force kill se ainda estiver rodando
        if ps -p "$PID" > /dev/null 2>&1; then
            echo "  Forando encerramento..."
            kill -9 "$PID" 2>/dev/null
        fi

        rm -f "$PID_FILE"
        echo "  ? Servio parado"
    else
        echo "  Processo no est rodando"
        rm -f "$PID_FILE"
    fi
else
    echo "  Arquivo PID no encontrado"

    # Tentar encontrar processo pelo nome
    PIDS=$(pgrep -f "aviator_service2.py")
    if [ -n "$PIDS" ]; then
        echo "  Encontrados processos: $PIDS"
        kill $PIDS 2>/dev/null
        echo "  ? Processos parados"
    fi
fi

# Parar Xvfb se existir
if [ -f "$XVFB_PID_FILE" ]; then
    XVFB_PID=$(cat "$XVFB_PID_FILE")
    if ps -p "$XVFB_PID" > /dev/null 2>&1; then
        echo "  Parando Xvfb (PID: $XVFB_PID)..."
        kill "$XVFB_PID" 2>/dev/null
        rm -f "$XVFB_PID_FILE"
    else
        rm -f "$XVFB_PID_FILE"
    fi
fi

echo ""
echo "? Servio parado com sucesso"
echo ""
