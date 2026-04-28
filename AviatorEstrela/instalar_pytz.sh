#!/bin/bash
# Instala pytz e atualiza dependências

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
VENV_DIR="$SCRIPT_DIR/venv"

echo "Instalando pytz (suporte a timezone de Brasília)..."

# Ativar ambiente virtual
if [ -f "$VENV_DIR/bin/activate" ]; then
    source "$VENV_DIR/bin/activate"
else
    echo "Ambiente virtual não encontrado!"
    echo "Execute primeiro: ./instalar_linux.sh"
    exit 1
fi

# Instalar pytz
pip install pytz==2024.1

echo ""
echo "? pytz instalado com sucesso!"
echo ""
echo "Testando..."

# Testar importação
python3 << 'EOF'
import pytz
from datetime import datetime

brt = pytz.timezone('America/Sao_Paulo')
agora = datetime.now(brt)

print(f"Horário de Brasília: {agora.strftime('%d/%m/%Y %H:%M:%S %Z')}")
print(f"Offset UTC: {agora.strftime('%z')}")
print("")
print("? Timezone configurado corretamente!")
EOF

echo ""
echo "Agora todos os logs e análises usarão horário de Brasília."
echo ""
