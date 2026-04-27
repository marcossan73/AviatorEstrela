#!/bin/bash
# Para a sessão screen

SESSION_NAME="aviator"

if screen -list | grep -q "$SESSION_NAME"; then
    echo "Encerrando sessão screen '$SESSION_NAME'..."
    screen -S "$SESSION_NAME" -X quit
    sleep 1

    if screen -list | grep -q "$SESSION_NAME"; then
        echo "? Falha ao encerrar sessão"
    else
        echo "? Sessão encerrada com sucesso"
    fi
else
    echo "Sessão '$SESSION_NAME' não encontrada"
    echo ""
    echo "Sessões ativas:"
    screen -list || echo "  Nenhuma"
fi

echo ""
