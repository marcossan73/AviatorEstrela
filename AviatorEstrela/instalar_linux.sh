#!/bin/bash

#!/bin/bash

# =============================================================================

#  instalar_linux.sh - Instalador do Aviator ML Intelligence para Ubuntu/Debian

#

#  USO:

#    chmod +x instalar_linux.sh

#    ./instalar_linux.sh

# =============================================================================



set -e



RED='\033[0;31m'

GREEN='\033[0;32m'

YELLOW='\033[1;33m'

NC='\033[0m'



SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"



echo ""

echo "  ==================================================="

echo "   Aviator ML Intelligence - Instalador Linux/Ubuntu"

echo "  ==================================================="

echo ""



# -------------------------------------------------

# 1. Verificar/Instalar Python 3.10+

# -------------------------------------------------

echo -e "[1/6] Verificando Python..."



PYTHON_CMD=""

for cmd in python3.10 python3 python; do

    if command -v "$cmd" &>/dev/null; then

        PY_VER=$("$cmd" --version 2>&1 | grep -oP '\d+\.\d+')

        PY_MAJOR=$(echo "$PY_VER" | cut -d. -f1)

        PY_MINOR=$(echo "$PY_VER" | cut -d. -f2)

        if [ "$PY_MAJOR" -ge 3 ] && [ "$PY_MINOR" -ge 10 ]; then

            PYTHON_CMD="$cmd"

            break

        fi

    fi

done



if [ -z "$PYTHON_CMD" ]; then

    echo -e "   ${YELLOW}Python 3.10+ nao encontrado. Instalando...${NC}"

    sudo apt-get update -qq

    sudo apt-get install -y software-properties-common

    sudo add-apt-repository -y ppa:deadsnakes/ppa

    sudo apt-get update -qq

    sudo apt-get install -y python3.10 python3.10-venv python3.10-dev python3-pip



    for cmd in python3.10 python3; do

        if command -v "$cmd" &>/dev/null; then

            PYTHON_CMD="$cmd"

            break

        fi

    done

fi



if [ -z "$PYTHON_CMD" ]; then

    echo -e "   ${RED}ERRO: Nao foi possivel instalar Python 3.10+${NC}"

    echo "   Instale manualmente: sudo apt install python3.10 python3.10-venv"

    exit 1

fi



PY_FULL=$("$PYTHON_CMD" --version 2>&1)

echo -e "   ${GREEN}OK: $PY_FULL ($PYTHON_CMD)${NC}"



# -------------------------------------------------

# 2. Verificar/Instalar Google Chrome

# -------------------------------------------------

echo ""

echo -e "[2/7] Verificando Google Chrome..."



if command -v google-chrome &>/dev/null || command -v google-chrome-stable &>/dev/null; then

    CHROME_VER=$(google-chrome --version 2>/dev/null || google-chrome-stable --version 2>/dev/null)

    echo -e "   ${GREEN}OK: $CHROME_VER${NC}"

else

    echo -e "   ${YELLOW}Chrome nao encontrado. Instalando...${NC}"

    wget -q -O /tmp/chrome.deb https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb

    sudo dpkg -i /tmp/chrome.deb 2>/dev/null || sudo apt-get install -f -y

    rm -f /tmp/chrome.deb

    if command -v google-chrome-stable &>/dev/null; then

        echo -e "   ${GREEN}OK: Chrome instalado.${NC}"

    else

        echo -e "   ${RED}AVISO: Falha ao instalar Chrome. Instale manualmente.${NC}"

        echo "   https://www.google.com/chrome/"

    fi

fi



# -------------------------------------------------

# 3. Verificar/Instalar ChromeDriver

# -------------------------------------------------

echo ""

echo -e "[3/7] Verificando ChromeDriver..."



if command -v chromedriver &>/dev/null; then

    DRIVER_VER=$(chromedriver --version 2>/dev/null)

    echo -e "   ${GREEN}OK: $DRIVER_VER${NC}"

