# -*- coding: utf-8 -*-
# =============================================================================
#  AviatorService.py  —  Versão STACKED REGIME DETECTOR (Final)
#  Melhorias: Detecção de estados de 'Seca', Ensemble de ML (GBM/Ridge),
#  e lógica de confiança para reduzir entradas em momentos desfavoráveis.
# =============================================================================

import os
import time
import json
import joblib
import threading
import winsound
import numpy as np
import pandas as pd
from datetime import date, datetime, timedelta
from flask import Flask, render_template_string, request

# ML & Preprocessing
from sklearn.ensemble import RandomForestRegressor, GradientBoostingRegressor, StackingRegressor
from sklearn.linear_model import Ridge
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import mean_absolute_error, mean_squared_error
from sklearn.model_selection import TimeSeriesSplit

# Selenium
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# ---------------------------------------------------------------------------
# Configurações e Caminhos
# ---------------------------------------------------------------------------
LOGIN_URL = "https://www.tipminer.com/br/historico/estrelabet/aviator"
EMAIL = "marcossa73.ms@gmail.com"
SENHA = "Mrcs3@46(*&"

BASE_DIR         = os.path.dirname(os.path.abspath(__file__))
OUTPUT_FILE      = os.path.join(BASE_DIR, "resultados_aviator.txt")
LOG_FILE         = os.path.join(BASE_DIR, "log_execucao.txt")
PREDICTIONS_FILE = os.path.join(BASE_DIR, "predictions.txt")
ACCURACY_LOG     = os.path.join(BASE_DIR, "accuracy_log.json")

THRESHOLD_5, THRESHOLD_10, THRESHOLD_50 = 5.0, 10.0, 50.0
WINDOW_SIZE = 5
INTERVALO_SEGUNDOS = 10
MAX_REGISTROS = 10000

# ---------------------------------------------------------------------------
# Novo: Detector de Regime Oculto (Minimização de Seca)
# ---------------------------------------------------------------------------
class RegimeDetector:
    """Classifica o estado do jogo para evitar apostas em períodos de 'baixa' usando Meta-Análise."""
    def __init__(self, window=12, macro_window=12):
        self.window = window
        self.macro_window = macro_window

    def _evaluate_slice(self, slice_series):
        volatility = slice_series.std()
        avg = slice_series.mean()

        # Identificação de padrões
        if avg < 1.8 and volatility < 0.8:
            return "Seca Severa", 0.15 # Confiança muito baixa
        elif avg < 2.2 and volatility > 1.2:
            return "Recuperação", 0.55 # Transição
        elif avg > 2.8 or (slice_series > 10).any():
            return "Distribuição", 0.85 # Momento propício
        return "Estável", 0.50

    def get_state(self, df):
        if len(df) < self.window: 
            return "Amostragem Baixa", 0.5, "Indefinido", 0.5

        # Análise Micro (Janela atual isolada)
        recent = df.tail(self.window)['value']
        regime_micro, conf_micro = self._evaluate_slice(recent)

        # Meta-Análise Macro (Histórico de avaliações de confiança)
        historico_confiancas = []
        max_idx = len(df)
        # Limite voltando rodada por rodada, respeitando tamanho dos dados
        limites_analise = min(self.macro_window, max_idx - self.window + 1)

        for i in range(limites_analise):
            start = max_idx - self.window - i
            end = max_idx - i
            slice_series = df.iloc[start:end]['value']
            _, conf_slice = self._evaluate_slice(slice_series)
            historico_confiancas.append(conf_slice)

        if not historico_confiancas:
            macro_mean = conf_micro
        else:
            macro_mean = sum(historico_confiancas) / len(historico_confiancas)

        if macro_mean <= 0.35:
            regime_macro = "Tendência Baixa"
        elif macro_mean <= 0.60:
            regime_macro = "Tendência Estável"
        else:
            regime_macro = "Tendência Alta"

        return regime_micro, conf_micro, regime_macro, macro_mean

# ---------------------------------------------------------------------------
# Funções de Log e Driver
# ---------------------------------------------------------------------------
def log(msg):
    agora = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    linha = f"[{agora}] {msg}"
    print(linha)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(linha + "\n")

def iniciar_driver():
    options = Options()
    options.add_argument("--headless")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--log-level=3")  # Oculta mensagens não-críticas
    options.add_experimental_option('excludeSwitches', ['enable-logging']) # Desabilita devtools port warning e info messages de GCM
    options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36")
    
    # Reparo do erro OSError: [WinError 193]
    # O driver baixado no cache da biblioteca ChromeDriverManager corrompeu.
    # O Selenium (a partir da v4.6+) gerencia automaticamente o ChromeDriver sem precisar dele.
    driver = webdriver.Chrome(options=options)
    driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
    return driver

# ---------------------------------------------------------------------------
# Lógica de Captura e Login (Preservada)
# ---------------------------------------------------------------------------
def fazer_login(driver):
    try:
        log("Iniciando Login...")
        driver.get(LOGIN_URL)
        time.sleep(3)
        btn_login = WebDriverWait(driver, 20).until(EC.presence_of_element_located((By.XPATH, "//button[contains(., 'Acesse sua conta')]")))
        driver.execute_script("arguments[0].click();", btn_login)
        
        WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.CSS_SELECTOR, "input.action-email"))).send_keys(EMAIL)
        driver.find_element(By.CSS_SELECTOR, "input.action-password").send_keys(SENHA)
        btn_acessar = driver.find_element(By.XPATH, "//button[@type='submit' and contains(., 'Acessar')]")
        driver.execute_script("arguments[0].click();", btn_acessar)
        time.sleep(3)
        log("Login OK.")
    except Exception as e:
        log(f"Falha no Login: {e}")

def capturar_ultimos(driver):
    try:
        driver.get(f"{LOGIN_URL}?t={int(time.time()*1000)}&limit=50&subject=filter&isLoadMore=true")
        WebDriverWait(driver, 20).until(EC.presence_of_element_located((By.CSS_SELECTOR, ".cell__result")))

        now = datetime.now()
        hoje_str = now.strftime("%d/%m/%Y")
        ontem_str = (now - timedelta(days=1)).strftime("%d/%m/%Y")
        novos = []

        # Batch extraction via JavaScript para desempenho ultra-rápido (Sem gargalo IPC Selenium)
        script_extracao = """
        let resultados = [];
        document.querySelectorAll('.cell__result').forEach(el => {
            let val = el.innerText.replace('x','').replace('X','').replace(',', '.').trim();
            let btn = el.closest('button');

            if (!val && btn) {
                let dataResult = btn.getAttribute('data-result');
                if (dataResult) val = dataResult.replace('X', '').replace('x', '').replace(',', '.').trim();
            }

            let hora = '';
            if (btn) {
                let dateEl = btn.querySelector('.cell__date');
                if (dateEl) hora = dateEl.innerText.trim();
            }

            if (val && hora) {
                resultados.push({val: val.replace('.', ','), hora: hora});
            }
        });
        return resultados;
        """
        extracted = driver.execute_script(script_extracao)

        for item in extracted:
            val = item.get("val")
            hora = item.get("hora")

            try:
                dt_tentativa = datetime.strptime(f"{hoje_str} {hora}", "%d/%m/%Y %H:%M:%S")
                # Se o horário do chute no site for por exemplo 23:59 e agora for 00:01
                # o dt_tentativa cai no 'hoje' as 23:59 (Quase 24h no futuro)
                data_correta = ontem_str if dt_tentativa > now + timedelta(minutes=5) else hoje_str
                ts = datetime.strptime(f"{data_correta} {hora}", "%d/%m/%Y %H:%M:%S")
                novos.append((val, ts.timestamp()))
            except:
                continue

        return novos
    except Exception as e:
        log(f"Erro captura: {e}")
        return []

