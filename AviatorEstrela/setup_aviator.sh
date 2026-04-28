#!/bin/bash
# =============================================================================
#  setup_aviator.sh - Instalação Completa do Aviator ML Intelligence
#  
#  Este script faz a instalação completa do zero, incluindo:
#  - Python 3.10+
#  - Google Chrome via APT (não Snap)
#  - ChromeDriver compatível
#  - Ambiente virtual Python
#  - Todas as dependências (pytz, selenium, flask, etc.)
#  - Webdriver Manager (opcional)
#  - Configuração de timezone para Brasília
#  - Scripts de controle (iniciar, parar, status)
#  - Teste completo da instalação
#
#  USO:
#    chmod +x setup_aviator.sh
#    ./setup_aviator.sh
# =============================================================================

set -e  # Parar em caso de erro

# Cores para output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo ""
echo "  ============================================================"
echo "   ?? Aviator ML Intelligence - Instalação Completa"
echo "  ============================================================"
echo ""
echo "  Este script instalará:"
echo "    • Python 3.10+"
echo "    • Google Chrome (via APT)"
echo "    • ChromeDriver"
echo "    • Ambiente Virtual Python"
echo "    • Dependências (Flask, Selenium, ML, pytz)"
echo "    • Configuração de Timezone (Brasília)"
echo "    • Scripts de controle"
echo ""
read -p "  Continuar com a instalação? [S/n] " -r RESPOSTA
if [[ ! "$RESPOSTA" =~ ^[Ss]?$ ]]; then
    echo "Instalação cancelada."
    exit 0
fi

# =============================================================================
# ETAPA 1: VERIFICAR/INSTALAR PYTHON 3.10+
# =============================================================================
echo ""
echo -e "${BLUE}[1/10] Verificando Python...${NC}"

PYTHON_CMD=""
for cmd in python3.12 python3.11 python3.10 python3; do
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
    echo -e "   ${YELLOW}Python 3.10+ não encontrado. Instalando...${NC}"
    sudo apt-get update -qq
    sudo apt-get install -y software-properties-common
    sudo add-apt-repository -y ppa:deadsnakes/ppa
    sudo apt-get update -qq
    sudo apt-get install -y python3.10 python3.10-venv python3.10-dev python3-pip
    PYTHON_CMD="python3.10"
fi

PY_FULL=$("$PYTHON_CMD" --version 2>&1)
echo -e "   ${GREEN}? $PY_FULL${NC}"

# =============================================================================
# ETAPA 2: REMOVER SNAP E INSTALAR CHROME VIA APT
# =============================================================================
echo ""
echo -e "${BLUE}[2/10] Instalando Google Chrome via APT...${NC}"

# Remover Chrome/Chromium via Snap
sudo snap remove chromium 2>/dev/null || true
sudo snap remove google-chrome 2>/dev/null || true

# Remover pacotes antigos
sudo apt-get remove -y google-chrome-stable google-chrome chromium-browser 2>/dev/null || true

# Adicionar repositório oficial do Google Chrome
wget -q -O - https://dl-ssl.google.com/linux/linux_signing_key.pub | sudo apt-key add - 2>/dev/null || true
echo "deb [arch=amd64] http://dl.google.com/linux/chrome/deb/ stable main" | sudo tee /etc/apt/sources.list.d/google-chrome.list >/dev/null

# Atualizar e instalar
sudo apt-get update -qq
sudo apt-get install -y google-chrome-stable

CHROME_PATH=$(which google-chrome-stable)
CHROME_REAL=$(readlink -f "$CHROME_PATH")
CHROME_VER=$(google-chrome-stable --version)

echo -e "   ${GREEN}? $CHROME_VER${NC}"
echo -e "   ${GREEN}? Caminho: $CHROME_REAL${NC}"

# =============================================================================
# ETAPA 3: INSTALAR CHROMEDRIVER
# =============================================================================
echo ""
echo -e "${BLUE}[3/10] Instalando ChromeDriver...${NC}"

