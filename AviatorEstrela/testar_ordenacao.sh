#!/bin/bash

# Testa ordenao dos dados aps mudana de timezone



SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

VENV_DIR="$SCRIPT_DIR/venv"

OUTPUT_FILE="$SCRIPT_DIR/resultados_aviator.txt"



echo "=== TESTE DE ORDENAO DE DADOS ==="

echo ""



if [ ! -f "$VENV_DIR/bin/activate" ]; then

    echo "Ambiente virtual no encontrado!"

    exit 1

fi



source "$VENV_DIR/bin/activate"



if [ ! -f "$OUTPUT_FILE" ]; then

    echo "Arquivo de dados no encontrado: $OUTPUT_FILE"

    exit 1

fi



echo "1. Verificando primeiras 10 linhas do arquivo:"

echo "----------------------------------------"

head -n 10 "$OUTPUT_FILE"

echo "----------------------------------------"

echo ""



echo "2. Verificando ltimas 10 linhas do arquivo:"

echo "----------------------------------------"

tail -n 10 "$OUTPUT_FILE"

echo "----------------------------------------"

echo ""



echo "3. Testando carregamento e ordenao com Python:"

python3 << 'EOF'

import os

import sys

import pytz

from datetime import datetime

import pandas as pd



sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from aviator_service2 import load_data_for_analysis, agora_brasilia



print("Carregando dados...")

df = load_data_for_analysis()



if df.empty:

    print("Nenhum dado carregado!")

    sys.exit(1)



print(f"Total de registros: {len(df)}")

print("")



print("Primeiros 5 registros (mais antigos):")

print(df.head(5)[['value', 'timestamp']])

print("")



print("ltimos 5 registros (mais recentes):")

print(df.tail(5)[['value', 'timestamp']])

print("")



# Verificar se est ordenado

is_sorted = df['timestamp'].is_monotonic_increasing

print(f"Est ordenado corretamente? {is_sorted}")



if not is_sorted:

    print("")

    print("ERRO: Dados no esto ordenados!")

    print("Verificando onde h problema...")



    for i in range(1, len(df)):

        if df['timestamp'].iloc[i] < df['timestamp'].iloc[i-1]:

            print(f"Problema no ndice {i}:")

            print(f"  Anterior: {df['timestamp'].iloc[i-1]} - {df['value'].iloc[i-1]}")

            print(f"  Atual:    {df['timestamp'].iloc[i]} - {df['value'].iloc[i]}")

            break

else:

    print("")

    print("? Dados esto ordenados corretamente do mais antigo para o mais recente!")



# Verificar timezone

print("")

print("Horrio atual de Braslia:", agora_brasilia().strftime('%d/%m/%Y %H:%M:%S %Z'))



EOF



echo ""

echo "=== FIM DO TESTE ==="