# ---------------------------------------------------------------------------
# Machine Learning Adaptativo (Refatorado para Stacked Ensemble)
# ---------------------------------------------------------------------------

# Cache global de modelos treinados — evita retreinar do zero a cada ciclo
_model_cache = {}
# Intervalo de retreino proporcional: thresholds raros (>50x) retreinam com menos gaps novos
_MODEL_RETRAIN_INTERVALS = {
    'default': 50,   # Padrão para labels desconhecidos
    '>5': 40,        # Spikes frequentes — retreina a cada ~40 gaps
    '>10': 25,       # Spikes moderados — retreina a cada ~25 gaps
    '>50': 10,       # Spikes raros — retreina a cada ~10 gaps (era 50!)
}
_MODEL_MAX_AGE_SECONDS = 7200  # Modelo expira após 2 horas independentemente
_MODEL_CV_MAE_DEGRADE_FACTOR = 1.5  # Retreina se CV MAE atual > 1.5x o CV MAE do treino
_MODEL_PERSIST_DIR = os.path.join(BASE_DIR, "ml_models")
os.makedirs(_MODEL_PERSIST_DIR, exist_ok=True)

def _safe_filename(name):
    """Sanitiza nome para uso como arquivo no Windows (remove caracteres invalidos)."""
    return name.replace('>', 'gt').replace('<', 'lt').replace(':', '_').replace('"', '_').replace('|', '_').replace('?', '_').replace('*', '_')


def build_features(gaps: pd.Series, timestamps: pd.Series = None, forced_lag: int = None):
    """
    Constrói features a partir de janela deslizante sobre os gaps.
    Se timestamps for fornecido, adiciona features cíclicas de hora e dia.
    """
    n = len(gaps)
    lag = forced_lag if forced_lag is not None else (5 if n > 15 else 3)
    X, y = [], []
    for i in range(lag, n):
        window = gaps.iloc[i-lag:i]
        feats = list(window.values)
        feats.append(window.mean())
        feats.append(window.std() if len(window) > 1 else 0)
        feats.append(window.iloc[-1] / (window.mean() + 1e-6))  # Ratio
        feats.append(window.min())
        feats.append(window.max())
        feats.append(window.max() - window.min())  # Range

        # Features cíclicas de hora do dia e dia da semana
        if timestamps is not None and i < len(timestamps):
            ts = timestamps.iloc[i]
            hour = ts.hour + ts.minute / 60.0
            feats.append(np.sin(2 * np.pi * hour / 24))
            feats.append(np.cos(2 * np.pi * hour / 24))
            dow = ts.weekday()
            feats.append(np.sin(2 * np.pi * dow / 7))
            feats.append(np.cos(2 * np.pi * dow / 7))
        else:
            feats.extend([0.0, 0.0, 0.0, 0.0])

        X.append(feats)
        y.append(gaps.iloc[i])
    return np.array(X), np.array(y)





def predict_optimized(data_series, threshold_label, spike_timestamps=None):
    """
    Treina o modelo usando o passado (X, y)
    E preve O FUTURO criando features a partir dos ultimos 'lag' observados.
    Usa cache de modelo para evitar retreinamento desnecessário.
    """
    global _model_cache

    if len(data_series) < 10:
        mean_val = float(data_series.mean())
        return mean_val, mean_val

    try:
        # Calcula lag UMA VEZ baseado em data_series e reutiliza em treino e previsão
        n = len(data_series)
        lag = 5 if n > 15 else 3
        n_features = lag + 10  # lag values + 6 estatísticas + 4 cíclicas

        X, y = build_features(data_series, spike_timestamps, forced_lag=lag)
        n_samples = len(X)

        if n_samples < 3:
            mean_val = float(data_series.mean())
            return mean_val, mean_val

        # Cache de modelo — retreina por múltiplos critérios inteligentes
        cache_key = threshold_label
        cached = _model_cache.get(cache_key)
        cached_n_features = cached.get('n_features') if cached else None

        # Determina intervalo de retreino proporcional ao threshold
        base_label = threshold_label.split('_')[0]  # ">5_tempo" -> ">5"
        retrain_interval = _MODEL_RETRAIN_INTERVALS.get(base_label, _MODEL_RETRAIN_INTERVALS['default'])

        # Critério de expiração por tempo (modelo velho demais)
        is_expired = False
        if cached and 'trained_at' in cached:
            age = time.time() - cached['trained_at']
            is_expired = age >= _MODEL_MAX_AGE_SECONDS

        # Critério de degradação de performance (CV MAE subiu demais)
        is_degraded = False
        if cached and cached.get('cv_mae') and n_samples > 50:
            # Calcula MAE rápido nas últimas amostras contra o modelo atual
            try:
                recent_n = min(20, n_samples)
                X_recent = X[-recent_n:]
                y_recent = y[-recent_n:]
                X_recent_s = cached['scaler'].transform(X_recent)
                preds_recent = cached['model'].predict(X_recent_s)
                recent_mae = float(np.mean(np.abs(y_recent - preds_recent)))
                is_degraded = recent_mae > cached['cv_mae'] * _MODEL_CV_MAE_DEGRADE_FACTOR
                if is_degraded:
                    log(f"[RETRAIN] {threshold_label}: MAE recente ({recent_mae:.2f}) > {_MODEL_CV_MAE_DEGRADE_FACTOR}x CV MAE treino ({cached['cv_mae']:.2f}). Forçando retreino.")
            except:
                pass  # Se falhar (ex: features mudaram), o critério n_features já cobre

        needs_retrain = (
            cached is None
            or abs(n_samples - cached['n_samples']) >= retrain_interval
            or cached_n_features != n_features
            or is_expired
            or is_degraded
        )

        if is_expired and cached:
            age_min = (time.time() - cached.get('trained_at', 0)) / 60
            log(f"[RETRAIN] {threshold_label}: Modelo expirado ({age_min:.0f} min). Forçando retreino.")

        if needs_retrain:
            scaler = StandardScaler()
            X_s = scaler.fit_transform(X)

            # Peso exponencial — amostras recentes valem mais
            sample_weights = np.array([0.995 ** (n_samples - 1 - i) for i in range(n_samples)])

            base_models = [
                ('ridge', Ridge(alpha=1.0)),
                ('rf', RandomForestRegressor(
                    n_estimators=80, max_depth=6, min_samples_leaf=3, random_state=42
                )),
                ('gb', GradientBoostingRegressor(
                    n_estimators=80, max_depth=4, learning_rate=0.05, random_state=42
                ))
            ]
            model = StackingRegressor(
                estimators=base_models, final_estimator=Ridge(alpha=0.5), cv=3
            )

            # Cross-validate para medir confiança real
            cv_mae = None
            if n_samples > 50:
                tscv = TimeSeriesSplit(n_splits=3)
                scores = []
                for train_idx, val_idx in tscv.split(X):
                    model_temp = StackingRegressor(
                        estimators=base_models, final_estimator=Ridge(alpha=0.5), cv=3
                    )
                    model_temp.fit(X_s[train_idx], y[train_idx],
                                   sample_weight=sample_weights[train_idx])
                    pred_val = model_temp.predict(X_s[val_idx])
                    scores.append(mean_absolute_error(y[val_idx], pred_val))
                cv_mae = np.mean(scores)
                log(f"CV MAE for {threshold_label}: {cv_mae:.2f}")

            model.fit(X_s, y, sample_weight=sample_weights)

            # Salvar no cache em memória
            _model_cache[cache_key] = {
                'model': model,
                'scaler': scaler,
                'n_samples': n_samples,
                'n_features': n_features,
                'cv_mae': cv_mae,
                'trained_at': time.time()
            }

            # Persistir modelo em disco para sobreviver a reinícios
            try:
                persist_path = os.path.join(_MODEL_PERSIST_DIR, f"{_safe_filename(cache_key)}.pkl")
                joblib.dump(_model_cache[cache_key], persist_path)
            except Exception as e:
                log(f"[WARN] Falha ao persistir modelo {cache_key}: {e}")

            log(f"Modelo [{threshold_label}] treinado com {n_samples} amostras ({n_features} features, intervalo={retrain_interval}).")
        else:
            model = cached['model']
            scaler = cached['scaler']

        # ====== Previsão do FUTURO ======
        future_window = data_series.iloc[-lag:]
        feats = list(future_window.values)
        feats.append(future_window.mean())
        feats.append(future_window.std() if len(future_window) > 1 else 0)
        feats.append(future_window.iloc[-1] / (future_window.mean() + 1e-6))
        feats.append(future_window.min())
        feats.append(future_window.max())
        feats.append(future_window.max() - future_window.min())

        # Features cíclicas para o instante da previsão (agora)
        now = datetime.now()
        hour = now.hour + now.minute / 60.0
        feats.append(np.sin(2 * np.pi * hour / 24))
        feats.append(np.cos(2 * np.pi * hour / 24))
        dow = now.weekday()
        feats.append(np.sin(2 * np.pi * dow / 7))
        feats.append(np.cos(2 * np.pi * dow / 7))

        future_x = np.array(feats).reshape(1, -1)
        pred = model.predict(scaler.transform(future_x))[0]

        mean_val = data_series.mean()

        # Clamp: limita a previsão ao range razoável do histórico
        # Evita extrapolações absurdas (ex: prever 4007x quando o P95 real é 30x)
        p95 = float(np.percentile(data_series, 95))
        upper_bound = max(p95 * 2.0, mean_val * 3.0)
        pred = float(np.clip(pred, 1.0, upper_bound))

        return pred, mean_val

    except Exception as e:
        log(f"[WARN] predict_optimized({threshold_label}) falhou: {e}")
        mean_val = float(data_series.mean())
        return mean_val, mean_val


