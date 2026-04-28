# ? Configuração de Fuso Horário - Horário de Brasília

## ?? Problema Resolvido

O servidor pode estar em qualquer fuso horário (UTC, GMT, etc.), mas todas as análises e registros devem usar o **Horário de Brasília (BRT/BRST)**.

## ? Solução Implementada

### **Biblioteca pytz**

Adicionada ao `requirements.txt`:
```
pytz==2024.1
```

### **Funções Utilitárias**

Em `aviator_service2.py` e `ml_diagnostico.py`:

```python
import pytz

# Timezone de Brasília
TIMEZONE_BRT = pytz.timezone('America/Sao_Paulo')

def agora_brasilia():
    """Retorna datetime atual no horário de Brasília."""
    return datetime.now(TIMEZONE_BRT)

def converter_para_brasilia(dt):
    """Converte datetime para horário de Brasília."""
    if dt.tzinfo is None:
        dt = pytz.UTC.localize(dt)
    return dt.astimezone(TIMEZONE_BRT)
```

## ?? Onde É Aplicado

### 1. **Logs** (`log_execucao.txt`)

**Antes:**
```
[27/04/2026 20:30:45] Iniciando Serviço Principal...
```

**Depois:**
```
[27/04/2026 17:30:45 -03] Iniciando Serviço Principal...
```
(Se servidor estiver em UTC, mostra horário de Brasília -3h)

### 2. **Captura de Dados** (`resultados_aviator.txt`)

Timestamps salvos são convertidos para horário de Brasília antes de armazenar:

```python
# Antes
ts = datetime.strptime(f"{data} {hora}", "%d/%m/%Y %H:%M:%S")

# Depois
ts = TIMEZONE_BRT.localize(datetime.strptime(f"{data} {hora}", "%d/%m/%Y %H:%M:%S"))
```

### 3. **Análises ML**

Todas as comparações de tempo usam horário de Brasília:

```python
# Antes
now = datetime.now()

# Depois
now = agora_brasilia()
```

### 4. **Predições** (`predictions.txt`)

Timestamps das predições em horário de Brasília:

```python
# Antes
f.write(f"{datetime.now()};{thresh};...")

# Depois
f.write(f"{agora_brasilia().strftime('%Y-%m-%d %H:%M:%S')};{thresh};...")
```

### 5. **Histórico de Assertividade** (`ml_history.json`)

Parse de timestamps com timezone correto:

```python
# Antes
rs_t = datetime.strptime(spike_ts, '%Y-%m-%d %H:%M:%S')

# Depois
rs_t = TIMEZONE_BRT.localize(datetime.strptime(spike_ts, '%Y-%m-%d %H:%M:%S'))
```

### 6. **Diagnóstico ML**

Exibição de timestamps em horário de Brasília:

```python
def fmt_ts(unix_ts):
    dt_utc = datetime.fromtimestamp(unix_ts, tz=pytz.UTC)
    dt_brt = converter_para_brasilia(dt_utc)
    return dt_brt.strftime("%d/%m/%Y %H:%M:%S %Z")
```

**Saída:**
```
27/04/2026 17:30:45 -03
```

## ?? Exemplos Práticos

### **Servidor em UTC (Londres, +0h)**

```
Hora do Servidor: 2026-04-27 20:30:00 UTC
Hora de Brasília: 2026-04-27 17:30:00 -03
```

### **Servidor em GMT-5 (Nova York)**

```
Hora do Servidor: 2026-04-27 15:30:00 EST
Hora de Brasília: 2026-04-27 17:30:00 -03
```

### **Servidor em GMT+8 (Singapura)**

```
Hora do Servidor: 2026-04-28 04:30:00 SGT
Hora de Brasília: 2026-04-27 17:30:00 -03
```

## ?? Instalação

### **Atualizar Dependências**

```sh
# No servidor Linux
cd ~/AviatorEstrela/AviatorEstrela
source venv/bin/activate
pip install pytz
```

Ou reinstalar tudo:

```sh
pip install -r requirements.txt
```

