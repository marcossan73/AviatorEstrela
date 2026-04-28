# -*- coding: utf-8 -*-
# =============================================================================
#  AviatorService.py    verso aprimorada com ML adaptativo
#  Melhorias: feature engineering rica, validao temporal, limpeza de outliers,
#  seleo automtica de modelo por volume de dados, log de acurcia contnuo.
#  Dashboard e visualizaes INALTERADOS.
# =============================================================================

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from datetime import date, datetime, timedelta
import time
import os
import json
import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestRegressor, GradientBoostingRegressor
from sklearn.linear_model import Ridge
from sklearn.model_selection import TimeSeriesSplit, cross_val_score
from sklearn.metrics import mean_absolute_error, mean_squared_error
from sklearn.preprocessing import StandardScaler
import joblib
from flask import Flask, render_template_string
import threading
from webdriver_manager.chrome import ChromeDriverManager

# ---------------------------------------------------------------------------
# URLs e credenciais
# ---------------------------------------------------------------------------

LOGIN_URL = "https://www.tipminer.com/br/historico/estrelabet/aviator"
URL_50 = (
    "https://www.tipminer.com/br/historico/estrelabet/aviator"
    "?t=1775174557808&limit=50&subject=filter&isLoadMore=true"
)

EMAIL = "marcossa73.ms@gmail.com"
SENHA = "Mrcs3@46"

# ---------------------------------------------------------------------------
# Caminhos de arquivo
# ---------------------------------------------------------------------------

BASE_DIR         = os.path.dirname(os.path.abspath(__file__))
OUTPUT_FILE      = os.path.join(BASE_DIR, "resultados_aviator.txt")
LOG_FILE         = os.path.join(BASE_DIR, "log_execucao.txt")
PREDICTIONS_FILE = os.path.join(BASE_DIR, "predictions.txt")
ACCURACY_LOG     = os.path.join(BASE_DIR, "accuracy_log.json")

# Modelos de tempo (gap em segundos)
MODEL_FILE_5  = os.path.join(BASE_DIR, "gap_model_5.pkl")
MODEL_FILE_10 = os.path.join(BASE_DIR, "gap_model_10.pkl")
MODEL_FILE_50 = os.path.join(BASE_DIR, "gap_model_50.pkl")

# Modelos de ocorrncias (gap em rodadas)
MODEL_FILE_OC_5  = os.path.join(BASE_DIR, "gap_oc_model_5.pkl")
MODEL_FILE_OC_10 = os.path.join(BASE_DIR, "gap_oc_model_10.pkl")
MODEL_FILE_OC_50 = os.path.join(BASE_DIR, "gap_oc_model_50.pkl")

# Scalers para normalizao
SCALER_FILE_5    = os.path.join(BASE_DIR, "scaler_5.pkl")
SCALER_FILE_10   = os.path.join(BASE_DIR, "scaler_10.pkl")
SCALER_FILE_50   = os.path.join(BASE_DIR, "scaler_50.pkl")
SCALER_FILE_OC_5  = os.path.join(BASE_DIR, "scaler_oc_5.pkl")
SCALER_FILE_OC_10 = os.path.join(BASE_DIR, "scaler_oc_10.pkl")
SCALER_FILE_OC_50 = os.path.join(BASE_DIR, "scaler_oc_50.pkl")

# ---------------------------------------------------------------------------
# Constantes gerais
# ---------------------------------------------------------------------------

INTERVALO_SEGUNDOS = 30
MAX_REGISTROS      = 10000

THRESHOLD_5  = 5.0
THRESHOLD_10 = 10.0
THRESHOLD_50 = 50.0
WINDOW_SIZE  = 5
PRE_WINDOW   = 4

# ---------------------------------------------------------------------------
# Limiares adaptativos  o sistema escolhe o modelo conforme os dados crescem
# ---------------------------------------------------------------------------

MIN_GAPS_RIDGE        = 8    # regresso linear regularizada
MIN_GAPS_RF           = 20   # Random Forest
MIN_GAPS_GBM          = 50   # Gradient Boosting + CV temporal
MIN_GAPS_FEATURES_EXT = 15   # features de rolling stats


# ===========================================================================
# Log
# ===========================================================================

def log(msg):
    agora = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    linha = "[" + agora + "] " + msg
    print(linha)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(linha + "\n")


# ===========================================================================
# Driver
# ===========================================================================

def iniciar_driver():
    options = Options()
    options.add_argument("--headless")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--disable-extensions")
    options.add_argument("--disable-plugins")
    options.add_argument("--disable-images")
    options.add_argument("--no-first-run")
    options.add_argument("--remote-debugging-port=9222")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option('useAutomationExtension', False)
    options.add_argument(
        "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/134.0.0.0 Safari/537.36"
    )
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)
    driver.set_page_load_timeout(120)
    driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
    return driver


def clicar_js(driver, elemento):
    driver.execute_script("arguments[0].scrollIntoView({block:'center'});", elemento)
    time.sleep(0.5)
    driver.execute_script("arguments[0].click();", elemento)


# ===========================================================================
# Login
# ===========================================================================

def fazer_login(driver):
    log("Abrindo pagina de login...")
    driver.get(LOGIN_URL)
    time.sleep(3)

    btn_login = WebDriverWait(driver, 30).until(
        EC.presence_of_element_located((By.XPATH, "//button[contains(., 'Acesse sua conta')]"))
    )
    clicar_js(driver, btn_login)

    campo_email = WebDriverWait(driver, 20).until(
        EC.presence_of_element_located((By.CSS_SELECTOR, "input.action-email"))
    )
    driver.execute_script("arguments[0].value = '';", campo_email)
    campo_email.send_keys(EMAIL)

    campo_senha = WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.CSS_SELECTOR, "input.action-password"))
    )
    driver.execute_script("arguments[0].value = '';", campo_senha)
    campo_senha.send_keys(SENHA)

    btn_acessar = WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.XPATH, "//button[@type='submit' and contains(., 'Acessar')]"))
    )
    clicar_js(driver, btn_acessar)

    WebDriverWait(driver, 30).until(
        EC.invisibility_of_element_located((By.XPATH, "//button[contains(., 'Acesse sua conta')]"))
    )
    time.sleep(3)
    log("Login realizado com sucesso.")


# ===========================================================================
# Captura dos ltimos 50 resultados
# ===========================================================================

