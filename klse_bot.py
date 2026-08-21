import os, math
from datetime import datetime
from zoneinfo import ZoneInfo
import pandas as pd
import requests
import yfinance as yf
from config import BUY_SCORE, WATCH_SCORE, BUY_ZONE_DISCOUNT, MAX_FAIR_PE

TZ = ZoneInfo('Asia/Kuala_Lumpur')
TOKEN = os.environ.get('TELEGRAM_TOKEN')
CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID')

STOCK_NAMES = {
    # 金融板块
    '1155': 'MAYBANK',
    '1023': 'CIMB',
    '1295': 'PBBANK',
    '1146': 'RHBBANK',
    '4162': 'HLBANK',
    '4707': 'AMBANK',
    # 核心蓝筹与基建
    '5347': 'TENAGA',
    '6742': 'YTLPOWR',
    '4677': 'YTL',
    '5211': 'SUNWAY',
    '5014': 'GAMUDA',
    '6947': 'CelcomDigi',
    '6888': 'AXIATA',
    '5225': 'IHH',
    '5183': 'PCHEM',
    # 热门与科技股
    '0166': 'INARI',
    '0138': 'MYEG',
    '0097': 'VITROX',
    '0208': 'GREATEC',
    '0273': 'NATGATE',
    '0256': 'UMC',
    '5341': 'LACMED'
}

def num(x):
    try:
        x = float(x)
        return x if math.isfinite(x) else None
    except: return None

def pct(x): return f'{x:.1f}%' if x is not None else 'N/A'
def money(x): return f'RM{x:.2f}' if x is not None else 'N/A'
def fmt_val(x, fmt='{:.2f}'): return fmt.format(x) if x is not None else 'N/A'

def get_macro_summary():
    try:
        klci = yf.Ticker('^KLSE').history(period='2d')
        usd_myr = yf.Ticker('MYR=X').history(period='2d')
        brent = yf.Ticker('BZ=F').history(period='2d')
        
        klci_p = klci['Close'].iloc[-1] if not klci.empty else None
        klci_chg = ((klci['Close'].iloc[-1] - klci['Close'].iloc[-2]) / klci['Close'].iloc[-2] * 100) if len(klci) >= 2 else 0
        
        myr_p = usd_myr['Close'].iloc[-1] if not usd_myr.empty else None
        brent_p = brent['Close'].iloc[-1] if not brent.empty else None

        return (
            f"🌐 **MACRO & MARKET**\n"
            f"KLCI: {klci_p:.2f} ({'+' if klci_chg>=0 else ''}{klci_chg:.2f}%)\n"
            f"USD/MYR: {myr_p:.4f} | Brent Crude: ${brent_p:.2f}\n"
        )
    except Exception as e:
        return f"🌐 **MACRO & MARKET**: Data unavailable ({e})\n"

def growth_from(df, names):
    if df is None or df.empty: return None
    for n in names:
        if n in df.index:
            v = pd.to_numeric(df.loc[n], errors='coerce').dropna().tolist()
            if len(v) >= 2 and v[-2] != 0: return (v[-1] / v[-2] - 1) * 100
    return None

def get_ai_impact_analysis(score, dy, rg, pg, news_titles):
    impact = []
    if score >= 65:
        impact.append("基本面坚挺，抗跌能力较强")
    elif score <= 35:
        impact.append("基本面受压，短期提振动力不足")
        
    if dy and dy >= 4.0:
        impact.append("高股息率提供下行安全垫")
    if pg and pg < 0:
        impact.append("盈利负增长为主要隐忧")
        
    news_str = " ".join(news_titles).lower()
    if "profit" in news_str or "growth" in news_str or "surge" in news_str:
        impact.append("最新消息利好业绩预期")
    elif "drop" in news_str or "risk" in news_str or "loss" in news_str:
        impact.append("新闻面偏向谨慎与观望")

    return " | ".join(impact) if impact else "缺乏显著催化剂，跟随大盘波动"

