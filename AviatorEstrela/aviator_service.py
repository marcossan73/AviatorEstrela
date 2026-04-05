from sklearn.ensemble import RandomForestRegressor
import joblib
from flask import Flask, render_template_string
import threading
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager

INTERVALO_SEGUNDOS = 30  # Intervalo de 30 segundos para captura
MAX_REGISTROS = 10000

# Constantes para análise
THRESHOLD_5  = 5.0
THRESHOLD_50 = 50.0
WINDOW_SIZE  = 5
PRE_WINDOW   = 4

def iniciar_driver():
    options = Options()
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1920,1080")
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
    driver.set_page_load_timeout(120)
    driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
    return driver

driver = iniciar_driver()

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
    # Exibe analise dos dados pre-existentes antes de qualquer nova captura
    if os.path.exists(OUTPUT_FILE):
        log("Exibindo analise dos dados pre-existentes...")
        run_analysis()

    ciclo = 0
    while True:
        # Capturar dados a cada 3 ciclos (90 segundos)
        if ciclo % 3 == 0:
            try:
                capturar_dados(driver)
            except Exception as e:
                log("ERRO ao capturar dados: " + str(e))

        # Analisar dados a cada ciclo (30 segundos)
        try:
            if df is not None and not df.empty:
                run_analysis()
        except Exception as e:
            log("ERRO na analise dos dados: " + str(e))

        # Aguardar próximo ciclo
        time.sleep(INTERVALO_SEGUNDOS)

        ciclo += 1
except Exception as e:
    log("ERRO na execucao do ciclo principal: " + str(e))

PREDICTIONS_FILE = os.path.join(BASE_DIR, "predictions.txt")
MODEL_FILE_5 = os.path.join(BASE_DIR, "gap_model_5.pkl")
MODEL_FILE_50 = os.path.join(BASE_DIR, "gap_model_50.pkl")

def analyze_spikes(df, threshold, label):
    """Analisa picos acima do threshold e calcula estimativas."""
    if df.empty:
        return None

    spikes = df[df["value"] > threshold].copy()
    if len(spikes) < 2:
        print(f"[ANALYSIS] {label}: Poucos dados para analise (menos de 2 picos)")
        return None

    # Calcular intervalos entre picos
    spikes["gap_seconds"] = spikes["timestamp"].diff().dt.total_seconds()
    gaps = spikes["gap_seconds"].dropna()

    if gaps.empty:
        return None

    mean_gap = gaps.mean()
    std_gap = gaps.std()
    if pd.isna(std_gap):
        std_gap = 0.0
    median_gap = gaps.median()

    # Treinar modelo ML para prever o próximo gap
    model_file = MODEL_FILE_5 if threshold == THRESHOLD_5 else MODEL_FILE_50
    if len(gaps) > 5:
        X = []
        y = []
        for i in range(3, len(gaps)):
            X.append(gaps.iloc[i-3:i].values)
            y.append(gaps.iloc[i])
        if X:
            model = RandomForestRegressor(n_estimators=100, random_state=42)
            model.fit(X, y)
            joblib.dump(model, model_file)

    # Prever o próximo gap usando ML ou estatística
    if os.path.exists(model_file) and len(gaps) >= 3:
        model = joblib.load(model_file)
        features = gaps.iloc[-3:].values
        predicted_gap = model.predict([features])[0]
    else:
        predicted_gap = mean_gap

    last_spike_time = spikes["timestamp"].iloc[-1]
    predicted_next = last_spike_time + timedelta(seconds=predicted_gap)
    predicted_early = last_spike_time + timedelta(seconds=max(0, predicted_gap - 0.5 * std_gap))
    predicted_late = last_spike_time + timedelta(seconds=predicted_gap + 0.5 * std_gap)

    print(f"\n[ANALYSIS] {label} - Analise de Picos:")
    print(f"  Total de picos: {len(spikes)}")
    print(f"  Intervalo medio: {mean_gap/60:.2f} min (+/-{std_gap/60:.2f} min)")
    print(f"  Mediana dos intervalos: {median_gap/60:.2f} min")
    print(f"  Proximo gap previsto (ML): {predicted_gap/60:.2f} min")
    print(f"  Ultimo pico: {last_spike_time.strftime('%d/%m/%Y %H:%M:%S')}")
    print(f"  Proximo pico estimado: {predicted_next.strftime('%d/%m/%Y %H:%M:%S')}")
    print(f"  Janela provavel: {predicted_early.strftime('%H:%M:%S')} -> {predicted_late.strftime('%H:%M:%S')}")

    # Salva a previsão
    save_prediction(threshold, predicted_next, predicted_early, predicted_late)

    # Update dashboard data
    key = 'spikes_5' if threshold == THRESHOLD_5 else 'spikes_50'
    latest_analysis[key] = {
        'total': len(spikes),
        'mean_gap': mean_gap / 60,
        'predicted_gap': predicted_gap / 60,
        'predicted_next': predicted_next.strftime('%d/%m/%Y %H:%M:%S'),
        'window': f"{predicted_early.strftime('%H:%M:%S')} -> {predicted_late.strftime('%H:%M:%S')}"
    }

    return predicted_next

