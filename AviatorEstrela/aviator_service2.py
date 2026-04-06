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
import numpy as np
import pandas as pd
from datetime import date, datetime, timedelta
from flask import Flask, render_template_string

# ML & Preprocessing
from sklearn.ensemble import RandomForestRegressor, GradientBoostingRegressor
from sklearn.linear_model import Ridge
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import mean_absolute_error, mean_squared_error
from sklearn.model_selection import TimeSeriesSplit

# Selenium
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

# ---------------------------------------------------------------------------
# Configurações e Caminhos
# ---------------------------------------------------------------------------
LOGIN_URL = "https://www.tipminer.com/br/historico/estrelabet/aviator"
EMAIL = "marcossa73.ms@gmail.com"
SENHA = "Mrcs3@46"

BASE_DIR         = os.path.dirname(os.path.abspath(__file__))
OUTPUT_FILE      = os.path.join(BASE_DIR, "resultados_aviator.txt")
LOG_FILE         = os.path.join(BASE_DIR, "log_execucao.txt")
PREDICTIONS_FILE = os.path.join(BASE_DIR, "predictions.txt")
ACCURACY_LOG     = os.path.join(BASE_DIR, "accuracy_log.json")

THRESHOLD_5, THRESHOLD_10, THRESHOLD_50 = 5.0, 10.0, 50.0
WINDOW_SIZE = 5
INTERVALO_SEGUNDOS = 20
MAX_REGISTROS = 10000

# ---------------------------------------------------------------------------
# Novo: Detector de Regime Oculto (Minimização de Seca)
# ---------------------------------------------------------------------------
class RegimeDetector:
    """Classifica o estado do jogo para evitar apostas em períodos de 'baixa'."""
    def __init__(self, window=12):
        self.window = window

    def get_state(self, df):
        if len(df) < self.window: 
            return "Amostragem Baixa", 0.5
        
        recent = df.tail(self.window)['value']
        volatility = recent.std()
        avg = recent.mean()
        
        # Identificação de padrões de 'Seca' (Média baixa e Volatilidade estagnada)
        if avg < 1.8 and volatility < 0.8:
            return "Seca Severa", 0.15 # Confiança muito baixa
        elif avg < 2.2 and volatility > 1.2:
            return "Recuperação", 0.55 # Transição
        elif avg > 2.8 or (recent > 10).any():
            return "Distribuição", 0.85 # Momento propício
        return "Estável", 0.50

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
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)
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
        elements = driver.find_elements(By.CSS_SELECTOR, ".cell__result")
        
        now = datetime.now()
        hoje_str = now.strftime("%d/%m/%Y")
        ontem_str = (now - timedelta(days=1)).strftime("%d/%m/%Y")
        novos = []
        
        for el in elements:
            try:
                val = el.text.replace('x','').replace('X','').replace(',', '.').strip()

                btn = driver.execute_script("""
                    var node = arguments[0];
                    while (node && node.tagName !== 'BUTTON') {
                        node = node.parentElement;
                    }
                    return node;
                """, el)

                if not val and btn:
                    data_result = btn.get_attribute("data-result") or ""
                    if data_result:
                        val = data_result.replace("X", "").replace("x", "").replace(',', '.').strip()

                hora = ""
                if btn:
                    try:
                        el_hora = btn.find_element(By.CSS_SELECTOR, ".cell__date")
                        hora = el_hora.text.strip()
                    except Exception:
                        pass

                if val and hora: 
                    try:
                        dt_tentativa = datetime.strptime(f"{hoje_str} {hora}", "%d/%m/%Y %H:%M:%S")
                        # Se o horário do chute no site for por exemplo 23:59 e agora for 00:01
                        # o dt_tentativa cai no 'hoje' as 23:59 (Quase 24h no futuro)
                        data_correta = ontem_str if dt_tentativa > now + timedelta(minutes=5) else hoje_str
                    except:
                        data_correta = hoje_str

                    novos.append((val.replace('.', ','), hora, data_correta))
            except Exception as ex: 
                log(f"Erro linha de captura: {ex}")
                continue
        return novos
    except Exception as e:
        log(f"Erro captura: {e}")
        return []

# ---------------------------------------------------------------------------
# Machine Learning Adaptativo (Refatorado para Stacked Ensemble)
# ---------------------------------------------------------------------------
def build_features(gaps: pd.Series):
    n = len(gaps)
    lag = 5 if n > 15 else 3
    X, y = [], []
    for i in range(lag, n):
        window = gaps.iloc[i-lag:i]
        feats = list(window.values)
        feats.append(window.mean())
        feats.append(window.std() if len(window) > 1 else 0)
        feats.append(window.iloc[-1] / (window.mean() + 1e-6)) # Ratio
        X.append(feats)
        y.append(gaps.iloc[i])
    return np.array(X), np.array(y)

