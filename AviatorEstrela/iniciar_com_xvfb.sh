#!/bin/bash

# Wrapper que inicia o servio com Xvfb (display virtual)



SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

VENV_DIR="$SCRIPT_DIR/venv"



# Detecta se est rodando em ambiente sem display (servidor headless)

if [ -z "$DISPLAY" ]; then

    echo "Display no detectado. Iniciando com Xvfb..."



    # Instalar Xvfb se no estiver instalado

    if ! command -v Xvfb &>/dev/null; then

        echo "Instalando Xvfb..."

        sudo apt-get update -qq

        sudo apt-get install -y xvfb

    fi



    # Iniciar Xvfb

    export DISPLAY=:99

    Xvfb :99 -screen 0 1920x1080x24 > /dev/null 2>&1 &

    XVFB_PID=$!

    sleep 2



    echo "Xvfb iniciado (PID: $XVFB_PID)"

fi



cd "$SCRIPT_DIR"

source "$VENV_DIR/bin/activate"



echo ""

echo "  Aviator ML Intelligence"

echo "  Dashboard: http://localhost:5005"

echo "  Ctrl+C para encerrar."

echo ""



# Trap para matar Xvfb ao encerrar

cleanup() {

    echo ""

    echo "Encerrando..."

    if [ ! -z "$XVFB_PID" ]; then

        kill $XVFB_PID 2>/dev/null || true

    fi

    exit 0

}



trap cleanup SIGINT SIGTERM



python aviator_service2.py

