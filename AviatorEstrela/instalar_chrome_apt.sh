#!/bin/bash
# Soluo definitiva: Remove Snap e instala Chrome via APT

set -e

echo ""
echo "  ============================================"
echo "   Soluo Definitiva - Chrome via APT"
echo "  ============================================"
echo ""

echo "[1/5] Removendo Chrome/Chromium via Snap..."
sudo snap remove chromium 2>/dev/null || true
sudo snap remove google-chrome 2>/dev/null || true
echo "  OK - Snaps removidos"

echo ""
echo "[2/5] Removendo pacotes antigos..."
sudo apt-get remove -y google-chrome-stable google-chrome chromium-browser 2>/dev/null || true
sudo apt-get autoremove -y 2>/dev/null || true
echo "  OK - Pacotes antigos removidos"

echo ""
echo "[3/5] Adicionando repositrio oficial do Google Chrome..."
wget -q -O - https://dl-ssl.google.com/linux/linux_signing_key.pub | sudo apt-key add -
echo "deb [arch=amd64] http://dl.google.com/linux/chrome/deb/ stable main" | sudo tee /etc/apt/sources.list.d/google-chrome.list
sudo apt-get update -qq
echo "  OK - Repositrio adicionado"

echo ""
echo "[4/5] Instalando Google Chrome via APT..."
sudo apt-get install -y google-chrome-stable
echo "  OK - Chrome instalado"

echo ""
echo "[5/5] Verificando instalao..."

CHROME_PATH=$(which google-chrome-stable)
CHROME_REAL=$(readlink -f "$CHROME_PATH")

echo "  Caminho do comando: $CHROME_PATH"
echo "  Caminho real: $CHROME_REAL"
echo "  Verso: $(google-chrome-stable --version)"

# Testar execuo
if google-chrome-stable --headless --no-sandbox --disable-gpu --dump-dom https://www.google.com 2>&1 | grep -q "Google"; then
    echo "  ? Teste headless: OK"
else
    echo "  ? Teste headless: FALHOU (mas pode funcionar com Selenium)"
fi

echo ""
echo "  ============================================"
echo "   ? Instalao Concluda!"
echo "  ============================================"
echo ""
echo "Caminho para usar no cdigo:"
echo "  $CHROME_REAL"
echo ""
echo "Salvo em: /tmp/chrome_path.txt"
echo "$CHROME_REAL" > /tmp/chrome_path.txt

echo ""
echo "Agora execute:"
echo "  ./testar_chrome_selenium.sh"
echo ""