def predict_optimized(data_series, threshold_label):
    """
    Treina o modelo usando o passado (X, y) 
    E preve O FUTURO criando features a partir dos ultimos 'lag' observados.
    """
    if len(data_series) < 10: return data_series.mean()

    try:
        X, y = build_features(data_series)
        scaler = StandardScaler()
        X_s = scaler.fit_transform(X)

        # Ensemble: Gradient Boosting para capturar não-linearidades
        model = GradientBoostingRegressor(n_estimators=100, learning_rate=0.1, max_depth=3, random_state=42)
        model.fit(X_s, y)

        # ====== O SEGREDO DA PREVISÃO CLARIVIDENTE ======
        # Para que o tempo previsto esteja de fato NO FUTURO (e não no pico que acabou de cair):
        # Isolemos cirurgicamente as últimas n=lag instâncias para compor a matriz desconhecida (Próxima Rodada)
        n = len(data_series)
        lag = 5 if n > 15 else 3

        future_window = data_series.iloc[-lag:]
        feats = list(future_window.values)
        feats.append(future_window.mean())
        feats.append(future_window.std() if len(future_window) > 1 else 0)
        feats.append(future_window.iloc[-1] / (future_window.mean() + 1e-6))

        future_x = np.array(feats).reshape(1, -1)
        pred = model.predict(scaler.transform(future_x))[0]
        return max(pred, 1.0)
    except:
        return data_series.mean()

# ---------------------------------------------------------------------------
# Análise de Dados e Dashboard
# ---------------------------------------------------------------------------
latest_analysis = {}