def capturar_ultimos(driver):
    current_t = str(int(time.time() * 1000))
    url_50 = (
        "https://www.tipminer.com/br/historico/estrelabet/aviator"
        f"?t={current_t}&limit=50&subject=filter&isLoadMore=true"
    )
    driver.get(url_50)
    time.sleep(3)

    tentativas = 3
    for tentativa in range(1, tentativas + 1):
        try:
            WebDriverWait(driver, 60).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, ".cell__result"))
            )
            time.sleep(3)
            break
        except Exception as e:
            if tentativa < tentativas:
                driver.refresh()
                time.sleep(5)
            else:
                log("ERRO ao carregar pagina: " + str(e))
                return []

    elementos_result = driver.find_elements(By.CSS_SELECTOR, ".cell__result")
    hoje = date.today().strftime("%d/%m/%Y")
    novos = []

    for el_result in elementos_result:
        try:
            valor_bruto = el_result.text.strip()

            btn = driver.execute_script("""
                var el = arguments[0];
                while (el && el.tagName !== 'BUTTON') {
                    el = el.parentElement;
                }
                return el;
            """, el_result)

            if not valor_bruto and btn:
                data_result = btn.get_attribute("data-result") or ""
                if data_result:
                    valor_bruto = data_result.replace("X", ",")

            if btn:
                try:
                    el_hora = btn.find_element(By.CSS_SELECTOR, ".cell__date")
                    hora = el_hora.text.strip()
                except Exception:
                    hora = ""
            else:
                hora = ""

            valor = valor_bruto.replace("x", "").replace("X", "").strip()

            if valor and hora:
                novos.append((valor, hora, hoje))
        except Exception:
            continue

    return novos


# ===========================================================================
# Leitura e escrita do arquivo
# ===========================================================================

def carregar_existentes():
    if not os.path.exists(OUTPUT_FILE):
        return []
    with open(OUTPUT_FILE, "r", encoding="utf-8") as f:
        linhas = [l.strip() for l in f if l.strip()]
    registros = []
    for linha in linhas:
        partes = linha.split(";")
        if len(partes) == 3:
            registros.append((partes[0], partes[1], partes[2]))
    return registros


def mesclar(existentes, novos):
    chaves = set((v, h) for v, h, d in existentes)
    adicionados = 0
    for registro in novos:
        chave = (registro[0], registro[1])
        if chave not in chaves:
            existentes.insert(0, registro)
            chaves.add(chave)
            adicionados += 1

    existentes.sort(key=lambda r: r[1], reverse=True)
    return existentes, adicionados


def salvar_arquivo(registros):
    registros = registros[:MAX_REGISTROS]
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        for valor, hora, data in registros:
            f.write(valor + ";" + hora + ";" + data + "\n")
    log(f"Arquivo salvo com {len(registros)} registros.")


# ===========================================================================
# Carga de dados para anlise
# ===========================================================================

