#!/bin/bash
# Para a sesso screen

SESSION_NAME="aviator"

if screen -list | grep -q "$SESSION_NAME"; then
    echo "Encerrando sesso screen '$SESSION_NAME'..."
    screen -S "$SESSION_NAME" -X quit
    sleep 1

    if screen -list | grep -q "$SESSION_NAME"; then
        echo "? Falha ao encerrar sesso"
    else
        echo "? Sesso encerrada com sucesso"
    fi
else
    echo "Sesso '$SESSION_NAME' no encontrada"
    echo ""
    echo "Sesses ativas:"
    screen -list || echo "  Nenhuma"
fi

echo ""
