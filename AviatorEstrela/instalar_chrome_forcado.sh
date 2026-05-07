#!/bin/bash

# Instalao forada do Chrome e ChromeDriver



set -e



echo "=== INSTALAO FORADA DO CHROME ==="

echo ""



# 1. Remover instalaes antigas

echo "1. Removendo instalaes antigas..."

sudo apt-get remove -y google-chrome-stable google-chrome chromium-browser 2>/dev/null || true

sudo rm -f /usr/bin/google-chrome /usr/bin/google-chrome-stable /usr/bin/chromium-browser 2>/dev/null || true



# 2. Atualizar sistema

echo ""

echo "2. Atualizando sistema..."

sudo apt-get update



# 3. Instalar dependncias

echo ""

echo "3. Instalando dependncias..."

sudo apt-get install -y wget curl unzip gnupg2 software-properties-common apt-transport-https ca-certificates



# 4. Adicionar repositrio do Chrome

echo ""

echo "4. Adicionando repositrio oficial do Chrome..."

wget -q -O - https://dl-ssl.google.com/linux/linux_signing_key.pub | sudo apt-key add -

sudo sh -c 'echo "deb [arch=amd64] http://dl.google.com/linux/chrome/deb/ stable main" >> /etc/apt/sources.list.d/google-chrome.list'



# 5. Instalar Chrome via apt (mtodo mais confivel)

echo ""

echo "5. Instalando Google Chrome..."

sudo apt-get update

sudo apt-get install -y google-chrome-stable



# 6. Verificar instalao

echo ""

echo "6. Verificando instalao..."

if command -v google-chrome-stable &>/dev/null; then

    CHROME_PATH=$(which google-chrome-stable)

    CHROME_VER=$(google-chrome-stable --version)

    echo "  ? Chrome instalado com sucesso!"

    echo "    Caminho: $CHROME_PATH"

    echo "    Verso: $CHROME_VER"

else

    echo "  ? ERRO: Chrome no foi instalado corretamente"

    exit 1

fi



# 7. Criar link simblico se necessrio

echo ""

echo "7. Criando links simblicos..."

sudo ln -sf /usr/bin/google-chrome-stable /usr/bin/google-chrome 2>/dev/null || true



# 8. Instalar ChromeDriver

echo ""

echo "8. Instalando ChromeDriver..."



CHROME_VERSION=$(google-chrome-stable --version | grep -oP '\d+\.\d+\.\d+' | head -1)

CHROME_MAJOR=$(echo "$CHROME_VERSION" | cut -d. -f1)



echo "  Chrome verso: $CHROME_VERSION (major: $CHROME_MAJOR)"



cd /tmp



# Para Chrome 115+

if [ "$CHROME_MAJOR" -ge 115 ]; then

    echo "  Baixando ChromeDriver $CHROME_VERSION..."



    # Tentar verso especfica

    DRIVER_URL="https://edgedl.me.gvt1.com/edgedl/chrome/chrome-for-testing/${CHROME_VERSION}/linux64/chromedriver-linux64.zip"



    if wget -q "$DRIVER_URL" 2>/dev/null; then

        echo "  ? Download bem-sucedido (verso especfica)"

    else

        # Fallback: pegar verso LATEST conhecida

        echo "  Verso especfica no disponvel, usando verso estvel..."

        LATEST_URL="https://googlechromelabs.github.io/chrome-for-testing/LATEST_RELEASE_${CHROME_MAJOR}"

        LATEST_VERSION=$(curl -s "$LATEST_URL")

        DRIVER_URL="https://edgedl.me.gvt1.com/edgedl/chrome/chrome-for-testing/${LATEST_VERSION}/linux64/chromedriver-linux64.zip"

        wget -q "$DRIVER_URL"

    fi



    unzip -q chromedriver-linux64.zip

    sudo mv chromedriver-linux64/chromedriver /usr/local/bin/

    sudo chmod +x /usr/local/bin/chromedriver

    rm -rf chromedriver-linux64*

else

    # Chrome < 115

    echo "  Baixando ChromeDriver para Chrome <115..."

    DRIVER_VERSION=$(curl -s "https://chromedriver.storage.googleapis.com/LATEST_RELEASE_${CHROME_MAJOR}")

    wget -q "https://chromedriver.storage.googleapis.com/${DRIVER_VERSION}/chromedriver_linux64.zip"

    unzip -q chromedriver_linux64.zip

    sudo mv chromedriver /usr/local/bin/

    sudo chmod +x /usr/local/bin/chromedriver

    rm -f chromedriver_linux64.zip

fi



# 9. Verificar ChromeDriver

echo ""

echo "9. Verificando ChromeDriver..."

if command -v chromedriver &>/dev/null; then

    DRIVER_VER=$(chromedriver --version)

    echo "  ? ChromeDriver instalado: $DRIVER_VER"

else

    echo "  ? ERRO: ChromeDriver no foi instalado"

    exit 1

fi



# 10. Teste final

echo ""

echo "10. Testando Chrome headless..."

if google-chrome-stable --headless --disable-gpu --dump-dom https://www.google.com 2>&1 | grep -q "Google"; then

    echo "  ? Teste bem-sucedido!"

else

    echo "  ? Teste falhou, mas instalao concluda"

fi



# 11. Instalar Xvfb (necessrio para headless em alguns casos)

echo ""

echo "11. Instalando Xvfb (virtual display)..."

sudo apt-get install -y xvfb



echo ""

echo "=== INSTALAO CONCLUDA ==="

echo ""

echo "Informaes:"

echo "  Chrome: $(which google-chrome-stable)"

echo "  Verso: $(google-chrome-stable --version)"

echo "  Driver: $(which chromedriver)"

echo "  Verso Driver: $(chromedriver --version)"

echo ""

echo "Agora execute: ./iniciar.sh"

echo ""

