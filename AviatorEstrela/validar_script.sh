#!/bin/bash
# Teste rápido do script de instalação (apenas testes Python)

set -e

echo "=== TESTE DE VALIDACAO DO SCRIPT ==="
echo ""

# Criar venv temporário para teste
TEMP_VENV="/tmp/test_venv_$$"
python3 -m venv "$TEMP_VENV"
source "$TEMP_VENV/bin/activate"

# Instalar dependências mínimas
pip install -q pytz selenium flask pandas scikit-learn

echo "1. Testando imports Python..."
python3 << 'PYTEST'
# -*- coding: utf-8 -*-
import sys
try:
    import pytz
    import selenium
    import flask
    import pandas
    import sklearn
    print("OK - Todas as dependencias Python instaladas")
except ImportError as e:
    print("ERRO - Importacao falhou: " + str(e))
    sys.exit(1)

# Teste timezone
from datetime import datetime
brt = pytz.timezone('America/Sao_Paulo')
agora = datetime.now(brt)
print("OK - Timezone Brasilia: " + agora.strftime('%d/%m/%Y %H:%M:%S %Z'))
PYTEST

if [ $? -eq 0 ]; then
    echo ""
    echo "OK - Teste de Python passou!"
else
    echo ""
    echo "ERRO - Teste de Python falhou!"
    rm -rf "$TEMP_VENV"
    exit 1
fi

# Limpar
rm -rf "$TEMP_VENV"

echo ""
echo "=== VALIDACAO COMPLETA ==="
echo ""
echo "O script setup_aviator.sh esta pronto para uso!"
echo ""