def analyze_trends(df):
    """Analisa tendencias usando rolling window"""
    if len(df) < WINDOW_SIZE:
        return

    df = df.copy()
    df["rolling_mean"] = df["value"].rolling(WINDOW_SIZE).mean()
    df["rolling_slope"] = df["value"].rolling(WINDOW_SIZE).apply(
        lambda x: np.polyfit(range(len(x)), x, 1)[0] if len(x) == WINDOW_SIZE else np.nan, raw=True
    )

    if not df["rolling_slope"].isna().all():
        last_mean = df["rolling_mean"].iloc[-1]
        last_slope = df["rolling_slope"].iloc[-1]

        print("\n[ANALYSIS] Tendencia Rolling Window (ultimas 5 amostras):")
        print(f"  Media: {last_mean:.2f}")
        print(f"  Inclinacao: {last_slope:.4f}")

        # Projeções para os próximos 4 resultados
        projections = []
        for i in range(1, 5):
            pred = last_mean + i * last_slope
            projections.append(pred)
            print(f"  Projecao proxima {i}: {pred:.2f}")
            if pred > THRESHOLD_5:
                print(f"    ALERTA: Projecao {i} aponta para valor > 5!")
            if pred > THRESHOLD_50:
                print(f"    ALERTA: Projecao {i} aponta para valor > 50!")

        # Update dashboard data
        latest_analysis['trends'] = {
            'mean': last_mean,
            'slope': last_slope,
            'projections': [{'value': p, 'alert_5': p > THRESHOLD_5, 'alert_50': p > THRESHOLD_50} for p in projections]
        }

app = Flask(__name__)
latest_analysis = {}
latest_predictions = {}

