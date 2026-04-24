# -*- coding: utf-8 -*-
# =============================================================================
#  ml_diagnostico.py -- Diagnostico e Treinamento Manual dos Modelos ML
#
#  USO:
#    python ml_diagnostico.py                  -> Diagnostico completo (leitura)
#    python ml_diagnostico.py --retrain        -> Forca retreino de TODOS os modelos
#    python ml_diagnostico.py --retrain >50    -> Forca retreino apenas dos modelos >50
#    python ml_diagnostico.py --clean          -> Limpa modelos expirados/orfaos
#    python ml_diagnostico.py --history        -> Mostra historico de previsoes
# =============================================================================

import os
import sys
import time
import json
import joblib
import numpy as np
import pandas as pd
from datetime import datetime, timedelta

# Importa funcoes do servico principal
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from aviator_service2 import (
    BASE_DIR, _MODEL_PERSIST_DIR, _MODEL_MAX_AGE_SECONDS,
    _MODEL_RETRAIN_INTERVALS, _model_cache, _safe_filename,
    load_data_for_analysis, analyze_spikes, analyze_trends,
    build_features, predict_optimized, latest_analysis,
    THRESHOLD_5, THRESHOLD_10, THRESHOLD_50, THRESHOLD_100
)

SEPARATOR = "=" * 70
HIST_FILE = os.path.join(BASE_DIR, "ml_history.json")


def fmt_ts(unix_ts):
    """Converte unix timestamp para string legivel."""
    return datetime.fromtimestamp(unix_ts).strftime("%d/%m/%Y %H:%M:%S")


def fmt_age(unix_ts):
    """Retorna idade em minutos desde o timestamp."""
    age_s = time.time() - unix_ts
    if age_s < 60:
        return "%.0fs" % age_s
    elif age_s < 3600:
        return "%.0f min" % (age_s / 60)
    else:
        return "%.1fh" % (age_s / 3600)


def diagnostico_modelos():
    """Diagnostico completo dos modelos em cache e em disco."""
    print(SEPARATOR)
    print("  DIAGNOSTICO DOS MODELOS ML")
    print(SEPARATOR)

    # 1. Modelos em disco (ml_models/)
    print("\n[PASTA] %s" % _MODEL_PERSIST_DIR)
    pkl_files = []
    if os.path.exists(_MODEL_PERSIST_DIR):
        pkl_files = [f for f in os.listdir(_MODEL_PERSIST_DIR) if f.endswith('.pkl')]

    if not pkl_files:
        print("   AVISO: Nenhum modelo .pkl encontrado na pasta ml_models/")
    else:
        print("   Encontrados %d modelo(s):\n" % len(pkl_files))
        header = "   %-25s %10s %10s %10s %10s %-20s" % ("Nome", "Amostras", "Features", "CV MAE", "Idade", "Status")
        print(header)
        print("   " + "-" * 90)

        for fname in sorted(pkl_files):
            fpath = os.path.join(_MODEL_PERSIST_DIR, fname)
            try:
                loaded = joblib.load(fpath)
                name = fname.replace('.pkl', '')
                n_samples = loaded.get('n_samples', '?')
                n_features = loaded.get('n_features', '?')
                cv_mae = loaded.get('cv_mae')
                cv_str = "%.2f" % cv_mae if cv_mae else "N/A"
                trained_at = loaded.get('trained_at')

                if trained_at:
                    age = time.time() - trained_at
                    age_str = fmt_age(trained_at)
                    if age >= _MODEL_MAX_AGE_SECONDS:
                        status = "EXPIRADO"
                    else:
                        status = "OK"
                else:
                    age_str = "?"
                    status = "SEM TIMESTAMP"

                if 'n_features' not in loaded:
                    status = "FORMATO ANTIGO"

                print("   %-25s %10s %10s %10s %10s %-20s" % (name, n_samples, n_features, cv_str, age_str, status))
            except Exception as e:
                print("   %-25s %10s %s" % (fname, "ERRO", str(e)[:40]))

    # 2. PKLs orfaos na raiz (de versoes anteriores)
    root_pkls = [f for f in os.listdir(BASE_DIR) if f.endswith('.pkl')]
    if root_pkls:
        print("\n   AVISO: %d arquivo(s) .pkl ORFAO(S) na raiz (versoes anteriores):" % len(root_pkls))
        for f in root_pkls:
            fpath = os.path.join(BASE_DIR, f)
            size_kb = os.path.getsize(fpath) / 1024
            mtime = datetime.fromtimestamp(os.path.getmtime(fpath)).strftime("%d/%m/%Y %H:%M")
            print("   - %s (%.0f KB, modificado em %s)" % (f, size_kb, mtime))
        print("   -> Estes arquivos NAO sao usados pelo aviator_service2.py")
        print("   -> Use --clean para remove-los")

    # 3. Configuracao de retreino
    print("\n[CONFIG] Retreino:")
    print("   Expiracao por tempo: %.0f min (%.1fh)" % (_MODEL_MAX_AGE_SECONDS / 60, _MODEL_MAX_AGE_SECONDS / 3600))
    print("   Intervalos por threshold:")
    for k, v in _MODEL_RETRAIN_INTERVALS.items():
        print("     %s: %d gaps" % (k, v))

    # 4. Cache em memoria
    print("\n[CACHE] Em memoria: %d modelo(s)" % len(_model_cache))
    for k, v in _model_cache.items():
        trained_at = v.get('trained_at', 0)
        print("   %s: %s amostras, %s features, idade=%s" % (k, v.get('n_samples', '?'), v.get('n_features', '?'), fmt_age(trained_at)))