else

    echo -e "   ${YELLOW}ChromeDriver nao encontrado. Instalando...${NC}"



    # Obter verso do Chrome

    CHROME_VERSION=$(google-chrome --version 2>/dev/null || google-chrome-stable --version 2>/dev/null | grep -oP '\d+\.\d+\.\d+' | head -1)

    CHROME_MAJOR=$(echo "$CHROME_VERSION" | cut -d. -f1)



    cd /tmp



    # Para Chrome 115+, usar Chrome for Testing

    if [ "$CHROME_MAJOR" -ge 115 ]; then

        echo "   Baixando ChromeDriver $CHROME_VERSION..."

        DRIVER_URL="https://edgedl.me.gvt1.com/edgedl/chrome/chrome-for-testing/${CHROME_VERSION}/linux64/chromedriver-linux64.zip"



        if wget -q "$DRIVER_URL"; then

            unzip -q chromedriver-linux64.zip 2>/dev/null

            sudo mv chromedriver-linux64/chromedriver /usr/local/bin/ 2>/dev/null || true

            sudo chmod +x /usr/local/bin/chromedriver 2>/dev/null || true

            rm -rf chromedriver-linux64* 2>/dev/null || true

        else

            # Fallback: usar verso genrica recente

            echo "   Verso especfica no encontrada. Usando verso 120..."

            wget -q https://storage.googleapis.com/chrome-for-testing-public/120.0.6099.109/linux64/chromedriver-linux64.zip

            unzip -q chromedriver-linux64.zip 2>/dev/null

            sudo mv chromedriver-linux64/chromedriver /usr/local/bin/ 2>/dev/null || true

            sudo chmod +x /usr/local/bin/chromedriver 2>/dev/null || true

            rm -rf chromedriver-linux64* 2>/dev/null || true

        fi

    else

        echo "   Baixando ChromeDriver para Chrome <115..."

        DRIVER_VERSION=$(curl -s "https://chromedriver.storage.googleapis.com/LATEST_RELEASE_${CHROME_MAJOR}")

        wget -q "https://chromedriver.storage.googleapis.com/${DRIVER_VERSION}/chromedriver_linux64.zip"

        unzip -q chromedriver_linux64.zip 2>/dev/null

        sudo mv chromedriver /usr/local/bin/ 2>/dev/null || true

        sudo chmod +x /usr/local/bin/chromedriver 2>/dev/null || true

        rm -f chromedriver_linux64.zip 2>/dev/null || true

    fi



    cd "$SCRIPT_DIR"



    if command -v chromedriver &>/dev/null; then

        echo -e "   ${GREEN}OK: ChromeDriver instalado.${NC}"

    else

        echo -e "   ${YELLOW}AVISO: Falha ao instalar ChromeDriver. O Selenium tentar gerenciar automaticamente.${NC}"

    fi

fi



# -------------------------------------------------

# 4. Dependencias do sistema

# -------------------------------------------------

echo ""

echo -e "[4/7] Instalando dependencias do sistema..."

sudo apt-get install -y -qq python3-pip python3-venv build-essential libffi-dev wget unzip curl 2>/dev/null || true

echo -e "   ${GREEN}OK${NC}"



# -------------------------------------------------

# 5. Criar ambiente virtual e instalar pacotes Python

# -------------------------------------------------

echo ""

echo -e "[5/7] Criando ambiente virtual e instalando dependencias Python..."



VENV_DIR="$SCRIPT_DIR/venv"



if [ -f "$VENV_DIR/bin/activate" ]; then

    echo "   venv ja existe."

else

    "$PYTHON_CMD" -m venv "$VENV_DIR"

    echo "   venv criado."

fi



source "$VENV_DIR/bin/activate"

pip install --upgrade pip -q



# Procura requirements.txt

REQ_FILE="$SCRIPT_DIR/requirements.txt"

if [ ! -f "$REQ_FILE" ]; then

    REQ_FILE="$SCRIPT_DIR/AviatorEstrela/requirements.txt"

fi



if [ -f "$REQ_FILE" ]; then

    pip install -r "$REQ_FILE"

else

    echo "   requirements.txt nao encontrado. Instalando manualmente..."

    pip install Flask==3.0.3 joblib==1.4.2 'numpy<2.0' pandas==2.2.2 scikit-learn==1.5.0 selenium==4.21.0

fi