def analyze(symbol):
    t = yf.Ticker(symbol)
    try: info = t.info or {}
    except: info = {}
    try: hist = t.history(period='1y', auto_adjust=False)
    except: hist = pd.DataFrame()
    try: income = t.financials
    except: income = pd.DataFrame()

    price = num(hist['Close'].dropna().iloc[-1]) if not hist.empty else None
    pe = num(info.get('trailingPE')); eps = num(info.get('trailingEps'))
    roe = num(info.get('returnOnEquity')); roe = roe * 100 if roe is not None and abs(roe) < 1 else roe
    rg = num(info.get('revenueGrowth')); rg = rg * 100 if rg is not None and abs(rg) < 1 else rg
    pg = num(info.get('earningsGrowth')); pg = pg * 100 if pg is not None and abs(pg) < 1 else pg
    
    dy = num(info.get('dividendYield')); dy = dy * 100 if dy is not None and abs(dy) < 1 else dy
    pm = num(info.get('profitMargins')); pm = pm * 100 if pm is not None and abs(pm) < 1 else pm
    fcf = num(info.get('freeCashflow'))
    
    if rg is None: rg = growth_from(income, ['Total Revenue', 'Operating Revenue'])
    if pg is None: pg = growth_from(income, ['Net Income', 'Net Income Common Stockholders'])
    de = num(info.get('debtToEquity')); de = de / 100 if de is not None else None
    peg = pe / pg if pe is not None and pg is not None and pg > 0 else None
    
    news_titles = []
    try:
        raw_news = t.news or []
        for n in raw_news[:2]:
            title = n.get('title') or n.get('content', {}).get('title')
            if title: news_titles.append(title)
    except: pass

    score = 0
    if peg is not None: score += 20 if peg <= .8 else 12 if peg <= 1.2 else 5 if peg <= 1.8 else 0
    if roe is not None: score += 15 if roe >= 15 else 8 if roe >= 10 else 3 if roe >= 5 else 0
    if dy is not None: score += 15 if dy >= 4.5 else 10 if dy >= 3.0 else 4 if dy >= 1.5 else 0
    if pm is not None: score += 10 if pm >= 15 else 5 if pm >= 8 else 0
    if fcf is not None and fcf > 0: score += 10
    if rg is not None: score += 10 if rg >= 15 else 5 if rg >= 5 else 0
    if pg is not None: score += 10 if pg >= 20 else 5 if pg >= 10 else 0
    if de is not None: score += 5 if de <= .5 else 2 if de <= 1 else 0
    
    tech = 0
    if not hist.empty:
        c = hist['Close'].dropna()
        ma50 = c.rolling(50).mean().iloc[-1] if len(c) >= 50 else None
        ma200 = c.rolling(200).mean().iloc[-1] if len(c) >= 200 else None
        if price and ma50 and price > ma50: tech += 2.5
        if price and ma200 and price > ma200: tech += 2.5
    
    score = round(min(100, score + tech), 1)

    fair_value = buy_zone = None
    if eps and eps > 0 and pg is not None and pg >= 5:
        fair_pe = min(max(pg, 5), MAX_FAIR_PE)
        fair_value = eps * fair_pe
        buy_zone = fair_value * (1 - BUY_ZONE_DISCOUNT)
    
    discount = (fair_value - price) / fair_value * 100 if fair_value and price else None
    
    if fair_value and price:
        status = '🟢 BUY' if score >= BUY_SCORE and price <= buy_zone else '🔴 OVERVALUED' if price > fair_value * 1.05 else '🟡 WATCH'
    else:
        status = '🟢 BUY' if score >= BUY_SCORE else '🟡 WATCH' if score >= WATCH_SCORE else '🔴 AVOID'

    code = symbol.replace('.KL', '')
    raw_name = info.get('shortName') or info.get('longName') or STOCK_NAMES.get(code, code)
    display_name = f"{raw_name} ({code})" if raw_name != code else code

    ai_impact = get_ai_impact_analysis(score, dy, rg, pg, news_titles)

    return dict(
        symbol=display_name,
        price=price,
        score=score,
        fair_value=fair_value,
        buy_zone=buy_zone,
        discount=discount,
        peg=peg,
        roe=roe,
        dy=dy,
        pm=pm,
        fcf=fcf,
        rg=rg,
        pg=pg,
        status=status,
        news=news_titles,
        ai_impact=ai_impact
    )

def send(text):
    if not TOKEN or not CHAT_ID:
        print("Error: TELEGRAM_TOKEN or TELEGRAM_CHAT_ID environment variable is missing!")
        return
    r = requests.post(f'https://api.telegram.org/bot{TOKEN}/sendMessage', data={'chat_id': CHAT_ID, 'text': text}, timeout=20)
    r.raise_for_status()

def main():
    syms = [x.strip().upper().lstrip('$') for x in open('stocks.txt', encoding='utf8') if x.strip() and not x.startswith('#')]
    syms = [x if x.endswith('.KL') else x + '.KL' for x in syms]
    out = []
    for s in syms:
        try:
            res = analyze(s)
            if res and res.get('price') is not None:
                out.append(res)
        except Exception as e:
            print(f"Skipping {s}: {e}")
    
    if not out:
        print("No valid stock data returned.")
        return

    out.sort(key=lambda x: x['score'], reverse=True)
    
    lines = [f"📊 KLSE SMART REPORT\n{datetime.now(TZ):%d %b %Y %H:%M}\n"]
    lines.append(get_macro_summary())

    for label, st in [('🟢 BUY ZONE', '🟢 BUY'), ('🟡 WATCHLIST', '🟡 WATCH'), ('🔴 OVERVALUED / AVOID', '🔴 OVERVALUED'), ('🔴 AVOID', '🔴 AVOID')]:
        g = [x for x in out if x['status'] == st]
        if not g: continue
        lines.append('\n' + label)
        for x in g:
            fcf_status = "Positive" if x['fcf'] and x['fcf'] > 0 else "N/A or Negative"
            news_txt = f"\n📰 新闻: {x['news'][0]}" if x['news'] else ""
            
            lines.append(
                f"\n{x['symbol']} | {money(x['price'])} | Score {x['score']}/100\n"
                f"Fair Value {money(x['fair_value'])} | Buy Zone {money(x['buy_zone'])}\n"
                f"DY {pct(x['dy'])} | Margin {pct(x['pm'])} | FCF {fcf_status}\n"
                f"Discount {pct(x['discount'])} | PEG {fmt_val(x['peg'])} | ROE {pct(x['roe'])}\n"
                f"Revenue G {pct(x['rg'])} | Profit G {pct(x['pg'])}{news_txt}\n"
                f"💡 AI 影响评估: {x['ai_impact']}"
            )
    
    lines.append('\n⚠️ Screening tool only, not financial advice. Free-market data may be delayed/incomplete.')
    
    try:
        send('\n'.join(lines))
        print("Report sent successfully!")
    except Exception as e:
        print(f"Error sending message: {e}")

if __name__ == '__main__':
    main()
