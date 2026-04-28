#!/bin/bash
# Script mestre - Instalao automtica completa

set -e

echo ""
echo "  =================================================="
echo "   Aviator ML Intelligence - Instalao Automtica"
echo "  =================================================="
echo ""

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

# Dar permisses a todos os scripts
echo "[0/6] Configurando permisses..."
chmod +x *.sh
echo "  ? Permisses configuradas"

# 1. Instalao base
echo ""
echo "[1/6] Executando instalao base..."
if [ -f "instalar_linux.sh" ]; then
    ./instalar_linux.sh
else
    echo "  ? instalar_linux.sh no encontrado!"
    exit 1
fi

# 2. Corrigir Chrome (Snap -> APT)
echo ""
echo "[2/6] Corrigindo instalao do Chrome..."
if [ -f "instalar_chrome_apt.sh" ]; then
    ./instalar_chrome_apt.sh || true  # Continua mesmo se falhar
else
    echo "  ? instalar_chrome_apt.sh no encontrado, pulando..."
fi

# 3. Instalar webdriver-manager (opcional)
echo ""
echo "[3/6] Instalando webdriver-manager..."
if [ -f "usar_webdriver_manager.sh" ]; then
    ./usar_webdriver_manager.sh || true
else
    echo "  ? usar_webdriver_manager.sh no encontrado, pulando..."
fi

# 4. Testar instalao
echo ""
echo "[4/6] Testando instalao..."
if [ -f "testar_chrome_selenium.sh" ]; then
    if ./testar_chrome_selenium.sh; then
        echo "  ? Teste bem-sucedido!"
    else
        echo "  ? Teste falhou!"
        echo ""
        echo "Solues:"
        echo "  1. Executar manualmente: ./instalar_chrome_apt.sh"
        echo "  2. Ver logs: ./diagnostico_chrome.sh"
        echo "  3. Tentar novamente: ./instalacao_automatica.sh"
        exit 1
    fi
else
    echo "  ? testar_chrome_selenium.sh no encontrado, pulando teste..."
fi

# 5. Criar servio systemd (opcional)
echo ""
echo "[5/6] Deseja criar servio systemd (auto-start no boot)? [s/N]"
read -t 10 -r RESPOSTA || RESPOSTA="n"

if [[ "$RESPOSTA" =~ ^[Ss]$ ]]; then
    if [ -f "criar_servico_systemd.sh" ]; then
        ./criar_servico_systemd.sh
        echo ""
        echo "Para iniciar: sudo systemctl start aviator"
    else
        echo "  ? criar_servico_systemd.sh no encontrado"
    fi
else
    echo "  Pulando criao de servio systemd"
fi

# 6. Iniciar servio
echo ""
echo "[6/6] Iniciando servio..."
echo ""
echo "Escolha o mtodo de execuo:"
echo "  1) Primeiro plano (para teste, Ctrl+C para parar)"
echo "  2) Background com nohup (pode desconectar SSH)"
echo "  3) Sesso screen (acesso ao terminal)"
echo "  4) No iniciar agora"
echo ""
read -t 15 -p "Opo [1-4]: " -r OPCAO || OPCAO="2"

case "$OPCAO" in
    1)
        echo "Iniciando em primeiro plano..."
        echo "Pressione Ctrl+C para parar"
        sleep 2
        ./iniciar.sh
        ;;
    2)
        echo "Iniciando em background..."
        ./iniciar_background.sh
        ;;
    3)
        echo "Iniciando em sesso screen..."
        ./iniciar_screen.sh
        ;;
    4)
        echo "Servio no iniciado"
        echo ""
        echo "Para iniciar manualmente:"
        echo "  ./iniciar.sh              # Primeiro plano"
        echo "  ./iniciar_background.sh   # Background"
        echo "  ./iniciar_screen.sh       # Screen"
        ;;
    *)
        echo "Opo invlida. Iniciando em background..."
        ./iniciar_background.sh
        ;;
esac

echo ""
echo "  =================================================="
echo "   ? Instalao Concluda!"
echo "  =================================================="
echo ""
echo "Dashboard: http://$(hostname -I | awk '{print $1}'):5005"
echo ""
echo "Comandos teis:"
echo "  Status:    ./status.sh"
echo "  Logs:      tail -f aviator_service.log"
echo "  Parar:     ./parar.sh"
echo "  Retreinar: ./diagnostico.sh --retrain"
echo ""