CHROME_VERSION=$(google-chrome-stable --version | grep -oP '\d+\.\d+\.\d+' | head -1)
CHROME_MAJOR=$(echo "$CHROME_VERSION" | cut -d. -f1)

cd /tmp

if [ "$CHROME_MAJOR" -ge 115 ]; then
    # Chrome 115+ usa Chrome for Testing
    DRIVER_URL="https://storage.googleapis.com/chrome-for-testing-public/${CHROME_VERSION}/linux64/chromedriver-linux64.zip"

    if wget -q "$DRIVER_URL" 2>/dev/null; then
        echo -e "   ${GREEN}? Download ChromeDriver $CHROME_VERSION${NC}"
    else
        # Fallback
        LATEST_URL="https://googlechromelabs.github.io/chrome-for-testing/LATEST_RELEASE_${CHROME_MAJOR}"
        LATEST_VERSION=$(curl -s "$LATEST_URL")
        DRIVER_URL="https://storage.googleapis.com/chrome-for-testing-public/${LATEST_VERSION}/linux64/chromedriver-linux64.zip"
        wget -q "$DRIVER_URL"
    fi

    unzip -q chromedriver-linux64.zip
    sudo mv chromedriver-linux64/chromedriver /usr/local/bin/
    sudo chmod +x /usr/local/bin/chromedriver
    rm -rf chromedriver-linux64*
else
    # Chrome < 115
    DRIVER_VERSION=$(curl -s "https://chromedriver.storage.googleapis.com/LATEST_RELEASE_${CHROME_MAJOR}")
    wget -q "https://chromedriver.storage.googleapis.com/${DRIVER_VERSION}/chromedriver_linux64.zip"
    unzip -q chromedriver_linux64.zip
    sudo mv chromedriver /usr/local/bin/
    sudo chmod +x /usr/local/bin/chromedriver
    rm -f chromedriver_linux64.zip
fi

cd "$SCRIPT_DIR"

DRIVER_VER=$(chromedriver --version)
echo -e "   ${GREEN}? $DRIVER_VER${NC}"

# =============================================================================
# ETAPA 4: INSTALAR DEPENDÊNCIAS DO SISTEMA
# =============================================================================
echo ""
echo -e "${BLUE}[4/10] Instalando dependências do sistema...${NC}"

sudo apt-get install -y -qq \
    python3-pip \
    python3-venv \
    build-essential \
    libffi-dev \
    wget \
    curl \
    unzip \
    xvfb \
    screen \
    git \
    2>/dev/null || true

echo -e "   ${GREEN}? Dependências instaladas${NC}"

# =============================================================================
# ETAPA 5: CRIAR AMBIENTE VIRTUAL
# =============================================================================
echo ""
echo -e "${BLUE}[5/10] Criando ambiente virtual Python...${NC}"

VENV_DIR="$SCRIPT_DIR/venv"

if [ -d "$VENV_DIR" ]; then
    echo -e "   ${YELLOW}Removendo venv antigo...${NC}"
    rm -rf "$VENV_DIR"
fi

"$PYTHON_CMD" -m venv "$VENV_DIR"
source "$VENV_DIR/bin/activate"
pip install --upgrade pip -q

echo -e "   ${GREEN}? Ambiente virtual criado${NC}"

# =============================================================================
# ETAPA 6: INSTALAR DEPENDÊNCIAS PYTHON
# =============================================================================
echo ""
echo -e "${BLUE}[6/10] Instalando dependências Python...${NC}"

# Criar requirements.txt se não existir
cat > /tmp/requirements_aviator.txt << 'EOF'
Flask==3.0.3
joblib==1.4.2
numpy<2.0
pandas==2.2.2
scikit-learn==1.5.0
selenium==4.21.0
pytz==2024.1
webdriver-manager==4.0.1
EOF

pip install -r /tmp/requirements_aviator.txt

echo -e "   ${GREEN}? Dependências Python instaladas${NC}"

