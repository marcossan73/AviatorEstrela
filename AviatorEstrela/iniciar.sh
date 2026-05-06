
#!/bin/bash

cd "/root/AviatorEstrela/AviatorEstrela"

source "/root/AviatorEstrela/AviatorEstrela/venv/bin/activate"

echo ""

echo "  Aviator ML Intelligence"

echo "  Dashboard: http://localhost:5005"

echo "  Ctrl+C para encerrar."

echo ""

python aviator_service2.py