def diagnostico_dados():
    """Diagnostico dos dados de entrada."""
    print("\n" + SEPARATOR)
    print("  DIAGNOSTICO DOS DADOS")
    print(SEPARATOR)

    df = load_data_for_analysis()
    if df.empty:
        print("   ERRO: Nenhum dado encontrado em resultados_aviator.txt")
        return df

    print("\n   Total de registros: %d" % len(df))
    print("   Periodo: %s -> %s" % (df['timestamp'].iloc[0], df['timestamp'].iloc[-1]))
    print("   Valor medio: %.2fx" % df['value'].mean())
    print("   Valor maximo: %.2fx" % df['value'].max())
    print("   P95: %.2fx" % np.percentile(df['value'], 95))
    print("   P99: %.2fx" % np.percentile(df['value'], 99))

    for threshold, label in [(5.0, ">5x"), (10.0, ">10x"), (50.0, ">50x"), (100.0, ">100x")]:
        spikes = df[df["value"] > threshold]
        print("\n   Spikes %s: %d ocorrencias (%.1f%%)" % (label, len(spikes), len(spikes) / len(df) * 100))
        if len(spikes) > 0:
            print("     Valor medio spike: %.2fx" % spikes['value'].mean())
            print("     P95 spike: %.2fx" % np.percentile(spikes['value'], 95))
            print("     Ultimo: %s (%.2fx)" % (spikes['timestamp'].iloc[-1], spikes['value'].iloc[-1]))

    return df


def diagnostico_history():
    """Mostra historico de previsoes e avalia assertividade."""
    print("\n" + SEPARATOR)
    print("  HISTORICO DE PREVISOES")
    print(SEPARATOR)

    if not os.path.exists(HIST_FILE):
        print("   ERRO: ml_history.json nao encontrado")
        return

    with open(HIST_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)

    for key in sorted(data.keys()):
        entries = data[key]
        print("\n   [%s] (%d entradas)" % (key, len(entries)))
        header = "   %12s %12s %25s %10s %10s %5s" % ("Spike", "Previsao", "Janela", "Valor", "Gap(s)", "TS?")
        print(header)
        print("   " + "-" * 80)

        hits = 0
        evaluated = 0

        for idx, h in enumerate(entries):
            spike_t = h.get('spike_time', '?')
            next_t = h.get('next', '?')
            window = h.get('window', '?')
            value = h.get('value', 0)
            gap = h.get('predicted_gap', 0)
            has_ts = 'Y' if 'spike_ts' in h else 'N'

            val_flag = " AVISO" if value > 500 else ""

            print("   %12s %12s %25s %9.2fx %9.1f %5s%s" % (spike_t, next_t, window, value, gap, has_ts, val_flag))

            # Calcula assertividade
            if idx > 0:
                prev = entries[idx]
                real = entries[idx - 1]
                try:
                    if 'spike_ts' in real and 'window_start_ts' in prev:
                        rs_t = datetime.strptime(real['spike_ts'], '%Y-%m-%d %H:%M:%S')
                        s_t = datetime.strptime(prev['window_start_ts'], '%Y-%m-%d %H:%M:%S')
                        e_t = datetime.strptime(prev['window_end_ts'], '%Y-%m-%d %H:%M:%S')
                        if s_t <= rs_t <= e_t:
                            hits += 1
                        evaluated += 1
                except:
                    pass

        if evaluated > 0:
            print("\n   -> Assertividade: %d/%d = %.0f%%" % (hits, evaluated, hits / evaluated * 100))
        else:
            print("\n   -> Assertividade: N/A (dados insuficientes)")


