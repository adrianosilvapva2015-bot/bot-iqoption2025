import time
import datetime
import requests
import pandas as pd
from ta.momentum import RSIIndicator
from ta.trend import EMAIndicator, MACD
from iqoptionapi.stable_api import IQ_Option

# === CREDENCIAIS ===
IQ_USER = "energyprojeto2022@gmail.com"
IQ_PASSWORD = "LuanaYuriEloahAlice#2025"
TELEGRAM_TOKEN = "7747612591:AAH8UKsYTo3EdWoyQjw0kRsxVGZUqIvwWqU"
TELEGRAM_CHAT_ID = "1159000783"

# === CONFIGURAÇÕES ===
VALOR_INICIAL = 10
TIMEFRAME = 5 * 60  # 5 minutos
INTERVALO_ENTRE_OPERACOES = 600
PAR_LISTA = ["EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "EURJPY", "EURGBP"]
TIPO_CONTA = "PRACTICE"  # ou "REAL"

# === VARIÁVEIS DE CONTROLE ===
soros_nivel = 0
lucro_acumulado = 0
valor_atual = VALOR_INICIAL
vitorias = 0
derrotas = 0
empates = 0

# === UTILITÁRIOS ===
def log(msg):
    print(f"[{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {msg}")

def send_telegram(msg):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        data = {"chat_id": TELEGRAM_CHAT_ID, "text": msg, "parse_mode": "HTML"}
        requests.post(url, data=data)
    except Exception as e:
        log(f"Erro ao enviar Telegram: {e}")

# === ESTRATÉGIA PROFISSIONAL ===
def analisar_e_operar(Iq, par, valor_operacao):
    global vitorias, derrotas, empates, soros_nivel, lucro_acumulado, valor_atual

    try:
        candles = Iq.get_candles(par, TIMEFRAME, 100, time.time())
        if not candles:
            log(f"❌ Falha ao obter candles para {par}")
            return None

        df = pd.DataFrame(candles)
        df["close"] = df["close"].astype(float)

        # Indicadores
        rsi = RSIIndicator(close=df["close"], window=14).rsi()
        ema9 = EMAIndicator(close=df["close"], window=9).ema_indicator()
        ema21 = EMAIndicator(close=df["close"], window=21).ema_indicator()
        macd = MACD(close=df["close"]).macd_diff()

        # Sinais atuais e anteriores
        rsi_now = rsi.iloc[-1]
        ema_now = ema9.iloc[-1]
        ema_prev = ema9.iloc[-2]
        ema21_now = ema21.iloc[-1]
        ema21_prev = ema21.iloc[-2]
        macd_now = macd.iloc[-1]
        macd_prev = macd.iloc[-2]

        direcao = None
        motivo = ""

        # Estratégia para CALL
        if rsi_now < 30 and ema_prev < ema21_prev and ema_now > ema21_now and macd_now > macd_prev:
            direcao = "call"
            motivo = f"RSI {rsi_now:.1f} < 30, EMA9 cruzou ACIMA da EMA21 e MACD em alta"
        # Estratégia para PUT
        elif rsi_now > 70 and ema_prev > ema21_prev and ema_now < ema21_now and macd_now < macd_prev:
            direcao = "put"
            motivo = f"RSI {rsi_now:.1f} > 70, EMA9 cruzou ABAIXO da EMA21 e MACD em queda"

        if direcao:
            entrada_msg = (
                f"📈 <b>ENTRADA REALIZADA</b>\n"
                f"Par: <b>{par}</b>\n"
                f"Direção: <b>{direcao.upper()}</b>\n"
                f"Valor: <b>R$ {valor_operacao:.2f}</b>\n"
                f"🔍 Estratégia: {motivo}"
            )
            log(entrada_msg)
            send_telegram(entrada_msg)

            ok, id_op = Iq.buy(valor_operacao, par, direcao, 5)
            if not ok:
                erro = "❌ Erro ao enviar ordem."
                log(erro)
                send_telegram(erro)
                return None

            while True:
                status, lucro = Iq.check_win_v4(id_op)
                if status:
                    saldo_atual = Iq.get_balance()
                    if lucro > 0:
                        vitorias += 1
                        resultado = f"✅ Vitória | Lucro: R$ {lucro:.2f}"
                        soros_nivel += 1
                        lucro_acumulado += lucro
                        if soros_nivel >= 2:
                            soros_nivel = 0
                            lucro_acumulado = 0
                            valor_atual = VALOR_INICIAL
                        else:
                            valor_atual = round(VALOR_INICIAL + lucro_acumulado, 2)
                    elif lucro == 0:
                        empates += 1
                        resultado = "⚪ Empate"
                        soros_nivel = 0
                        lucro_acumulado = 0
                        valor_atual = VALOR_INICIAL
                    else:
                        derrotas += 1
                        resultado = f"❌ Derrota | Perda: R$ {-lucro:.2f}"
                        soros_nivel = 0
                        lucro_acumulado = 0
                        valor_atual = VALOR_INICIAL

                    resumo = (
                        f"📊 <b>RESULTADO DA OPERAÇÃO</b>\n"
                        f"{resultado}\n"
                        f"Par: <b>{par}</b>\n"
                        f"Direção: <b>{direcao.upper()}</b>\n"
                        f"💰 Saldo Atual: <b>R$ {saldo_atual:.2f}</b>\n"
                        f"🌀 Soros Nível: <b>{soros_nivel}</b>\n\n"
                        f"🏆 Vitórias: <b>{vitorias}</b>\n"
                        f"❌ Derrotas: <b>{derrotas}</b>\n"
                        f"⚪ Empates: <b>{empates}</b>"
                    )
                    send_telegram(resumo)
                    log(resumo)
                    return lucro
                time.sleep(1)

    except Exception as e:
        erro = f"⚠️ Erro ao analisar {par}: {e}"
        log(erro)
        send_telegram(erro)
        return None

# === LOOP PRINCIPAL (SEM HORÁRIO) ===
def main():
    global valor_atual

    log("🔄 Conectando à IQ Option...")
    Iq = IQ_Option(IQ_USER, IQ_PASSWORD)
    Iq.connect()

    if not Iq.check_connect():
        erro = "❌ Falha na conexão com a IQ Option."
        log(erro)
        send_telegram(erro)
        return

    Iq.change_balance(TIPO_CONTA)
    saldo = Iq.get_balance()
    log(f"✅ Conectado à conta {TIPO_CONTA} | Saldo: R$ {saldo:.2f}")

    send_telegram(
        f"🤖 <b>Bot Iniciado com Sucesso</b>\n"
        f"📂 Conta: <b>{TIPO_CONTA}</b>\n"
        f"💰 Saldo: <b>R$ {saldo:.2f}</b>\n"
        f"⏳ Estratégia: RSI + EMA(9/21) + MACD\n"
        f"📊 Pares: {', '.join(PAR_LISTA)}"
    )

    while True:
        for par in PAR_LISTA:
            log(f"🔍 Analisando: {par}")
            resultado = analisar_e_operar(Iq, par, valor_atual)
            if resultado is not None:
                break

        log(f"⏳ Aguardando {INTERVALO_ENTRE_OPERACOES//60} min...")
        time.sleep(INTERVALO_ENTRE_OPERACOES)

if __name__ == "__main__":
    main()