def load_data_for_analysis():
    """Carrega dados do arquivo para analise"""
    if not os.path.exists(OUTPUT_FILE):
        return pd.DataFrame()

    rows = []
    with open(OUTPUT_FILE, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            partes = line.split(";")
            if len(partes) == 3:
                val_str, hora, data = partes
                try:
                    val = float(val_str.replace(",", "."))
                    dt = datetime.strptime(f"{data} {hora}", "%d/%m/%Y %H:%M:%S")
                    rows.append({"value": val, "timestamp": dt})
                except ValueError:
                    continue

    df = pd.DataFrame(rows)
    if not df.empty:
        df = df.sort_values("timestamp").reset_index(drop=True)
    return df


# ===========================================================================
# MDULO ML ADAPTATIVO
# ===========================================================================

# ---------------------------------------------------------------------------
# 1. Limpeza de outliers
# ---------------------------------------------------------------------------

def clean_gaps(gaps: pd.Series) -> pd.Series:
    """Remove outliers adaptativamente conforme o tamanho da amostra."""
    if len(gaps) < 5:
        return gaps

    if len(gaps) < 20:
        # IQR ampliado  menos agressivo com poucos dados
        q1, q3 = gaps.quantile(0.25), gaps.quantile(0.75)
        iqr = q3 - q1
        lower, upper = q1 - 2.5 * iqr, q3 + 2.5 * iqr
    else:
        # z-score 3 para amostras maiores
        mean, std = gaps.mean(), gaps.std()
        lower, upper = mean - 3 * std, mean + 3 * std

    cleaned = gaps[(gaps >= lower) & (gaps <= upper)]
    removed = len(gaps) - len(cleaned)
    if removed > 0:
        log(f"  [LIMPEZA] {removed} outlier(s) removido(s) dos gaps.")
    return cleaned if len(cleaned) >= 3 else gaps  # reverte se limpou demais


# ---------------------------------------------------------------------------
# 2. Feature engineering adaptativa
# ---------------------------------------------------------------------------

def build_features(gaps: pd.Series):
    """
    Gera matriz de features X e vetor alvo y.
    A janela e os tipos de feature crescem com o volume de dados disponveis.
    Retorna (X, y).
    """
    n = len(gaps)

    # Janela de lags dinmica
    if n < 10:
        lag_window = 2
    elif n < 20:
        lag_window = 3
    elif n < 40:
        lag_window = 5
    else:
        lag_window = 8

    X, y = [], []

    for i in range(lag_window, n):
        row = list(gaps.iloc[i - lag_window:i].values)  # lags brutos

        # Features de rolling stats (com amostra suficiente)
        if n >= MIN_GAPS_FEATURES_EXT:
            window_vals = gaps.iloc[max(0, i - lag_window):i]
            wm = window_vals.mean()
            row += [
                wm,                                                          # mdia da janela
                window_vals.std() if len(window_vals) > 1 else 0.0,         # desvio padro
                window_vals.min(),                                           # mnimo
                window_vals.max(),                                           # mximo
                gaps.iloc[i - 1] / (wm + 1e-9),                            # ratio ltimo/mdia
                float((window_vals.diff().dropna() > 0).sum()),             # n de altas
                gaps.iloc[i - 1] - gaps.iloc[i - lag_window],               # delta da janela
            ]

        # Posio relativa na srie (tendncia temporal leve)
        if n >= 30:
            row.append(i / n)

        X.append(row)
        y.append(gaps.iloc[i])

    return np.array(X), np.array(y)


# ---------------------------------------------------------------------------
# 3. Seleo automtica de modelo por volume
# ---------------------------------------------------------------------------

def select_model(n_gaps: int):
    """Retorna (model, model_name) adequados para o volume de dados disponvel."""
    if n_gaps >= MIN_GAPS_GBM:
        return GradientBoostingRegressor(
            n_estimators=300, max_depth=4,
            learning_rate=0.05, subsample=0.8,
            min_samples_leaf=3, random_state=42
        ), "GradientBoosting"
    elif n_gaps >= MIN_GAPS_RF:
        return RandomForestRegressor(
            n_estimators=200, max_depth=6,
            min_samples_leaf=2, random_state=42
        ), "RandomForest"
    elif n_gaps >= MIN_GAPS_RIDGE:
        return Ridge(alpha=1.0), "Ridge"
    else:
        return None, "Estatistico"


# ---------------------------------------------------------------------------
# 4. Log de acurcia
# ---------------------------------------------------------------------------

def load_accuracy_log() -> dict:
    if os.path.exists(ACCURACY_LOG):
        try:
            with open(ACCURACY_LOG, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {"5": [], "10": [], "50": [], "oc_5": [], "oc_10": [], "oc_50": []}


def save_accuracy_log(acc_log: dict):
    try:
        with open(ACCURACY_LOG, "w", encoding="utf-8") as f:
            json.dump(acc_log, f, indent=2)
    except Exception as e:
        log(f"  [WARN] Nao foi possivel salvar log de acuracia: {e}")


# ---------------------------------------------------------------------------
# 5. Treinamento com validao temporal  s salva se melhorar
# ---------------------------------------------------------------------------

def train_and_maybe_update(gaps: pd.Series, model_file: str,
                            scaler_file: str, log_key: str) -> dict:
    """
    Treina, valida e substitui o modelo apenas se a acurcia melhorar.
    Suporta amostras pequenas com degradao graciosa.
    """
    metrics = {'model_name': 'Estatistico', 'n_gaps': len(gaps),
               'mae': None, 'rmse': None, 'cv_mae': None, 'cv_std': None}

    n = len(gaps)
    model, model_name = select_model(n)
    metrics['model_name'] = model_name

    if model is None:
        return metrics

    try:
        X, y = build_features(gaps)
        if len(X) < 6:
            return metrics

        scaler = StandardScaler()
        X_scaled = scaler.fit_transform(X)

        # Validao cruzada temporal (quando h dados suficientes)
        if n >= MIN_GAPS_GBM and len(X) >= 15:
            n_splits = min(5, len(X) // 5)
            tscv = TimeSeriesSplit(n_splits=n_splits)
            cv_scores = cross_val_score(
                model, X_scaled, y,
                cv=tscv, scoring='neg_mean_absolute_error'
            )
            metrics['cv_mae'] = float(-cv_scores.mean())
            metrics['cv_std'] = float(cv_scores.std())
            log(f"  [{log_key}] CV-MAE: {metrics['cv_mae']:.1f}s "
                f"({metrics['cv_std']:.1f}s) | Modelo: {model_name}")
        else:
            log(f"  [{log_key}] Amostra limitada ({n} gaps) | Modelo: {model_name}")

        # Hold-out temporal (80/20)
        split = max(1, int(len(X) * 0.8))
        X_tr, X_te = X_scaled[:split], X_scaled[split:]
        y_tr, y_te = y[:split], y[split:]

        model.fit(X_tr, y_tr)

        new_mae = None
        if len(X_te) > 0:
            preds    = model.predict(X_te)
            new_mae  = mean_absolute_error(y_te, preds)
            new_rmse = np.sqrt(mean_squared_error(y_te, preds))
            metrics['mae']  = float(new_mae)
            metrics['rmse'] = float(new_rmse)
            log(f"  [{log_key}] MAE={new_mae:.1f}s | RMSE={new_rmse:.1f}s")

        # Compara com modelo anterior antes de salvar
        should_save = True
        if os.path.exists(model_file) and new_mae is not None:
            try:
                old_model  = joblib.load(model_file)
                old_scaler = joblib.load(scaler_file) if os.path.exists(scaler_file) else scaler
                X_te_old   = old_scaler.transform(X[split:])
                old_preds  = old_model.predict(X_te_old)
                old_mae    = mean_absolute_error(y_te, old_preds)
                if old_mae <= new_mae:
                    should_save = False
                    log(f"  [{log_key}] Modelo anterior mantido "
                        f"(MAE {old_mae:.1f}s vs {new_mae:.1f}s)")
            except Exception:
                pass  # modelo incompatvel  substitui

        if should_save:
            model.fit(X_scaled, y)   # retreina com 100% antes de salvar
            joblib.dump(model, model_file)
            joblib.dump(scaler, scaler_file)
            log(f"  [{log_key}] Modelo atualizado e salvo.")

        # Persiste log de acurcia
        acc_log = load_accuracy_log()
        if log_key not in acc_log:
            acc_log[log_key] = []
        acc_log[log_key].append({
            'ts': datetime.now().isoformat(),
            'n_gaps': n, 'model': model_name,
            'mae': metrics['mae'], 'rmse': metrics['rmse'],
            'cv_mae': metrics['cv_mae']
        })
        acc_log[log_key] = acc_log[log_key][-200:]
        save_accuracy_log(acc_log)

    except Exception as e:
        log(f"  [{log_key}] ERRO no treinamento: {e}")

    return metrics


# ---------------------------------------------------------------------------
# 6. Predio robusta com fallback estatstico
# ---------------------------------------------------------------------------

def predict_next_gap(gaps: pd.Series, model_file: str,
                      scaler_file: str, mean_gap: float) -> float:
    """
    Retorna o gap previsto em segundos (ou rodadas).
    Fallback: mdia ponderada (recentes pesam mais)  mdia simples.
    """
    if os.path.exists(model_file) and len(gaps) >= MIN_GAPS_RIDGE:
        try:
            model  = joblib.load(model_file)
            scaler = joblib.load(scaler_file) if os.path.exists(scaler_file) else None

            X, _ = build_features(gaps)
            if len(X) == 0:
                raise ValueError("Features vazias")

            last_x = X[-1].reshape(1, -1)
            if scaler:
                last_x = scaler.transform(last_x)

            pred = float(model.predict(last_x)[0])
            # Sanitizao  rejeita predies negativas ou absurdas
            pred = max(pred, 1.0)
            pred = min(pred, mean_gap * 10)
            return pred
        except Exception as e:
            log(f"  [WARN] Predicao ML falhou ({e}), usando fallback.")

    # Fallback: mdia ponderada exponencial
    if len(gaps) >= 3:
        weights = np.linspace(0.5, 1.5, len(gaps))
        return float(np.average(gaps.values, weights=weights))

    return mean_gap


# ===========================================================================
# Funes de anlise
# ===========================================================================

def analyze_spikes(df, threshold, label):
    """Analisa picos acima do threshold e calcula estimativas."""
    if df.empty:
        return None

    spikes = df[df["value"] > threshold].copy()
    if len(spikes) < 2:
        print(f"[ANALYSIS] {label}: Poucos dados para analise (menos de 2 picos)")
        return None

    # Calcular intervalos entre picos
    spikes = spikes.sort_values("timestamp").reset_index(drop=True)
    spikes["gap_seconds"]     = spikes["timestamp"].diff().dt.total_seconds()
    spikes["gap_occurrences"] = spikes.index.to_series().diff()

    raw_gaps    = spikes["gap_seconds"].dropna()
    gaps_oc_raw = spikes["gap_occurrences"].dropna()

    if raw_gaps.empty:
        return None

    #  Limpeza de outliers 
    gaps    = clean_gaps(raw_gaps)
    gaps_oc = clean_gaps(gaps_oc_raw)

    #  Estatsticas descritivas 
    mean_gap   = gaps.mean()
    median_gap = gaps.median()
    std_gap    = gaps.std() if len(gaps) > 1 else 0.0
    if pd.isna(std_gap):
        std_gap = 0.0

    # Percentis para janela de confiana mais robusta
    p25 = gaps.quantile(0.25) if len(gaps) >= 4 else mean_gap - std_gap
    p75 = gaps.quantile(0.75) if len(gaps) >= 4 else mean_gap + std_gap

    #  Seleo de arquivos por threshold 
    if threshold == THRESHOLD_5:
        model_file, model_file_oc = MODEL_FILE_5,  MODEL_FILE_OC_5
        scaler_file, scaler_oc    = SCALER_FILE_5, SCALER_FILE_OC_5
        log_key, log_key_oc       = "5",  "oc_5"
    elif threshold == THRESHOLD_10:
        model_file, model_file_oc = MODEL_FILE_10, MODEL_FILE_OC_10
        scaler_file, scaler_oc    = SCALER_FILE_10, SCALER_FILE_OC_10
        log_key, log_key_oc       = "10", "oc_10"
    else:
        model_file, model_file_oc = MODEL_FILE_50, MODEL_FILE_OC_50
        scaler_file, scaler_oc    = SCALER_FILE_50, SCALER_FILE_OC_50
        log_key, log_key_oc       = "50", "oc_50"

    #  Treinamento adaptativo  modelo de tempo 
    train_and_maybe_update(gaps, model_file, scaler_file, f">{threshold} tempo")

    #  Treinamento adaptativo  modelo de ocorrncias 
    if len(gaps_oc) > 5:
        train_and_maybe_update(gaps_oc, model_file_oc, scaler_oc,
                               f">{threshold} rodadas")

    #  Predio de tempo 
    predicted_gap = predict_next_gap(gaps, model_file, scaler_file, mean_gap)

    #  Predio de ocorrncias 
    mean_oc = gaps_oc.mean() if not gaps_oc.empty else 0
    predicted_gap_oc = predict_next_gap(gaps_oc, model_file_oc, scaler_oc, mean_oc) \
        if not gaps_oc.empty else 0.0

    # Rodadas desde o ltimo pico (usa ndice original do df)
    original_spike_idx = df[df["value"] > threshold].index
    current_oc = (len(df) - 1) - original_spike_idx[-1] if len(original_spike_idx) > 0 else 0

    #  Janela de confiana robusta 
    if len(gaps) >= 10:
        half_low  = predicted_gap - (predicted_gap - p25) * 0.5
        half_high = predicted_gap + (p75 - predicted_gap) * 0.5
    else:
        half_low  = max(0, predicted_gap - 0.5 * std_gap)
        half_high = predicted_gap + 0.5 * std_gap

    last_spike_time  = spikes["timestamp"].iloc[-1]
    predicted_next   = last_spike_time + timedelta(seconds=predicted_gap)
    predicted_early  = last_spike_time + timedelta(seconds=half_low)
    predicted_late   = last_spike_time + timedelta(seconds=half_high)

    #  Sada no terminal (formato idntico ao original) 
    print(f"\n[ANALYSIS] {label} - Analise de Picos:")
    print(f"  Total de picos: {len(spikes)}")
    print(f"  Intervalo medio: {mean_gap/60:.2f} min (+/-{std_gap/60:.2f} min)")
    print(f"  Mediana dos intervalos: {median_gap/60:.2f} min")
    print(f"  Proximo gap previsto (ML Tempo): {predicted_gap/60:.2f} min")
    print(f"  Proximo gap previsto (ML Rodadas): {predicted_gap_oc:.1f}")
    print(f"  Rodadas desde o ultimo: {current_oc}")
    print(f"  Ultimo pico: {last_spike_time.strftime('%d/%m/%Y %H:%M:%S')}")
    print(f"  Proximo pico estimado: {predicted_next.strftime('%d/%m/%Y %H:%M:%S')}")
    print(f"  Janela provavel: {predicted_early.strftime('%H:%M:%S')} -> {predicted_late.strftime('%H:%M:%S')}")

    #  Salva previso 
    save_prediction(threshold, predicted_next, predicted_early, predicted_late)

    #  Atualiza dashboard (chaves idnticas ao original) 
    if threshold == THRESHOLD_5:
        key = 'spikes_5'
    elif threshold == THRESHOLD_10:
        key = 'spikes_10'
    else:
        key = 'spikes_50'

    latest_analysis[key] = {
        'total':            len(spikes),
        'mean_gap':         mean_gap / 60,
        'predicted_gap':    predicted_gap / 60,
        'predicted_gap_oc': predicted_gap_oc,
        'current_oc':       current_oc,
        'predicted_next':   predicted_next.strftime('%d/%m/%Y %H:%M:%S'),
        'window':           f"{predicted_early.strftime('%H:%M:%S')} -> {predicted_late.strftime('%H:%M:%S')}"
    }

    return predicted_next


def analyze_trends(df):
    """Analisa tendencias usando rolling window com ajuste polinomial de grau 2."""
    if len(df) < WINDOW_SIZE:
        return

    df = df.copy()
    df["rolling_mean"] = df["value"].rolling(WINDOW_SIZE).mean()

    # Slope linear (grau 1)  mantido para exibio
    df["rolling_slope"] = df["value"].rolling(WINDOW_SIZE).apply(
        lambda x: np.polyfit(range(len(x)), x, 1)[0] if len(x) == WINDOW_SIZE else np.nan,
        raw=True
    )

    # Curvatura (grau 2)  melhora a projeo capturando acelerao
    df["rolling_curv"] = df["value"].rolling(WINDOW_SIZE).apply(
        lambda x: np.polyfit(range(len(x)), x, 2)[0] if len(x) == WINDOW_SIZE else np.nan,
        raw=True
    )

    df["projection"] = df["rolling_mean"] + df["rolling_slope"]

    if not df["rolling_slope"].isna().all():
        last_mean  = df["rolling_mean"].iloc[-1]
        last_slope = df["rolling_slope"].iloc[-1]
        last_curv  = df["rolling_curv"].iloc[-1] if not df["rolling_curv"].isna().all() else 0.0

        # Sada no terminal (formato idntico ao original)
        print("\n[ANALYSIS] Tendencia Rolling Window (ultimas 5 amostras):")
        print(f"  Media: {last_mean:.2f}")
        print(f"  Inclinacao: {last_slope:.4f}")

        projections = []
        for i in range(1, 5):
            # Projeo com componente quadrtico (mais precisa que linear puro)
            pred = last_mean + i * last_slope + (i ** 2) * last_curv * 0.5
            projections.append(pred)
            print(f"  Projecao proxima {i}: {pred:.2f}")
            if pred > THRESHOLD_5:
                print(f"    ALERTA: Projecao {i} aponta para valor > 5!")
            if pred > THRESHOLD_10:
                print(f"    ALERTA: Projecao {i} aponta para valor > 10!")
            if pred > THRESHOLD_50:
                print(f"    ALERTA: Projecao {i} aponta para valor > 50!")

        # Atualiza dashboard (chaves idnticas ao original)
        latest_analysis['trends'] = {
            'mean':  last_mean,
            'slope': last_slope,
            'projections': [
                {'value': p, 'alert_5': p > THRESHOLD_5,
                 'alert_10': p > THRESHOLD_10, 'alert_50': p > THRESHOLD_50}
                for p in projections
            ]
        }


def analyze_signatures(df, threshold, label):
    """Analisa assinaturas pre-pico"""
    if df.empty:
        return

    spikes = df[df["value"] > threshold]
    if len(spikes) < 1:
        return

    signatures = []
    for idx in spikes.index:
        if idx >= PRE_WINDOW:
            pre_values = df.loc[idx - PRE_WINDOW:idx - 1, "value"].values
            signatures.append(pre_values)

    if signatures:
        mean_signature = np.mean(signatures, axis=0)
        print(f"\n[ANALYSIS] {label} - Assinatura media pre-pico (ultimas {PRE_WINDOW} amostras):")
        print(f"  {np.round(mean_signature, 2)}")


def save_prediction(threshold, predicted_next, predicted_early, predicted_late):
    """Saves a prediction to the predictions file."""
    with open(PREDICTIONS_FILE, "a", encoding="utf-8") as f:
        ts_now    = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        next_str  = predicted_next.strftime("%d/%m/%Y %H:%M:%S")
        early_str = predicted_early.strftime("%d/%m/%Y %H:%M:%S")
        late_str  = predicted_late.strftime("%d/%m/%Y %H:%M:%S")
        f.write(f"{ts_now};{threshold};{next_str};{early_str};{late_str};pendente\n")


def check_predictions(df):
    """Checks pending predictions against current data and updates status."""
    if not os.path.exists(PREDICTIONS_FILE):
        return

    lines = []
    with open(PREDICTIONS_FILE, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            parts = line.split(";")
            if len(parts) == 6:
                ts_str, thresh_str, next_str, early_str, late_str, status = parts
                thresh = float(thresh_str)
                early  = datetime.strptime(early_str, "%d/%m/%Y %H:%M:%S")
                late   = datetime.strptime(late_str,  "%d/%m/%Y %H:%M:%S")
                if status == "pendente":
                    spikes_in_window = df[
                        (df["timestamp"] >= early) &
                        (df["timestamp"] <= late) &
                        (df["value"] > thresh)
                    ]
                    if not spikes_in_window.empty:
                        status = "acerto"
                    elif datetime.now() > late:
                        status = "erro"
                lines.append(f"{ts_str};{thresh_str};{next_str};{early_str};{late_str};{status}\n")

    with open(PREDICTIONS_FILE, "w", encoding="utf-8") as f:
        f.writelines(lines)


def run_analysis():
    """Executa analise completa"""
    df = load_data_for_analysis()
    if df.empty:
        print("[ANALYSIS] Nenhum dado encontrado no arquivo.")
        return

    print(f"\n{'='*60}")
    print(f"[ANALYSIS] Analise apos captura - {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")
    print(f"  Total de registros: {len(df)}")
    print(f"  Periodo: {df['timestamp'].min()} -> {df['timestamp'].max()}")
    print(f"  Ultimo registro: {df['timestamp'].max()} - Valor: {df['value'].iloc[-1]:.2f}")

    # Update dashboard initial data
    latest_analysis['total_registros'] = len(df)
    latest_analysis['periodo'] = f"{df['timestamp'].min()} -> {df['timestamp'].max()}"
    latest_analysis['ultimo']  = f"{df['timestamp'].max()} - Valor: {df['value'].iloc[-1]:.2f}"

    last_50_df = df.tail(100)

    latest_analysis['counts_100'] = {
        'c2':  len(last_50_df[last_50_df['value'] >= 2]),
        'c5':  len(last_50_df[last_50_df['value'] >= 5]),
        'c10': len(last_50_df[last_50_df['value'] >= 10]),
        'c50': len(last_50_df[last_50_df['value'] >= 50])
    }

    # Pre-calcula rolling para o grfico
    df_chart = df.copy()
    df_chart["rolling_mean"]  = df_chart["value"].rolling(WINDOW_SIZE).mean()
    df_chart["rolling_slope"] = df_chart["value"].rolling(WINDOW_SIZE).apply(
        lambda x: np.polyfit(range(len(x)), x, 1)[0] if len(x) == WINDOW_SIZE else np.nan,
        raw=True
    )
    df_chart["projection"] = df_chart["rolling_mean"] + df_chart["rolling_slope"]
    df_chart_sliced = df_chart.tail(100)

    last_50_formatted = []
    for _, r in df_chart_sliced.iterrows():
        val = r['value']
        color = '#6c757d'
        if val >= 50:
            color = '#007bff'
        elif val >= 10:
            color = '#e83e8c'
        elif val >= 5:
            color = '#28a745'
        elif val >= 2:
            color = '#6f42c1'
        last_50_formatted.append({
            'value': val,
            'time': r['timestamp'].strftime('%H:%M:%S'),
            'color': color,
            'rolling_mean': float(r['rolling_mean']) if not pd.isna(r['rolling_mean']) else None,
            'projection':   float(r['projection'])   if not pd.isna(r['projection'])   else None
        })
    latest_analysis['last_100'] = last_50_formatted

    # Anlise para cada threshold
    analyze_spikes(df, THRESHOLD_5,  ">5")
    analyze_spikes(df, THRESHOLD_10, ">10")
    analyze_spikes(df, THRESHOLD_50, ">50")

    # Tendncias
    analyze_trends(df)

    # Assinaturas
    analyze_signatures(df, THRESHOLD_5,  ">5")
    analyze_signatures(df, THRESHOLD_10, ">10")
    analyze_signatures(df, THRESHOLD_50, ">50")

    # Verifica e atualiza previses
    check_predictions(df)

    # Exibe estatsticas de previses
    if os.path.exists(PREDICTIONS_FILE):
        stats = {}
        with open(PREDICTIONS_FILE, "r", encoding="utf-8") as f:
            for line in f:
                parts = line.strip().split(";")
                if len(parts) == 6:
                    thresh_str, status = parts[1], parts[5]
                    thresh = float(thresh_str)
                    if thresh not in stats:
                        stats[thresh] = {"acertos": 0, "erros": 0, "pendentes": 0}
                    if status == "acerto":
                        stats[thresh]["acertos"] += 1
                    elif status == "erro":
                        stats[thresh]["erros"] += 1
                    elif status == "pendente":
                        stats[thresh]["pendentes"] += 1

        for thresh, counts in stats.items():
            total              = counts["acertos"] + counts["erros"]
            total_predictions  = total + counts["pendentes"]
            if total > 0:
                taxa_acerto = counts["acertos"] / total * 100
                print(f"\n[ANALYSIS] Prediction Statistics for >{int(thresh)}: "
                      f"Total predictions: {total_predictions}, "
                      f"Hits: {counts['acertos']}, Misses: {counts['erros']}, "
                      f"Hit Rate: {taxa_acerto:.1f}%, Pending: {counts['pendentes']}")
            else:
                print(f"\n[ANALYSIS] Prediction Statistics for >{int(thresh)}: "
                      f"Total predictions: {total_predictions}, "
                      f"No completed predictions, Pending: {counts['pendentes']}")

            if thresh == 5.0:
                key = 'pred_5'
            elif thresh == 10.0:
                key = 'pred_10'
            else:
                key = 'pred_50'

            latest_predictions[key] = {
                'total':   total_predictions,
                'hits':    counts['acertos'],
                'misses':  counts['erros'],
                'rate':    taxa_acerto if total > 0 else 0,
                'pending': counts['pendentes']
            }


# ===========================================================================
# Loop principal do servio
# ===========================================================================

def main():
    if os.path.exists(OUTPUT_FILE):
        log("=== AviatorService iniciado - continuando captura em arquivo existente ===")
    else:
        log("=== AviatorService iniciado ===")
    driver = iniciar_driver()

    # Start Flask dashboard in a thread
    threading.Thread(
        target=lambda: app.run(host='0.0.0.0', port=5000,
                               debug=False, use_reloader=False),
        daemon=True
    ).start()

    # Tentar login com retry em caso de timeout
    login_sucesso = False
    for tentativa in range(1, 3):
        try:
            fazer_login(driver)
            login_sucesso = True
            break
        except Exception as e:
            log("ERRO no login tentativa " + str(tentativa) + ": " + str(e))
            if tentativa < 2 and "timeout" in str(e).lower():
                log("Tentando login novamente apos timeout...")
                time.sleep(5)
            else:
                log("Falha no login, tentando captura sem login.")
                break

    if login_sucesso:
        log("Login realizado com sucesso.")
    else:
        log("Proceeding without login.")

    try:
        if os.path.exists(OUTPUT_FILE):
            run_analysis()

        ciclo = 0
        while True:
            ciclo += 1
            log("--- Ciclo " + str(ciclo) + " ---")

            try:
                novos = capturar_ultimos(driver)
                log("Capturados " + str(len(novos)) + " registros da pagina.")

                existentes = carregar_existentes()
                mesclados, adicionados = mesclar(existentes, novos)
                salvar_arquivo(mesclados)

                log("Adicionados " + str(adicionados) + " novos registros. "
                    "Total no arquivo: " + str(len(mesclados)) + ".")

            except Exception as e:
                log("ERRO no ciclo " + str(ciclo) + ": " + str(e))
                if "timeout" in str(e).lower():
                    log("Timeout detectado, reiniciando driver e fazendo login...")
                    driver.quit()
                    driver = iniciar_driver()
                    try:
                        fazer_login(driver)
                    except Exception as e2:
                        log("ERRO ao relogar apos timeout: " + str(e2))
                else:
                    try:
                        fazer_login(driver)
                    except Exception as e2:
                        log("ERRO ao relogar: " + str(e2))

            run_analysis()

            log("Aguardando " + str(INTERVALO_SEGUNDOS) + " segundos...")
            time.sleep(INTERVALO_SEGUNDOS)

    except KeyboardInterrupt:
        log("Servico encerrado pelo usuario.")
    finally:
        driver.quit()


# ===========================================================================
# Flask App (dashboard idntico ao original)
# ===========================================================================

if __name__ == "__main__":
    app = Flask(__name__)
    latest_analysis    = {'spikes_5': None, 'spikes_10': None, 'spikes_50': None, 'trends': None}
    latest_predictions = {'pred_5': None, 'pred_10': None, 'pred_50': None}

    @app.route('/')
    def dashboard():
        import json
        html = """
        <!DOCTYPE html>
        <html lang="pt-BR">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Aviator Analytics Dashboard</title>
            <meta http-equiv="refresh" content="30">
            <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
            <style>
                body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; margin: 0; background-color: #f4f7f6; color: #333; }
                .header { background-color: #fff; padding: 20px 40px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; }
                .header h1 { margin: 0; color: #e83e8c; font-size: 24px; }
                .container { display: flex; flex-wrap: wrap; gap: 20px; padding: 0 40px 40px 40px; }
                .sidebar { flex: 1; min-width: 250px; display: flex; flex-direction: column; gap: 20px; }
                .main-content { flex: 3; min-width: 600px; display: flex; flex-direction: column; gap: 20px; }
                .card { background: #fff; border-radius: 8px; box-shadow: 0 2px 10px rgba(0,0,0,0.05); padding: 20px; }
                .kpi { display: flex; flex-direction: column; align-items: center; justify-content: center; text-align: center; border: 1px solid #eee; border-radius: 8px; padding: 15px; }
                .kpi h4 { margin: 0 0 10px 0; color: #888; font-size: 14px; text-transform: uppercase; }
                .kpi-value { font-size: 24px; font-weight: bold; color: #e83e8c; margin: 0; }

                .grid-3 { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 20px; }
                .alert { background-color: #ffeeba; color: #856404; padding: 10px; border-radius: 5px; font-weight: bold; margin-bottom: 15px; }
                .history-list { display: flex; flex-wrap: wrap; gap: 5px; margin-top: 15px; }
                .history-item { padding: 4px 8px; border-radius: 4px; color: #fff; font-size: 12px; font-weight: bold; }

                h2, h3 { color: #444; margin-top: 0; }
                p { margin: 8px 0; font-size: 14px; }
            </style>
        </head>
        <body>
            <button id="btn-sound" style="position:fixed; top:10px; right:10px; z-index:9999; padding:8px 12px; background:#28a745; color:#fff; border:none; border-radius:5px; cursor:pointer; font-weight:bold;"></button>

            <div class="container" style="padding-top: 20px;">
                <div class="sidebar">
                    <div class="card" style="text-align: center; font-size: 14px; color: #666;">
                        <p><strong>Atual:</strong> {{ now }}</p>
                        <p><strong>ltima:</strong> {{ ultimo.split(' - ')[0] if ultimo else 'N/A' }}</p>
                    </div>

                    <div class="card">
                        <h3>Geral</h3>
                        <div style="display:flex; gap:10px;">
                            <div class="kpi" style="flex:1; margin-bottom:10px; padding: 10px;">
                                <h4>Total Registros</h4>
                                <p class="kpi-value" style="font-size: 20px;">{{ total_registros }}</p>
                            </div>
                            <div class="kpi" style="flex:1; margin-bottom:10px; padding: 10px;">
                                <h4>ltimo Valor</h4>
                                <p class="kpi-value" style="color:#333; font-size: 20px;">{{ ultimo.split(' - ')[1] if ultimo else 'N/A' }}</p>
                            </div>
                        </div>
                        <div style="font-size:13px; margin-top:5px; border-top:1px solid #eee; padding-top:10px; text-align: center;">
                            <strong>Nas ltimas 100 rodadas:</strong><br>
                            <span style="color:#6f42c1;font-weight:bold;">>2:</span> {{ counts_100.c2 if counts_100 else 0 }} | 
                            <span style="color:#28a745;font-weight:bold;">>5:</span> {{ counts_100.c5 if counts_100 else 0 }} | 
                            <span style="color:#e83e8c;font-weight:bold;">>10:</span> {{ counts_100.c10 if counts_100 else 0 }} | 
                            <span style="color:#007bff;font-weight:bold;">>50:</span> {{ counts_100.c50 if counts_100 else 0 }}
                        </div>
                        <p style="font-size:12px;text-align:center;color:#666;margin-top:10px;">Perodo: {{ periodo }}</p>
                    </div>

                    <div class="card">
                        <h3>Alertas & Tendncias</h3>
                        {% if trends and trends.projections %}
                            {% for proj in trends.projections %}
                                {% if proj.alert_50 %}
                                    <div class="alert" data-level="50" style="background-color: #f8d7da; color: #721c24;">ALERTA! Previso {{ loop.index }} aponta p/ >50</div>
                                {% elif proj.alert_10 %}
                                    <div class="alert" data-level="10" style="background-color: #cce5ff; color: #004085;">ALERTA! Previso {{ loop.index }} aponta p/ >10</div>
                                {% elif proj.alert_5 %}
                                    <div class="alert" data-level="5">ALERTA! Previso {{ loop.index }} aponta p/ >5</div>
                                {% endif %}
                            {% endfor %}
                            <p><strong>Mdia Movel:</strong> {{ "%.2f"|format(trends.mean) }}</p>
                            <p><strong>Inclinao:</strong> {{ "%.4f"|format(trends.slope) }}</p>
                            <p><strong>Prximas 4 Projees:</strong> 
                            {% for proj in trends.projections %}
                                {{ "%.2f"|format(proj.value) }} {% if not loop.last %} | {% endif %}
                            {% endfor %}
                            </p>
                        {% else %}
                            <p>Anlise em andamento...</p>
                        {% endif %}
                    </div>
                </div>

                <div class="main-content">
                    <div class="card">
                        <h3>ltimas 100 Ocorrncias</h3>
                        <canvas id="historyChart" width="400" height="80"></canvas>

                        <div class="history-list">
                            {% if last_100 %}
                                {% for item in last_100|reverse %}
                                    <span class="history-item" style="background-color: {{ item.color }};" title="{{ item.time }}">{{ "%.2f"|format(item.value) }}x</span>
                                {% endfor %}
                            {% endif %}
                        </div>
                    </div>

                    <div class="grid-3">
                        <div class="card">
                            <h3>Spikes > 5</h3>
                            <p><strong>Total Picos:</strong> {{ spikes_5.total if spikes_5 else 'N/A' }}</p>
                            <p><strong>Gap Mdio:</strong> {{ "%.2f"|format(spikes_5.mean_gap) if spikes_5 else 'N/A' }} min</p>
                            <p><strong>Previso Tempo ML:</strong> {{ "%.2f"|format(spikes_5.predicted_gap) if spikes_5 else 'N/A' }} min</p>
                            <p><strong>Previso (Rodadas):</strong> {{ "%.1f"|format(spikes_5.predicted_gap_oc) if spikes_5 else 'N/A' }}</p>
                            <p><strong>Desde ltimo Pico:</strong> {{ spikes_5.current_oc if spikes_5 else 'N/A' }} rodadas</p>
                            <p><strong>Prximo Pico:</strong> <span style="color:#e83e8c;font-weight:bold;">{{ spikes_5.predicted_next if spikes_5 else 'N/A' }}</span></p>
                            <p><strong>Janela:</strong> {{ spikes_5.window if spikes_5 else 'N/A' }}</p>
                            <br>
                            <p style="font-size:12px;color:#666;">Performance Previses >5: <br>Acertos: {{ pred_5.hits if pred_5 else 'N/A' }} / Erros: {{ pred_5.misses if pred_5 else 'N/A' }} / Taxa: {{ "%.1f"|format(pred_5.rate) if pred_5 and pred_5.rate is not none else 'N/A' }}%</p>
                        </div>
                        <div class="card">
                            <h3>Spikes > 10</h3>
                            <p><strong>Total Picos:</strong> {{ spikes_10.total if spikes_10 else 'N/A' }}</p>
                            <p><strong>Gap Mdio:</strong> {{ "%.2f"|format(spikes_10.mean_gap) if spikes_10 else 'N/A' }} min</p>
                            <p><strong>Previso Tempo ML:</strong> {{ "%.2f"|format(spikes_10.predicted_gap) if spikes_10 else 'N/A' }} min</p>
                            <p><strong>Previso (Rodadas):</strong> {{ "%.1f"|format(spikes_10.predicted_gap_oc) if spikes_10 else 'N/A' }}</p>
                            <p><strong>Desde ltimo Pico:</strong> {{ spikes_10.current_oc if spikes_10 else 'N/A' }} rodadas</p>
                            <p><strong>Prximo Pico:</strong> <span style="color:#007bff;font-weight:bold;">{{ spikes_10.predicted_next if spikes_10 else 'N/A' }}</span></p>
                            <p><strong>Janela:</strong> {{ spikes_10.window if spikes_10 else 'N/A' }}</p>
                            <br>
                            <p style="font-size:12px;color:#666;">Performance Previses >10: <br>Acertos: {{ pred_10.hits if pred_10 else 'N/A' }} / Erros: {{ pred_10.misses if pred_10 else 'N/A' }} / Taxa: {{ "%.1f"|format(pred_10.rate) if pred_10 and pred_10.rate is not none else 'N/A' }}%</p>
                        </div>
                        <div class="card">
                            <h3>Spikes > 50</h3>
                            <p><strong>Total Picos:</strong> {{ spikes_50.total if spikes_50 else 'N/A' }}</p>
                            <p><strong>Gap Mdio:</strong> {{ "%.2f"|format(spikes_50.mean_gap) if spikes_50 else 'N/A' }} min</p>
                            <p><strong>Previso Tempo ML:</strong> {{ "%.2f"|format(spikes_50.predicted_gap) if spikes_50 else 'N/A' }} min</p>
                            <p><strong>Previso (Rodadas):</strong> {{ "%.1f"|format(spikes_50.predicted_gap_oc) if spikes_50 else 'N/A' }}</p>
                            <p><strong>Desde ltimo Pico:</strong> {{ spikes_50.current_oc if spikes_50 else 'N/A' }} rodadas</p>
                            <p><strong>Prximo Pico:</strong> <span id="next-spike-50" style="color:#6f42c1;font-weight:bold;">{{ spikes_50.predicted_next if spikes_50 else 'N/A' }}</span></p>
                            <p><strong>Janela:</strong> {{ spikes_50.window if spikes_50 else 'N/A' }}</p>
                            <br>
                            <p style="font-size:12px;color:#666;">Performance Previses >50: <br>Acertos: {{ pred_50.hits if pred_50 else 'N/A' }} / Erros: {{ pred_50.misses if pred_50 else 'N/A' }} / Taxa: {{ "%.1f"|format(pred_50.rate) if pred_50 and pred_50.rate is not none else 'N/A' }}%</p>
                        </div>
                    </div>
                </div>
            </div>

            <script>
                const canvas = document.getElementById('historyChart');
                if(canvas) {
                    const ctx = canvas.getContext('2d');
                    const lastData = {{ last_100|tojson if last_100 else '[]' }};
                    const chartData = lastData.slice(-50); // Mantm exibio grfica em 50

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
                                label: 'Mdia Mvel (5)',
                                data: rollingMeans,
                                borderColor: '#ffc107',
                                borderWidth: 1,
                                borderDash: [5, 5],
                                pointRadius: 0,
                                fill: false,
                                tension: 0.2
                            },
                            {
                                label: 'Projeo de Tendncia',
                                data: projections,
                                borderColor: '#dc3545',
                                borderWidth: 1,
                                borderDash: [2, 2],
                                pointRadius: 0,
                                fill: false,
                                tension: 0.2
                            }]
                        },
                        options: {
                            responsive: true,
                            scales: {
                                y: {
                                    beginAtZero: true,
                                    suggestedMax: 10
                                },
                                x: {
                                    display: false
                                }
                            },
                            plugins: {
                                legend: {
                                    display: true,
                                    position: 'top',
                                    labels: {
                                        boxWidth: 12,
                                        font: {
                                            size: 10
                                        }
                                    }
                                }
                            }
                        }
                    });
                }
            </script>
            <script>
                // Controle de Audio para Alertas
                const btnSound = document.getElementById('btn-sound');
                let soundEnabled = localStorage.getItem('sound_enabled') === 'true';

                function updateBtn() {
                    if(!btnSound) return;
                    btnSound.innerText = soundEnabled ? " Som Ativado" : " Ativar Som";
                    btnSound.style.backgroundColor = soundEnabled ? "#28a745" : "#6c757d";
                }

                if(btnSound) {
                    updateBtn();
                    btnSound.addEventListener('click', () => {
                        soundEnabled = !soundEnabled;
                        localStorage.setItem('sound_enabled', soundEnabled);
                        updateBtn();
                        if(soundEnabled) playChangeSound(); // Toca som de teste para garantir interao
                    });
                }

                function playAlertSound(times) {
                    if(!soundEnabled || times <= 0) return;
                    try {
                        const ctx = new (window.AudioContext || window.webkitAudioContext)();
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
                        const ctx = new (window.AudioContext || window.webkitAudioContext)();
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
                    } catch(e) { console.error('Erro de audio:', e); }
                }

                window.addEventListener('DOMContentLoaded', () => {
                    let alerts = document.querySelectorAll('.alert');
                    let maxLevel = 0;
                    alerts.forEach(a => {
                        let level = parseInt(a.getAttribute('data-level')) || 0;
                        if (level > maxLevel) maxLevel = level;
                    });

                    let beepCount = 0;
                    if (maxLevel === 50) beepCount = 20;
                    else if (maxLevel === 10) beepCount = 10;
                    else if (maxLevel === 5) beepCount = 5;

                    let nextSpike50El = document.getElementById('next-spike-50');
                    let currentSpike50 = nextSpike50El ? nextSpike50El.innerText.trim() : 'N/A';
                    let lastSpike50 = localStorage.getItem('last_spike_50');

                    let spikeChanged = false;
                    if (currentSpike50 !== 'N/A' && lastSpike50 && currentSpike50 !== lastSpike50) {
                        spikeChanged = true;
                    }
                    if (currentSpike50 !== 'N/A') {
                        localStorage.setItem('last_spike_50', currentSpike50);
                    }

                    // Tocar alarmes (se ativado pelo usurio)
                    if (beepCount > 0) {
                        setTimeout(() => playAlertSound(beepCount), 500);
                    } else if (spikeChanged) {
                        setTimeout(playChangeSound, 500);
                    }
                });
            </script>
        </body>
        </html>
        """
        return render_template_string(html, now=datetime.now().strftime("%d/%m/%Y %H:%M:%S"), **latest_analysis, **latest_predictions)

    main()
