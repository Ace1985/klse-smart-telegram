import os
import math
from datetime import datetime
from zoneinfo import ZoneInfo

import pandas as pd
import requests
import yfinance as yf

from config import BUY_SCORE, WATCH_SCORE, BUY_ZONE_DISCOUNT, MAX_FAIR_PE

TZ = ZoneInfo("Asia/Kuala_Lumpur")
TOKEN = os.environ.get("TELEGRAM_TOKEN")
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

STOCK_NAMES = {
    "1155": "MAYBANK", "1023": "CIMB", "1295": "PBBANK",
    "1146": "RHBBANK", "4162": "HLBANK", "4707": "AMBANK",
    "5347": "TENAGA", "6742": "YTLPOWR", "4677": "YTL",
    "5211": "SUNWAY", "5014": "GAMUDA", "6947": "CelcomDigi",
    "6888": "AXIATA", "5225": "IHH", "5183": "PCHEM",
    "0166": "INARI", "0138": "MYEG", "0097": "VITROX",
    "0208": "GREATEC", "0273": "NATGATE", "0256": "UMC",
    "5341": "LACMED",
}

def num(x):
    try:
        x = float(x)
        return x if math.isfinite(x) else None
    except (TypeError, ValueError):
        return None

def pct(x):
    return f"{x:.1f}%" if x is not None else "N/A"

def money(x):
    return f"RM{x:.2f}" if x is not None else "N/A"

def fmt_val(x, fmt="{:.2f}"):
    return fmt.format(x) if x is not None else "N/A"

def safe_last(series):
    try:
        s = pd.to_numeric(series, errors="coerce").dropna()
        return num(s.iloc[-1]) if not s.empty else None
    except Exception:
        return None

def growth_from(df, names):
    if df is None or df.empty:
        return None
    for name in names:
        if name in df.index:
            try:
                values = pd.to_numeric(df.loc[name], errors="coerce").dropna().tolist()
                if len(values) >= 2 and values[-2] != 0:
                    return (values[-1] / values[-2] - 1) * 100
            except Exception:
                pass
    return None

def get_macro_summary():
    try:
        klci = yf.Ticker("^KLSE").history(period="5d")
        usd_myr = yf.Ticker("MYR=X").history(period="5d")
        brent = yf.Ticker("BZ=F").history(period="5d")

        kc = pd.to_numeric(klci["Close"], errors="coerce").dropna()
        uc = pd.to_numeric(usd_myr["Close"], errors="coerce").dropna()
        bc = pd.to_numeric(brent["Close"], errors="coerce").dropna()

        kp = safe_last(kc)
        up = safe_last(uc)
        bp = safe_last(bc)
        chg = (kc.iloc[-1] / kc.iloc[-2] - 1) * 100 if len(kc) >= 2 else None

        ktxt = (f"{kp:.2f} ({'+' if chg is not None and chg >= 0 else ''}{chg:.2f}%)"
                if kp is not None and chg is not None else "N/A")
        utxt = f"{up:.4f}" if up is not None else "N/A"
        btxt = f"${bp:.2f}" if bp is not None else "N/A"

        return f"🌐 MARKET\nKLCI: {ktxt}\nUSD/MYR: {utxt} | Brent: {btxt}\n"
    except Exception as e:
        print(f"Macro data error: {e}")
        return "🌐 MARKET\nKLCI: N/A | USD/MYR: N/A | Brent: N/A\n"

def get_news_titles(ticker, limit=2):
    titles = []
    try:
        for item in (ticker.news or [])[:limit]:
            title = item.get("title") if isinstance(item, dict) else None
            if not title and isinstance(item, dict):
                content = item.get("content")
                if isinstance(content, dict):
                    title = content.get("title")
            if title:
                titles.append(str(title))
    except Exception as e:
        print(f"News error: {e}")
    return titles