# =============================================================================
# ETAPA 7: CRIAR COMPATIBILIDADE CROSS-PLATFORM
# =============================================================================
echo ""
echo -e "${BLUE}[7/10] Configurando compatibilidade cross-platform...${NC}"

# Criar stub do winsound (só existe no Windows)
cat > "$SCRIPT_DIR/_platform_compat.py" << 'EOF'
"""Compatibilidade cross-platform: stub do winsound para Linux."""
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
EOF

# Adicionar import no aviator_service2.py se ainda não existe
if [ -f "$SCRIPT_DIR/aviator_service2.py" ]; then
    if ! grep -q "_platform_compat" "$SCRIPT_DIR/aviator_service2.py"; then
        sed -i '1 a\import _platform_compat  # Compatibilidade Linux' "$SCRIPT_DIR/aviator_service2.py"
    fi
fi

# Mesmo para ml_diagnostico.py
if [ -f "$SCRIPT_DIR/ml_diagnostico.py" ]; then
    if ! grep -q "_platform_compat" "$SCRIPT_DIR/ml_diagnostico.py"; then
        sed -i '1 a\import _platform_compat  # Compatibilidade Linux' "$SCRIPT_DIR/ml_diagnostico.py"
    fi
fi

echo -e "   ${GREEN}? Compatibilidade configurada${NC}"

# =============================================================================
# ETAPA 8: CRIAR SCRIPTS DE CONTROLE
# =============================================================================
echo ""
echo -e "${BLUE}[8/10] Criando scripts de controle...${NC}"

# --- SCRIPT: iniciar.sh ---
cat > "$SCRIPT_DIR/iniciar.sh" << INITEOF
#!/bin/bash
cd "$SCRIPT_DIR"
source "$VENV_DIR/bin/activate"
echo ""
echo "  Aviator ML Intelligence"
echo "  Dashboard: http://localhost:5005"
echo "  Ctrl+C para encerrar."
echo ""
python aviator_service2.py
INITEOF
chmod +x "$SCRIPT_DIR/iniciar.sh"

# --- SCRIPT: iniciar_background.sh ---
cat > "$SCRIPT_DIR/iniciar_background.sh" << BGEOF
#!/bin/bash
SCRIPT_DIR="$SCRIPT_DIR"
VENV_DIR="$VENV_DIR"
LOG_FILE="\$SCRIPT_DIR/aviator_service.log"
PID_FILE="\$SCRIPT_DIR/aviator_service.pid"

cd "\$SCRIPT_DIR"
source "\$VENV_DIR/bin/activate"

if [ -f "\$PID_FILE" ]; then
    OLD_PID=\$(cat "\$PID_FILE")
    if ps -p "\$OLD_PID" > /dev/null 2>&1; then
        echo "Serviço já está rodando (PID: \$OLD_PID)"
        exit 1
    fi
fi

if [ -z "\$DISPLAY" ]; then
    export DISPLAY=:99
    Xvfb :99 -screen 0 1920x1080x24 > /dev/null 2>&1 &
    echo "\$!" > "\$SCRIPT_DIR/xvfb.pid"
    sleep 2
fi

nohup python aviator_service2.py > "\$LOG_FILE" 2>&1 &
echo "\$!" > "\$PID_FILE"

echo ""
echo "? Serviço iniciado em background!"
echo "  PID: \$!"
echo "  Log: \$LOG_FILE"
echo "  Dashboard: http://\$(hostname -I | awk '{print \$1}'):5005"
echo ""
BGEOF
chmod +x "$SCRIPT_DIR/iniciar_background.sh"

# --- SCRIPT: parar.sh ---
cat > "$SCRIPT_DIR/parar.sh" << STOPEOF
#!/bin/bash
SCRIPT_DIR="$SCRIPT_DIR"
PID_FILE="\$SCRIPT_DIR/aviator_service.pid"
XVFB_PID_FILE="\$SCRIPT_DIR/xvfb.pid"

