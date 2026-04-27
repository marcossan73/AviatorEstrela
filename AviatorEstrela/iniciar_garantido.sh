#!/bin/bash
# Inicialização garantida - testa antes de iniciar

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
VENV_DIR="$SCRIPT_DIR/venv"

echo ""
echo "  ==========================================="
echo "   Aviator ML Intelligence - Inicialização"
echo "  ==========================================="
echo ""

# 1. Verificar ambiente virtual
if [ ! -f "$VENV_DIR/bin/activate" ]; then
    echo "ERRO: Ambiente virtual não encontrado!"
    echo "Execute: ./instalar_linux.sh"
    exit 1
fi

source "$VENV_DIR/bin/activate"

# 2. Verificar Chrome
echo "[1/4] Verificando Chrome..."
CHROME_PATH=""
for path in /usr/bin/google-chrome-stable /usr/bin/google-chrome /usr/bin/chromium-browser /snap/bin/chromium; do
    if [ -f "$path" ]; then
        CHROME_PATH="$path"
        CHROME_VER=$($path --version 2>/dev/null || echo "?")
        echo "  ? Chrome: $CHROME_VER"
        echo "  ? Caminho: $path"
        break
    fi
done

if [ -z "$CHROME_PATH" ]; then
    echo "  ? Chrome não encontrado!"
    echo ""
    echo "Execute: ./instalar_chrome_forcado.sh"
    exit 1
fi

# 3. Verificar ChromeDriver
echo ""
echo "[2/4] Verificando ChromeDriver..."
if command -v chromedriver &>/dev/null; then
    DRIVER_VER=$(chromedriver --version 2>/dev/null || echo "?")
    echo "  ? ChromeDriver: $DRIVER_VER"
else
    echo "  ? ChromeDriver não encontrado (Selenium tentará gerenciar automaticamente)"
fi

# 4. Teste rápido Selenium
echo ""
echo "[3/4] Testando Selenium..."
python3 << 'EOF'
import sys
try:
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options

    options = Options()
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")

    # Força caminho do Chrome
    import os
    chrome_paths = [
        '/usr/bin/google-chrome-stable',
        '/usr/bin/google-chrome',
        '/usr/bin/chromium-browser',
        '/snap/bin/chromium'
    ]

    for path in chrome_paths:
        if os.path.exists(path):
            options.binary_location = path
            break

    # Teste rápido
    driver = webdriver.Chrome(options=options)
    driver.get("https://www.google.com")
    titulo = driver.title
    driver.quit()

    print(f"  ? Selenium funcionando (teste: {titulo})")
    sys.exit(0)

except Exception as e:
    print(f"  ? Erro no teste Selenium: {e}")
    print("")
    print("Tente executar com Xvfb: ./iniciar_com_xvfb.sh")
    sys.exit(1)
EOF

if [ $? -ne 0 ]; then
    echo ""
    echo "ERRO: Teste de Selenium falhou."
    echo ""
    echo "Soluções:"
    echo "  1. Executar com Xvfb: ./iniciar_com_xvfb.sh"
    echo "  2. Ver logs detalhados: ./testar_chrome_selenium.sh"
    exit 1
fi

# 5. Iniciar serviço
echo ""
echo "[4/4] Iniciando serviço..."
echo ""

# Detectar se precisa de Xvfb
if [ -z "$DISPLAY" ]; then
    echo "Display não detectado. Iniciando Xvfb..."

    if ! command -v Xvfb &>/dev/null; then
        echo "Instalando Xvfb..."
        sudo apt-get update -qq
        sudo apt-get install -y xvfb
    fi

    export DISPLAY=:99
    Xvfb :99 -screen 0 1920x1080x24 > /dev/null 2>&1 &
    XVFB_PID=$!
    sleep 2
    echo "Xvfb iniciado (PID: $XVFB_PID, DISPLAY=$DISPLAY)"
fi

echo ""
echo "  ==========================================="
echo "   ? Tudo pronto!"
echo "  ==========================================="
echo ""
echo "  Dashboard: http://localhost:5005"
echo "  Externo: http://$(hostname -I | awk '{print $1}'):5005"
echo ""
echo "  Pressione Ctrl+C para encerrar"
echo ""

# Trap para cleanup
cleanup() {
    echo ""
    echo "Encerrando..."
    if [ ! -z "$XVFB_PID" ]; then
        kill $XVFB_PID 2>/dev/null || true
        echo "Xvfb encerrado"
    fi
    exit 0
}

trap cleanup SIGINT SIGTERM

# Iniciar Python
python aviator_service2.py
