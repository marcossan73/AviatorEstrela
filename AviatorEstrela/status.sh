#!/bin/bash

# Verifica status do servio



SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

PID_FILE="$SCRIPT_DIR/aviator_service.pid"

LOG_FILE="$SCRIPT_DIR/aviator_service.log"



echo "=== STATUS DO SERVIO ==="

echo ""



# Verificar processo

if [ -f "$PID_FILE" ]; then

    PID=$(cat "$PID_FILE")

    if ps -p "$PID" > /dev/null 2>&1; then

        echo "Status: ? RODANDO"

        echo "PID: $PID"



        # Tempo de execuo

        ELAPSED=$(ps -p "$PID" -o etime= | tr -d ' ')

        echo "Tempo de execuo: $ELAPSED"



        # Uso de CPU e memria

        echo ""

        echo "Recursos:"

        ps -p "$PID" -o pid,pcpu,pmem,vsz,rss,cmd --no-headers | awk '{printf "  CPU: %s%%  |  MEM: %s%%  |  RSS: %d MB\n", $2, $3, $5/1024}'



    else

        echo "Status: ? PARADO (arquivo PID existe mas processo no)"

        rm -f "$PID_FILE"

    fi

else

    # Procurar processo pelo nome

    PIDS=$(pgrep -f "aviator_service2.py")

    if [ -n "$PIDS" ]; then

        echo "Status: ? RODANDO (sem arquivo PID)"

        echo "PIDs encontrados: $PIDS"

    else

        echo "Status: ? PARADO"

    fi

fi



# Verificar porta

echo ""

echo "Porta 5005:"

if netstat -tlnp 2>/dev/null | grep -q ":5005"; then

    netstat -tlnp 2>/dev/null | grep ":5005"

    echo "  ? Dashboard acessvel"

else

    echo "  ? Porta no est escutando"

fi



# ltimas linhas do log

if [ -f "$LOG_FILE" ]; then

    echo ""

    echo "ltimas 10 linhas do log:"

    echo "----------------------------------------"

    tail -n 10 "$LOG_FILE"

    echo "----------------------------------------"

    echo ""

    echo "Ver log completo: tail -f $LOG_FILE"

fi



echo ""

echo "Dashboard: http://$(hostname -I | awk '{print $1}'):5005"

echo ""