def get_ai_impact_analysis(score, dy, rg, pg, news_titles):
    impact = []
    if score >= 65:
        impact.append("基本面坚挺，抗跌能力较强")
    elif score <= 35:
        impact.append("基本面受压，短期提振动力不足")
    if dy is not None and dy >= 4:
        impact.append("高股息率提供下行安全垫")
    if pg is not None and pg < 0:
        impact.append("盈利负增长为主要隐忧")

    news = " ".join(news_titles).lower()
    positive = ["profit growth", "profit rises", "profit surge", "earnings growth",
                "earnings beat", "revenue growth", "contract win", "new contract",
                "dividend", "upgrade", "surge", "growth"]
    negative = ["profit drop", "profit falls", "profit decline", "loss", "downgrade",
                "risk", "lawsuit", "weak", "drop", "decline"]

    if any(w in news for w in positive):
        impact.append("最新消息偏向正面")
    elif any(w in news for w in negative):
        impact.append("新闻面偏向谨慎与观望")
    return " | ".join(impact) if impact else "缺乏显著催化剂，跟随大盘波动"

def calculate_rsi(close, period=14):
    if close is None or len(close) < period + 1:
        return None
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.rolling(period).mean()
    avg_loss = loss.rolling(period).mean()
    if avg_loss.iloc[-1] == 0:
        return 100.0 if avg_gain.iloc[-1] > 0 else 50.0
    return num(100 - (100 / (1 + avg_gain.iloc[-1] / avg_loss.iloc[-1])))

def analyze(symbol):
    ticker = yf.Ticker(symbol)
    try: info = ticker.info or {}
    except Exception: info = {}
    try: hist = ticker.history(period="1y", auto_adjust=False)
    except Exception: hist = pd.DataFrame()
    try: income = ticker.financials
    except Exception: income = pd.DataFrame()

    price = safe_last(hist["Close"]) if not hist.empty and "Close" in hist else None
    pe = num(info.get("trailingPE"))
    forward_pe = num(info.get("forwardPE"))
    pb = num(info.get("priceToBook"))
    eps = num(info.get("trailingEps"))

    roe = num(info.get("returnOnEquity"))
    if roe is not None and abs(roe) < 1: roe *= 100
    rg = num(info.get("revenueGrowth"))
    if rg is not None and abs(rg) < 1: rg *= 100
    pg = num(info.get("earningsGrowth"))
    if pg is not None and abs(pg) < 1: pg *= 100
    dy = num(info.get("dividendYield"))
    if dy is not None and abs(dy) < 1: dy *= 100
    pm = num(info.get("profitMargins"))
    if pm is not None and abs(pm) < 1: pm *= 100
    fcf = num(info.get("freeCashflow"))
    de = num(info.get("debtToEquity"))
    if de is not None: de /= 100

    if rg is None: rg = growth_from(income, ["Total Revenue", "Operating Revenue"])
    if pg is None: pg = growth_from(income, ["Net Income", "Net Income Common Stockholders"])

    eps_growth = pg
    peg = pe / pg if pe is not None and pg is not None and pg > 0 else None
    news_titles = get_news_titles(ticker)

    week52_high = num(info.get("fiftyTwoWeekHigh"))
    week52_low = num(info.get("fiftyTwoWeekLow"))
    if (week52_high is None or week52_low is None) and not hist.empty:
        try:
            one_year = hist.tail(252)
            if week52_high is None: week52_high = num(one_year["High"].max())
            if week52_low is None: week52_low = num(one_year["Low"].min())
        except Exception:
            pass

    score = 0
    if peg is not None: score += 20 if peg <= .8 else 12 if peg <= 1.2 else 5 if peg <= 1.8 else 0
    if roe is not None: score += 15 if roe >= 15 else 8 if roe >= 10 else 3 if roe >= 5 else 0
    if dy is not None: score += 15 if dy >= 4.5 else 10 if dy >= 3 else 4 if dy >= 1.5 else 0
    if pm is not None: score += 10 if pm >= 15 else 5 if pm >= 8 else 0
    if fcf is not None and fcf > 0: score += 10
    if rg is not None: score += 10 if rg >= 15 else 5 if rg >= 5 else 0
    if pg is not None: score += 10 if pg >= 20 else 5 if pg >= 10 else 0
    if de is not None: score += 5 if de <= .5 else 2 if de <= 1 else 0

    tech = 0
    ma20 = ma50 = ma200 = rsi14 = volume_ratio = support = resistance = None

    if not hist.empty and "Close" in hist.columns:
        close = pd.to_numeric(hist["Close"], errors="coerce").dropna()
        if len(close) >= 20: ma20 = num(close.rolling(20).mean().iloc[-1])
        if len(close) >= 50: ma50 = num(close.rolling(50).mean().iloc[-1])
        if len(close) >= 200: ma200 = num(close.rolling(200).mean().iloc[-1])
        rsi14 = calculate_rsi(close, 14)

        if "Volume" in hist.columns and len(hist) >= 20:
            volume = pd.to_numeric(hist["Volume"], errors="coerce").dropna()
            if len(volume) >= 20:
                current = num(volume.iloc[-1])
                average = num(volume.rolling(20).mean().iloc[-1])
                if current is not None and average: volume_ratio = current / average

        if len(hist) >= 20:
            recent = hist.tail(20)
            try:
                support = num(recent["Low"].min())
                resistance = num(recent["High"].max())
            except Exception:
                pass

        if price is not None and ma50 is not None and price > ma50: tech += 2.5
        if price is not None and ma200 is not None and price > ma200: tech += 2.5

    score = round(min(100, score + tech), 1)

    fair_value = buy_zone = None
    if eps is not None and eps > 0 and pg is not None and pg >= 5:
        fair_pe = min(max(pg, 5), MAX_FAIR_PE)
        fair_value = eps * fair_pe
        buy_zone = fair_value * (1 - BUY_ZONE_DISCOUNT)

    discount = ((fair_value - price) / fair_value * 100
                if fair_value is not None and price is not None else None)
    margin_of_safety = discount

    if fair_value is not None and price is not None:
        if score >= BUY_SCORE and price <= buy_zone:
            status = "🟢 BUY"
        elif price > fair_value * 1.05:
            status = "🔴 OVERVALUED"
        else:
            status = "🟡 WATCH"
    else:
        status = "🟢 BUY" if score >= BUY_SCORE else "🟡 WATCH" if score >= WATCH_SCORE else "🔴 AVOID"

    code = symbol.replace(".KL", "")
    raw_name = info.get("shortName") or info.get("longName") or STOCK_NAMES.get(code, code)
    display_name = f"{raw_name} ({code})" if raw_name != code else code

    return {
        "symbol": display_name, "price": price, "score": score,
        "pe": pe, "forward_pe": forward_pe, "pb": pb, "peg": peg,
        "fair_value": fair_value, "buy_zone": buy_zone,
        "discount": discount, "margin_of_safety": margin_of_safety,
        "eps": eps, "eps_growth": eps_growth, "roe": roe, "dy": dy,
        "pm": pm, "fcf": fcf, "rg": rg, "pg": pg, "de": de,
        "week52_high": week52_high, "week52_low": week52_low,
        "ma20": ma20, "ma50": ma50, "ma200": ma200, "rsi14": rsi14,
        "volume_ratio": volume_ratio, "support": support, "resistance": resistance,
        "status": status, "news": news_titles,
        "ai_impact": get_ai_impact_analysis(score, dy, rg, pg, news_titles),
    }

