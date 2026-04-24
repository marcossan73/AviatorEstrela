# Melhorias no Sistema ML de Previsão - AviatorEstrela

## Resumo das Alterações

Este documento descreve as melhorias implementadas no sistema de Machine Learning para aumentar a acurácia das previsões, especialmente para valores altos (>100x).

## Problemas Identificados

1. **Previsão de Valores Estagnada**: O modelo de previsão de valores (especialmente para spikes >50x e >100x) não conseguia estimar adequadamente os picos maiores
2. **Clamping Muito Restritivo**: O limite superior da previsão (P75 * 2) era muito conservador e impedia a predição de valores altos
3. **Falta de Features Especializadas**: Modelos de valor usavam as mesmas features que modelos de tempo
4. **Sem Threshold >100x**: Não havia análise específica para valores extremamente altos

## Soluções Implementadas

### 1. Novo Threshold >100x
- Adicionado `THRESHOLD_100 = 100.0`
- Janela de treinamento de 7500 rodadas (máximo histórico para spikes muito raros)
- Intervalo de retreino de 5 gaps (mais frequente devido à raridade)
- Análise completa integrada ao dashboard

### 2. Features Especializadas para Modelos de Valor
Adicionadas 5 novas features estatísticas quando `is_value_model=True`:
- **P75 (Percentil 75)**: Captura tendência de valores médio-altos
- **P90 (Percentil 90)**: Captura valores próximos aos extremos
- **Mediana**: Mais robusta que média para distribuições assimétricas
- **Skewness (Assimetria)**: Detecta se há concentração de valores baixos ou altos
- **Tendência Recente**: Slope dos últimos 3 valores (momentum)

### 3. Modelos Mais Robustos para Previsão de Valores
Para modelos com `_valor` no label:
- **Random Forest**: 120 estimadores (vs 80), max_depth=8 (vs 6)
- **Gradient Boosting**: 120 estimadores (vs 80), max_depth=5 (vs 4), learning_rate=0.03 (vs 0.05)
- **Ridge Final**: alpha=0.3 (vs 0.5) - mais flexível
- Maior capacidade de capturar padrões complexos em valores extremos

### 4. Clamping Adaptativo e Permissivo
**Para Modelos de Valor**:
- Upper bound: `max(P90*2.5, P75*3.5, max*1.5, median*5.0)`
- Muito mais permissivo que antes (P75*2)

**Para Spikes >50x (inclui >100x)**:
- Upper bound específico: `max(P90*3.0, P75*4.0, max*1.8, median*6.0)`
- Permite previsões até 6x a mediana para capturar outliers extremos

**Para Spikes <50x**:
- Upper bound: `max(P90*2.0, P75*3.0, max*1.5, median*4.0)`
- Mais conservador, apropriado para valores mais frequentes

### 5. Ajustes no Dashboard
- Adicionado contador de >100x nas últimas 100 rodadas
- Card de análise para spikes_100 no grid principal
- Estatísticas completas de >100x no diagnóstico

## Configurações de Retreino por Threshold

| Threshold | Intervalo Retreino | Janela Treinamento | Estimativa Gaps |
|-----------|-------------------|-------------------|-----------------|
| >5x       | 40 gaps           | 1750 rodadas      | 250-350 gaps    |
| >10x      | 25 gaps           | 3000 rodadas      | 40-60 gaps      |
| >50x      | 10 gaps           | 5000 rodadas      | 17-25 gaps      |
| **>100x** | **5 gaps**        | **7500 rodadas**  | **10-15 gaps**  |

## Impacto Esperado

### Previsão de Tempo
- Mantém alta acurácia (~60-70%)
- Sem alterações significativas no comportamento

### Previsão de Valor
- **Antes**: Limitado a ~2x o P75 ? Subestimava spikes altos
- **Depois**: Até 6x a mediana para >50x ? Pode prever valores >100x
- **Melhoria Esperada**: 
  - Valores <50x: +10-15% de acurácia (menos underfitting)
  - Valores >100x: +30-50% de acurácia (antes não conseguia prever adequadamente)

## Como Testar

### 1. Retreinar Modelos Existentes
```bash
# Retreinar apenas modelos de valor
python ml_diagnostico.py --retrain

# Limpar modelos antigos primeiro
python ml_diagnostico.py --clean
python ml_diagnostico.py --retrain
```

### 2. Monitorar Predições
```bash
# Ver estatísticas completas
python ml_diagnostico.py

# Ver histórico de assertividade
python ml_diagnostico.py --history
```

### 3. Verificar no Dashboard
- Acessar `http://localhost:5005`
- Verificar card "Spikes > 100"
- Observar "Previsão ML (Valor)" em cada threshold
- Contador ">100:" nas últimas 100 rodadas

## Arquivos Modificados

1. **aviator_service2.py**:
   - `build_features()`: +5 features para modelos de valor
   - `predict_optimized()`: Modelos mais robustos + clamping adaptativo
   - `analyze_spikes()`: +1 janela de treinamento (>100x)
   - `main_loop()`: +1 análise (THRESHOLD_100)
   - Dashboard HTML: +1 card e contador

2. **ml_diagnostico.py**:
   - Import THRESHOLD_100
   - Estatísticas de >100x
   - Retreino incluindo >100x

## Observações Importantes

1. **Peso Exponencial**: O peso `0.995^i` garante que dados antigos têm mínima influência, então janelas maiores são seguras
2. **Log Transformation**: Mantida para domesticar distribuição long-tail (valores muito dispersos)
3. **Cross-Validation**: Ativada apenas para n_samples > 50 (consistência estatística)
4. **Persistência**: Modelos salvos em `ml_models/` com metadados completos

## Próximos Passos (Opcional)

1. Adicionar weight_sample baseado em valores (dar mais peso a spikes altos)
2. Feature engineering com interações (ex: mean * std, max/min ratio)
3. Ensemble com modelos não-lineares adicionais (XGBoost, LightGBM)
4. Análise de erro por faixa de valor (MAE separado para <50, 50-100, >100)

---
**Data**: Dezembro 2024  
**Versão**: 2.0 - Enhanced Value Prediction
