#!/bin/bash
# Teste rápido do Chrome e Selenium

echo "=== TESTE CHROME + SELENIUM ==="
echo ""

# Ativar ambiente virtual
cd ~/AviatorEstrela/AviatorEstrela
source venv/bin/activate

echo "1. Testando importação Selenium..."
python3 -c "from selenium import webdriver; print('? Selenium importado')"

echo ""
echo "2. Testando Chrome headless com Selenium..."
python3 << 'EOF'
import os
from selenium import webdriver
from selenium.webdriver.chrome.options import Options

print("  Configurando opções...")
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
        print(f"  ? Chrome encontrado: {path}")
        break

if not chrome_found:
    print("  ? Chrome não encontrado nos caminhos padrão")
    exit(1)

print("  Iniciando Chrome...")
try:
    driver = webdriver.Chrome(options=options)
    print("  ? Chrome iniciado com sucesso!")

    print("  Acessando Google...")
    driver.get("https://www.google.com")

    titulo = driver.title
    print(f"  ? Página carregada: {titulo}")

    driver.quit()
    print("  ? Chrome encerrado")

    print("")
    print("=== TESTE BEM-SUCEDIDO! ===")
    print("")
    print("O Chrome e Selenium estão funcionando corretamente.")
    print("Você pode iniciar o serviço normalmente com: ./iniciar.sh")

except Exception as e:
    print(f"  ? ERRO: {e}")
    print("")
    print("Detalhes do erro:")
    import traceback
    traceback.print_exc()
    exit(1)
EOF

echo ""
