# Guia Rápido - Sistema ML Melhorado

## Como Usar as Novas Funcionalidades

### 1. Limpar e Retreinar (Recomendado Após Atualização)
```bash
# Limpa modelos antigos (incompatíveis com novas features)
python ml_diagnostico.py --clean

# Retreina todos os modelos com as novas melhorias
python ml_diagnostico.py --retrain
```

### 2. Verificar Performance dos Modelos

#### Diagnóstico Completo
```bash
python ml_diagnostico.py
```
Mostra:
- Modelos em disco (idade, amostras, CV MAE)
- Dados disponíveis (total, período, percentis)
- Estatísticas por threshold (incluindo >100x)
- Histórico de assertividade

#### Ver Apenas Histórico
```bash
python ml_diagnostico.py --history
```

### 3. Retreino Seletivo

```bash
# Retreinar apenas modelos >50x
python ml_diagnostico.py --retrain >50

# Retreinar apenas modelos >100x
python ml_diagnostico.py --retrain >100
```

### 4. Interpretar Resultados no Dashboard

#### Card "Spikes > 100"
- **Assertividade ML**: % de previsões corretas (janela acertada)
- **Gap Médio**: Tempo/rodadas históricos entre spikes
- **Previsão ML (Tempo)**: Próximo spike em X minutos
- **Previsão ML (Valor)**: Estimativa do valor do próximo spike >100x
- **ML ALINHADO** ??: Previsão ML concorda com média estatística (±35%)
- **ML DIVERGENTE** ??: ML detectou padrão diferente da média

#### Contador "Nas últimas 100 rodadas"
- **>100: X**: Quantos valores ?100x ocorreram recentemente
- Útil para avaliar "momento quente" de valores altos

### 5. Entender as Previsões de Valor

#### Antes (Limitado)
```
Spike >50x detectado: 120.5x
Previsão próximo valor: 68.2x  ? Clamped em P75*2 (subestimado)
```

#### Agora (Melhorado)
```
Spike >50x detectado: 120.5x
Previsão próximo valor: 142.8x  ? Pode prever valores altos (até median*6)
```

### 6. Indicadores de Qualidade

#### CV MAE (Cross-Validation Mean Absolute Error)
- **<10 para tempo**: Excelente (±10 min de erro médio)
- **<20 para rounds**: Excelente (±20 rodadas de erro médio)  
- **<30 para valor**: Muito bom (±30x de erro médio)
- **<50 para valor >100**: Aceitável (valores muito variáveis)

#### Assertividade (Accuracy)
- **>70%**: Excelente
- **50-70%**: Bom
- **30-50%**: Aceitável (spikes muito raros)
- **<30%**: Ruim (considere retreinar ou aumentar histórico)

### 7. Quando Retreinar Manualmente

Retreine se:
1. **CV MAE alto**: Modelo desatualizado
2. **Assertividade baixa**: Padrões mudaram
3. **Idade >2h**: Modelos expirados automaticamente
4. **Após coletar muitos dados novos**: Ex: +500 rodadas

### 8. Troubleshooting

#### "N/A" em Previsões
- **Causa**: Poucos dados (<10 amostras)
- **Solução**: Aguarde mais capturas ou force retreino

#### Valores Sempre Baixos (mesmo com spikes altos no histórico)
- **Causa**: Modelos antigos sem novas features
- **Solução**: `python ml_diagnostico.py --clean` + `--retrain`

#### "ML DIVERGENTE" Constante
- **Causa**: Regime em transição ou mudança de padrão
- **Interpretação**: ML pode estar certo (detectou tendência futura)

#### Previsões Irreais (ex: 500x para >5x)
- **Causa**: Corrupção de dados ou outliers extremos
- **Solução**: `python ml_diagnostico.py --clean` (remove entradas >500x do histórico)

---

## Fluxo de Trabalho Recomendado

### Diário
1. Iniciar `python aviator_service2.py`
2. Monitorar dashboard em `http://localhost:5005`
3. Observar >100 e >50 para entradas de alto valor

### Semanal
```bash
# Diagnóstico e limpeza
python ml_diagnostico.py --clean
python ml_diagnostico.py
```

### Mensal
```bash
# Retreino completo para incorporar padrões novos
python ml_diagnostico.py --retrain
```

---

## Features Exclusivas para Modelos de Valor

Quando o modelo detecta `_valor` no label, adiciona:
1. **P75**: Captura valores médio-altos
2. **P90**: Captura valores próximos ao extremo
3. **Mediana**: Robusta a outliers
4. **Skewness**: Detecta assimetria da distribuição
5. **Trend (slope recente)**: Momentum dos últimos 3 valores

Total: **lag + 6 base + 5 valor + 4 cíclicas = lag + 15 features**

Modelos normais (tempo/rounds): **lag + 10 features**

---

**Dica Pro**: Para maximizar assertividade de valores >100x, acumule pelo menos 15-20 ocorrências (?7500-10000 rodadas) antes de confiar nas previsões.