def _load_cached_models():
    """Carrega modelos persistidos em disco ao iniciar o serviço."""
    global _model_cache
    if not os.path.exists(_MODEL_PERSIST_DIR):
        return
    for fname in os.listdir(_MODEL_PERSIST_DIR):
        if fname.endswith('.pkl'):
            try:
                # Reverte sanitizacao do nome do arquivo para a cache_key original
                key = fname.replace('.pkl', '').replace('gt', '>').replace('lt', '<')
                loaded = joblib.load(os.path.join(_MODEL_PERSIST_DIR, fname))
                # Descarta modelos antigos que não possuem n_features (incompatíveis)
                if 'n_features' not in loaded:
                    log(f"[WARN] Modelo [{key}] descartado (formato antigo sem n_features).")
                    os.remove(os.path.join(_MODEL_PERSIST_DIR, fname))
                    continue
                # Descarta modelos expirados por tempo (salvos há mais de _MODEL_MAX_AGE_SECONDS)
                if 'trained_at' in loaded:
                    age = time.time() - loaded['trained_at']
                    if age >= _MODEL_MAX_AGE_SECONDS:
                        log(f"[WARN] Modelo [{key}] descartado (expirado: {age/60:.0f} min).")
                        os.remove(os.path.join(_MODEL_PERSIST_DIR, fname))
                        continue
                else:
                    # Modelo sem trained_at = formato antigo, descarta
                    log(f"[WARN] Modelo [{key}] descartado (sem timestamp de treino).")
                    os.remove(os.path.join(_MODEL_PERSIST_DIR, fname))
                    continue
                _model_cache[key] = loaded
                age_min = (time.time() - loaded['trained_at']) / 60
                log(f"Modelo [{key}] carregado do disco ({loaded['n_samples']} amostras, {loaded['n_features']} features, idade={age_min:.0f} min).")
            except Exception as e:
                log(f"[WARN] Falha ao carregar modelo {fname}: {e}")

# ---------------------------------------------------------------------------
# Análise de Dados e Dashboard
# ---------------------------------------------------------------------------
latest_analysis = {}

