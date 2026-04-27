#!/bin/bash
# Instalação e uso do webdriver-manager para gerenciar ChromeDriver automaticamente
#
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
VENV_DIR="$SCRIPT_DIR/venv"

echo ""
echo "  =========================================="
echo "   Webdriver Manager - Instalação"
echo "  =========================================="
echo ""

# Ativar ambiente virtual
if [ ! -f "$VENV_DIR/bin/activate" ]; then
    echo "ERRO: Ambiente virtual não encontrado!"
    echo "Execute primeiro: ./instalar_linux.sh"
    exit 1
fi

source "$VENV_DIR/bin/activate"

# Instalar webdriver-manager
echo "[1/3] Instalando webdriver-manager..."
pip install webdriver-manager --quiet

echo "  OK - webdriver-manager instalado"

# Testar instalação
echo ""
echo "[2/3] Testando webdriver-manager..."
python3 << 'EOF'
# -*- coding: utf-8 -*-
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager

print("  Baixando/atualizando ChromeDriver...")

options = Options()
options.add_argument("--headless")
options.add_argument("--no-sandbox")
options.add_argument("--disable-dev-shm-usage")
options.add_argument("--disable-gpu")

# webdriver-manager gerencia automaticamente o ChromeDriver
service = Service(ChromeDriverManager().install())

try:
    driver = webdriver.Chrome(service=service, options=options)
    driver.get("https://www.google.com")
    print("  OK - Teste bem-sucedido: {0}".format(driver.title))
    driver.quit()
except Exception as e:
    print("  ERRO: {0}".format(e))
    exit(1)
EOF

if [ $? -ne 0 ]; then
    echo ""
    echo "ERRO: Teste falhou"
    exit 1
fi

# Atualizar aviator_service2.py para usar webdriver-manager
echo ""
echo "[3/3] Atualizando aviator_service2.py..."

# Criar backup
cp aviator_service2.py aviator_service2.py.backup

# Adicionar import do webdriver-manager no topo do arquivo
if ! grep -q "webdriver_manager" aviator_service2.py; then
    sed -i '1 a\# Webdriver Manager (gerencia ChromeDriver automaticamente)\ntry:\n    from webdriver_manager.chrome import ChromeDriverManager\n    from selenium.webdriver.chrome.service import Service\n    USE_WEBDRIVER_MANAGER = True\nexcept ImportError:\n    USE_WEBDRIVER_MANAGER = False' aviator_service2.py
    echo "  OK - Import adicionado"
else
    echo "  OK - Import ja existe"
fi

echo ""
echo "  =========================================="
echo "   Instalacao Concluida!"
echo "  =========================================="
echo ""
echo "Agora o ChromeDriver sera gerenciado automaticamente."
echo "Execute: ./iniciar.sh"
echo ""
