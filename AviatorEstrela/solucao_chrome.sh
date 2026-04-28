#!/bin/bash

# =============================================================================

#  solucao_chrome.sh - Instala Chrome e ChromeDriver no Ubuntu/Debian

#

#  USO:

#    chmod +x solucao_chrome.sh

#    ./solucao_chrome.sh

# =============================================================================



set -e



RED='\033[0;31m'

GREEN='\033[0;32m'

YELLOW='\033[1;33m'

NC='\033[0m'



echo ""

echo "  ========================================"

echo "   Instalao Chrome + ChromeDriver"

echo "  ========================================"

echo ""



# -------------------------------------------------

# 1. Instalar Google Chrome

# -------------------------------------------------

echo -e "[1/3] Instalando Google Chrome..."



if command -v google-chrome &>/dev/null || command -v google-chrome-stable &>/dev/null; then

    CHROME_VER=$(google-chrome --version 2>/dev/null || google-chrome-stable --version 2>/dev/null)

    echo -e "   ${GREEN}Chrome j instalado: $CHROME_VER${NC}"

else

    cd /tmp

    echo "   Baixando Chrome..."

    wget -q https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb



    echo "   Instalando Chrome..."

    sudo dpkg -i google-chrome-stable_current_amd64.deb 2>/dev/null || true

    sudo apt-get install -f -y



    rm -f google-chrome-stable_current_amd64.deb



    if command -v google-chrome-stable &>/dev/null; then

        CHROME_VER=$(google-chrome-stable --version)

        echo -e "   ${GREEN}Chrome instalado: $CHROME_VER${NC}"

    else

        echo -e "   ${RED}ERRO: Falha ao instalar Chrome${NC}"

        exit 1

    fi

fi



# -------------------------------------------------

# 2. Verificar/Instalar ChromeDriver

# -------------------------------------------------

echo ""

echo -e "[2/3] Instalando ChromeDriver..."



# Obter verso do Chrome

CHROME_VERSION=$(google-chrome --version 2>/dev/null || google-chrome-stable --version 2>/dev/null | grep -oP '\d+\.\d+\.\d+' | head -1)

CHROME_MAJOR=$(echo "$CHROME_VERSION" | cut -d. -f1)



echo "   Chrome verso: $CHROME_VERSION (major: $CHROME_MAJOR)"



# Baixar ChromeDriver compatvel

cd /tmp



# Para Chrome 115+, usar Chrome for Testing

if [ "$CHROME_MAJOR" -ge 115 ]; then

    DRIVER_URL="https://edgedl.me.gvt1.com/edgedl/chrome/chrome-for-testing/${CHROME_VERSION}/linux64/chromedriver-linux64.zip"

    echo "   Baixando ChromeDriver $CHROME_VERSION..."



    if wget -q "$DRIVER_URL"; then

        unzip -q chromedriver-linux64.zip

        sudo mv chromedriver-linux64/chromedriver /usr/local/bin/

        sudo chmod +x /usr/local/bin/chromedriver

        rm -rf chromedriver-linux64*

    else

        # Fallback: usar verso genrica recente

        echo "   Verso especfica no encontrada. Usando verso 120..."

        wget -q https://storage.googleapis.com/chrome-for-testing-public/120.0.6099.109/linux64/chromedriver-linux64.zip

        unzip -q chromedriver-linux64.zip

        sudo mv chromedriver-linux64/chromedriver /usr/local/bin/

        sudo chmod +x /usr/local/bin/chromedriver

        rm -rf chromedriver-linux64*

    fi

else

    # Para verses antigas do Chrome

    echo "   Baixando ChromeDriver para Chrome <115..."

    DRIVER_VERSION=$(curl -s "https://chromedriver.storage.googleapis.com/LATEST_RELEASE_${CHROME_MAJOR}")

    wget -q "https://chromedriver.storage.googleapis.com/${DRIVER_VERSION}/chromedriver_linux64.zip"

    unzip -q chromedriver_linux64.zip

    sudo mv chromedriver /usr/local/bin/

    sudo chmod +x /usr/local/bin/chromedriver

    rm -f chromedriver_linux64.zip

fi



if command -v chromedriver &>/dev/null; then

    DRIVER_VER=$(chromedriver --version)

    echo -e "   ${GREEN}ChromeDriver instalado: $DRIVER_VER${NC}"

else

    echo -e "   ${RED}ERRO: Falha ao instalar ChromeDriver${NC}"

    exit 1

fi



# -------------------------------------------------

# 3. Testar Chrome Headless

# -------------------------------------------------

echo ""

echo -e "[3/3] Testando Chrome headless..."



if google-chrome --headless --disable-gpu --dump-dom https://www.google.com 2>/dev/null | grep -q "Google"; then

    echo -e "   ${GREEN}Teste bem-sucedido!${NC}"

else

    echo -e "   ${YELLOW}AVISO: Teste falhou, mas instalao concluda.${NC}"

fi



# -------------------------------------------------

# Resumo

# -------------------------------------------------

echo ""

echo "  ========================================"

echo -e "   ${GREEN}INSTALAO CONCLUDA!${NC}"

echo "  ========================================"

echo ""

echo "  Binrios instalados:"

echo "    $(which google-chrome || which google-chrome-stable)"

echo "    $(which chromedriver)"

echo ""

echo "  Verses:"

echo "    $(google-chrome --version 2>/dev/null || google-chrome-stable --version 2>/dev/null)"

echo "    $(chromedriver --version)"

echo ""

echo "  Agora execute:"

echo "    ./iniciar.sh"

echo ""