def analyze_spikes(df_full, threshold, label):
    # ML RE-TRAIN LIMIT: Usa todo o log para exibir pro DB, 
    # mas APENAS as últimas 1750 rodadas para treinamento do ML e cálculo de Gaps 
    # para evitar obsolescência precoce (A roleta muda de padrão sazonalmente a cada dia/duas semanas).
    df = df_full.tail(1750).copy()

    spikes = df[df["value"] > threshold].copy()
    if len(spikes) < 3: return

    # Para não contaminar o ML com Gaps irreais (ex: quando o bot fica desligado por horas),
    # agrupamos as rodadas em "sessões" e só calculamos a diferença de tempo entre picos da MESMA sessão.
    # Qualquer rodada da roleta com diferença > 15 minutos (900s) pra anterior indica que a captação esteve off.
    df_temp = df.copy()
    df_temp["session"] = (df_temp["timestamp"].diff().dt.total_seconds() > 900).cumsum()
    
    # Atualiza spikes com a sessão atribuída a cada rodada
    spikes["session"] = df_temp.loc[spikes.index, "session"]
    
    # Agora o diff() só é calculado entre picos seguidos que ocorreram na mesma tacada de captação do robô
    spikes["gap_seconds"] = spikes.groupby("session")["timestamp"].diff().dt.total_seconds()
    gaps = spikes["gap_seconds"].dropna()

    # Gaps Medidos em Quantidade de Rodadas (Distância entre ocorrências)
    df_temp["round_idx"] = np.arange(len(df_temp))
    spikes["round_idx"] = df_temp.loc[spikes.index, "round_idx"]
    spikes["gap_rounds"] = spikes.groupby("session")["round_idx"].diff()
    gaps_rounds = spikes["gap_rounds"].dropna()
    mean_gap_rounds = gaps_rounds.mean() if len(gaps_rounds) > 0 else 0

    # Detecção de Regime (Cérebro do Sistema - Com Meta-Análise)
    detector = RegimeDetector()
    regime_name, confidence, regime_macro, conf_macro = detector.get_state(df)

    # Timestamps correspondentes aos gaps (para features cíclicas)
    spike_ts_for_gaps = spikes.loc[gaps.index, "timestamp"].reset_index(drop=True)
    spike_ts_for_rounds = spikes.loc[gaps_rounds.index, "timestamp"].reset_index(drop=True)

    # Predição ML Temporal
    pred_gap_ml, mean_gap = predict_optimized(
        gaps.reset_index(drop=True), label + "_tempo", spike_ts_for_gaps
    )

    # Predição ML Rodadas Extras
    pred_gap_rounds_ml, _ = predict_optimized(
        gaps_rounds.reset_index(drop=True), label + "_rounds", spike_ts_for_rounds
    )

    # Correlação: O ML (Inteligência) coincide com a Estatística Média?
    diff_temo = abs(pred_gap_ml - mean_gap) / (mean_gap + 1e-5)
    is_correlated = diff_temo <= 0.35 # Tolerância de 35% de diferença para validar Alarme

    # Utiliza o algoritmo do ML 100% puro sem interferência de médias estatísticas (Hibridização removida)
    pred_gap = pred_gap_ml
    pred_gap_rounds = pred_gap_rounds_ml

    # Predição ML Valor Extra (Estratégia similar de ML para saídas prováveis em pico)
    spike_values = spikes["value"]
    pred_value_ml, mean_val_stat = predict_optimized(
        spike_values.reset_index(drop=True), label + "_valor",
        spikes["timestamp"].reset_index(drop=True)
    )
    # Clamp final de segurança: valor previsto nunca ultrapassa o maior spike já registrado
    max_spike_real = float(spike_values.max())
    pred_value = min(pred_value_ml, max_spike_real)

    last_spike = spikes["timestamp"].iloc[-1]
    predicted_next = last_spike + timedelta(seconds=pred_gap)

    # Margem da janela: ±25% do gap previsto, com piso mínimo de 60 segundos
    # Evita janelas absurdamente estreitas quando o pred_gap é muito pequeno
    margin = max(pred_gap * 0.25, 60.0)
    early = predicted_next - timedelta(seconds=margin)
    late = predicted_next + timedelta(seconds=margin)

    key = f'spikes_{int(threshold)}'

    # Injeção dos dados globais
    if len(df_full) > 0:
        latest_analysis['now'] = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        latest_analysis['ultimo'] = f"{df_full['timestamp'].iloc[-1].strftime('%d/%m/%Y %H:%M:%S')} - {df_full['value'].iloc[-1]:.2f}x"
        latest_analysis['total_registros'] = len(df_full)
        latest_analysis['periodo'] = f"{df_full['timestamp'].iloc[0].strftime('%d/%m/%Y %H:%M:%S')} -> {df_full['timestamp'].iloc[-1].strftime('%d/%m/%Y %H:%M:%S')}"

        # Mantém o cálculo original para as contagens
        last_100_df = df_full.tail(100)
        latest_analysis['counts_100'] = {
            'c2':  len(last_100_df[last_100_df['value'] >= 2]),
            'c5':  len(last_100_df[last_100_df['value'] >= 5]),
            'c10': len(last_100_df[last_100_df['value'] >= 10]),
            'c50': len(last_100_df[last_100_df['value'] >= 50])
        }

        # Aumenta o buffer de histórico para a função 'carregar mais'
        df_chart = df_full.tail(1000).copy()
        df_chart["rolling_mean"]  = df_chart["value"].rolling(WINDOW_SIZE).mean()
        df_chart["rolling_slope"] = df_chart["value"].rolling(WINDOW_SIZE).apply(
            lambda x: np.polyfit(range(len(x)), x, 1)[0] if len(x) == WINDOW_SIZE else np.nan,
            raw=True
        )
        df_chart["rolling_curv"] = df_chart["value"].rolling(WINDOW_SIZE).apply(
            lambda x: np.polyfit(range(len(x)), x, 2)[0] if len(x) == WINDOW_SIZE else np.nan,
            raw=True
        )

        # Previsão feita na rodada atual para a PRÓXIMA rodada
        df_chart["pred_next"] = df_chart["rolling_mean"] + df_chart["rolling_slope"] + 0.5 * df_chart["rolling_curv"]

        # A previsão da rodada ATUAL é a "pred_next" da rodada ANTERIOR (shift 1)
        df_chart["saida_provavel"] = df_chart["pred_next"].shift(1)

        last_100_formatted = []
        for _, r in df_chart.iterrows():
            val = r['value']
            color = '#6c757d'
            if val >= 50: color = '#007bff'
            elif val >= 10: color = '#e83e8c'
            elif val >= 5: color = '#28a745'
            elif val >= 2: color = '#6f42c1'
            last_100_formatted.append({
                'value': val, 
                'time': r['timestamp'].strftime('%H:%M:%S'), 
                'color': color,
                'rolling_mean': float(r['rolling_mean']) if not pd.isna(r['rolling_mean']) else None,
                'projection': float(r['saida_provavel']) if not pd.isna(r['saida_provavel']) else None
            })
        latest_analysis['raw_history'] = last_100_formatted
        latest_analysis['last_100'] = last_100_formatted[-100:]

    old_history = latest_analysis.get(key, {}).get('history', [])

    # Load persistence if empty memory
    hist_file = os.path.join(BASE_DIR, "ml_history.json")
    if not old_history and os.path.exists(hist_file):
        try:
            with open(hist_file, "r", encoding="utf-8") as f:
                old_history = json.load(f).get(key, [])
        except: pass

    last_spike_iso = last_spike.strftime('%Y-%m-%d %H:%M:%S')
    last_spike_str = last_spike.strftime('%H:%M:%S')

    # Store the prediction in history, unique per last_spike (deduplicação por timestamp completo)
    if not any(h.get('spike_ts', h.get('spike_time')) == last_spike_iso for h in old_history):
        old_history.insert(0, {
            'prev_time': datetime.now().strftime('%H:%M:%S'),
            'spike_time': last_spike_str,
            'spike_ts': last_spike_iso,
            'next': predicted_next.strftime('%H:%M:%S'),
            'next_ts': predicted_next.strftime('%Y-%m-%d %H:%M:%S'),
            'window': f"{early.strftime('%H:%M:%S')} -> {late.strftime('%H:%M:%S')}",
            'window_start_ts': early.strftime('%Y-%m-%d %H:%M:%S'),
            'window_end_ts': late.strftime('%Y-%m-%d %H:%M:%S'),
            'value': pred_value,
            'predicted_gap': pred_gap
        })
        old_history = old_history[:25] # Keep last 25 predictions
        # Save persistence
        try:
            saved_data = {}
            if os.path.exists(hist_file):
                with open(hist_file, "r", encoding="utf-8") as f:
                    saved_data = json.load(f)
            saved_data[key] = old_history
            with open(hist_file, "w", encoding="utf-8") as f:
                json.dump(saved_data, f)
        except: pass

    # ============================================================
    # Métrica de Assertividade Dinâmica (com timestamps completos)
    # ============================================================
    hits = 0
    evaluated = 0
    for i in range(1, len(old_history)):
        try:
            # A previsão [i] dizia: "o PRÓXIMO spike cairá na janela X"
            # O spike que realmente veio depois é registrado em [i-1]
            pred_entry = old_history[i]
            real_entry = old_history[i-1]

            # Usa timestamps completos (ISO) quando disponíveis, senão fallback HH:MM:SS
            if 'spike_ts' in real_entry and 'window_start_ts' in pred_entry:
                rs_t = datetime.strptime(real_entry['spike_ts'], '%Y-%m-%d %H:%M:%S')
                s_t = datetime.strptime(pred_entry['window_start_ts'], '%Y-%m-%d %H:%M:%S')
                e_t = datetime.strptime(pred_entry['window_end_ts'], '%Y-%m-%d %H:%M:%S')
            else:
                # Fallback legado (entradas antigas sem _ts)
                real_spike_str = real_entry.get('spike_time', '')
                start_str, end_str = pred_entry['window'].split(' -> ')
                rs_t = datetime.strptime(real_spike_str, "%H:%M:%S")
                s_t = datetime.strptime(start_str, "%H:%M:%S")
                e_t = datetime.strptime(end_str, "%H:%M:%S")
                if e_t < s_t:
                    e_t += timedelta(days=1)
                    if rs_t < s_t and rs_t.hour < 12: rs_t += timedelta(days=1)

            if s_t <= rs_t <= e_t:
                hits += 1
            evaluated += 1
        except: pass

    accuracy_perc = f"{(hits / evaluated * 100):.0f}%" if evaluated > 0 else "N/A"

    # Adicionado: Alerta sonoro para mudança na janela de >50x
    new_window_str = f"{early.strftime('%H:%M:%S')} -> {late.strftime('%H:%M:%S')}"
    old_window_str = latest_analysis.get(key, {}).get('window')
    if threshold == 50.0 and old_window_str and new_window_str != old_window_str:
        log("!!! Janela de >50x ATUALIZADA. Emitindo alerta sonoro. !!!")
        winsound.Beep(800, 250) # Frequência, Duração em ms
        time.sleep(0.1)
        winsound.Beep(800, 250)

    latest_analysis[key] = {
        'total': len(spikes),
        'mean_gap': mean_gap / 60,
        'mean_gap_rounds': mean_gap_rounds,
        'predicted_gap': pred_gap / 60,
        'predicted_gap_rounds': pred_gap_rounds,
        'predicted_value': pred_value,
        'regime': regime_name,
        'confidence': f"{confidence*100:.0f}%",
        'regime_macro': regime_macro,
        'conf_macro': f"{conf_macro*100:.0f}%",
        'correlated': is_correlated,
        'accuracy': accuracy_perc, # Porcentual novo
        'next': predicted_next.strftime('%H:%M:%S'),
        'window': f"{early.strftime('%H:%M:%S')} -> {late.strftime('%H:%M:%S')}",
        'current_oc': len(df_full) - 1 - df_full[df_full["value"] > threshold].index[-1],
        'history': old_history
    }

    log(f"Análise de {key} concluída e atualizada no dashboard!")

    save_prediction(threshold, predicted_next, early, late)

