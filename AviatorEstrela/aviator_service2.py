# =============================================================================
#  aviator_service.py  —  versão aprimorada com ML adaptativo
#  Melhorias: feature engineering rica, validação temporal, limpeza de outliers,
#  seleção automática de modelo por volume de dados, log de acurácia contínuo.
# =============================================================================

from sklearn.ensemble import RandomForestRegressor, GradientBoostingRegressor
from sklearn.linear_model import Ridge
from sklearn.model_selection import TimeSeriesSplit, cross_val_score
from sklearn.metrics import mean_absolute_error, mean_squared_error
from sklearn.preprocessing import StandardScaler
import numpy as np
import pandas as pd
import joblib
import os
import time
import json
from datetime import datetime, timedelta
from flask import Flask, render_template_string
import threading
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager

# ─────────────────────────────────────────────
#  CONSTANTES GERAIS
# ─────────────────────────────────────────────
INTERVALO_SEGUNDOS = 30
MAX_REGISTROS      = 10000
THRESHOLD_5        = 5.0
THRESHOLD_50       = 50.0
WINDOW_SIZE        = 5
PRE_WINDOW         = 4

# ─────────────────────────────────────────────
#  LIMIARES ADAPTATIVOS DE AMOSTRA
#  O sistema escolhe automaticamente a estratégia
#  conforme o número de gaps disponíveis cresce.
# ─────────────────────────────────────────────
MIN_GAPS_ESTATISTICO  = 3    # apenas média/mediana
MIN_GAPS_RIDGE        = 8    # regressão linear regularizada
MIN_GAPS_RF           = 20   # Random Forest
MIN_GAPS_GBM          = 50   # Gradient Boosting + CV temporal
MIN_GAPS_FEATURES_EXT = 15   # features estendidas (rolling stats)

# ─────────────────────────────────────────────
#  ARQUIVOS DE MODELO E LOG
# ─────────────────────────────────────────────
BASE_DIR         = os.path.dirname(os.path.abspath(__file__))
OUTPUT_FILE      = os.path.join(BASE_DIR, "aviator_data.csv")
PREDICTIONS_FILE = os.path.join(BASE_DIR, "predictions.txt")
MODEL_FILE_5     = os.path.join(BASE_DIR, "gap_model_5.pkl")
MODEL_FILE_50    = os.path.join(BASE_DIR, "gap_model_50.pkl")
SCALER_FILE_5    = os.path.join(BASE_DIR, "scaler_5.pkl")
SCALER_FILE_50   = os.path.join(BASE_DIR, "scaler_50.pkl")
ACCURACY_LOG     = os.path.join(BASE_DIR, "accuracy_log.json")

# ─────────────────────────────────────────────
#  ESTADO DO DASHBOARD
# ─────────────────────────────────────────────
latest_analysis    = {
    'spikes_5': None, 'spikes_50': None,
    'trends': None,
    'total_registros': 0, 'periodo': '', 'ultimo': ''
}
latest_predictions = {'pred_5': None, 'pred_50': None}

# =============================================================================
#  UTILIDADES DE LOG
# =============================================================================

def log(msg):
    print(f"[{datetime.now().strftime('%d/%m/%Y %H:%M:%S')}] {msg}")


# =============================================================================
#  1. LIMPEZA DE OUTLIERS
#     Remove gaps que ficam além de ±3 desvios-padrão.
#     Com poucos dados usa IQR para ser menos agressivo.
# =============================================================================

def clean_gaps(gaps: pd.Series) -> pd.Series:
    """Remove outliers adaptativamente conforme o tamanho da amostra."""
    if len(gaps) < 5:
        return gaps  # amostra muito pequena — não filtra

    if len(gaps) < 20:
        # Com pouca amostra usa IQR (menos agressivo que z-score)
        q1, q3 = gaps.quantile(0.25), gaps.quantile(0.75)
        iqr = q3 - q1
        lower, upper = q1 - 2.5 * iqr, q3 + 2.5 * iqr
    else:
        # Com amostra maior usa z-score ±3σ
        mean, std = gaps.mean(), gaps.std()
        lower, upper = mean - 3 * std, mean + 3 * std

    cleaned = gaps[(gaps >= lower) & (gaps <= upper)]
    removed = len(gaps) - len(cleaned)
    if removed > 0:
        log(f"  [LIMPEZA] {removed} outlier(s) removido(s) dos gaps.")
    return cleaned


