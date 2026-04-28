#!/bin/bash

# Inicia o servio em uma sesso screen persistente



SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

VENV_DIR="$SCRIPT_DIR/venv"

SESSION_NAME="aviator"



cd "$SCRIPT_DIR"



# Verificar se screen est instalado

if ! command -v screen &> /dev/null; then

    echo "Screen no est instalado. Instalando..."

    sudo apt-get update -qq

    sudo apt-get install -y screen

fi



# Verificar se j existe sesso

if screen -list | grep -q "$SESSION_NAME"; then

    echo "Sesso '$SESSION_NAME' j existe!"

    echo ""

    echo "Para acessar: screen -r $SESSION_NAME"

    echo "Para parar: ./parar_screen.sh"

    echo "Para listar: screen -list"

    exit 1

fi



# Criar sesso screen

echo "Criando sesso screen '$SESSION_NAME'..."



screen -dmS "$SESSION_NAME" bash -c "

    cd '$SCRIPT_DIR'

    source '$VENV_DIR/bin/activate'



    # Configurar display virtual se necessrio

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

    echo "? Servio iniciado em sesso screen!"

    echo ""

    echo "  Sesso: $SESSION_NAME"

    echo "  Dashboard: http://$(hostname -I | awk '{print $1}'):5005"

    echo ""

    echo "Comandos teis:"

    echo "  Acessar sesso: screen -r $SESSION_NAME"

    echo "  Listar sesses: screen -list"

    echo "  Desconectar: Ctrl+A depois D"

    echo "  Parar servio: ./parar_screen.sh"

    echo ""

    echo "Voc pode desconectar do SSH agora (Ctrl+D)"

    echo ""

else

    echo "? Erro ao criar sesso screen"

    exit 1

fi