def analyze_trends(df_full):
    """Analisa tendencias usando rolling window com ajuste polinomial de grau 2."""
    df = df_full.tail(1750).copy()
    if len(df) < WINDOW_SIZE:
        return

    df["rolling_mean"] = df["value"].rolling(WINDOW_SIZE).mean()

    # Slope linear (grau 1) — mantido para exibição
    df["rolling_slope"] = df["value"].rolling(WINDOW_SIZE).apply(
        lambda x: np.polyfit(range(len(x)), x, 1)[0] if len(x) == WINDOW_SIZE else np.nan,
        raw=True
    )

    # Curvatura (grau 2) — melhora a projeção capturando aceleração
    df["rolling_curv"] = df["value"].rolling(WINDOW_SIZE).apply(
        lambda x: np.polyfit(range(len(x)), x, 2)[0] if len(x) == WINDOW_SIZE else np.nan,
        raw=True
    )

    df["projection"] = df["rolling_mean"] + df["rolling_slope"]

    if not df["rolling_slope"].isna().all():
        last_mean  = df["rolling_mean"].iloc[-1]
        last_slope = df["rolling_slope"].iloc[-1]
        last_curv  = df["rolling_curv"].iloc[-1] if not df["rolling_curv"].isna().all() else 0.0

        projections = []
        for i in range(1, 5):
            # Projeção com componente quadrático (mais precisa que linear puro)
            pred = last_mean + i * last_slope + (i ** 2) * last_curv * 0.5
            projections.append(pred)

        # Atualiza dashboard 
        latest_analysis['trends'] = {
            'mean':  last_mean,
            'slope': last_slope,
            'projections': []
        }

        for p in projections:
            color = '#6c757d'
            if p >= 50: color = '#007bff'
            elif p >= 10: color = '#e83e8c'
            elif p >= 5: color = '#28a745'
            elif p >= 2: color = '#6f42c1';

            latest_analysis['trends']['projections'].append({
                'value': p, 
                'color': color,
                'alert_5': p > THRESHOLD_5,
                'alert_10': p > THRESHOLD_10, 
                'alert_50': p > THRESHOLD_50
            })

def save_prediction(thresh, nxt, erl, lte):
    with open(PREDICTIONS_FILE, "a", encoding="utf-8") as f:
        f.write(f"{datetime.now()};{thresh};{nxt};{erl};{lte};pendente\n")

def load_data_for_analysis():
    if not os.path.exists(OUTPUT_FILE): return pd.DataFrame()
    data = []
    
    # Lendo o arquivo do mais novo pro mais antigo
    with open(OUTPUT_FILE, "r", encoding="utf-8") as f:
        linhas = [line.strip() for line in f if line.strip()]
        
    now = datetime.now();
    
    new_lines = []
    for line in linhas:
        p = line.split(";")
        if len(p) >= 2:
            try:
                val = float(p[0].replace(",", "."))
                if len(p) == 2:
                    # New format: value;timestamp
                    ts = datetime.fromtimestamp(float(p[1]))
                    new_lines.append(line)  # already new
                elif len(p) == 3:
                    # Old format: value;hora;data
                    ts = datetime.strptime(f"{p[2]} {p[1]}", "%d/%m/%Y %H:%M:%S")
                    # Correção Dinâmica de Timestamp Retroativo
                    if ts > now + timedelta(minutes=5):
                        ts -= timedelta(days=1)
                    new_lines.append(f"{p[0]};{ts.timestamp()}")
                else:
                    continue
                data.append({"value": val, "timestamp": ts})
            except: continue
    
    # Convert the file if any old format
    if new_lines and new_lines != linhas:
        with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
            for nl in new_lines:
                f.write(nl + "\n")
    
    if not data: return pd.DataFrame()

    # data está com os mais novos no topo
    df = pd.DataFrame(data)

    # Ordena perfeitamente pela Data e Hora consertada do mais antigo (esquerda) pro mais presente (direita)
    df = df.sort_values(by="timestamp", ascending=True).reset_index(drop=True)

    # Deduplicação: remove linhas com mesmo valor e timestamp (tolerância de 1s)
    df["_ts_round"] = df["timestamp"].dt.round("1s")
    df = df.drop_duplicates(subset=["value", "_ts_round"], keep="first").drop(columns=["_ts_round"]).reset_index(drop=True)

    return df