@app.route('/')
def dashboard():
    html = """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Aviator Dashboard</title>
        <meta http-equiv="refresh" content="30">
        <style>
            body { font-family: Arial, sans-serif; margin: 20px; }
            h1, h2, h3 { color: #333; }
            .section { margin-bottom: 20px; border: 1px solid #ccc; padding: 10px; }
            .alert { color: red; font-weight: bold; }
        </style>
    </head>
    <body>
        <h1>Aviator Analysis Dashboard</h1>
        <div class="section">
            <h2>Latest Analysis</h2>
            <p><strong>Total registros:</strong> {{ total_registros }}</p>
            <p><strong>Periodo:</strong> {{ periodo }}</p>
            <p><strong>Ultimo registro:</strong> {{ ultimo }}</p>
        </div>
        <div class="section">
            <h3>Spikes >5</h3>
            <p><strong>Total picos:</strong> {{ spikes_5.total if spikes_5 else 'N/A' }}</p>
            <p><strong>Intervalo medio:</strong> {{ "%.2f"|format(spikes_5.mean_gap) if spikes_5 else 'N/A' }} min</p>
            <p><strong>Proximo gap previsto (ML):</strong> {{ "%.2f"|format(spikes_5.predicted_gap) if spikes_5 else 'N/A' }} min</p>
            <p><strong>Proximo pico estimado:</strong> {{ spikes_5.predicted_next if spikes_5 else 'N/A' }}</p>
            <p><strong>Janela provavel:</strong> {{ spikes_5.window if spikes_5 else 'N/A' }}</p>
        </div>
        <div class="section">
            <h3>Spikes >50</h3>
            <p><strong>Total picos:</strong> {{ spikes_50.total if spikes_50 else 'N/A' }}</p>
            <p><strong>Intervalo medio:</strong> {{ "%.2f"|format(spikes_50.mean_gap) if spikes_50 else 'N/A' }} min</p>
            <p><strong>Proximo gap previsto (ML):</strong> {{ "%.2f"|format(spikes_50.predicted_gap) if spikes_50 else 'N/A' }} min</p>
            <p><strong>Proximo pico estimado:</strong> {{ spikes_50.predicted_next if spikes_50 else 'N/A' }}</p>
            <p><strong>Janela provavel:</strong> {{ spikes_50.window if spikes_50 else 'N/A' }}</p>
        </div>
        <div class="section">
            <h3>Tendencia Rolling Window</h3>
            <p><strong>Media:</strong> {{ "%.2f"|format(trends.mean) if trends else 'N/A' }}</p>
            <p><strong>Inclinacao:</strong> {{ "%.4f"|format(trends.slope) if trends else 'N/A' }}</p>
            {% for proj in trends.projections %}
            <p><strong>Projecao proxima {{ loop.index }}:</strong> {{ "%.2f"|format(proj.value) }} {% if proj.alert_5 %} <span class="alert">ALERTA >5!</span> {% endif %} {% if proj.alert_50 %} <span class="alert">ALERTA >50!</span> {% endif %}</p>
            {% endfor %}
        </div>
        <div class="section">
            <h3>Prediction Statistics</h3>
            <p><strong>For >5:</strong> Total: {{ pred_5.total }}, Hits: {{ pred_5.hits }}, Misses: {{ pred_5.misses }}, Hit Rate: {{ "%.1f"|format(pred_5.rate) }}%, Pending: {{ pred_5.pending }}</p>
            <p><strong>For >50:</strong> Total: {{ pred_50.total }}, Hits: {{ pred_50.hits }}, Misses: {{ pred_50.misses }}, Hit Rate: {{ "%.1f"|format(pred_50.rate) }}%, Pending: {{ pred_50.pending }}</p>
        </div>
    </body>
    </html>
    """
    return render_template_string(html, **latest_analysis, **latest_predictions)

def run_analysis():
    """Executa analise dos dados capturados e atualiza dashboard."""
    if df is None or df.empty:
        print("DataFrame vazio. Abortando analise.")
        return

    print(f"\n{'='*60}")
    print(f"[ANALYSIS] Analise apos captura - {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")
    print(f"  Total de registros: {len(df)}")
    print(f"  Periodo: {df['timestamp'].min()} -> {df['timestamp'].max()}")
    print(f"  Ultimo registro: {df['timestamp'].max()} - Valor: {df['value'].iloc[-1]:.2f}")

    # Update dashboard initial data
    latest_analysis['total_registros'] = len(df)
    latest_analysis['periodo'] = f"{df['timestamp'].min()} -> {df['timestamp'].max()}"
    latest_analysis['ultimo'] = f"{df['timestamp'].max()} - Valor: {df['value'].iloc[-1]:.2f}"

