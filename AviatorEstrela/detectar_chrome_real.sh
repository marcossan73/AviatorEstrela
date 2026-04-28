#!/bin/bash
# Script para detectar e corrigir caminho do Chrome

echo "=== DETECO DO CHROME REAL ==="
echo ""

echo "1. Verificando instalaes do Chrome..."
echo ""

# Verificar se  snap
if command -v snap &>/dev/null; then
    echo "Snap detectado. Verificando Chrome via snap..."
    snap list | grep -i chrome || echo "  Chrome no instalado via snap"
    echo ""
fi

# Procurar executvel real do Chrome
echo "2. Procurando executvel real do Chrome..."
echo ""

CHROME_PATHS=(
    "/opt/google/chrome/chrome"
    "/opt/google/chrome/google-chrome"
    "/snap/chromium/current/usr/lib/chromium-browser/chrome"
    "/snap/chromium/current/bin/chromium"
    "/snap/google-chrome/current/usr/bin/google-chrome-stable"
    "/usr/bin/google-chrome"
    "/usr/bin/google-chrome-stable"
    "/usr/bin/chromium-browser"
    "/usr/bin/chromium"
)

CHROME_REAL=""
for path in "${CHROME_PATHS[@]}"; do
    if [ -f "$path" ]; then
        # Verificar se  executvel de verdade (no link)
        if [ -x "$path" ]; then
            FILE_TYPE=$(file "$path" 2>/dev/null)
            if echo "$FILE_TYPE" | grep -q "ELF.*executable"; then
                echo "  ? ENCONTRADO (binrio real): $path"
                CHROME_REAL="$path"
                break
            elif [ -L "$path" ]; then
                REAL_PATH=$(readlink -f "$path")
                if [ -f "$REAL_PATH" ] && [ -x "$REAL_PATH" ]; then
                    echo "  ? ENCONTRADO (via link): $path -> $REAL_PATH"
                    CHROME_REAL="$REAL_PATH"
                    break
                fi
            fi
        fi
    fi
done

if [ -z "$CHROME_REAL" ]; then
    echo "  ? Chrome executvel NO ENCONTRADO"
    echo ""
    echo "3. Tentando localizar via comandos..."

    # Tentar via which
    for cmd in google-chrome-stable google-chrome chromium-browser chromium; do
        if command -v "$cmd" &>/dev/null; then
            CMD_PATH=$(which "$cmd")
            REAL_PATH=$(readlink -f "$CMD_PATH")
            if [ -f "$REAL_PATH" ] && [ -x "$REAL_PATH" ]; then
                echo "  ? Encontrado via 'which $cmd': $REAL_PATH"
                CHROME_REAL="$REAL_PATH"
                break
            fi
        fi
    done
fi

echo ""
echo "=== RESULTADO ==="
echo ""

if [ -n "$CHROME_REAL" ]; then
    echo "Chrome real encontrado em:"
    echo "  $CHROME_REAL"
    echo ""

    # Testar se funciona
    echo "Testando execuo..."
    if "$CHROME_REAL" --version 2>/dev/null; then
        echo "  ? Chrome funciona!"
    else
        echo "  ? Chrome no executa corretamente"
    fi

    echo ""
    echo "Use este caminho no cdigo Python:"
    echo "  options.binary_location = \"$CHROME_REAL\""

    # Salvar em arquivo para outros scripts
    echo "$CHROME_REAL" > /tmp/chrome_path.txt
    echo ""
    echo "Caminho salvo em: /tmp/chrome_path.txt"
else
    echo "? Chrome no encontrado em nenhum caminho!"
    echo ""
    echo "Soluo: Remover snap e instalar via APT"
    echo ""
    echo "  sudo snap remove chromium google-chrome 2>/dev/null || true"
    echo "  sudo apt-get install -y google-chrome-stable"
fi

echo ""