# ---------------------------------------------------------------------------
# Flask Dashboard (Modernizado e Unificado com o Original)
# ---------------------------------------------------------------------------
app = Flask(__name__)

@app.route('/')
def dashboard():
    html = """
    <!DOCTYPE html>
    <html lang="pt-br">
    <head>
        <meta charset="UTF-8"><title>Aviator ML Intelligence</title>
        <meta http-equiv="refresh" content="10">
        <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
        <style>
            body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background-color: #f4f7f6; color: #333; margin: 0; }
            .container { display: flex; flex-wrap: wrap; gap: 20px; padding: 20px 40px 40px 40px; }
            .sidebar { flex: 1; min-width: 250px; display: flex; flex-direction: column; gap: 20px; }
            .main-content { flex: 3; min-width: 600px; display: flex; flex-direction: column; gap: 20px; }
            .card { background: #fff; border-radius: 8px; box-shadow: 0 2px 10px rgba(0,0,0,0.05); padding: 20px; }
            .kpi { display: flex; flex-direction: column; align-items: center; justify-content: center; text-align: center; border: 1px solid #eee; border-radius: 8px; padding: 15px; }
            .kpi h4 { margin: 0 0 10px 0; color: #888; font-size: 14px; text-transform: uppercase; }
            .kpi-value { font-size: 24px; font-weight: bold; color: #e83e8c; margin: 0; }
            .grid-3 { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 20px; }
            .history-list { display: flex; flex-wrap: wrap; gap: 5px; margin-top: 15px; }
            .history-item { padding: 4px 8px; border-radius: 4px; color: #fff; font-size: 12px; font-weight: bold; }

            .regime { display: inline-block; padding: 4px 10px; border-radius: 6px; font-weight: bold; background: #e9ecef; margin-bottom: 10px; color: #333; font-size:12px; }
            .conf-high { color: #28a745; font-weight:bold; } .conf-low { color: #dc3545; font-weight:bold; }
            h2, h3 { color: #444; margin-top: 0; }
            p { margin: 8px 0; font-size: 14px; }
            .alert { background-color: #ffeeba; color: #856404; padding: 10px; border-radius: 5px; font-weight: bold; margin-bottom: 15px; }
        </style>
    </head>
    <body>
        <button id="btn-sound" style="position:fixed; top:10px; right:10px; z-index:9999; padding:8px 12px; background:#28a745; color:#fff; border:none; border-radius:5px; cursor:pointer; font-weight:bold;"></button>

        <div class="container">
            <div class="sidebar">
                <div class="card" style="text-align: center; font-size: 14px; color: #666;">
                    <p><strong>Atual:</strong> {{ data.now }}</p>
                    <p><strong>Última:</strong> {{ data.ultimo.split(' - ')[0] if data.ultimo else 'N/A' }}</p>
                </div>

                <div class="card">
                    <h3>Geral</h3>
                    <div style="display:flex; gap:10px;">
                        <div class="kpi" style="flex:1; margin-bottom:10px; padding: 10px;">
                            <h4>Total Registros</h4>
                            <p class="kpi-value" style="font-size: 20px;">{{ data.total_registros }}</p>
                        </div>
                        <div class="kpi" style="flex:1; margin-bottom:10px; padding: 10px;">
                            <h4>Último Valor</h4>
                            <p class="kpi-value" style="color:#333; font-size: 20px;">{{ data.ultimo.split(' - ')[1] if data.ultimo else 'N/A' }}</p>
                        </div>
                    </div>
                    <div style="font-size:13px; margin-top:5px; border-top:1px solid #eee; padding-top:10px; text-align: center;">
                        <strong>Nas últimas 100 rodadas:</strong><br>
                        <span style="color:#6f42c1;font-weight:bold;">>2:</span> {{ data.counts_100.c2 if data.counts_100 else 0 }} | 
                        <span style="color:#28a745;font-weight:bold;">>5:</span> {{ data.counts_100.c5 if data.counts_100 else 0 }} | 
                        <span style="color:#e83e8c;font-weight:bold;">>10:</span> {{ data.counts_100.c10 if data.counts_100 else 0 }} | 
                        <span style="color:#007bff;font-weight:bold;">>50:</span> {{ data.counts_100.c50 if data.counts_100 else 0 }}
                    </div>
                    <p style="font-size:12px;text-align:center;color:#666;margin-top:10px;">Período: {{ data.periodo }}</p>
                </div>

                <div class="card">
                    <h3>Alertas & Tendências</h3>
                    {% if data.trends and data.trends.projections %}
                        {% for proj in data.trends.projections %}
                            {% if proj.alert_50 %}
                                <div class="alert" data-level="50" style="background-color: #f8d7da; color: #721c24;">ALERTA! Previsão {{ loop.index }} aponta p/ >50</div>
                            {% elif proj.alert_10 %}
                                <div class="alert" data-level="10" style="background-color: #cce5ff; color: #004085;">ALERTA! Previsão {{ loop.index }} aponta p/ >10</div>
                            {% elif proj.alert_5 %}
                                <div class="alert" data-level="5">ALERTA! Previsão {{ loop.index }} aponta p/ >5</div>
                            {% endif %}
                        {% endfor %}
                        <p><strong>Média Movel:</strong> {{ "%.2f"|format(data.trends.mean) }}</p>
                        <p><strong>Inclinação:</strong> {{ "%.4f"|format(data.trends.slope) }}</p>
                        <p><strong>Saída Provável (Próximo):</strong> <span class="history-item" style="font-size: 14px; background-color:{{ data.trends.projections[0].color }};">{{ "%.2f"|format(data.trends.projections[0].value) }}x</span></p>
                        <p><strong>Próximas 4 Projeções:</strong><br> 
                        {% for proj in data.trends.projections %}
                            <span class="history-item" style="background-color:{{ proj.color }};">{{ "%.2f"|format(proj.value) }}x</span>
                        {% endfor %}
                        </p>
                    {% else %}
                        <p>Análise em andamento...</p>
                    {% endif %}
                </div>
            </div>

            <div class="main-content">
                <div class="card">
                    <h3>Últimas 100 Ocorrências</h3>
                    <canvas id="historyChart" width="400" height="80"></canvas>
                    <div class="history-list">
                        {% if data.raw_history %}
                            {% for item in data.raw_history|reverse %}
                                <div class="history-item-div" style="display:inline-flex; flex-direction:column; align-items:center; min-width:40px; {% if loop.index > 100 %}display: none;{% endif %}">
                                    <span style="font-size:10px; color:#888; line-height:1;" title="Saída Provável Calculada (Projeção Polinomial)">
                                        {% if item.projection %}{{ "%.2f"|format(item.projection) }}x{% else %}--{% endif %}
                                    </span>
                                    <span class="history-item" style="background-color: {{ item.color }}; margin-top:2px;" title="Real: {{ item.time }}">{{ "%.2f"|format(item.value) }}x</span>
                                </div>
                            {% endfor %}
                        {% endif %}
                    </div>
                    <button id="load-more" style="margin-top:10px; padding:8px 12px; background:#007bff; color:#fff; border:none; border-radius:5px; cursor:pointer;">Carregar Mais Histórico</button>
                </div>

                <div class="grid-3">
                    {% for k in ['spikes_5', 'spikes_10', 'spikes_50'] %}
                    <div class="card">
                        <h3>Spikes {{ k.replace('spikes_', '> ') }}</h3>
                        {% if k in data and data[k] %}
                            <div style="display: flex; gap: 15px; margin-bottom: 15px; justify-content: center;">
                                <div style="flex:1; padding:10px; border:1px solid #eee; border-radius:8px; text-align:center;">
                                    <div class="regime">Local (Micro): {{ data[k].regime }}</div>
                                    <p style="margin:5px 0;"><strong>Confiança:</strong> <br><span style="font-size:20px;" class="{{ 'conf-high' if '8' in data[k].confidence or '9' in data[k].confidence or '10' in data[k].confidence else 'conf-low' }}">{{ data[k].confidence }}</span></p>
                                </div>
                                <div style="flex:1; padding:10px; border:1px solid #eee; border-radius:8px; text-align:center;">
                                    <div class="regime">Tendência (Macro): {{ data[k].regime_macro }}</div>
                                    <p style="margin:5px 0;"><strong>Confiança:</strong> <br><span style="font-size:20px;" class="{{ 'conf-high' if '8' in data[k].conf_macro or '9' in data[k].conf_macro or '7' in data[k].conf_macro or '10' in data[k].conf_macro else 'conf-low' }}">{{ data[k].conf_macro }}</span></p>
                                </div>
                            </div>
                            <p><strong>Assertividade ML:</strong> <span style="font-weight:bold; color:#0056b3;">{{ data[k].accuracy }}</span></p>
                            <p><strong>Gap Médio:</strong> {{ "%.2f"|format(data[k].mean_gap) }} min / {{ "%.0f"|format(data[k].mean_gap_rounds) }} rodadas</p>
                            <p><strong>Previsão ML (Tempo):</strong> {{ "%.2f"|format(data[k].predicted_gap) }} min / {{ "%.0f"|format(data[k].predicted_gap_rounds) }} rodadas</p>
                            <p><strong>Previsão ML (Valor):</strong> <span style="color:#28a745;font-weight:bold;">{{ "%.2f"|format(data[k].predicted_value) }}x</span></p>
                            <p><strong>Desde Último Pico:</strong> {{ data[k].current_oc }} rodadas</p>
                            <hr style="border:0.5px solid #eee; margin:10px 0;">
                            <p><strong>Próximo Pico:</strong> <span class="next-spike" data-corr="{{ '1' if data[k].correlated else '0' }}" data-level="{{ k.split('_')[1] }}" data-early="{{ data[k].window.split(' -> ')[0] }}" id="next-spike-{{ k.split('_')[1] }}" style="color:#007bff;font-weight:bold;">{{ data[k].next }}</span>
                            <span style="font-size:10px; margin-left:5px; padding:2px 4px; border-radius:3px; font-weight:bold; color:#fff; background-color: {{ '#28a745' if data[k].correlated else '#dc3545' }}">{{ '✓ ML ALINHADO' if data[k].correlated else '⚠ ML DIVERGENTE' }}</span></p>
                            <p><strong>Janela:</strong> {{ data[k].window }}</p>

                            <details open>
                                <summary style="font-size:12px; cursor:pointer; color:#0056b3; margin-top:10px; outline:none; font-weight:bold;">Histórico (Últimas 25)</summary>
                                <div style="font-size:11px; margin-top:5px; max-height:180px; overflow-y:auto; border:1px solid #eee; padding:5px; background:#fdfdfd;">
                                    <table style="width:100%; border-collapse: collapse; text-align:left;">
                                        <thead>
                                            <tr style="border-bottom:1px solid #ccc; color:#555;">
                                                <th style="padding:2px;">Reg. Previsão</th>
                                                <th style="padding:2px;">Alvo (Valor)</th>
                                                <th style="padding:2px;">Alvo (Hora)</th>
                                                <th style="padding:2px;">Janela</th>
                                            </tr>
                                        </thead>
                                        <tbody>
                                            {% for hist in data[k].history %}
                                            <tr style="border-bottom:1px solid #eee;">
                                                <td style="padding:2px; color:#888;">{{ hist.prev_time if hist.prev_time else hist.spike_time }}</td>
                                                <td style="padding:2px; font-weight:bold; color:#28a745;">{{ "%.2f"|format(hist.value) }}x</td>
                                                <td style="padding:2px; font-weight:bold; color:#007bff;">{{ hist.next }}</td>
                                                <td style="padding:2px; font-size:10px; color:#666;">{{ hist.window.split(' -> ')[0][:5] }} às {{ hist.window.split(' -> ')[1][:5] }}</td>
                                            </tr>
                                            {% endfor %}
                                        </tbody>
                                    </table>
                                </div>
                            </details>
                        {% else %}
                            <p>Aguardando...</p>
                        {% endif %}
                    </div>
                    {% endfor %}
                </div>
            </div>
        </div>

        <script>
            const canvas = document.getElementById('historyChart');
            if(canvas) {
                const ctx = canvas.getContext('2d');
                const lastData = {{ data.raw_history|tojson if data.raw_history else '[]' }};
                const chartData = lastData.slice(-50); 
                const labels = chartData.map(d => d.time);
                const values = chartData.map(d => d.value);
                const colors = chartData.map(d => d.color);
                const rollingMeans = chartData.map(d => d.rolling_mean);
                const projections = chartData.map(d => d.projection);

                new Chart(ctx, {
                    type: 'line',
                    data: {
                        labels: labels,
                        datasets: [{
                            label: 'Multiplicador',
                            data: values,
                            borderColor: '#0056b3',
                            borderWidth: 2,
                            pointBackgroundColor: colors,
                            pointBorderColor: '#fff',
                            pointRadius: 4,
                            fill: false,
                            tension: 0.1
                        },
                        {
                            label: 'Média Móvel (5)',
                            data: rollingMeans,
                            borderColor: '#ffc107',
                            borderWidth: 1,
                            borderDash: [5, 5],
                            pointRadius: 0,
                            fill: false,
                            tension: 0.2
                        },
                        {
                            label: 'Projeção de Tendência',
                            data: projections,
                            borderColor: '#dc3545',
                            borderWidth: 1,
                            borderDash: [2, 2],
                            pointRadius: 0,
                            fill: false,
                            tension: 0.2
                        }]
                    },
                    options: { responsive: true, scales: { y: { beginAtZero: true, suggestedMax: 10 }, x: { display: false } }, plugins: { legend: { display: false } } }
                });
            }

            // Audio Alert
            const btnSound = document.getElementById('btn-sound');
            let soundEnabled = localStorage.getItem('sound_enabled') === 'true';

            function updateBtn() {
                if(!btnSound) return;
                btnSound.innerText = soundEnabled ? "🔊 Som Ativado" : "🔇 Ativar Som";
                btnSound.style.backgroundColor = soundEnabled ? "#28a745" : "#6c757d";
            }

            if(btnSound) {
                updateBtn();
                btnSound.addEventListener('click', () => {
                    soundEnabled = !soundEnabled;
                    localStorage.setItem('sound_enabled', soundEnabled);
                    updateBtn();
                    if(soundEnabled) playChangeSound();
                });
            }

            function playAlertSound(times) {
                if(!soundEnabled || times <= 0) return;
                try {
                    const ctx = new (window.AudioContext || window.webkit.AudioContext)();
                    const now = ctx.currentTime;
                    for (let i = 0; i < times; i++) {
                        const startTime = now + (i * 0.6); // 0.6s de intervalo entre cada loop
                        const osc = ctx.createOscillator();
                        osc.type = 'sawtooth';
                        osc.frequency.setValueAtTime(440, startTime);
                        osc.frequency.exponentialRampToValueAtTime(880, startTime + 0.2);

                        const gain = ctx.createGain();
                        gain.gain.setValueAtTime(0.1, startTime);
                        gain.gain.exponentialRampToValueAtTime(0.01, startTime + 0.4);

                        osc.connect(gain);
                        gain.connect(ctx.destination);
                        osc.start(startTime);
                        osc.stop(startTime + 0.4);
                    }
                } catch(e) { console.error('Erro de audio:', e); }
            }

            function playChangeSound() {
                if(!soundEnabled) return;
                try {
                    const ctx = new (window.AudioContext || window.webkit.AudioContext)();
                    const osc = ctx.createOscillator();
                    osc.type = 'sine';
                    osc.frequency.setValueAtTime(600, ctx.currentTime);
                    const gain = ctx.createGain();
                    gain.gain.setValueAtTime(0.1, ctx.currentTime);
                    gain.gain.exponentialRampToValueAtTime(0.01, ctx.currentTime + 0.5);
                    osc.connect(gain);
                    gain.connect(ctx.destination);
                    osc.start();
                    osc.stop(ctx.currentTime + 0.5);
                } catch(e) { console.error(e); }
            }

            window.addEventListener('DOMContentLoaded', () => {
                let maxLevel = 0;

                // Mapeia exclusivamente os alertas de Saída Provável (Tendência/Estatística não ML)
                let trendAlerts = document.querySelectorAll('.alert[data-level]');
                trendAlerts.forEach(alerta => {
                    let text = alerta.innerText || "";
                    // Dispara o alerta sonoro SOMENTE se a "Previsão 1" (Próximo) apontar para >5, >10 ou >50
                    if (text.includes("Previsão 1")) {
                        let l = parseInt(alerta.getAttribute('data-level')) || 0;
                        if (l > maxLevel) maxLevel = l;
                    }
                });

                let beepCount = 0;
                if (maxLevel === 50) beepCount = 20;
                else if (maxLevel === 10) beepCount = 10;
                else if (maxLevel === 5) beepCount = 5;

                // Toca os alertas sonoros baseados primariamente e exclusivamente na Saída Provável
                if (beepCount > 0) {
                    setTimeout(() => playAlertSound(beepCount), 500);
                } 
            });

            // Load More History
            let currentShown = parseInt(localStorage.getItem('historyShown')) || 100;
            const loadMoreBtn = document.getElementById('load-more');
            if(loadMoreBtn) {
                // Initially show up to currentShown
                const items = document.querySelectorAll('.history-item-div');
                for(let i = 0; i < Math.min(currentShown, items.length); i++) {
                    items[i].style.display = 'inline-flex';
                }
                if(currentShown >= items.length) {
                    loadMoreBtn.style.display = 'none';
                }

                loadMoreBtn.addEventListener('click', () => {
                    const items = document.querySelectorAll('.history-item-div');
                    for(let i = currentShown; i < currentShown + 100 && i < items.length; i++) {
                        items[i].style.display = 'inline-flex';
                    }
                    currentShown += 100;
                    localStorage.setItem('historyShown', currentShown);
                    if(currentShown >= items.length) {
                        loadMoreBtn.style.display = 'none';
                    }
                });
            }
        </script>
    </body>
    </html>
    """
    return render_template_string(html, data=latest_analysis)