if [ -f "\$PID_FILE" ]; then
    PID=\$(cat "\$PID_FILE")
    if ps -p "\$PID" > /dev/null 2>&1; then
        kill "\$PID" 2>/dev/null
        sleep 2
        ps -p "\$PID" > /dev/null 2>&1 && kill -9 "\$PID" 2>/dev/null
        rm -f "\$PID_FILE"
        echo "? Serviço parado"
    else
        rm -f "\$PID_FILE"
        echo "Processo não está rodando"
    fi
else
    pkill -f aviator_service2.py 2>/dev/null && echo "? Processos parados" || echo "Nenhum processo encontrado"
fi

[ -f "\$XVFB_PID_FILE" ] && kill \$(cat "\$XVFB_PID_FILE") 2>/dev/null && rm -f "\$XVFB_PID_FILE"
STOPEOF
chmod +x "$SCRIPT_DIR/parar.sh"

# --- SCRIPT: status.sh ---
cat > "$SCRIPT_DIR/status.sh" << STATEOF
#!/bin/bash
SCRIPT_DIR="$SCRIPT_DIR"
PID_FILE="\$SCRIPT_DIR/aviator_service.pid"
LOG_FILE="\$SCRIPT_DIR/aviator_service.log"

echo "=== STATUS DO SERVIÇO ==="
echo ""

if [ -f "\$PID_FILE" ]; then
    PID=\$(cat "\$PID_FILE")
    if ps -p "\$PID" > /dev/null 2>&1; then
        echo "Status: ? RODANDO"
        echo "PID: \$PID"
        echo "Tempo: \$(ps -p "\$PID" -o etime= | tr -d ' ')"
        ps -p "\$PID" -o pid,pcpu,pmem,rss,cmd --no-headers | awk '{printf "CPU: %s%%  MEM: %s%%  RSS: %dMB\\n", \$2, \$3, \$4/1024}'
    else
        echo "Status: ? PARADO"
        rm -f "\$PID_FILE"
    fi
else
    pgrep -f aviator_service2.py >/dev/null && echo "Status: ? RODANDO (sem PID file)" || echo "Status: ? PARADO"
fi

echo ""
netstat -tlnp 2>/dev/null | grep ":5005" && echo "? Porta 5005 ativa" || echo "? Porta 5005 inativa"

[ -f "\$LOG_FILE" ] && echo "" && echo "Últimas 5 linhas do log:" && tail -n 5 "\$LOG_FILE"
STATEOF
chmod +x "$SCRIPT_DIR/status.sh"

# --- SCRIPT: diagnostico.sh ---
cat > "$SCRIPT_DIR/diagnostico.sh" << DIAGEOF
#!/bin/bash
cd "$SCRIPT_DIR"
source "$VENV_DIR/bin/activate"
python ml_diagnostico.py "\$@"
DIAGEOF
chmod +x "$SCRIPT_DIR/diagnostico.sh"

echo -e "   ${GREEN}? Scripts criados: iniciar.sh, iniciar_background.sh, parar.sh, status.sh, diagnostico.sh${NC}"

# =============================================================================
# ETAPA 9: TESTAR INSTALAÇÃO
# =============================================================================
echo ""
echo -e "${BLUE}[9/10] Testando instalação...${NC}"

# Teste 1: Python e dependências
source "$VENV_DIR/bin/activate"
python3 << 'PYTEST'
# -*- coding: utf-8 -*-
import sys
try:
    import pytz
    import selenium
    import flask
    import pandas
    import sklearn
    print("OK - Todas as dependencias Python instaladas")
except ImportError as e:
    print("ERRO - Importacao falhou: " + str(e))
    sys.exit(1)

# Teste timezone
from datetime import datetime
brt = pytz.timezone('America/Sao_Paulo')
agora = datetime.now(brt)
print("OK - Timezone Brasilia: " + agora.strftime('%d/%m/%Y %H:%M:%S %Z'))
PYTEST

if [ $? -ne 0 ]; then
    echo -e "${RED}ERRO - Teste de dependencias falhou!${NC}"
    exit 1
