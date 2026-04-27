#!/bin/bash
# Inicia o serviço em uma sessão screen persistente

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
VENV_DIR="$SCRIPT_DIR/venv"
SESSION_NAME="aviator"

cd "$SCRIPT_DIR"

# Verificar se screen está instalado
if ! command -v screen &> /dev/null; then
    echo "Screen não está instalado. Instalando..."
    sudo apt-get update -qq
    sudo apt-get install -y screen
fi

# Verificar se já existe sessão
if screen -list | grep -q "$SESSION_NAME"; then
    echo "Sessão '$SESSION_NAME' já existe!"
    echo ""
    echo "Para acessar: screen -r $SESSION_NAME"
    echo "Para parar: ./parar_screen.sh"
    echo "Para listar: screen -list"
    exit 1
fi

# Criar sessão screen
echo "Criando sessão screen '$SESSION_NAME'..."

screen -dmS "$SESSION_NAME" bash -c "
    cd '$SCRIPT_DIR'
    source '$VENV_DIR/bin/activate'

    # Configurar display virtual se necessário
    if [ -z \"\$DISPLAY\" ]; then
        export DISPLAY=:99
        Xvfb :99 -screen 0 1920x1080x24 > /dev/null 2>&1 &
        sleep 2
    fi

    echo 'Iniciando Aviator ML Intelligence...'
    echo 'Dashboard: http://$(hostname -I | awk '{print \$1}'):5005'
    echo ''
    echo 'Pressione Ctrl+A depois D para desconectar (detach)'
    echo 'Para reconectar: screen -r $SESSION_NAME'
    echo ''

    python aviator_service2.py
"

sleep 2

if screen -list | grep -q "$SESSION_NAME"; then
    echo ""
    echo "? Serviço iniciado em sessão screen!"
    echo ""
    echo "  Sessão: $SESSION_NAME"
    echo "  Dashboard: http://$(hostname -I | awk '{print $1}'):5005"
    echo ""
    echo "Comandos úteis:"
    echo "  Acessar sessão: screen -r $SESSION_NAME"
    echo "  Listar sessões: screen -list"
    echo "  Desconectar: Ctrl+A depois D"
    echo "  Parar serviço: ./parar_screen.sh"
    echo ""
    echo "Você pode desconectar do SSH agora (Ctrl+D)"
    echo ""
else
    echo "? Erro ao criar sessão screen"
    exit 1
fi