# ---------------------------------------------------------------------------
# Loop Principal
# ---------------------------------------------------------------------------
def main_loop():
    log("Iniciando Serviço Principal...")
    _load_cached_models()
    driver = iniciar_driver()
    fazer_login(driver)
    
    try:
        while True:
            novos = capturar_ultimos(driver)
            if novos:
                # Lógica de persistência (mesclar e salvar)
                dirigentes = []
                if os.path.exists(OUTPUT_FILE):
                    with open(OUTPUT_FILE, "r", encoding="utf-8") as f:
                        dirigentes = [l.strip() for l in f if l.strip()]

                # Filtro anti-duplicação: checa TODAS as linhas existentes (não apenas as 100 primeiras)
                existing_fingerprints = set()
                for r in dirigentes:
                    parts = r.split(';')
                    if len(parts) >= 2:
                        existing_fingerprints.add(f"{parts[0]};{parts[1]}")

                adicionados = 0
                for n in reversed(novos):
                    fingerprint = f"{n[0]};{n[1]}"
                    if fingerprint not in existing_fingerprints:
                        line = f"{n[0]};{n[1]}"
                        dirigentes.insert(0, line)
                        existing_fingerprints.add(fingerprint)
                        adicionados += 1
                # Otimização severa de ML: Só roda cálculos onerosos e reconstrução de base
                # SE alguma informação inteiramente nova entrou no sistema!
                if adicionados > 0:
                    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
                        for item in dirigentes[:MAX_REGISTROS]:
                            f.write(item + "\n")

                    log(f"Adicionados: {adicionados}. Total: {len(dirigentes)}")

                    # Executar Análise
                    df = load_data_for_analysis()
                    if not df.empty:
                        analyze_spikes(df, THRESHOLD_5, ">5")
                        analyze_spikes(df, THRESHOLD_10, ">10")
                        analyze_spikes(df, THRESHOLD_50, ">50")
                        analyze_trends(df)

            time.sleep(INTERVALO_SEGUNDOS)
    except KeyboardInterrupt:
        log("Encerrado.")
    finally:
        driver.quit()

if __name__ == "__main__":
    # Dashboard em Thread separada
    threading.Thread(target=lambda: app.run(host='0.0.0.0', port=5000, debug=False, use_reloader=False), daemon=True).start()
    main_loop()