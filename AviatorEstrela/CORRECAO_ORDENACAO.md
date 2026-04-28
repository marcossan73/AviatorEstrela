# ?? Correção - Ordenação do Dashboard com Timezone

## ? Problema Identificado

Após implementar o suporte ao horário de Brasília, o dashboard não estava atualizando corretamente a ordem dos dados. Os novos registros apareciam fora de ordem.

## ?? Causa Raiz

1. **Conversão de Timezone Incorreta**: Ao converter timestamps UTC para Brasília, estávamos removendo a informação de timezone, mas depois tentando usar métodos que requeriam timezone-aware datetimes.

2. **Comparação de Datetime Inconsistente**: Mistura de datetime com timezone e sem timezone na função `load_data_for_analysis()`.

3. **Deduplicação Usando Método Incompatível**: Tentativa de usar `.dt.round()` em datetime sem timezone.

4. **Uso de datetime.now() em vez de agora_brasilia()**: Alguns lugares ainda usavam `datetime.now()` sem timezone.

## ? Correções Implementadas

### 1. **Função `load_data_for_analysis()`**

**Antes:**
```python
ts_utc = datetime.fromtimestamp(float(p[1]), tz=pytz.UTC)
ts = converter_para_brasilia(ts_utc).replace(tzinfo=None)

# ...

if ts > now + timedelta(minutes=5):  # now tinha timezone, ts não tinha
    ts -= timedelta(days=1)

# ...

df["_ts_round"] = df["timestamp"].dt.round("1s")  # Erro: dt.round() não funciona sem timezone
```

**Depois:**
```python
# Converte para Brasília e remove timezone de forma consistente
ts_utc = datetime.fromtimestamp(float(p[1]), tz=pytz.UTC)
ts_brt = converter_para_brasilia(ts_utc)
ts = ts_brt.replace(tzinfo=None)  # Naive datetime em BRT

# Comparação correta (ambos naive)
now_naive = now.replace(tzinfo=None)
if ts > now_naive + timedelta(minutes=5):
    ts -= timedelta(days=1)

# Deduplicação usando timestamp Unix
df["_ts_seconds"] = df["timestamp"].apply(lambda x: int(x.timestamp()))
df = df.drop_duplicates(subset=["value", "_ts_seconds"], keep="first")
```

### 2. **Função `predict_optimized()` - Linha 703**

**Antes:**
```python
latest_analysis['now'] = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
```

**Depois:**
```python
latest_analysis['now'] = agora_brasilia().strftime("%d/%m/%Y %H:%M:%S")
```

### 3. **Função `predict_optimized()` - Linha 770**

**Antes:**
```python
old_history.insert(0, {
    'prev_time': datetime.now().strftime('%H:%M:%S'),
```

**Depois:**
```python
old_history.insert(0, {
    'prev_time': agora_brasilia().strftime('%H:%M:%S'),
```

## ?? Como Funciona Agora

### **Fluxo de Dados**

```
1. Captura do Site (com horário real)
   ?
2. Conversão para timestamp Unix (independente de timezone)
   ?
3. Salvar em resultados_aviator.txt (formato: valor;timestamp)
   ?
4. Leitura e conversão para Brasília
   ?
5. Armazenamento em DataFrame (naive datetime em BRT)
   ?
6. Ordenação por timestamp
   ?
7. Exibição no dashboard (do mais recente para o mais antigo)
```

### **Timestamps no Arquivo**

Formato: `valor;timestamp_unix`

Exemplo:
```
1.25;1735337400.0
2.50;1735337460.0
10.35;1735337520.0
```

O timestamp Unix é **independente de timezone** e é convertido para Brasília durante a leitura.

### **Ordenação no DataFrame**

```python
df = df.sort_values(by="timestamp", ascending=True).reset_index(drop=True)
```

- **ascending=True**: Do mais antigo para o mais recente
- DataFrame tem timestamps em ordem cronológica

### **Exibição no Dashboard**

