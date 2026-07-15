import os
import csv
import time
from datetime import date
try:
    import pandas as pd  # type: ignore[reportMissingModuleSource]
except ImportError as erro:
    raise ImportError(
        "A biblioteca pandas é necessária para executar este scanner. "
        "Instale com 'pip install pandas' e tente novamente."
    ) from erro

try:
    import yfinance as yf  # type: ignore[reportMissingModuleSource]
except ImportError as erro:
    raise ImportError(
        "A biblioteca yfinance é necessária para executar este scanner. "
        "Instale com 'pip install yfinance' e tente novamente."
    ) from erro

# ---------------------------------------------------------------------------
# CONFIGURAÇÕES
# ---------------------------------------------------------------------------
# Lista de ações da B3 (Adicionado o sufixo .SA exigido pelo Yahoo Finance)
TICKERS = [
    "PETR4.SA", "VALE3.SA", "ITUB4.SA", "BBDC4.SA", "BBAS3.SA", "ABEV3.SA", 
    "WEGE3.SA", "RENT3.SA", "SUZB3.SA", "GGBR4.SA", "CSNA3.SA", "USIM5.SA", 
    "EQTL3.SA", "AXIA3.SA", "CPFE3.SA", "TAEE11.SA", "RADL3.SA", "LREN3.SA", 
    "MGLU3.SA", "VIVT3.SA", "TOTS3.SA", "PRIO3.SA", "HAPV3.SA", "RDOR3.SA", 
    "BPAC11.SA", "B3SA3.SA", "CMIG4.SA", "SBSP3.SA", "ENGI11.SA", "KLBN11.SA", 
    "JBSS3.SA", "MRFG3.SA", "CCRO3.SA", "EMBJ3.SA", "GOAU4.SA", 
    "BEEF3.SA", "CYRE3.SA", "MRVE3.SA", "ASAI3.SA"
]

EMA_RAPIDA = 80
EMA_LENTA = 180
RISCO_RETORNO = 2.0
ARQUIVO_SAIDA = "resultados/oportunidades.csv"

# ---------------------------------------------------------------------------
# PROCESSAMENTO DOS DADOS
# ---------------------------------------------------------------------------

def calcular_medias(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    # Utiliza a média móvel exponencial (EMA)
    df["ema_rapida"] = df["fechamento"].ewm(span=EMA_RAPIDA, adjust=False).mean()
    df["ema_lenta"] = df["fechamento"].ewm(span=EMA_LENTA, adjust=False).mean()
    return df

def checar_setup_123(df: pd.DataFrame) -> dict | None:
    minimo_de_velas = EMA_LENTA + 5
    if len(df) < minimo_de_velas:
        return None

    # Seleciona os últimos 4 candles: candle1 (anteantepenúltimo), candle2 (antepenúltimo), candle3 (penúltimo), hoje (último)
    candle1, candle2, candle3, hoje = df.iloc[-4], df.iloc[-3], df.iloc[-2], df.iloc[-1]

    # Regra 1: O candle do meio (candle2) precisa ter a menor mínima dos três
    padrao_123 = (candle2["minima"] < candle1["minima"]) and (candle2["minima"] < candle3["minima"])
    if not padrao_123:
        return None

    # Regra 2: Filtro de tendência (fechamento de hoje acima das médias)
    tendencia_de_alta = (
        hoje["fechamento"] > hoje["ema_rapida"]
        and hoje["fechamento"] > hoje["ema_lenta"]
    )
    if not tendencia_de_alta:
        return None

    # Regra 3: Gatilho de entrada (rompimento da máxima do candle3)
    rompeu_hoje = hoje["maxima"] > candle3["maxima"]
    if not rompeu_hoje:
        return None

    entrada = candle3["maxima"]
    stop = candle2["minima"]
    risco = entrada - stop
    if risco <= 0:
        return None
    alvo = entrada + (risco * RISCO_RETORNO)

    return {
        "data": hoje.name.strftime("%Y-%m-%d"),
        "preco_atual": round(hoje["fechamento"], 2),
        "entrada": round(entrada, 2),
        "stop": round(stop, 2),
        "alvo": round(alvo, 2),
        "risco_rs": round(risco, 2),
        "retorno_potencial_rs": round(alvo - entrada, 2),
    }

# ---------------------------------------------------------------------------
# EXECUÇÃO PRINCIPAL
# ---------------------------------------------------------------------------

def rodar_scanner():
    oportunidades = []
    print("Iniciando varredura via Yahoo Finance...")

    for ticker in TICKERS:
        try:
            # Baixa diretamente 1 ano de histórico (resolve o problema da EMA80 e elimina arquivos locais)
            ticker_yf = yf.Ticker(ticker)
            df = ticker_yf.history(period="1y", interval="1d")
            
            if df.empty or len(df) < (EMA_LENTA + 5):
                print(f"[{ticker}] dados insuficientes ou ativo inválido.")
                continue

            # Ajusta os nomes das colunas vindas do yfinance
            df = df.rename(columns={
                "Open": "abertura", "High": "maxima", "Low": "minima",
                "Close": "fechamento", "Volume": "volume"
            })

            df = calcular_medias(df)
            sinal = checar_setup_123(df)
            
            if sinal:
                sinal["ticker"] = ticker.replace(".SA", "") # Limpa o nome para o relatório
                oportunidades.append(sinal)
                print(f"🟢 [{ticker}] SINAL ENCONTRADO! Entrada: {sinal['entrada']} | Stop: {sinal['stop']} | Alvo: {sinal['alvo']}")
            else:
                print(f"🔴 [{ticker}] sem sinal técnico hoje.")
                
        except Exception as erro:
            print(f"❌ [{ticker}] erro ao processar: {erro}")
        
        time.sleep(0.5) # Pausa amigável para evitar bloqueios de IP

    salvar_resultados(oportunidades)
    print(f"\nVarredura concluída. {len(oportunidades)} oportunidade(s) salva(s).")

def salvar_resultados(oportunidades: list[dict]):
    os.makedirs(os.path.dirname(ARQUIVO_SAIDA), exist_ok=True)
    colunas = ["data", "ticker", "preco_atual", "entrada", "stop", "alvo", "risco_rs", "retorno_potencial_rs"]

    with open(ARQUIVO_SAIDA, "w", newline="", encoding="utf-8") as arquivo:
        escritor = csv.DictWriter(arquivo, fieldnames=colunas)
        escritor.writeheader()
        for op in oportunidades:
            escritor.writerow({c: op.get(c, "") for c in colunas})

if __name__ == "__main__":
    rodar_scanner()