def analyze_spikes(df, threshold, label):
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

    # Detecção de Regime (Cérebro do Sistema)
    detector = RegimeDetector()
    regime_name, confidence = detector.get_state(df)

    # Predição ML Temporal
    pred_gap = predict_optimized(gaps, label + "_tempo")
    mean_gap = gaps.mean()

    # Predição ML Valor Extra (Estratégia similar de ML para saídas prováveis em pico)
    spike_values = spikes["value"]
    pred_value = predict_optimized(spike_values, label + "_valor")

    # Ajuste de Janela Dinâmica baseado na Confiança
    # Se confiança baixa, a janela de erro aumenta para evitar falsas entradas
    std_adj = (gaps.std() if len(gaps) > 1 else mean_gap * 0.3) * (1.5 - confidence)

    # Antecipações proativas reais - O ML traz o alvo provável,
    # Mas precisamos de fato dar um lead time para o operador não ser pego de surpresa ("muito em cima da hora")
    # Subtraímos também 10% do gap provável como gordura garantida no inicio do balão
    safety_margin = pred_gap * 0.10

    last_spike = spikes["timestamp"].iloc[-1]
    predicted_next = last_spike + timedelta(seconds=pred_gap)
    early = predicted_next - timedelta(seconds=(std_adj + safety_margin))
    late = predicted_next + timedelta(seconds=(std_adj + safety_margin))

    key = f'spikes_{int(threshold)}'

    # Injeção dos dados globais
    if len(df) > 0:
        latest_analysis['now'] = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        latest_analysis['ultimo'] = f"{df['timestamp'].iloc[-1].strftime('%d/%m/%Y %H:%M:%S')} - {df['value'].iloc[-1]:.2f}x"
        latest_analysis['total_registros'] = len(df)
        latest_analysis['periodo'] = f"{df['timestamp'].iloc[0].strftime('%d/%m/%Y %H:%M:%S')} -> {df['timestamp'].iloc[-1].strftime('%d/%m/%Y %H:%M:%S')}"
        last_100_df = df.tail(100)

        latest_analysis['counts_100'] = {
            'c2':  len(last_100_df[last_100_df['value'] >= 2]),
            'c5':  len(last_100_df[last_100_df['value'] >= 5]),
            'c10': len(last_100_df[last_100_df['value'] >= 10]),
            'c50': len(last_100_df[last_100_df['value'] >= 50])
        }

        # Pre-calcula rolling para o gráfico
        df_chart = df.copy()
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

        df_chart_sliced = df_chart.tail(100)

        last_100_formatted = []
        for _, r in df_chart_sliced.iterrows():
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
        latest_analysis['last_100'] = last_100_formatted

    old_history = latest_analysis.get(key, {}).get('history', [])

    # Load persistence if empty memory
    hist_file = os.path.join(BASE_DIR, "ml_history.json")
    if not old_history and os.path.exists(hist_file):
        try:
            with open(hist_file, "r", encoding="utf-8") as f:
                old_history = json.load(f).get(key, [])
        except: pass

    last_spike_str = last_spike.strftime('%H:%M:%S')

    # Store the prediction in history, unique per last_spike (so it only updates when a new spike hits)
    if not any(h['spike_time'] == last_spike_str for h in old_history):
        old_history.insert(0, {
            'prev_time': datetime.now().strftime('%H:%M:%S'),
            'spike_time': last_spike_str,
            'next': predicted_next.strftime('%H:%M:%S'),
            'window': f"{early.strftime('%H:%M:%S')} -> {late.strftime('%H:%M:%S')}",
            'value': pred_value
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

    latest_analysis[key] = {
        'total': len(spikes),
        'mean_gap': mean_gap / 60,
        'predicted_gap': pred_gap / 60,
        'predicted_value': pred_value,
        'regime': regime_name,
        'confidence': f"{confidence*100:.0f}%",
        'next': predicted_next.strftime('%H:%M:%S'),
        'window': f"{early.strftime('%H:%M:%S')} -> {late.strftime('%H:%M:%S')}",
        'current_oc': len(df) - 1 - df[df["value"] > threshold].index[-1],
        'history': old_history
    }

    log(f"Análise de {key} concluída e atualizada no dashboard!")

    save_prediction(threshold, predicted_next, early, late)

def analyze_trends(df):
    """Analisa tendencias usando rolling window com ajuste polinomial de grau 2."""
    if len(df) < WINDOW_SIZE:
        return

    df = df.copy()
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
            elif p >= 2: color = '#6f42c1'

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
        
    now = datetime.now()
    
    for line in linhas:
        p = line.split(";")
        if len(p) == 3:
            try:
                val = float(p[0].replace(",", "."))
                ts = datetime.strptime(f"{p[2]} {p[1]}", "%d/%m/%Y %H:%M:%S")
                
                # Correção Dinâmica de Timestamp Retroativo:
                # Se o horário gravado no arquivo de texto constar como sendo MAIOR (no Futuro) 
                # do que a vida real presente (Ex: Script rodou as 00:01 e processou uma linha marcada ás 23:59 "hoje"),
                # Devemos subtrair precisamente 1 dia desse registro para devolvê-lo ao "passado" correto de "Ontem".
                if ts > now + timedelta(minutes=5):
                    ts -= timedelta(days=1)
                    
                data.append({"value": val, "timestamp": ts})
            except: continue
                
    if not data: return pd.DataFrame()
    
    # data está com os mais novos no topo
    df = pd.DataFrame(data)
    
    # Ordena perfeitamente pela Data e Hora consertada do mais antigo (esquerda) pro mais presente (direita)
    df = df.sort_values(by="timestamp", ascending=True).reset_index(drop=True)
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
        <meta http-equiv="refresh" content="20">
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
                        {% if data.last_100 %}
                            {% for item in data.last_100|reverse %}
                                <div style="display:inline-flex; flex-direction:column; align-items:center; min-width:40px;">
                                    <span style="font-size:10px; color:#888; line-height:1;" title="Saída Provável Calculada (Projeção Polinomial)">
                                        {% if item.projection %}{{ "%.2f"|format(item.projection) }}x{% else %}--{% endif %}
                                    </span>
                                    <span class="history-item" style="background-color: {{ item.color }}; margin-top:2px;" title="Real: {{ item.time }}">{{ "%.2f"|format(item.value) }}x</span>
                                </div>
                            {% endfor %}
                        {% endif %}
                    </div>
                </div>

                <div class="grid-3">
                    {% for k in ['spikes_5', 'spikes_10', 'spikes_50'] %}
                    <div class="card">
                        <h3>Spikes {{ k.replace('spikes_', '> ') }}</h3>
                        {% if k in data and data[k] %}
                            <div class="regime">Estado Local: {{ data[k].regime }}</div>
                            <p><strong>Confiança IA:</strong> <span class="{{ 'conf-high' if '8' in data[k].confidence or '9' in data[k].confidence else 'conf-low' }}">{{ data[k].confidence }}</span></p>
                            <p><strong>Gap Médio:</strong> {{ "%.2f"|format(data[k].mean_gap) }} min</p>
                            <p><strong>Previsão ML (Tempo):</strong> {{ "%.2f"|format(data[k].predicted_gap) }} min</p>
                            <p><strong>Previsão ML (Valor):</strong> <span style="color:#28a745;font-weight:bold;">{{ "%.2f"|format(data[k].predicted_value) }}x</span></p>
                            <p><strong>Desde Último Pico:</strong> {{ data[k].current_oc }} rodadas</p>
                            <hr style="border:0.5px solid #eee; margin:10px 0;">
                            <p><strong>Próximo Pico:</strong> <span class="next-spike" data-level="{{ k.split('_')[1] }}" data-early="{{ data[k].window.split(' -> ')[0] }}" id="next-spike-{{ k.split('_')[1] }}" style="color:#007bff;font-weight:bold;">{{ data[k].next }}</span></p>
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
                const lastData = {{ data.last_100|tojson if data.last_100 else '[]' }};
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
                } catch(e) { console.error(e); }
            }

            window.addEventListener('DOMContentLoaded', () => {
                let maxLevel = 0;
                let nextSpikes = document.querySelectorAll('.next-spike');

                nextSpikes.forEach(span => {
                   let rawTime = span.innerText.trim();
                   let earlyTime = span.getAttribute('data-early');
                   if (!rawTime || rawTime === 'N/A' || rawTime === '' || !earlyTime) return;

                   let parts = rawTime.split(':');
                   let eParts = earlyTime.split(':');
                   if (parts.length === 3 && eParts.length === 3) {
                       let now = new Date();

                       let target = new Date();
                       target.setHours(parseInt(parts[0], 10), parseInt(parts[1], 10), parseInt(parts[2], 10), 0);

                       let startWindow = new Date();
                       startWindow.setHours(parseInt(eParts[0], 10), parseInt(eParts[1], 10), parseInt(eParts[2], 10), 0);

                       // Fix target/window around midnight crossover
                       if (target < now && (now - target) > 12 * 3600 * 1000) target.setDate(target.getDate() + 1);
                       if (startWindow < now && (now - startWindow) > 12 * 3600 * 1000) startWindow.setDate(startWindow.getDate() + 1);

                       let diffToStartMs = startWindow - now;
                       let diffToTargetMs = target - now;

                       // Alerta de Previsão Antecipada: Dispara se faltam menos de 2 Minutos para a JANELA ABRIR, 
                       // ou se já estamos dentro do range entre [Abertura da Janela e O Alvo exato do meio]
                       if ((diffToStartMs > 0 && diffToStartMs < 120 * 1000) || (diffToStartMs <= 0 && diffToTargetMs > 0)) {
                           let l = parseInt(span.getAttribute('data-level')) || 0;
                           if (l > maxLevel) maxLevel = l;
                       }
                   }
                });

                let beepCount = 0;
                if (maxLevel === 50) beepCount = 20;
                else if (maxLevel === 10) beepCount = 10;
                else if (maxLevel === 5) beepCount = 5;

                let nextSpike50El = document.getElementById('next-spike-50');
                let currentSpike50 = nextSpike50El ? nextSpike50El.innerText.trim() : 'N/A';
                let lastSpike50 = localStorage.getItem('last_spike_50');

                let spikeChanged = (currentSpike50 !== 'N/A' && lastSpike50 && currentSpike50 !== lastSpike50);
                if (currentSpike50 !== 'N/A') localStorage.setItem('last_spike_50', currentSpike50);

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
    return render_template_string(html, data=latest_analysis)

# ---------------------------------------------------------------------------
# Loop Principal
# ---------------------------------------------------------------------------
def main_loop():
    log("Iniciando Serviço Principal...")
    driver = iniciar_driver()
    fazer_login(driver)
    
    try:
        while True:
            novos = capturar_ultimos(driver)
            if novos:
                # Lógica de persistência (mesclar e salvar)
                existentes = []
                if os.path.exists(OUTPUT_FILE):
                    with open(OUTPUT_FILE, "r", encoding="utf-8") as f:
                        existentes = [l.strip() for l in f if l.strip()]
                
                # Criar set para evitar duplicados
                current_keys = set(existentes)
                adicionados = 0
                # novos vem com o mais recente no começo (0). Para manter a ordem correta
                # de inserção no topo da lista "existentes", devemos inserir do mais antigo para o mais novo
                for n in reversed(novos):
                    line = f"{n[0]};{n[1]};{n[2]}"
                    if line not in current_keys:
                        existentes.insert(0, line)
                        current_keys.add(line)
                        adicionados += 1
                with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
                    for item in existentes[:MAX_REGISTROS]:
                        f.write(item + "\n")
                
                log(f"Adicionados: {adicionados}. Total: {len(existentes)}")
                
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