def main():
    if os.path.exists(OUTPUT_FILE):
        log("=== AviatorService iniciado - continuando captura em arquivo existente ===")
    else:
        log("=== AviatorService iniciado ===")
    driver = iniciar_driver()

    # Start Flask dashboard in a thread
    threading.Thread(target=lambda: app.run(host='0.0.0.0', port=5000, debug=False, use_reloader=False)).start()

    try:
        fazer_login(driver)

        # Exibe analise dos dados pre-existentes antes de qualquer nova captura
        if os.path.exists(OUTPUT_FILE):
            log("Exibindo analise dos dados pre-existentes...")
            run_analysis()

        ciclo = 0
        while True:
            # Verifica e atualiza previsões
            check_predictions(df)

            # Exibe estatísticas de previsões separadas por threshold
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
                    total = counts["acertos"] + counts["erros"]
                    total_predictions = total + counts["pendentes"]
                    if total > 0:
                        taxa_acerto = counts["acertos"] / total * 100
                        print(f"\n[ANALYSIS] Prediction Statistics for >{int(thresh)}: Total predictions: {total_predictions}, Hits: {counts['acertos']}, Misses: {counts['erros']}, Hit Rate: {taxa_acerto:.1f}%, Pending: {counts['pendentes']}")
                    else:
                        print(f"\n[ANALYSIS] Prediction Statistics for >{int(thresh)}: Total predictions: {total_predictions}, No completed predictions, Pending: {counts['pendentes']}")

                    # Update dashboard data
                    key = 'pred_5' if thresh == 5.0 else 'pred_50'
                    latest_predictions[key] = {
                        'total': total_predictions,
                        'hits': counts['acertos'],
                        'misses': counts['erros'],
                        'rate': taxa_acerto if total > 0 else 0,
                        'pending': counts['pendentes']
                    }
            if os.path.exists(REPORT_FILE):
                with open(REPORT_FILE, "r", encoding="utf-8") as f:
                    report_data = f.read()
                    if "PICO" in report_data:
                        label = "Picos Detetados"
                        spikes = extrair_picos(report_data)
                        if spikes:
                            # Calcular intervalos entre picos
                            gaps = [(spikes[i] - spikes[i - 1]).total_seconds() for i in range(1, len(spikes))]
                            mean_gap = sum(gaps) / len(gaps) if gaps else 0
                            std_gap = (sum((x - mean_gap) ** 2 for x in gaps) / len(gaps)) ** 0.5 if gaps else 0
                            median_gap = sorted(gaps)[len(gaps) // 2] if gaps else 0
                            last_spike_time = spikes[-1]
                            next_spike_time = last_spike_time + timedelta(seconds=mean_gap)
                            predicted_next = next_spike_time
                            predicted_early  = last_spike_time + timedelta(seconds=max(0, mean_gap - 0.5 * std_gap))
                            predicted_late   = last_spike_time + timedelta(seconds=mean_gap + 0.5 * std_gap)

                            print(f"\n[ANALYSIS] {label} - Analise de Picos:")
                            print(f"  Total de picos: {len(spikes)}")
                            print(f"  Intervalo medio: {mean_gap/60:.2f} min (+/-{std_gap/60:.2f} min)")
                            print(f"  Mediana dos intervalos: {median_gap/60:.2f} min")
                            print(f"  Ultimo pico: {last_spike_time.strftime('%d/%m/%Y %H:%M:%S')}")
                            print(f"  Proximo pico estimado: {predicted_next.strftime('%d/%m/%Y %H:%M:%S')}")
                            print(f"  Janela provavel: {predicted_early.strftime('%H:%M:%S')} -> {predicted_late.strftime('%H:%M:%S')}")
except Exception as e:
    log("ERRO na execucao do ciclo principal: " + str(e))

PREDICTIONS_FILE = os.path.join(BASE_DIR, "predictions.txt")
MODEL_FILE_5 = os.path.join(BASE_DIR, "gap_model_5.pkl")
MODEL_FILE_50 = os.path.join(BASE_DIR, "gap_model_50.pkl")

def analyze_spikes(df, threshold, label):
    """Analisa picos acima do threshold e calcula estimativas."""
    if df.empty:
        return None

    spikes = df[df["value"] > threshold].copy()
    if len(spikes) < 2:
        print(f"[ANALYSIS] {label}: Poucos dados para analise (menos de 2 picos)")
        return None

    # Calcular intervalos entre picos
    spikes["gap_seconds"] = spikes["timestamp"].diff().dt.total_seconds()
    gaps = spikes["gap_seconds"].dropna()

    if gaps.empty:
        return None

    mean_gap = gaps.mean()
    std_gap = gaps.std()
    if pd.isna(std_gap):
        std_gap = 0.0
    median_gap = gaps.median()

    # Treinar modelo ML para prever o próximo gap
    model_file = MODEL_FILE_5 if threshold == THRESHOLD_5 else MODEL_FILE_50
    if len(gaps) > 5:
        X = []
        y = []
        for i in range(3, len(gaps)):
            X.append(gaps.iloc[i-3:i].values)
            y.append(gaps.iloc[i])
        if X:
            model = RandomForestRegressor(n_estimators=100, random_state=42)
            model.fit(X, y)
            joblib.dump(model, model_file)

    # Prever o próximo gap usando ML ou estatística
    if os.path.exists(model_file) and len(gaps) >= 3:
        model = joblib.load(model_file)
        features = gaps.iloc[-3:].values
        predicted_gap = model.predict([features])[0]
    else:
        predicted_gap = mean_gap

    last_spike_time = spikes["timestamp"].iloc[-1]
    predicted_next = last_spike_time + timedelta(seconds=predicted_gap)
    predicted_early = last_spike_time + timedelta(seconds=max(0, predicted_gap - 0.5 * std_gap))
    predicted_late = last_spike_time + timedelta(seconds=predicted_gap + 0.5 * std_gap)

    print(f"\n[ANALYSIS] {label} - Analise de Picos:")
    print(f"  Total de picos: {len(spikes)}")
    print(f"  Intervalo medio: {mean_gap/60:.2f} min (+/-{std_gap/60:.2f} min)")
    print(f"  Mediana dos intervalos: {median_gap/60:.2f} min")
    print(f"  Proximo gap previsto (ML): {predicted_gap/60:.2f} min")
    print(f"  Ultimo pico: {last_spike_time.strftime('%d/%m/%Y %H:%M:%S')}")
    print(f"  Proximo pico estimado: {predicted_next.strftime('%d/%m/%Y %H:%M:%S')}")
    print(f"  Janela provavel: {predicted_early.strftime('%H:%M:%S')} -> {predicted_late.strftime('%H:%M:%S')}")

    # Salva a previsão
    save_prediction(threshold, predicted_next, predicted_early, predicted_late)

    # Update dashboard data
    key = 'spikes_5' if threshold == THRESHOLD_5 else 'spikes_50'
    latest_analysis[key] = {
        'total': len(spikes),
        'mean_gap': mean_gap / 60,
        'predicted_gap': predicted_gap / 60,
        'predicted_next': predicted_next.strftime('%d/%m/%Y %H:%M:%S'),
        'window': f"{predicted_early.strftime('%H:%M:%S')} -> {predicted_late.strftime('%H:%M:%S')}"
    }

    return predicted_next

def analyze_trends(df):
    """Analisa tendencias usando rolling window"""
    if len(df) < WINDOW_SIZE:
        return

    df = df.copy()
    df["rolling_mean"] = df["value"].rolling(WINDOW_SIZE).mean()
    df["rolling_slope"] = df["value"].rolling(WINDOW_SIZE).apply(
        lambda x: np.polyfit(range(len(x)), x, 1)[0] if len(x) == WINDOW_SIZE else np.nan, raw=True
    )

    if not df["rolling_slope"].isna().all():
        last_mean = df["rolling_mean"].iloc[-1]
        last_slope = df["rolling_slope"].iloc[-1]

        print("\n[ANALYSIS] Tendencia Rolling Window (ultimas 5 amostras):")
        print(f"  Media: {last_mean:.2f}")
        print(f"  Inclinacao: {last_slope:.4f}")

        # Projeções para os próximos 4 resultados
        projections = []
        for i in range(1, 5):
            pred = last_mean + i * last_slope
            projections.append(pred)
            print(f"  Projecao proxima {i}: {pred:.2f}")
            if pred > THRESHOLD_5:
                print(f"    ALERTA: Projecao {i} aponta para valor > 5!")
            if pred > THRESHOLD_50:
                print(f"    ALERTA: Projecao {i} aponta para valor > 50!")

        # Update dashboard data
        latest_analysis['trends'] = {
            'mean': last_mean,
            'slope': last_slope,
            'projections': [{'value': p, 'alert_5': p > THRESHOLD_5, 'alert_50': p > THRESHOLD_50} for p in projections]
        }

WINDOW_SIZE  = 5
PRE_WINDOW   = 4

app = Flask(__name__)
latest_analysis = {}
latest_predictions = {}

@app.route('/')
def dashboard():
    html = """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Aviator Dashboard</title>
        <meta http-equiv="refresh" content="30">
        <style>
            body { font-family: Arial, sans-serif; margin: 20px; }
            h1, h2, h3 { color: #333; }
            .section { margin-bottom: 20px; border: 1px solid #ccc; padding: 10px; }
            .alert { color: red; font-weight: bold; }
        </style>
    </head>
    <body>
        <h1>Aviator Analysis Dashboard</h1>
        <div class="section">
            <h2>Latest Analysis</h2>
            <p><strong>Total registros:</strong> {{ total_registros }}</p>
            <p><strong>Periodo:</strong> {{ periodo }}</p>
            <p><strong>Ultimo registro:</strong> {{ ultimo }}</p>
        </div>
        <div class="section">
            <h3>Spikes >5</h3>
            <p><strong>Total picos:</strong> {{ spikes_5.total if spikes_5 else 'N/A' }}</p>
            <p><strong>Intervalo medio:</strong> {{ "%.2f"|format(spikes_5.mean_gap) if spikes_5 else 'N/A' }} min</p>
            <p><strong>Proximo gap previsto (ML):</strong> {{ "%.2f"|format(spikes_5.predicted_gap) if spikes_5 else 'N/A' }} min</p>
            <p><strong>Proximo pico estimado:</strong> {{ spikes_5.predicted_next if spikes_5 else 'N/A' }}</p>
            <p><strong>Janela provavel:</strong> {{ spikes_5.window if spikes_5 else 'N/A' }}</p>
        </div>
        <div class="section">
            <h3>Spikes >50</h3>
            <p><strong>Total picos:</strong> {{ spikes_50.total if spikes_50 else 'N/A' }}</p>
            <p><strong>Intervalo medio:</strong> {{ "%.2f"|format(spikes_50.mean_gap) if spikes_50 else 'N/A' }} min</p>
            <p><strong>Proximo gap previsto (ML):</strong> {{ "%.2f"|format(spikes_50.predicted_gap) if spikes_50 else 'N/A' }} min</p>
            <p><strong>Proximo pico estimado:</strong> {{ spikes_50.predicted_next if spikes_50 else 'N/A' }}</p>
            <p><strong>Janela provavel:</strong> {{ spikes_50.window if spikes_50 else 'N/A' }}</p>
        </div>
        <div class="section">
            <h3>Tendencia Rolling Window</h3>
            <p><strong>Media:</strong> {{ "%.2f"|format(trends.mean) if trends else 'N/A' }}</p>
            <p><strong>Inclinacao:</strong> {{ "%.4f"|format(trends.slope) if trends else 'N/A' }}</p>
            {% for proj in trends.projections %}
            <p><strong>Projecao proxima {{ loop.index }}:</strong> {{ "%.2f"|format(proj.value) }} {% if proj.alert_5 %} <span class="alert">ALERTA >5!</span> {% endif %} {% if proj.alert_50 %} <span class="alert">ALERTA >50!</span> {% endif %}</p>
            {% endfor %}
        </div>
        <div class="section">
            <h3>Prediction Statistics</h3>
            <p><strong>For >5:</strong> Total: {{ pred_5.total }}, Hits: {{ pred_5.hits }}, Misses: {{ pred_5.misses }}, Hit Rate: {{ "%.1f"|format(pred_5.rate) }}%, Pending: {{ pred_5.pending }}</p>
            <p><strong>For >50:</strong> Total: {{ pred_50.total }}, Hits: {{ pred_50.hits }}, Misses: {{ pred_50.misses }}, Hit Rate: {{ "%.1f"|format(pred_50.rate) }}%, Pending: {{ pred_50.pending }}</p>
        </div>
    </body>
    </html>
    """
    return render_template_string(html, **latest_analysis, **latest_predictions)

def run_analysis():
    """Executa analise dos dados capturados e atualiza dashboard."""
    if df is None or df.empty:
        print("DataFrame vazio. Abortando analise.")
        return

    print(f"\n{'='*60}")
    print(f"[ANALYSIS] Analise apos captura - {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")
    print(f"  Total de registros: {len(df)}")
    print(f"  Periodo: {df['timestamp'].min()} -> {df['timestamp'].max()}")
    print(f"  Ultimo registro: {df['timestamp'].max()} - Valor: {df['value'].iloc[-1]:.2f}")

    # Update dashboard initial data
    latest_analysis['total_registros'] = len(df)
    latest_analysis['periodo'] = f"{df['timestamp'].min()} -> {df['timestamp'].max()}"
    latest_analysis['ultimo'] = f"{df['timestamp'].max()} - Valor: {df['value'].iloc[-1]:.2f}"

def main():
    if os.path.exists(OUTPUT_FILE):
        log("=== AviatorService iniciado - continuando captura em arquivo existente ===")
    else:
        log("=== AviatorService iniciado ===")
    driver = iniciar_driver()

    # Start Flask dashboard in a thread
    threading.Thread(target=lambda: app.run(host='0.0.0.0', port=5000, debug=False, use_reloader=False)).start()

    try:
        fazer_login(driver)

        # Exibe analise dos dados pre-existentes antes de qualquer nova captura
        if os.path.exists(OUTPUT_FILE):
            log("Exibindo analise dos dados pre-existentes...")
            run_analysis()

        ciclo = 0
        while True:
            # Verifica e atualiza previsões
            check_predictions(df)

            # Exibe estatísticas de previsões separadas por threshold
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
                    total = counts["acertos"] + counts["erros"]
                    total_predictions = total + counts["pendentes"]
                    if total > 0:
                        taxa_acerto = counts["acertos"] / total * 100
                        print(f"\n[ANALYSIS] Prediction Statistics for >{int(thresh)}: Total predictions: {total_predictions}, Hits: {counts['acertos']}, Misses: {counts['erros']}, Hit Rate: {taxa_acerto:.1f}%, Pending: {counts['pendentes']}")
                    else:
                        print(f"\n[ANALYSIS] Prediction Statistics for >{int(thresh)}: Total predictions: {total_predictions}, No completed predictions, Pending: {counts['pendentes']}")

                    # Update dashboard data
                    key = 'pred_5' if thresh == 5.0 else 'pred_50'
                    latest_predictions[key] = {
                        'total': total_predictions,
                        'hits': counts['acertos'],
                        'misses': counts['erros'],
                        'rate': taxa_acerto if total > 0 else 0,
                        'pending': counts['pendentes']
                    }
            if os.path.exists(REPORT_FILE):
                with open(REPORT_FILE, "r", encoding="utf-8") as f:
                    report_data = f.read()
                    if "PICO" in report_data:
                        label = "Picos Detetados"
                        spikes = extrair_picos(report_data)
                        if spikes:
                            # Calcular intervalos entre picos
                            gaps = [(spikes[i] - spikes[i - 1]).total_seconds() for i in range(1, len(spikes))]
                            mean_gap = sum(gaps) / len(gaps) if gaps else 0
                            std_gap = (sum((x - mean_gap) ** 2 for x in gaps) / len(gaps)) ** 0.5 if gaps else 0
                            median_gap = sorted(gaps)[len(gaps) // 2] if gaps else 0
                            last_spike_time = spikes[-1]
                            next_spike_time = last_spike_time + timedelta(seconds=mean_gap)
                            predicted_next = next_spike_time
                            predicted_early  = last_spike_time + timedelta(seconds=max(0, mean_gap - 0.5 * std_gap))
                            predicted_late   = last_spike_time + timedelta(seconds=mean_gap + 0.5 * std_gap)

                            print(f"\n[ANALYSIS] {label} - Analise de Picos:")
                            print(f"  Total de picos: {len(spikes)}")
                            print(f"  Intervalo medio: {mean_gap/60:.2f} min (+/-{std_gap/60:.2f} min)")
                            print(f"  Mediana dos intervalos: {median_gap/60:.2f} min")
                            print(f"  Ultimo pico: {last_spike_time.strftime('%d/%m/%Y %H:%M:%S')}")
                            print(f"  Proximo pico estimado: {predicted_next.strftime('%d/%m/%Y %H:%M:%S')}")
                            print(f"  Janela provavel: {predicted_early.strftime('%H:%M:%S')} -> {predicted_late.strftime('%H:%M:%S')}")
except Exception as e:
    log("ERRO na execucao do ciclo principal: " + str(e))

PREDICTIONS_FILE = os.path.join(BASE_DIR, "predictions.txt")
MODEL_FILE_5 = os.path.join(BASE_DIR, "gap_model_5.pkl")
MODEL_FILE_50 = os.path.join(BASE_DIR, "gap_model_50.pkl")

def analyze_spikes(df, threshold, label):
    """Analisa picos acima do threshold e calcula estimativas."""
    if df.empty:
        return None

    spikes = df[df["value"] > threshold].copy()
    if len(spikes) < 2:
        print(f"[ANALYSIS] {label}: Poucos dados para analise (menos de 2 picos)")
        return None

    # Calcular intervalos entre picos
    spikes["gap_seconds"] = spikes["timestamp"].diff().dt.total_seconds()
    gaps = spikes["gap_seconds"].dropna()

    if gaps.empty:
        return None

    mean_gap = gaps.mean()
    std_gap = gaps.std()
    if pd.isna(std_gap):
        std_gap = 0.0
    median_gap = gaps.median()

    # Treinar modelo ML para prever o próximo gap
    model_file = MODEL_FILE_5 if threshold == THRESHOLD_5 else MODEL_FILE_50
    if len(gaps) > 5:
        X = []
        y = []
        for i in range(3, len(gaps)):
            X.append(gaps.iloc[i-3:i].values)
            y.append(gaps.iloc[i])
        if X:
            model = RandomForestRegressor(n_estimators=100, random_state=42)
            model.fit(X, y)
            joblib.dump(model, model_file)

    # Prever o próximo gap usando ML ou estatística
    if os.path.exists(model_file) and len(gaps) >= 3:
        model = joblib.load(model_file)
        features = gaps.iloc[-3:].values
        predicted_gap = model.predict([features])[0]
    else:
        predicted_gap = mean_gap

    last_spike_time = spikes["timestamp"].iloc[-1]
    predicted_next = last_spike_time + timedelta(seconds=predicted_gap)
    predicted_early = last_spike_time + timedelta(seconds=max(0, predicted_gap - 0.5 * std_gap))
    predicted_late = last_spike_time + timedelta(seconds=predicted_gap + 0.5 * std_gap)

    print(f"\n[ANALYSIS] {label} - Analise de Picos:")
    print(f"  Total de picos: {len(spikes)}")
    print(f"  Intervalo medio: {mean_gap/60:.2f} min (+/-{std_gap/60:.2f} min)")
    print(f"  Mediana dos intervalos: {median_gap/60:.2f} min")
    print(f"  Proximo gap previsto (ML): {predicted_gap/60:.2f} min")
    print(f"  Ultimo pico: {last_spike_time.strftime('%d/%m/%Y %H:%M:%S')}")
    print(f"  Proximo pico estimado: {predicted_next.strftime('%d/%m/%Y %H:%M:%S')}")
    print(f"  Janela provavel: {predicted_early.strftime('%H:%M:%S')} -> {predicted_late.strftime('%H:%M:%S')}")

    # Salva a previsão
    save_prediction(threshold, predicted_next, predicted_early, predicted_late)

    # Update dashboard data
    key = 'spikes_5' if threshold == THRESHOLD_5 else 'spikes_50'
    latest_analysis[key] = {
        'total': len(spikes),
        'mean_gap': mean_gap / 60,
        'predicted_gap': predicted_gap / 60,
        'predicted_next': predicted_next.strftime('%d/%m/%Y %H:%M:%S'),
        'window': f"{predicted_early.strftime('%H:%M:%S')} -> {predicted_late.strftime('%H:%M:%S')}"
    }

    return predicted_next

def analyze_trends(df):
    """Analisa tendencias usando rolling window"""
    if len(df) < WINDOW_SIZE:
        return

    df = df.copy()
    df["rolling_mean"] = df["value"].rolling(WINDOW_SIZE).mean()
    df["rolling_slope"] = df["value"].rolling(WINDOW_SIZE).apply(
        lambda x: np.polyfit(range(len(x)), x, 1)[0] if len(x) == WINDOW_SIZE else np.nan, raw=True
    )

    if not df["rolling_slope"].isna().all():
        last_mean = df["rolling_mean"].iloc[-1]
        last_slope = df["rolling_slope"].iloc[-1]

        print("\n[ANALYSIS] Tendencia Rolling Window (ultimas 5 amostras):")
        print(f"  Media: {last_mean:.2f}")
        print(f"  Inclinacao: {last_slope:.4f}")

        # Projeções para os próximos 4 resultados
        projections = []
        for i in range(1, 5):
            pred = last_mean + i * last_slope
            projections.append(pred)
            print(f"  Projecao proxima {i}: {pred:.2f}")
            if pred > THRESHOLD_5:
                print(f"    ALERTA: Projecao {i} aponta para valor > 5!")
            if pred > THRESHOLD_50:
                print(f"    ALERTA: Projecao {i} aponta para valor > 50!")

        # Update dashboard data
        latest_analysis['trends'] = {
            'mean': last_mean,
            'slope': last_slope,
            'projections': [{'value': p, 'alert_5': p > THRESHOLD_5, 'alert_50': p > THRESHOLD_50} for p in projections]
        }

if __name__ == "__main__":
    main()