def rsi_status(rsi):
    if rsi is None: return "N/A"
    if rsi < 30: return "🔵 Oversold"
    if rsi < 45: return "🟢 Attractive"
    if rsi < 60: return "🟢 Healthy"
    if rsi < 70: return "🟡 Strong"
    return "🔴 Overbought"

def trend_status(price, ma20, ma50, ma200):
    if price is not None and ma20 is not None and ma50 is not None and ma200 is not None:
        if price > ma20 > ma50 > ma200: return "🟢 Strong Bullish"
        if price > ma50: return "🟢 Bullish"
        if price > ma200: return "🟡 Pullback"
        return "🔴 Bearish"
    if price is not None and ma50 is not None:
        return "🟢 Above MA50" if price > ma50 else "🔴 Below MA50"
    return "N/A"

def volume_status(ratio):
    if ratio is None: return "N/A"
    if ratio >= 2: return "🔥 Very High"
    if ratio >= 1.5: return "🟢 High"
    if ratio >= .8: return "🟡 Normal"
    return "🔵 Low"

def build_stock_block(x):
    fcf_status = "Positive" if x["fcf"] is not None and x["fcf"] > 0 else "N/A or Negative"
    news_txt = "\n📰 NEWS\n• " + "\n• ".join(x["news"]) if x["news"] else ""

    return (
        f"\n{x['symbol']} | {money(x['price'])} | Score {x['score']}/100\n"
        "\n💰 VALUATION\n"
        f"PE {fmt_val(x['pe'])} | Forward PE {fmt_val(x['forward_pe'])} | P/B {fmt_val(x['pb'])}\n"
        f"PEG {fmt_val(x['peg'])}\n"
        f"Fair Value {money(x['fair_value'])} | Buy Zone {money(x['buy_zone'])}\n"
        f"Margin of Safety {pct(x['margin_of_safety'])}\n"
        "\n📈 FUNDAMENTAL\n"
        f"EPS {money(x['eps'])} | EPS Growth {pct(x['eps_growth'])}\n"
        f"ROE {pct(x['roe'])} | DY {pct(x['dy'])} | Margin {pct(x['pm'])}\n"
        f"Revenue G {pct(x['rg'])} | Profit G {pct(x['pg'])}\n"
        f"Debt/Equity {fmt_val(x['de'])} | FCF {fcf_status}\n"
        "\n📍 52 WEEK\n"
        f"High {money(x['week52_high'])} | Low {money(x['week52_low'])}\n"
        "\n📊 TECHNICAL\n"
        f"MA20 {money(x['ma20'])} | MA50 {money(x['ma50'])} | MA200 {money(x['ma200'])}\n"
        f"RSI14 {fmt_val(x['rsi14'])} {rsi_status(x['rsi14'])}\n"
        f"Volume {fmt_val(x['volume_ratio'], '{:.2f}')}x {volume_status(x['volume_ratio'])}\n"
        f"Trend {trend_status(x['price'], x['ma20'], x['ma50'], x['ma200'])}\n"
        f"Support {money(x['support'])} | Resistance {money(x['resistance'])}\n"
        f"{news_txt}\n"
        f"\n💡 AI IMPACT\n{x['ai_impact']}\n"
    )