def limpar_modelos():
    """Remove modelos expirados, orfaos e formatos antigos."""
    print("\n" + SEPARATOR)
    print("  LIMPEZA DE MODELOS")
    print(SEPARATOR)

    removed = 0

    # 1. Limpa PKLs orfaos na raiz
    root_pkls = [f for f in os.listdir(BASE_DIR) if f.endswith('.pkl')]
    for f in root_pkls:
        fpath = os.path.join(BASE_DIR, f)
        os.remove(fpath)
        print("   Removido (orfao raiz): %s" % f)
        removed += 1

    # 2. Limpa modelos expirados/invalidos em ml_models/
    if os.path.exists(_MODEL_PERSIST_DIR):
        for fname in os.listdir(_MODEL_PERSIST_DIR):
            if not fname.endswith('.pkl'):
                continue
            fpath = os.path.join(_MODEL_PERSIST_DIR, fname)
            try:
                loaded = joblib.load(fpath)
                should_remove = False
                reason = ""

                if 'n_features' not in loaded:
                    should_remove = True
                    reason = "formato antigo (sem n_features)"
                elif 'trained_at' not in loaded:
                    should_remove = True
                    reason = "formato antigo (sem trained_at)"
                elif time.time() - loaded['trained_at'] >= _MODEL_MAX_AGE_SECONDS:
                    should_remove = True
                    reason = "expirado (%s)" % fmt_age(loaded['trained_at'])

                if should_remove:
                    os.remove(fpath)
                    print("   Removido (%s): %s" % (reason, fname))
                    removed += 1
                else:
                    print("   OK: %s" % fname)
            except Exception as e:
                os.remove(fpath)
                print("   Removido (corrompido): %s - %s" % (fname, e))
                removed += 1

    # 3. Limpa ml_history.json se contiver valores absurdos
    if os.path.exists(HIST_FILE):
        with open(HIST_FILE, "r", encoding="utf-8") as f:
            hist_data = json.load(f)

        cleaned = False
        for key in hist_data:
            original_len = len(hist_data[key])
            hist_data[key] = [
                h for h in hist_data[key]
                if h.get('value', 0) <= 500 and 'spike_ts' in h
            ]
            if len(hist_data[key]) < original_len:
                diff = original_len - len(hist_data[key])
                print("   ml_history.json [%s]: removidas %d entradas invalidas" % (key, diff))
                cleaned = True

        if cleaned:
            with open(HIST_FILE, "w", encoding="utf-8") as f:
                json.dump(hist_data, f)
            print("   ml_history.json atualizado")

    # 4. Limpa cache em memoria
    _model_cache.clear()
    print("\n   Cache em memoria limpo")
    print("\n   Total removido: %d arquivo(s)" % removed)


def forcar_retreino(filtro=None):
    """Forca retreino de todos os modelos (ou filtrado por threshold)."""
    print("\n" + SEPARATOR)
    print("  FORCANDO RETREINO DOS MODELOS")
    print(SEPARATOR)

    # Limpa cache para forcar retreino
    keys_to_clear = []
    if filtro:
        keys_to_clear = [k for k in list(_model_cache.keys()) if k.startswith(filtro)]
    else:
        keys_to_clear = list(_model_cache.keys())

    for k in keys_to_clear:
        del _model_cache[k]
        print("   Cache removido: %s" % k)

    # Remove modelos em disco
    if os.path.exists(_MODEL_PERSIST_DIR):
        for fname in os.listdir(_MODEL_PERSIST_DIR):
            if not fname.endswith('.pkl'):
                continue
            if filtro and not fname.startswith(_safe_filename(filtro)):
                continue
            fpath = os.path.join(_MODEL_PERSIST_DIR, fname)
            os.remove(fpath)
            print("   Disco removido: %s" % fname)

    # Carrega dados e treina
    print("\n   Carregando dados...")
    df = load_data_for_analysis()
    if df.empty:
        print("   ERRO: Sem dados para treinar")
        return

    print("   Registros: %d" % len(df))

    thresholds = [(THRESHOLD_5, ">5"), (THRESHOLD_10, ">10"), (THRESHOLD_50, ">50"), (THRESHOLD_100, ">100")]
    for thresh, label in thresholds:
        if filtro and not label.startswith(filtro):
            continue
        print("\n   Treinando modelos para %s..." % label)
        try:
            analyze_spikes(df, thresh, label)
            print("   OK: %s concluido" % label)
        except Exception as e:
            print("   ERRO: %s falhou: %s" % (label, e))

    # Mostra resultado
    print("\n   Modelos em cache apos retreino: %d" % len(_model_cache))
    for k, v in _model_cache.items():
        cv = v.get('cv_mae')
        cv_str = "CV MAE=%.2f" % cv if cv else "CV MAE=N/A"
        print("     %s: %s amostras, %s" % (k, v.get('n_samples', '?'), cv_str))


def main():
    args = sys.argv[1:]

    if '--retrain' in args:
        filtro = None
        idx = args.index('--retrain')
        if idx + 1 < len(args) and not args[idx + 1].startswith('--'):
            filtro = args[idx + 1]
        forcar_retreino(filtro)

    elif '--clean' in args:
        limpar_modelos()

    elif '--history' in args:
        diagnostico_history()

    else:
        # Diagnostico completo
        diagnostico_modelos()
        diagnostico_dados()
        diagnostico_history()

        print("\n" + SEPARATOR)
        print("  COMANDOS DISPONIVEIS")
        print(SEPARATOR)
        print("   python ml_diagnostico.py                  -> Este diagnostico")
        print("   python ml_diagnostico.py --retrain        -> Forca retreino de TODOS")
        print("   python ml_diagnostico.py --retrain >50    -> Forca retreino apenas >50")
        print("   python ml_diagnostico.py --clean          -> Limpa modelos expirados/orfaos")
        print("   python ml_diagnostico.py --history        -> Mostra historico de previsoes")
        print(SEPARATOR)


if __name__ == "__main__":
    main()