### **Verificar Timezone**

```sh
# No Python
python3 << 'EOF'
import pytz
from datetime import datetime

brt = pytz.timezone('America/Sao_Paulo')
agora = datetime.now(brt)

print(f"Horário de Brasília: {agora.strftime('%d/%m/%Y %H:%M:%S %Z')}")
print(f"Offset UTC: {agora.strftime('%z')}")
EOF
```

**Saída esperada:**
```
Horário de Brasília: 27/04/2026 17:30:45 -03
Offset UTC: -0300
```

## ?? Horário de Verão

A biblioteca `pytz` lida automaticamente com:

- **BRT (Brasília Time)**: UTC-3 (horário padrão)
- **BRST (Brasília Summer Time)**: UTC-2 (horário de verão, quando aplicável)

**Nota**: O Brasil suspendeu o horário de verão em 2019, mas o `pytz` mantém compatibilidade histórica.

## ? Verificação

### **Teste Manual**

```sh
cd ~/AviatorEstrela/AviatorEstrela
source venv/bin/activate

python3 << 'EOF'
from aviator_service2 import agora_brasilia, converter_para_brasilia
from datetime import datetime
import pytz

# Horário atual de Brasília
print("1. Horário atual de Brasília:")
print(agora_brasilia().strftime("%d/%m/%Y %H:%M:%S %Z"))

# Converter UTC para Brasília
utc_now = datetime.now(pytz.UTC)
brt_now = converter_para_brasilia(utc_now)
print("\n2. Conversão UTC -> BRT:")
print(f"UTC: {utc_now.strftime('%H:%M:%S')}")
print(f"BRT: {brt_now.strftime('%H:%M:%S %Z')}")

# Verificar diferença
diff = (utc_now.hour - brt_now.hour) % 24
print(f"\n3. Diferença: {diff}h")
print("? Correto se diferença for 3h ou 2h (com horário de verão)")
EOF
```

### **Verificar Logs**

```sh
# Ver últimas linhas do log
tail -n 5 log_execucao.txt
```

Deve mostrar timestamps com `-03` ou `BRT`:
```
[27/04/2026 17:30:45 -03] Iniciando Serviço Principal...
```

## ?? Troubleshooting

### **Erro: No module named 'pytz'**

```sh
pip install pytz
```

### **Timestamps ainda em UTC**

Verifique se atualizou o código:

```sh
git pull origin master
./parar.sh
./iniciar_background.sh
```

### **Horário incorreto**

Verifique timezone do servidor:

```sh
# Ver timezone do sistema
timedatectl

# Verificar se pytz está usando timezone correto
python3 -c "import pytz; print(pytz.timezone('America/Sao_Paulo'))"
```

## ?? Resumo de Mudanças

| Arquivo | Mudança |
|---------|---------|
| `aviator_service2.py` | Adicionado `pytz`, funções `agora_brasilia()` e `converter_para_brasilia()` |
| `aviator_service2.py` | Função `log()` usa `agora_brasilia()` |
| `aviator_service2.py` | `capturar_ultimos()` usa `TIMEZONE_BRT.localize()` |
| `aviator_service2.py` | `save_prediction()` usa `agora_brasilia()` |
| `aviator_service2.py` | `load_data_for_analysis()` converte timestamps para BRT |
| `ml_diagnostico.py` | Adicionado `pytz` e funções de timezone |
| `ml_diagnostico.py` | `fmt_ts()` converte para BRT |
| `requirements.txt` | Adicionado `pytz==2024.1` |

## ?? Benefícios

? **Consistência**: Todos os registros no mesmo fuso horário  
? **Precisão**: Análises temporais corretas independente do servidor  
? **Rastreabilidade**: Logs sempre em horário brasileiro  
? **Debugging**: Fácil correlação com eventos reais  
? **Compatibilidade**: Funciona em qualquer servidor (UTC, GMT+8, etc.)

---

**Atualizado**: Dezembro 2024  
**Versão**: 2.1 - Timezone-aware