fi

# Teste 2: Chrome e Selenium
python3 << 'CHROMETEST'
# -*- coding: utf-8 -*-
import sys
import os
from selenium import webdriver
from selenium.webdriver.chrome.options import Options

try:
    options = Options()
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")

    chrome_paths = [
        '/opt/google/chrome/chrome',
        '/usr/bin/google-chrome-stable',
        '/usr/bin/google-chrome'
    ]

    for path in chrome_paths:
        if os.path.exists(path):
            real_path = os.path.realpath(path)
            options.binary_location = real_path
            break

    driver = webdriver.Chrome(options=options)
    driver.get("https://www.google.com")
    titulo = driver.title
    driver.quit()

    print("OK - Chrome + Selenium funcionando (teste: " + titulo + ")")
except Exception as e:
    print("ERRO - Chrome/Selenium falhou: " + str(e))
    sys.exit(1)
CHROMETEST

if [ $? -ne 0 ]; then
    echo -e "${RED}ERRO - Teste de Chrome/Selenium falhou!${NC}"
    exit 1
fi

echo -e "   ${GREEN}OK - Todos os testes passaram!${NC}"

# =============================================================================
# ETAPA 10: CONFIGURAÇÃO FINAL
# =============================================================================
echo ""
echo -e "${BLUE}[10/10] Configuração final...${NC}"

# Criar diretórios necessários
mkdir -p "$SCRIPT_DIR/ml_models"

# Configurar credenciais (se necessário)
echo ""
echo -e "${YELLOW}IMPORTANTE: Configure suas credenciais em aviator_service2.py:${NC}"
echo "  EMAIL = \"seu_email@gmail.com\""
echo "  SENHA = \"sua_senha\""
echo ""

# =============================================================================
# FINALIZAÇÃO
# =============================================================================
echo ""
echo "  ============================================================"
echo -e "   ${GREEN}? INSTALAÇÃO CONCLUÍDA COM SUCESSO!${NC}"
echo "  ============================================================"
echo ""
echo "  ?? Resumo:"
echo "    Python: $PY_FULL"
echo "    Chrome: $CHROME_VER"
echo "    ChromeDriver: $DRIVER_VER"
echo "    Timezone: America/Sao_Paulo (Brasília)"
echo ""
echo "  ?? Comandos disponíveis:"
echo "    ./iniciar.sh              - Iniciar em primeiro plano"
echo "    ./iniciar_background.sh   - Iniciar em background"
echo "    ./parar.sh                - Parar serviço"
echo "    ./status.sh               - Ver status"
echo "    ./diagnostico.sh          - Diagnóstico ML"
echo ""
echo "  ?? Diagnóstico ML:"
echo "    ./diagnostico.sh                - Status dos modelos"
echo "    ./diagnostico.sh --retrain      - Retreinar modelos"
echo "    ./diagnostico.sh --clean        - Limpar modelos antigos"
echo "    ./diagnostico.sh --history      - Ver histórico"
echo ""
echo "  ?? Dashboard:"
echo "    http://$(hostname -I | awk '{print $1}'):5005"
echo ""
echo "  ??  Próximos passos:"
echo "    1. Editar aviator_service2.py (configurar EMAIL e SENHA)"
echo "    2. Executar: ./iniciar_background.sh"
echo "    3. Acessar dashboard no navegador"
echo ""
echo "  ?? Logs e dados:"
echo "    aviator_service.log       - Log do serviço"
echo "    resultados_aviator.txt    - Dados capturados"
echo "    ml_models/                - Modelos ML treinados"
echo ""

# Perguntar se deseja iniciar agora
read -p "  Deseja iniciar o serviço agora? [s/N] " -r INICIAR
if [[ "$INICIAR" =~ ^[Ss]$ ]]; then
    echo ""
    echo "Iniciando serviço em background..."
    ./iniciar_background.sh
    sleep 2
    ./status.sh
fi

echo ""
echo "  ? Instalação completa!"
echo ""