# =============================================================================
#  2. FEATURE ENGINEERING ADAPTATIVA
#     Cresce em complexidade conforme mais dados ficam disponíveis.
# =============================================================================

def build_features(gaps: pd.Series):
    """
    Gera matriz de features X e vetor alvo y.
    A janela e os tipos de feature dependem do tamanho da amostra.
    Retorna (X, y, feature_names).
    """
    n = len(gaps)

    # ── Janela de lags dinâmica ──────────────────────────────────────────────
    if n < 10:
        lag_window = 2
    elif n < 20:
        lag_window = 3
    elif n < 40:
        lag_window = 5
    else:
        lag_window = 8

    start_idx = lag_window  # índice mínimo para ter lags completos

    X, y, names = [], [], []

    for i in range(start_idx, n):
        row = []
        feature_names = []

        # Lags brutos
        lags = gaps.iloc[i - lag_window:i].values
        for j, v in enumerate(lags):
            row.append(v)
            feature_names.append(f"lag_{j+1}")

        # Features de rolling stats (apenas se tiver amostra suficiente)
        if n >= MIN_GAPS_FEATURES_EXT:
            window_vals = gaps.iloc[max(0, i - lag_window):i]
            row += [
                window_vals.mean(),                          # média da janela
                window_vals.std() if len(window_vals) > 1 else 0.0,  # desvio
                window_vals.min(),                           # mínimo
                window_vals.max(),                           # máximo
                window_vals.iloc[-1] / (window_vals.mean() + 1e-9),  # ratio último/média
                float((window_vals.diff().dropna() > 0).sum()),       # nº de aumentos
                window_vals.iloc[-1] - window_vals.iloc[0],           # delta da janela
            ]
            feature_names += [
                'roll_mean', 'roll_std', 'roll_min', 'roll_max',
                'ratio_last_mean', 'count_up', 'delta_window'
            ]

        # Posição relativa dentro da série (captura deriva temporal leve)
        if n >= 30:
            row.append(i / n)
            feature_names.append('relative_position')

        X.append(row)
        y.append(gaps.iloc[i])

    if not names:
        names = feature_names  # salva os nomes da última iteração

    return np.array(X), np.array(y), feature_names


# =============================================================================
#  3. SELEÇÃO AUTOMÁTICA DE MODELO POR VOLUME
# =============================================================================

def select_model(n_gaps: int):
    """
    Retorna (model, model_name) adequados para o volume de dados disponível.
    """
    if n_gaps >= MIN_GAPS_GBM:
        model = GradientBoostingRegressor(
            n_estimators=300, max_depth=4,
            learning_rate=0.05, subsample=0.8,
            min_samples_leaf=3, random_state=42
        )
        name = "GradientBoosting"
    elif n_gaps >= MIN_GAPS_RF:
        model = RandomForestRegressor(
            n_estimators=200, max_depth=6,
            min_samples_leaf=2, random_state=42
        )
        name = "RandomForest"
    elif n_gaps >= MIN_GAPS_RIDGE:
        model = Ridge(alpha=1.0)
        name = "Ridge"
    else:
        return None, "Estatistico"

    return model, name


# =============================================================================
#  4. TREINAMENTO COM VALIDAÇÃO TEMPORAL E LOG DE ACURÁCIA
# =============================================================================

def load_accuracy_log() -> dict:
    if os.path.exists(ACCURACY_LOG):
        try:
            with open(ACCURACY_LOG, 'r') as f:
                return json.load(f)
        except Exception:
            pass
    return {"5": [], "50": []}


def save_accuracy_log(acc_log: dict):
    try:
        with open(ACCURACY_LOG, 'w') as f:
            json.dump(acc_log, f, indent=2)
    except Exception as e:
        log(f"  [WARN] Nao foi possivel salvar log de acuracia: {e}")


