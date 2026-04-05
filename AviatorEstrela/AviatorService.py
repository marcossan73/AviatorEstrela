# -*- coding: utf-8 -*-
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from datetime import date, datetime, timedelta
import time
import os
import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestRegressor
import joblib
from flask import Flask, render_template_string
import threading

LOGIN_URL = "https://www.tipminer.com/br/historico/estrelabet/aviator"
URL_50 = (
    "https://www.tipminer.com/br/historico/estrelabet/aviator"
    "?t=1775174557808&limit=50&subject=filter&isLoadMore=true"
)

EMAIL = "marcossa73.ms@gmail.com"
SENHA = "Mrcs3@46"

BASE_DIR   = os.path.dirname(os.path.abspath(__file__))
OUTPUT_FILE = os.path.join(BASE_DIR, "resultados_aviator.txt")
LOG_FILE    = os.path.join(BASE_DIR, "log_execucao.txt")
PREDICTIONS_FILE = os.path.join(BASE_DIR, "predictions.txt")
MODEL_FILE_5 = os.path.join(BASE_DIR, "gap_model_5.pkl")
MODEL_FILE_50 = os.path.join(BASE_DIR, "gap_model_50.pkl")

INTERVALO_SEGUNDOS = 30
MAX_REGISTROS = 10000

# Constantes para an?lise
THRESHOLD_5 = 5.0
THRESHOLD_50 = 50.0
WINDOW_SIZE = 5
PRE_WINDOW = 4


# ---------------------------------------------------------------------------
# Log
# ---------------------------------------------------------------------------

def log(msg):
    agora = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    linha = "[" + agora + "] " + msg
    print(linha)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(linha + "\n")


# ---------------------------------------------------------------------------
# Driver
# ---------------------------------------------------------------------------

def iniciar_driver():
    options = Options()
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--disable-features=VizDisplayCompositor")
    options.add_argument("--disable-gpu")
    options.add_argument(
        "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )
    options.add_argument("--disable-extensions")
    options.add_argument("--disable-plugins")
    options.add_argument("--disable-images")
    options.add_argument("--no-first-run")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option('useAutomationExtension', False)
    driver = webdriver.Chrome(options=options)
    driver.set_page_load_timeout(120)
    driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
    return driver


def clicar_js(driver, elemento):
    driver.execute_script("arguments[0].scrollIntoView({block:'center'});", elemento)
    time.sleep(0.5)
    driver.execute_script("arguments[0].click();", elemento)


# ---------------------------------------------------------------------------
# Login
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Captura dos ultimos 50 resultados
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Leitura e escrita do arquivo
# ---------------------------------------------------------------------------

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
    # Chave de deduplicacao: valor + hora (ignora data para nao perder virada de dia)
    chaves = set((v, h) for v, h, d in existentes)
    adicionados = 0
    for registro in novos:
        chave = (registro[0], registro[1])
        if chave not in chaves:
            existentes.insert(0, registro)   # insere no inicio (mais recente)
            chaves.add(chave)
            adicionados += 1

    # Reordena por hora decrescente (os novos ja vem antes, mas garante consistencia)
    existentes.sort(key=lambda r: r[1], reverse=True)
    return existentes, adicionados


def salvar_arquivo(registros):
    registros = registros[:MAX_REGISTROS]
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        for valor, hora, data in registros:
            f.write(valor + ";" + hora + ";" + data + "\n")
    log(f"Arquivo salvo com {len(registros)} registros.")


# ---------------------------------------------------------------------------
# Fun??es de an?lise
# ---------------------------------------------------------------------------

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

    # Treinar modelo ML para prever o pr?ximo gap
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

    # Prever o pr?ximo gap usando ML ou estat?stica
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

    # Salva a previs?o
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

        # Proje??es para os pr?ximos 4 resultados
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
        ts_now = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        next_str = predicted_next.strftime("%d/%m/%Y %H:%M:%S")
        early_str = predicted_early.strftime("%d/%m/%Y %H:%M:%S")
        late_str = predicted_late.strftime("%d/%m/%Y %H:%M:%S")
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
                early = datetime.strptime(early_str, "%d/%m/%Y %H:%M:%S")
                late = datetime.strptime(late_str, "%d/%m/%Y %H:%M:%S")
                if status == "pendente":
                    # Verifica se houve pico > thresh na janela
                    spikes_in_window = df[(df["timestamp"] >= early) & (df["timestamp"] <= late) & (df["value"] > thresh)]
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
    latest_analysis['ultimo'] = f"{df['timestamp'].max()} - Valor: {df['value'].iloc[-1]:.2f}"

    # Analise para >5
    pred_5 = analyze_spikes(df, THRESHOLD_5, ">5")

    # Analise para >50
    pred_50 = analyze_spikes(df, THRESHOLD_50, ">50")

    # Tendencias
    analyze_trends(df)

    # Assinaturas
    analyze_signatures(df, THRESHOLD_5, ">5")
    analyze_signatures(df, THRESHOLD_50, ">50")

    # Verifica e atualiza previs?es
    check_predictions(df)

    # Exibe estat?sticas de previs?es separadas por threshold
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


# ---------------------------------------------------------------------------
# Loop principal do servico
# ---------------------------------------------------------------------------

def main():
    if os.path.exists(OUTPUT_FILE):
        log("=== AviatorService iniciado - continuando captura em arquivo existente ===")
    else:
        log("=== AviatorService iniciado ===")
    driver = iniciar_driver()

    # Start Flask dashboard in a thread
    threading.Thread(target=lambda: app.run(host='0.0.0.0', port=5000, debug=False, use_reloader=False)).start()

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
        # An?lise inicial se arquivo j? existe
        if os.path.exists(OUTPUT_FILE):
            run_analysis()

        ciclo = 0
        while True:
            ciclo += 1
            log("--- Ciclo " + str(ciclo) + " ---")

            # Capturar dados a cada 3 ciclos (90 segundos)
            if ciclo % 3 == 1:
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
                    # Se for timeout, reinicie o driver e fa?a login novamente
                    if "timeout" in str(e).lower():
                        log("Timeout detectado, reiniciando driver e fazendo login...")
                        driver.quit()
                        driver = iniciar_driver()
                        try:
                            fazer_login(driver)
                        except Exception as e2:
                            log("ERRO ao relogar apos timeout: " + str(e2))
                            # Se falhar, continue sem driver ou algo, mas por enquanto log
                    else:
                        # Tenta relogar se a sessao expirou
                        try:
                            fazer_login(driver)
                        except Exception as e2:
                            log("ERRO ao relogar: " + str(e2))

            # Executar an?lise a cada ciclo (60 segundos)
            run_analysis()

            log("Aguardando " + str(INTERVALO_SEGUNDOS) + " segundos...")
            time.sleep(INTERVALO_SEGUNDOS)

    except KeyboardInterrupt:
        log("Servico encerrado pelo usuario.")
    finally:
        driver.quit()


if __name__ == "__main__":
    app = Flask(__name__)
    latest_analysis = {}
    latest_predictions = {}

    @app.route('/')
    def dashboard():
        html = """
        <!DOCTYPE html>`
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

    main()
