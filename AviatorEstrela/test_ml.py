from aviator_service2 import load_data_for_analysis, analyze_spikes, analyze_trends, latest_analysis
print("Carregando DF...")
df = load_data_for_analysis()
print("Linhas no DF:", len(df))
if not df.empty:
    analyze_spikes(df, 5.0, ">5")
    analyze_spikes(df, 10.0, ">10")
    analyze_spikes(df, 50.0, ">50")
    analyze_trends(df)

print("LATEST:", latest_analysis)
