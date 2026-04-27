#!/bin/bash
# Inicia o serviço em background com nohup

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
VENV_DIR="$SCRIPT_DIR/venv"
LOG_FILE="$SCRIPT_DIR/aviator_service.log"
PID_FILE="$SCRIPT_DIR/aviator_service.pid"

cd "$SCRIPT_DIR"

# Ativar ambiente virtual
source "$VENV_DIR/bin/activate"

# Verificar se já está rodando
if [ -f "$PID_FILE" ]; then
    OLD_PID=$(cat "$PID_FILE")
    if ps -p "$OLD_PID" > /dev/null 2>&1; then
        echo "Serviço já está rodando (PID: $OLD_PID)"
        echo "Para parar: ./parar.sh"
        exit 1
    fi
fi

# Configurar display virtual se necessário
if [ -z "$DISPLAY" ]; then
    export DISPLAY=:99
    Xvfb :99 -screen 0 1920x1080x24 > /dev/null 2>&1 &
    XVFB_PID=$!
    echo "$XVFB_PID" > "$SCRIPT_DIR/xvfb.pid"
    sleep 2
    echo "Xvfb iniciado (PID: $XVFB_PID)"
fi

# Iniciar serviço em background
echo "Iniciando Aviator ML Intelligence em background..."
nohup python aviator_service2.py > "$LOG_FILE" 2>&1 &
SERVICE_PID=$!

# Salvar PID
echo "$SERVICE_PID" > "$PID_FILE"

echo ""
echo "? Serviço iniciado com sucesso!"
echo ""
echo "  PID: $SERVICE_PID"
echo "  Log: $LOG_FILE"
echo "  Dashboard: http://$(hostname -I | awk '{print $1}'):5005"
echo ""
echo "Comandos úteis:"
echo "  Ver log: tail -f $LOG_FILE"
echo "  Parar: ./parar.sh"
echo "  Status: ./status.sh"
echo ""
echo "Você pode desconectar do SSH agora (Ctrl+D)"
echo ""