def split_telegram_messages(text, max_length=4000):
    if len(text) <= max_length: return [text]
    sections = text.split("\n\n")
    messages, current = [], ""
    for section in sections:
        candidate = section if not current else current + "\n\n" + section
        if len(candidate) <= max_length:
            current = candidate
        else:
            if current: messages.append(current)
            while len(section) > max_length:
                messages.append(section[:max_length])
                section = section[max_length:]
            current = section
    if current: messages.append(current)
    return messages

def send(text):
    if not TOKEN or not CHAT_ID:
        print("Error: TELEGRAM_TOKEN or TELEGRAM_CHAT_ID environment variable is missing!")
        return
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    for message in split_telegram_messages(text):
        response = requests.post(
            url,
            data={"chat_id": CHAT_ID, "text": message},
            timeout=20,
        )
        response.raise_for_status()

def main():
    try:
        with open("stocks.txt", encoding="utf8") as f:
            syms = [
                x.strip().upper().lstrip("$")
                for x in f
                if x.strip() and not x.strip().startswith("#")
            ]
    except Exception as e:
        print(f"Unable to read stocks.txt: {e}")
        return

    syms = [x if x.endswith(".KL") else x + ".KL" for x in syms]
    out = []

    for symbol in syms:
        try:
            result = analyze(symbol)
            if result and result.get("price") is not None:
                out.append(result)
        except Exception as e:
            print(f"Skipping {symbol}: {e}")

    if not out:
        print("No valid stock data returned.")
        return

    out.sort(key=lambda x: x["score"], reverse=True)
    now = datetime.now(TZ)

    lines = [
        "📊 KLSE SMART REPORT",
        f"{now:%d %b %Y %H:%M}",
        "",
        get_macro_summary(),
    ]

    groups = [
        ("🟢 BUY ZONE", "🟢 BUY"),
        ("🟡 WATCHLIST", "🟡 WATCH"),
        ("🔴 OVERVALUED", "🔴 OVERVALUED"),
        ("🔴 AVOID", "🔴 AVOID"),
    ]

    for label, status in groups:
        stocks = [x for x in out if x["status"] == status]
        if not stocks: continue
        lines.append(f"\n{label}")
        for stock in stocks:
            lines.append(build_stock_block(stock))

    lines.append(
        "\n⚠️ SCREENING TOOL ONLY\n"
        "Not financial advice. Yahoo Finance/free-market data may be delayed, "
        "incomplete, or occasionally incorrect."
    )

    try:
        send("\n".join(lines))
        print(f"Report sent successfully! {len(out)} stocks analyzed.")
    except Exception as e:
        print(f"Error sending message: {e}")

if __name__ == "__main__":
    main()