def train_and_maybe_update(gaps: pd.Series, model_file: str,
                            scaler_file: str, threshold_label: str) -> dict:
    """
    Treina novo modelo, compara com o salvo e substitui apenas se melhorar.
    Retorna um dict com métricas do ciclo atual.
    Funciona com amostras pequenas (degrada graciosamente).
    """
    metrics = {
        'model_name': 'Estatistico',
        'n_gaps': len(gaps),
        'mae': None, 'rmse': None,
        'cv_mae': None, 'cv_std': None,
        'improved': False
    }

    n = len(gaps)
    model, model_name = select_model(n)
    metrics['model_name'] = model_name

    if model is None:
        log(f"  [{threshold_label}] Amostra insuficiente ({n} gaps) → modo estatístico.")
        return metrics

    try:
        X, y, feat_names = build_features(gaps)

        if len(X) < 6:
            log(f"  [{threshold_label}] Poucos exemplos de treino ({len(X)}) → modo estatístico.")
            return metrics

        # ── Normalização (beneficia Ridge; neutro para RF/GBM) ──────────────
        scaler = StandardScaler()
        X_scaled = scaler.fit_transform(X)

        # ── Validação temporal cruzada (quando dados permitem) ──────────────
        if n >= MIN_GAPS_GBM and len(X) >= 15:
            n_splits = min(5, len(X) // 5)
            tscv = TimeSeriesSplit(n_splits=n_splits)
            cv_scores = cross_val_score(
                model, X_scaled, y,
                cv=tscv, scoring='neg_mean_absolute_error'
            )
            metrics['cv_mae'] = float(-cv_scores.mean())
            metrics['cv_std'] = float(cv_scores.std())
            log(f"  [{threshold_label}] CV-MAE: {metrics['cv_mae']:.1f}s "
                f"(±{metrics['cv_std']:.1f}s) | Modelo: {model_name}")
        else:
            log(f"  [{threshold_label}] Amostra limitada ({n} gaps) → sem CV completo. "
                f"Modelo: {model_name}")

        # ── Treino/Teste simples (hold-out temporal) ────────────────────────
        split = max(1, int(len(X) * 0.8))
        X_train, X_test = X_scaled[:split], X_scaled[split:]
        y_train, y_test = y[:split], y[split:]

        model.fit(X_train, y_train)

        new_mae = None
        if len(X_test) > 0:
            preds = model.predict(X_test)
            new_mae  = mean_absolute_error(y_test, preds)
            new_rmse = np.sqrt(mean_squared_error(y_test, preds))
            metrics['mae']  = float(new_mae)
            metrics['rmse'] = float(new_rmse)
            log(f"  [{threshold_label}] MAE={new_mae:.1f}s | RMSE={new_rmse:.1f}s")

        # ── Comparar com modelo anterior ────────────────────────────────────
        should_save = True
        if os.path.exists(model_file) and new_mae is not None:
            try:
                old_model  = joblib.load(model_file)
                old_scaler = joblib.load(scaler_file) if os.path.exists(scaler_file) else scaler
                X_test_old = old_scaler.transform(X[split:])
                old_preds  = old_model.predict(X_test_old)
                old_mae    = mean_absolute_error(y_test, old_preds)
                if old_mae <= new_mae:
                    should_save = False
                    log(f"  [{threshold_label}] Modelo anterior melhor "
                        f"(MAE {old_mae:.1f}s vs {new_mae:.1f}s) → mantido.")
            except Exception:
                pass  # modelo antigo incompatível → substitui

        if should_save:
            # Treina com todos os dados antes de salvar
            model.fit(X_scaled, y)
            joblib.dump(model, model_file)
            joblib.dump(scaler, scaler_file)
            metrics['improved'] = True
            log(f"  [{threshold_label}] Modelo atualizado e salvo.")

        # ── Persiste log de acurácia ─────────────────────────────────────────
        acc_log = load_accuracy_log()
        key = "5" if threshold_label.endswith("5") else "50"
        acc_log[key].append({
            'ts': datetime.now().isoformat(),
            'n_gaps': n,
            'model': model_name,
            'mae': metrics['mae'],
            'rmse': metrics['rmse'],
            'cv_mae': metrics['cv_mae'],
            'improved': metrics['improved']
        })
        # Mantém apenas os últimos 200 registros por threshold
        acc_log[key] = acc_log[key][-200:]
        save_accuracy_log(acc_log)

    except Exception as e:
        log(f"  [{threshold_label}] ERRO no treinamento: {e}")

    return metrics


# =============================================================================
#  5. PREDIÇÃO ROBUSTA (usa modelo salvo ou fallback estatístico)
# =============================================================================

def predict_next_gap(gaps: pd.Series, model_file: str,
                      scaler_file: str, mean_gap: float) -> tuple:
    """
    Retorna (predicted_gap_seconds, method_used).
    Garante predição mesmo com poucos dados.
    """
    if os.path.exists(model_file) and len(gaps) >= MIN_GAPS_RIDGE:
        try:
            model  = joblib.load(model_file)
            scaler = joblib.load(scaler_file) if os.path.exists(scaler_file) else None

            X, _, _ = build_features(gaps)
            if len(X) == 0:
                raise ValueError("Features vazias")

            # Usa apenas o último exemplo (estado mais recente)
            last_x = X[-1].reshape(1, -1)
            if scaler:
                last_x = scaler.transform(last_x)

            pred = model.predict(last_x)[0]
            # Sanitização: não aceita predições negativas ou absurdas (>10× a média)
            pred = max(pred, 1.0)
            pred = min(pred, mean_gap * 10)
            return float(pred), "ML"
        except Exception as e:
            log(f"  [WARN] Predição ML falhou ({e}), usando fallback.")

    # Fallback estatístico: média ponderada (recentes têm mais peso)
    if len(gaps) >= 3:
        weights = np.linspace(0.5, 1.5, len(gaps))
        weighted_mean = float(np.average(gaps.values, weights=weights))
        return weighted_mean, "Media-Ponderada"

    return mean_gap, "Media-Simples"


# =============================================================================
#  6. ANÁLISE DE PICOS — VERSÃO APRIMORADA
# =============================================================================

def analyze_spikes(df, threshold, label):
    """Analisa picos acima do threshold com ML adaptativo e estatísticas robustas."""
    if df is None or df.empty:
        return None

    spikes = df[df["value"] > threshold].copy()
    n_spikes = len(spikes)

    if n_spikes < 2:
        log(f"[ANALYSIS] {label}: Poucos picos ({n_spikes}) — aguardando mais dados.")
        return None

    # ── Gaps brutos ──────────────────────────────────────────────────────────
    spikes = spikes.sort_values("timestamp").reset_index(drop=True)
    spikes["gap_seconds"] = spikes["timestamp"].diff().dt.total_seconds()
    raw_gaps = spikes["gap_seconds"].dropna()

    if raw_gaps.empty:
        return None

    # ── Limpeza de outliers ──────────────────────────────────────────────────
    gaps = clean_gaps(raw_gaps)
    if gaps.empty:
        gaps = raw_gaps  # se limpou tudo, reverte

    # ── Estatísticas descritivas ─────────────────────────────────────────────
    mean_gap   = gaps.mean()
    median_gap = gaps.median()
    std_gap    = gaps.std() if len(gaps) > 1 else 0.0
    if pd.isna(std_gap):
        std_gap = 0.0

    # Percentis para intervalo de confiança mais robusto
    p25 = gaps.quantile(0.25)
    p75 = gaps.quantile(0.75)

    # ── Seleção de arquivos de modelo ────────────────────────────────────────
    is_5 = (threshold == THRESHOLD_5)
    model_file  = MODEL_FILE_5  if is_5 else MODEL_FILE_50
    scaler_file = SCALER_FILE_5 if is_5 else SCALER_FILE_50

    # ── Treinamento adaptativo ───────────────────────────────────────────────
    train_metrics = train_and_maybe_update(
        gaps, model_file, scaler_file,
        threshold_label=f">{threshold}"
    )

    # ── Predição ─────────────────────────────────────────────────────────────
    predicted_gap, pred_method = predict_next_gap(
        gaps, model_file, scaler_file, mean_gap
    )

    # ── Janela de confiança ──────────────────────────────────────────────────
    # Usa IQR quando tiver dados suficientes (mais robusto que σ)
    if len(gaps) >= 10:
        half_window_low  = predicted_gap - (predicted_gap - p25) * 0.5
        half_window_high = predicted_gap + (p75 - predicted_gap) * 0.5
    else:
        half_window_low  = max(0, predicted_gap - 0.5 * std_gap)
        half_window_high = predicted_gap + 0.5 * std_gap

    last_spike_time  = spikes["timestamp"].iloc[-1]
    predicted_next   = last_spike_time + timedelta(seconds=predicted_gap)
    predicted_early  = last_spike_time + timedelta(seconds=half_window_low)
    predicted_late   = last_spike_time + timedelta(seconds=half_window_high)

    # ── Exibição no log ──────────────────────────────────────────────────────
    print(f"\n[ANALYSIS] {label} — Análise de Picos:")
    print(f"  Total de picos (raw):     {n_spikes}")
    print(f"  Gaps usados (s/ outlier): {len(gaps)}")
    print(f"  Intervalo médio:          {mean_gap/60:.2f} min (±{std_gap/60:.2f} min)")
    print(f"  Mediana:                  {median_gap/60:.2f} min")
    print(f"  P25–P75:                  {p25/60:.2f} – {p75/60:.2f} min")
    print(f"  Próximo gap previsto:     {predicted_gap/60:.2f} min  [{pred_method}]")
    print(f"  Modelo ativo:             {train_metrics['model_name']}")
    if train_metrics['mae'] is not None:
        print(f"  MAE hold-out:             {train_metrics['mae']:.1f}s")
    if train_metrics['cv_mae'] is not None:
        print(f"  CV-MAE (temporal):        {train_metrics['cv_mae']:.1f}s "
              f"(±{train_metrics['cv_std']:.1f}s)")
    print(f"  Último pico:              {last_spike_time.strftime('%d/%m/%Y %H:%M:%S')}")
    print(f"  Próximo pico estimado:    {predicted_next.strftime('%d/%m/%Y %H:%M:%S')}")
    print(f"  Janela provável:          {predicted_early.strftime('%H:%M:%S')} → "
          f"{predicted_late.strftime('%H:%M:%S')}")

    # ── Salva previsão ───────────────────────────────────────────────────────
    save_prediction(threshold, predicted_next, predicted_early, predicted_late)

    # ── Atualiza dashboard ───────────────────────────────────────────────────
    key = 'spikes_5' if is_5 else 'spikes_50'
    latest_analysis[key] = {
        'total':          n_spikes,
        'gaps_clean':     len(gaps),
        'mean_gap':       mean_gap / 60,
        'median_gap':     median_gap / 60,
        'std_gap':        std_gap / 60,
        'p25':            p25 / 60,
        'p75':            p75 / 60,
        'predicted_gap':  predicted_gap / 60,
        'pred_method':    pred_method,
        'model_name':     train_metrics['model_name'],
        'mae':            train_metrics['mae'],
        'cv_mae':         train_metrics['cv_mae'],
        'predicted_next': predicted_next.strftime('%d/%m/%Y %H:%M:%S'),
        'window':         (f"{predicted_early.strftime('%H:%M:%S')} → "
                           f"{predicted_late.strftime('%H:%M:%S')}"),
    }

    return predicted_next


# =============================================================================
#  7. ANÁLISE DE TENDÊNCIAS — VERSÃO APRIMORADA
#     Usa ajuste polinomial de grau 2 (além do linear) e projeção ponderada.
# =============================================================================

def analyze_trends(df):
    """Analisa tendências com rolling window e ajuste polinomial adaptativo."""
    if df is None or len(df) < WINDOW_SIZE:
        return

    df = df.copy().reset_index(drop=True)
    df["rolling_mean"] = df["value"].rolling(WINDOW_SIZE).mean()

    # Slope linear (grau 1)
    df["rolling_slope"] = df["value"].rolling(WINDOW_SIZE).apply(
        lambda x: np.polyfit(range(len(x)), x, 1)[0]
        if len(x) == WINDOW_SIZE else np.nan,
        raw=True
    )

    # Curvatura (grau 2) — indica aceleração/desaceleração da tendência
    df["rolling_curv"] = df["value"].rolling(WINDOW_SIZE).apply(
        lambda x: np.polyfit(range(len(x)), x, 2)[0]
        if len(x) == WINDOW_SIZE else np.nan,
        raw=True
    )

    if df["rolling_slope"].isna().all():
        return

    last_mean  = df["rolling_mean"].iloc[-1]
    last_slope = df["rolling_slope"].iloc[-1]
    last_curv  = df["rolling_curv"].iloc[-1] if not df["rolling_curv"].isna().all() else 0.0

    print(f"\n[ANALYSIS] Tendência Rolling Window (últimas {WINDOW_SIZE} amostras):")
    print(f"  Média:      {last_mean:.2f}")
    print(f"  Inclinação: {last_slope:.4f}")
    print(f"  Curvatura:  {last_curv:.6f}")

    # Projeção com componente quadrático
    projections = []
    for i in range(1, PRE_WINDOW + 1):
        pred = last_mean + i * last_slope + (i ** 2) * last_curv * 0.5
        projections.append(pred)
        alert_5  = pred > THRESHOLD_5
        alert_50 = pred > THRESHOLD_50
        print(f"  Projeção +{i}: {pred:.2f}"
              + ("  ⚠ >5"  if alert_5  else "")
              + ("  ⚠ >50" if alert_50 else ""))

    latest_analysis['trends'] = {
        'mean':       last_mean,
        'slope':      last_slope,
        'curvature':  last_curv,
        'projections': [
            {'value': p, 'alert_5': p > THRESHOLD_5, 'alert_50': p > THRESHOLD_50}
            for p in projections
        ]
    }


# =============================================================================
#  8. DASHBOARD FLASK — ATUALIZADO COM MÉTRICAS DE ACURÁCIA
# =============================================================================

app = Flask(__name__)


@app.route('/')
def dashboard():
    html = """
    <!DOCTYPE html>
    <html lang="pt-BR">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Aviator Dashboard</title>
        <meta http-equiv="refresh" content="30">
        <style>
            body { font-family: Arial, sans-serif; margin: 20px; background: #f5f5f5; }
            h1 { color: #1a237e; }
            h2, h3 { color: #333; }
            .section { margin-bottom: 20px; border: 1px solid #ccc;
                       padding: 14px; background: #fff; border-radius: 6px; }
            .alert  { color: red;    font-weight: bold; }
            .good   { color: green;  font-weight: bold; }
            .info   { color: #555;   font-size: 0.9em; }
            .badge  { display:inline-block; padding:2px 8px; border-radius:4px;
                      font-size:0.85em; font-weight:bold; }
            .badge-gb  { background:#e8f5e9; color:#2e7d32; }
            .badge-rf  { background:#e3f2fd; color:#1565c0; }
            .badge-rdg { background:#fff3e0; color:#e65100; }
            .badge-est { background:#f3e5f5; color:#6a1b9a; }
            table { border-collapse:collapse; width:100%; font-size:0.9em; }
            td, th { padding:6px 10px; border:1px solid #ddd; text-align:left; }
            th { background:#e8eaf6; }
        </style>
    </head>
    <body>
        <h1>🛩 Aviator Analysis Dashboard</h1>

        <div class="section">
            <h2>Visão Geral</h2>
            <p><strong>Total de registros:</strong> {{ total_registros }}</p>
            <p><strong>Período:</strong> {{ periodo }}</p>
            <p><strong>Último registro:</strong> {{ ultimo }}</p>
        </div>

        {% for key, sp, label in [('spikes_5', spikes_5, 'Spikes > 5'),
                                   ('spikes_50', spikes_50, 'Spikes > 50')] %}
        <div class="section">
            <h3>{{ label }}</h3>
            {% if sp %}
            <table>
                <tr><th>Métrica</th><th>Valor</th></tr>
                <tr><td>Total de picos (raw)</td>
                    <td>{{ sp.total }}</td></tr>
                <tr><td>Gaps usados (s/ outliers)</td>
                    <td>{{ sp.gaps_clean }}</td></tr>
                <tr><td>Intervalo médio</td>
                    <td>{{ "%.2f"|format(sp.mean_gap) }} min
                        (±{{ "%.2f"|format(sp.std_gap) }} min)</td></tr>
                <tr><td>Mediana</td>
                    <td>{{ "%.2f"|format(sp.median_gap) }} min</td></tr>
                <tr><td>P25 – P75</td>
                    <td>{{ "%.2f"|format(sp.p25) }} – {{ "%.2f"|format(sp.p75) }} min</td></tr>
                <tr><td>Modelo ativo</td>
                    <td>
                    {% if sp.model_name == 'GradientBoosting' %}
                        <span class="badge badge-gb">{{ sp.model_name }}</span>
                    {% elif sp.model_name == 'RandomForest' %}
                        <span class="badge badge-rf">{{ sp.model_name }}</span>
                    {% elif sp.model_name == 'Ridge' %}
                        <span class="badge badge-rdg">{{ sp.model_name }}</span>
                    {% else %}
                        <span class="badge badge-est">{{ sp.model_name }}</span>
                    {% endif %}
                    </td></tr>
                <tr><td>Método de predição</td>
                    <td>{{ sp.pred_method }}</td></tr>
                <tr><td>Próximo gap previsto (ML)</td>
                    <td><strong>{{ "%.2f"|format(sp.predicted_gap) }} min</strong></td></tr>
                {% if sp.mae is not none %}
                <tr><td>MAE (hold-out)</td>
                    <td class="good">{{ "%.1f"|format(sp.mae) }}s</td></tr>
                {% endif %}
                {% if sp.cv_mae is not none %}
                <tr><td>CV-MAE (temporal)</td>
                    <td class="good">{{ "%.1f"|format(sp.cv_mae) }}s</td></tr>
                {% endif %}
                <tr><td>Último pico</td>
                    <td>{{ sp.predicted_next }}</td></tr>
                <tr><td>Próximo pico estimado</td>
                    <td><strong>{{ sp.predicted_next }}</strong></td></tr>
                <tr><td>Janela provável</td>
                    <td>{{ sp.window }}</td></tr>
            </table>
            {% else %}
            <p class="info">Aguardando dados suficientes…</p>
            {% endif %}
        </div>
        {% endfor %}

        <div class="section">
            <h3>Tendência Rolling Window</h3>
            {% if trends %}
            <p><strong>Média:</strong> {{ "%.2f"|format(trends.mean) }}</p>
            <p><strong>Inclinação:</strong> {{ "%.4f"|format(trends.slope) }}</p>
            <p><strong>Curvatura:</strong> {{ "%.6f"|format(trends.curvature) }}</p>
            {% for proj in trends.projections %}
            <p>
                <strong>Projeção +{{ loop.index }}:</strong>
                {{ "%.2f"|format(proj.value) }}
                {% if proj.alert_5  %}<span class="alert">⚠ &gt;5</span>{% endif %}
                {% if proj.alert_50 %}<span class="alert">⚠ &gt;50</span>{% endif %}
            </p>
            {% endfor %}
            {% else %}
            <p class="info">Aguardando dados suficientes…</p>
            {% endif %}
        </div>

        <div class="section">
            <h3>Estatísticas de Predição</h3>
            <p><strong>&gt;5:</strong>
                Total: {{ pred_5.total if pred_5 else 'N/A' }},
                Hits: {{ pred_5.hits if pred_5 else 'N/A' }},
                Misses: {{ pred_5.misses if pred_5 else 'N/A' }},
                Hit Rate: {{ "%.1f"|format(pred_5.rate) if pred_5 and pred_5.rate is not none else 'N/A' }}%,
                Pendentes: {{ pred_5.pending if pred_5 else 'N/A' }}
            </p>
            <p><strong>&gt;50:</strong>
                Total: {{ pred_50.total if pred_50 else 'N/A' }},
                Hits: {{ pred_50.hits if pred_50 else 'N/A' }},
                Misses: {{ pred_50.misses if pred_50 else 'N/A' }},
                Hit Rate: {{ "%.1f"|format(pred_50.rate) if pred_50 and pred_50.rate is not none else 'N/A' }}%,
                Pendentes: {{ pred_50.pending if pred_50 else 'N/A' }}
            </p>
        </div>

        <p class="info" style="text-align:right">
            Atualizado automaticamente a cada 30s —
            {{ now }}
        </p>
    </body>
    </html>
    """
    return render_template_string(
        html,
        now=datetime.now().strftime('%d/%m/%Y %H:%M:%S'),
        **latest_analysis,
        **latest_predictions
    )


# =============================================================================
#  9. ANÁLISE GERAL (chamada a cada ciclo)
# =============================================================================

def run_analysis():
    """Executa análise dos dados capturados e atualiza o dashboard."""
    try:
        df = carregar_existentes()
    except Exception:
        df = None

    if df is None or df.empty:
        log("DataFrame vazio. Abortando análise.")
        return

    log(f"\n{'='*60}")
    log(f"[ANALYSIS] Análise — {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")
    log(f"  Total de registros: {len(df)}")
    log(f"  Período: {df['timestamp'].min()} → {df['timestamp'].max()}")
    log(f"  Último valor: {df['value'].iloc[-1]:.2f}")

    latest_analysis['total_registros'] = len(df)
    latest_analysis['periodo'] = (
        f"{df['timestamp'].min().strftime('%d/%m/%Y %H:%M')} → "
        f"{df['timestamp'].max().strftime('%d/%m/%Y %H:%M')}"
    )
    latest_analysis['ultimo'] = (
        f"{df['timestamp'].max().strftime('%d/%m/%Y %H:%M:%S')} "
        f"— Valor: {df['value'].iloc[-1]:.2f}"
    )

    analyze_spikes(df, THRESHOLD_5,  "Spikes >5")
    analyze_spikes(df, THRESHOLD_50, "Spikes >50")
    analyze_trends(df)


# =============================================================================
#  10. DRIVER E FLUXO PRINCIPAL (inalterado)
# =============================================================================

def iniciar_driver():
    options = Options()
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1920,1080")
    driver = webdriver.Chrome(
        service=Service(ChromeDriverManager().install()), options=options
    )
    driver.set_page_load_timeout(120)
    driver.execute_script(
        "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
    )
    return driver


def main():
    if os.path.exists(OUTPUT_FILE):
        log("=== AviatorService iniciado — continuando captura em arquivo existente ===")
    else:
        log("=== AviatorService iniciado ===")

    driver = iniciar_driver()

    # Inicia dashboard Flask em thread separada
    threading.Thread(
        target=lambda: app.run(host='0.0.0.0', port=5000,
                               debug=False, use_reloader=False),
        daemon=True
    ).start()

    # Login com retry
    login_sucesso = False
    for tentativa in range(1, 3):
        try:
            fazer_login(driver)
            login_sucesso = True
            break
        except Exception as e:
            log(f"ERRO no login tentativa {tentativa}: {e}")
            if tentativa < 2 and "timeout" in str(e).lower():
                log("Tentando login novamente após timeout…")
                time.sleep(5)
            else:
                log("Falha no login — tentando captura sem login.")
                break

    log("Login realizado com sucesso." if login_sucesso else "Prosseguindo sem login.")

    # Análise inicial dos dados pré-existentes
    if os.path.exists(OUTPUT_FILE):
        log("Exibindo análise dos dados pré-existentes…")
        run_analysis()

    ciclo = 0
    while True:
        ciclo += 1
        log(f"--- Ciclo {ciclo} ---")

        try:
            novos = capturar_ultimos(driver)
            log(f"Capturados {len(novos)} registros da página.")

            existentes = carregar_existentes()
            mesclados, adicionados = mesclar(existentes, novos)
            salvar_arquivo(mesclados)
            log(f"Adicionados {adicionados} novos registros. "
                f"Total no arquivo: {len(mesclados)}.")

        except Exception as e:
            log(f"ERRO no ciclo {ciclo}: {e}")
            try:
                fazer_login(driver)
            except Exception as e2:
                log(f"ERRO ao relogar: {e2}")

        run_analysis()

        log(f"Aguardando {INTERVALO_SEGUNDOS} segundos…")
        time.sleep(INTERVALO_SEGUNDOS)


if __name__ == "__main__":
    main()
