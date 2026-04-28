#!/bin/bash

# Cria e instala servio systemd



SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

VENV_DIR="$SCRIPT_DIR/venv"

SERVICE_FILE="/etc/systemd/system/aviator.service"



echo "Criando servio systemd..."



# Criar arquivo de servio

sudo tee "$SERVICE_FILE" > /dev/null << EOF

[Unit]

Description=Aviator ML Intelligence Service

After=network.target



[Service]

Type=simple

User=root

WorkingDirectory=$SCRIPT_DIR

Environment="PATH=$VENV_DIR/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"

Environment="DISPLAY=:99"

ExecStartPre=/bin/bash -c 'Xvfb :99 -screen 0 1920x1080x24 > /dev/null 2>&1 &'

ExecStart=$VENV_DIR/bin/python $SCRIPT_DIR/aviator_service2.py

Restart=always

RestartSec=10

StandardOutput=append:$SCRIPT_DIR/aviator_service.log

StandardError=append:$SCRIPT_DIR/aviator_service.log



[Install]

WantedBy=multi-user.target

EOF



# Recarregar systemd

echo "Recarregando systemd..."

sudo systemctl daemon-reload



# Habilitar servio para iniciar no boot

echo "Habilitando servio para iniciar no boot..."

sudo systemctl enable aviator



echo ""

echo "? Servio systemd criado e habilitado!"

echo ""

echo "Comandos systemd:"

echo "  Iniciar:   sudo systemctl start aviator"

echo "  Parar:     sudo systemctl stop aviator"

echo "  Reiniciar: sudo systemctl restart aviator"

echo "  Status:    sudo systemctl status aviator"

echo "  Logs:      sudo journalctl -u aviator -f"

echo "  Desabilitar auto-start: sudo systemctl disable aviator"

echo ""

echo "Para iniciar agora: sudo systemctl start aviator"

echo ""