echo -e "   ${GREEN}OK: Dependencias instaladas.${NC}"



# -------------------------------------------------

# 6. Criar modulo de compatibilidade (winsound)

# -------------------------------------------------

echo ""

echo -e "[6/7] Criando compatibilidade cross-platform..."



# Detecta pasta do servico

SVC_DIR="$SCRIPT_DIR"

if [ -f "$SCRIPT_DIR/AviatorEstrela/aviator_service2.py" ]; then

    SVC_DIR="$SCRIPT_DIR/AviatorEstrela"

fi



# Cria stub do winsound (so existe no Windows)

COMPAT_FILE="$SVC_DIR/_platform_compat.py"

cat > "$COMPAT_FILE" << 'PYEOF'

"""Compatibilidade cross-platform: stub do winsound para Linux.

O aviator_service2.py usa winsound.Beep() para alertas sonoros,

que so existe no Windows. Este modulo cria um stub silencioso.

"""

import sys



if sys.platform != "win32":

    import types

    _ws = types.ModuleType("winsound")

    _ws.Beep = lambda freq, dur: None

    _ws.MB_OK = 0

    _ws.SND_FILENAME = 0

    _ws.SND_ASYNC = 0

    _ws.PlaySound = lambda sound, flags: None

    sys.modules["winsound"] = _ws

PYEOF



# Adiciona import no aviator_service2.py se ainda nao existe

SVC_FILE="$SVC_DIR/aviator_service2.py"

if [ -f "$SVC_FILE" ]; then

    if ! grep -q "_platform_compat" "$SVC_FILE"; then

        sed -i '1 a\import _platform_compat  # Compatibilidade Linux (winsound stub)' "$SVC_FILE"

        echo "   Patch de compatibilidade aplicado em aviator_service2.py"

    else

        echo "   Patch ja aplicado anteriormente."

    fi

fi



# Mesmo para ml_diagnostico.py se importar aviator_service2

DIAG_FILE="$SVC_DIR/ml_diagnostico.py"

if [ -f "$DIAG_FILE" ]; then

    if ! grep -q "_platform_compat" "$DIAG_FILE"; then

        sed -i '1 a\import _platform_compat  # Compatibilidade Linux (winsound stub)' "$DIAG_FILE"

        echo "   Patch de compatibilidade aplicado em ml_diagnostico.py"

    fi

fi



echo -e "   ${GREEN}OK${NC}"



# -------------------------------------------------

# 7. Criar scripts de execucao

# -------------------------------------------------

echo ""

echo -e "[7/7] Criando scripts de execucao..."



# iniciar.sh

cat > "$SCRIPT_DIR/iniciar.sh" << SHEOF

#!/bin/bash

cd "$SVC_DIR"

source "$VENV_DIR/bin/activate"

echo ""

echo "  Aviator ML Intelligence"

echo "  Dashboard: http://localhost:5005"

echo "  Ctrl+C para encerrar."

echo ""

python aviator_service2.py

SHEOF

chmod +x "$SCRIPT_DIR/iniciar.sh"



# diagnostico.sh

cat > "$SCRIPT_DIR/diagnostico.sh" << SHEOF

#!/bin/bash

cd "$SVC_DIR"

source "$VENV_DIR/bin/activate"

python ml_diagnostico.py "\$@"

SHEOF

chmod +x "$SCRIPT_DIR/diagnostico.sh"



echo -e "   ${GREEN}OK: iniciar.sh e diagnostico.sh criados.${NC}"



# -------------------------------------------------

# Finalizado

# -------------------------------------------------

echo ""

echo "  ==================================================="

echo -e "   ${GREEN}INSTALACAO CONCLUIDA COM SUCESSO!${NC}"

echo "  ==================================================="

echo ""

echo "  Para iniciar o servico:"

echo "    ./iniciar.sh"

echo ""

echo "  Dashboard:"

echo "    http://localhost:5005"

echo ""

echo "  Diagnostico ML:"

echo "    ./diagnostico.sh"

echo "    ./diagnostico.sh --retrain"

echo "    ./diagnostico.sh --clean"

echo "    ./diagnostico.sh --history"

echo ""

