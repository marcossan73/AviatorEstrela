#!/bin/bash
# Script de diagnóstico para verificar instalação do Chrome

echo "=== DIAGNÓSTICO CHROME ==="
echo ""

echo "1. Verificando comandos Chrome disponíveis:"
for cmd in google-chrome google-chrome-stable chromium-browser chromium; do
    if command -v $cmd &>/dev/null; then
        echo "  ? $cmd encontrado: $(which $cmd)"
        $cmd --version 2>/dev/null || echo "    (erro ao obter versão)"
    else
        echo "  ? $cmd NÃO encontrado"
    fi
done

echo ""
echo "2. Procurando binários Chrome no sistema:"
find /usr/bin /usr/local/bin /snap/bin -name "*chrome*" -o -name "*chromium*" 2>/dev/null | head -20

echo ""
echo "3. Verificando ChromeDriver:"
if command -v chromedriver &>/dev/null; then
    echo "  ? ChromeDriver: $(which chromedriver)"
    chromedriver --version 2>/dev/null || echo "    (erro ao obter versão)"
else
    echo "  ? ChromeDriver NÃO encontrado"
fi

echo ""
echo "4. Testando Chrome headless (se disponível):"
if command -v google-chrome-stable &>/dev/null; then
    google-chrome-stable --headless --disable-gpu --dump-dom https://www.google.com 2>&1 | head -5
elif command -v google-chrome &>/dev/null; then
    google-chrome --headless --disable-gpu --dump-dom https://www.google.com 2>&1 | head -5
else
    echo "  Chrome não disponível para teste"
fi

echo ""
echo "5. Verificando dependências:"
dpkg -l | grep -E "chrome|chromium" | head -10

echo ""
echo "=== FIM DO DIAGNÓSTICO ==="
