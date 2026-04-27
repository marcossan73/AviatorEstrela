#!/bin/bash
# Teste rápido do Chrome e Selenium

echo "=== TESTE CHROME + SELENIUM ==="
echo ""

# Ativar ambiente virtual
cd ~/AviatorEstrela/AviatorEstrela
source venv/bin/activate

echo "1. Testando importacao Selenium..."
python3 -c "from selenium import webdriver; print('OK - Selenium importado')"

echo ""
echo "2. Testando Chrome headless com Selenium..."
python3 << 'EOF'
# -*- coding: utf-8 -*-
# -*- coding: utf-8 -*-
import os
from selenium import webdriver
from selenium.webdriver.chrome.options import Options

print("  Configurando opcoes...")
options = Options()
options.add_argument("--headless")
options.add_argument("--no-sandbox")
options.add_argument("--disable-dev-shm-usage")
options.add_argument("--disable-gpu")

# Tentar caminhos do Chrome
chrome_paths = [
    '/usr/bin/google-chrome-stable',
    '/usr/bin/google-chrome',
    '/usr/bin/chromium-browser',
    '/snap/bin/chromium'
]

chrome_found = None
for path in chrome_paths:
    if os.path.exists(path):
        options.binary_location = path
        chrome_found = path
        print("  OK - Chrome encontrado: {0}".format(path))
        break

if not chrome_found:
    print("  ERRO - Chrome nao encontrado nos caminhos padrao")
    exit(1)

print("  Iniciando Chrome...")
try:
    driver = webdriver.Chrome(options=options)
    print("  OK - Chrome iniciado com sucesso!")

    print("  Acessando Google...")
    driver.get("https://www.google.com")

    titulo = driver.title
    print("  OK - Pagina carregada: {0}".format(titulo))

    driver.quit()
    print("  OK - Chrome encerrado")

    print("")
    print("=== TESTE BEM-SUCEDIDO! ===")
    print("")
    print("O Chrome e Selenium estao funcionando corretamente.")
    print("Voce pode iniciar o servico normalmente com: ./iniciar.sh")

except Exception as e:
    print("  ERRO: {0}".format(e))
    print("")
    print("Detalhes do erro:")
    import traceback
    traceback.print_exc()
    exit(1)
EOF

echo ""