```html
{% for item in data.raw_history|reverse %}
```

- **|reverse**: Inverte a ordem (do mais recente para o mais antigo)
- Usuário vê os dados mais recentes primeiro

## ?? Testes

### **Script de Teste**

Criado `testar_ordenacao.sh` para validar:

```sh
chmod +x testar_ordenacao.sh
./testar_ordenacao.sh
```

**Verifica:**
1. ? Primeiras e últimas linhas do arquivo
2. ? Carregamento correto dos dados
3. ? Ordenação monotônica crescente
4. ? Timezone de Brasília aplicado
5. ? Identifica problemas de ordenação

### **Teste Manual**

```sh
cd ~/AviatorEstrela/AviatorEstrela
source venv/bin/activate

python3 << 'EOF'
from aviator_service2 import load_data_for_analysis

df = load_data_for_analysis()
print("Total:", len(df))
print("\nPrimeiros 3:")
print(df.head(3)[['value', 'timestamp']])
print("\nÚltimos 3:")
print(df.tail(3)[['value', 'timestamp']])
print("\nOrdenado?", df['timestamp'].is_monotonic_increasing)
EOF
```

**Saída esperada:**
```
Total: 500
Primeiros 3:
   value           timestamp
0   1.25 2024-12-27 10:30:00
1   2.50 2024-12-27 10:31:00
2  10.35 2024-12-27 10:32:00

Últimos 3:
     value           timestamp
497   3.75 2024-12-27 18:25:00
498   1.10 2024-12-27 18:26:00
499   5.20 2024-12-27 18:27:00

Ordenado? True
```

## ?? Troubleshooting

### **Dashboard mostra dados fora de ordem**

```sh
# 1. Parar serviço
./parar.sh

# 2. Testar ordenação
./testar_ordenacao.sh

# 3. Se houver erros, reordenar arquivo
python3 << 'EOF'
from aviator_service2 import load_data_for_analysis
import os

df = load_data_for_analysis()
OUTPUT_FILE = "resultados_aviator.txt"

# Reescrever arquivo na ordem correta
with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
    for _, row in df.iterrows():
        ts = int(row['timestamp'].timestamp())
        f.write(f"{row['value']:.2f};{ts}\n")

print("Arquivo reordenado!")
EOF

# 4. Reiniciar
./iniciar_background.sh
```

### **Timestamps com horário errado**

Verifique timezone:
```sh
python3 -c "from aviator_service2 import agora_brasilia; print(agora_brasilia())"
```

Deve mostrar horário de Brasília com offset -03.

### **Dados duplicados**

A deduplicação agora usa timestamp Unix (precisão de 1 segundo):
```python
df["_ts_seconds"] = df["timestamp"].apply(lambda x: int(x.timestamp()))
df = df.drop_duplicates(subset=["value", "_ts_seconds"], keep="first")
```

## ?? Checklist de Validação

- [ ] `git pull` executado
- [ ] Serviço reiniciado
- [ ] `./testar_ordenacao.sh` executado sem erros
- [ ] Dashboard mostra dados na ordem correta
- [ ] Últimas capturas aparecem no topo
- [ ] Timestamps mostram horário de Brasília
- [ ] Sem dados duplicados
- [ ] Gráfico renderiza corretamente

## ?? Resumo das Mudanças

| Arquivo | Linha | Mudança |
|---------|-------|---------|
| `aviator_service2.py` | 929-973 | Correção em `load_data_for_analysis()` |
| `aviator_service2.py` | 941 | Conversão timezone consistente |
| `aviator_service2.py` | 947 | Comparação naive datetime |
| `aviator_service2.py` | 970-971 | Deduplicação por timestamp Unix |
| `aviator_service2.py` | 703 | Uso de `agora_brasilia()` |
| `aviator_service2.py` | 770 | Uso de `agora_brasilia()` |

---

**Correção implementada**: 27/12/2024  
**Versão**: 2.1.1 - Timezone Fix
