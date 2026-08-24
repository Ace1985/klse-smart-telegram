import math
import os
from datetime import datetime
from zoneinfo import ZoneInfo
import pandas as pd
import requests
import yfinance as yf
from config import BUY_SCORE, BUY_ZONE_DISCOUNT, MAX_FAIR_PE, WATCH_SCORE

TZ = ZoneInfo('Asia/Kuala_Lumpur')
TOKEN = os.environ.get('TELEGRAM_TOKEN')
CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID')
MODE = os.environ.get('REPORT_MODE', 'close').lower()

# 金融/银行股清单（采用 PB-ROE 与 DDM 专属估值模型）
FINANCIAL_SECTOR = {'1155', '1023', '1295', '1146', '4162', '4707'}

STOCK_NAMES = {
    '1155': '马来亚银行 (MAYBANK)', 
    '1023': '联昌国际 (CIMB)', 
    '1295': '大众银行 (PBBANK)', 
    '1146': '兴业银行 (RHBBANK)',
    '4162': '丰隆银行 (HLBANK)', 
    '4707': '大马银行 (AMBANK)', 
    '5347': '国家能源 (TENAGA)', 
    '6742': '杨忠礼电力 (YTLPOWR)',
    '4677': '杨忠礼机构 (YTL)', 
    '5211': '双威集团 (SUNWAY)', 
    '5014': '金务大 (GAMUDA)', 
    '6947': '天地数码 (CelcomDigi)',
    '6888': '亚通集团 (AXIATA)', 
    '5225': 'IHH医疗 (IHH)', 
    '5183': '国油石化 (PCHEM)', 
    '0166': '益纳利美昌 (INARI)',
    '0138': 'MYEG服务 (MYEG)', 
    '0097': '伟特机构 (VITROX)', 
    '0208': '阁代科技 (GREATEC)', 
    '0273': '纳斯达克 (NATGATE)',
    '0256': 'UMC医疗 (UMC)', 
    '5341': '康大医疗 (LACMED)'
}

POSITIVE_NEWS = ['profit growth', 'profit rises', 'profit surge', 'earnings growth', 'earnings beat', 'revenue growth', 'contract win', 'new contract', 'dividend', 'upgrade', 'surge', 'growth', 'strong demand']
NEGATIVE_NEWS = ['profit drop', 'profit falls', 'profit decline', 'loss', 'downgrade', 'risk', 'lawsuit', 'weak', 'drop', 'decline', 'guidance cut', 'slowdown', 'warning']

def num(x):
    try:
        x = float(x)
        return x if math.isfinite(x) else None
    except (TypeError, ValueError):
        return None

def pct(x):
    return f'{x:.1f}%' if x is not None else 'N/A'

def money(x):
    return f'RM{x:.2f}' if x is not None else 'N/A'

def fmt(x, f='{:.2f}'):
    return f.format(x) if x is not None else 'N/A'

def safe_last(s):
    try:
        s = pd.to_numeric(s, errors='coerce').dropna()
        return num(s.iloc[-1]) if not s.empty else None
    except Exception:
        return None

def growth_from(df, names):
    if df is None or df.empty:
        return None
    for name in names:
        if name in df.index:
            try:
                v = pd.to_numeric(df.loc[name], errors='coerce').dropna().tolist()
                if len(v) >= 2 and v[-2] != 0:
                    return (v[-1] / v[-2] - 1) * 100
            except Exception:
                pass
    return None

def html(s):
    s = '' if s is None else str(s)
    return s.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')

def macro():
    out = {'klci': None, 'chg': None, 'usd': None, 'brent': None}
    try:
        c = pd.to_numeric(yf.Ticker('^KLSE').history(period='5d')['Close'], errors='coerce').dropna()
        if not c.empty:
            out['klci'] = num(c.iloc[-1])
            out['chg'] = num((c.iloc[-1] / c.iloc[-2] - 1) * 100) if len(c) >= 2 else None
    except Exception:
        pass
    try:
        c = pd.to_numeric(yf.Ticker('MYR=X').history(period='5d')['Close'], errors='coerce').dropna()
        out['usd'] = safe_last(c)
    except Exception:
        pass
    try:
        c = pd.to_numeric(yf.Ticker('BZ=F').history(period='5d')['Close'], errors='coerce').dropna()
        out['brent'] = safe_last(c)
    except Exception:
        pass
    return out

def macro_text(m):
    kc = 'N/A' if m['klci'] is None else f"{m['klci']:.2f} ({'+' if m['chg'] is not None and m['chg'] >= 0 else ''}{m['chg']:.2f}%)" if m['chg'] is not None else f"{m['klci']:.2f}"
    us = 'N/A' if m['usd'] is None else f"{m['usd']:.4f}"
    br = 'N/A' if m['brent'] is None else f"${m['brent']:.2f}"
    return f"🌐 <b>宏观与大盘行情</b>\n综指 KLCI: {kc}\n美元/令吉 USD/MYR: {us} | 布伦特原油 Brent: {br}\n"

def rsi(series, period=14):
    if series is None or len(series) < period + 1:
        return None
    d = series.diff()
    g = d.clip(lower=0)
    l = -d.clip(upper=0)
    ag = g.rolling(period).mean().iloc[-1]
    al = l.rolling(period).mean().iloc[-1]
    if al == 0:
        return 100.0 if ag > 0 else 50.0
    return num(100 - (100 / (1 + ag / al)))

def news(ticker):
    out = []
    try:
        for n in (ticker.news or [])[:3]:
            title = n.get('title') if isinstance(n, dict) else None
            if not title and isinstance(n, dict) and isinstance(n.get('content'), dict):
                title = n['content'].get('title')
            if title:
                out.append(str(title))
    except Exception:
        pass
    text = ' '.join(out).lower()
    pos = sum(w in text for w in POSITIVE_NEWS)
    neg = sum(w in text for w in NEGATIVE_NEWS)
    return out, (1 if pos > neg else -1 if neg > pos else 0)

def intraday(symbol):
    try:
        df = yf.Ticker(symbol).history(period='1d', interval='5m', auto_adjust=False)
    except Exception:
        return {}
    if df.empty or 'Close' not in df:
        return {}
    c = pd.to_numeric(df['Close'], errors='coerce').dropna()
    h = pd.to_numeric(df.get('High'), errors='coerce')
    l = pd.to_numeric(df.get('Low'), errors='coerce')
    v = pd.to_numeric(df.get('Volume'), errors='coerce')
    if c.empty:
        return {}
    cur = num(c.iloc[-1])
    first = num(c.iloc[0])
    chg = (cur / first - 1) * 100 if cur is not None and first not in (None, 0) else None
    ma5 = num(c.rolling(5).mean().iloc[-1]) if len(c) >= 5 else None
    ma20 = num(c.rolling(20).mean().iloc[-1]) if len(c) >= 20 else None
    irsi = rsi(c, 14)
    vwap = None
    try:
        tp = (h + l + c) / 3
        cv = v.fillna(0).cumsum()
        val = (tp * v.fillna(0)).cumsum()
        vwap = num(val.iloc[-1] / cv.iloc[-1]) if cv.iloc[-1] > 0 else None
    except Exception:
        pass
    vr = None
    try:
        vv = v.dropna()
        vr = num(vv.iloc[-1] / vv.tail(20).mean()) if len(vv) >= 20 and vv.tail(20).mean() else None
    except Exception:
        pass
    return {
        'current': cur, 'change': chg, 'ma5': ma5, 'ma20': ma20, 'rsi': irsi,
        'vwap': vwap,
        'vwap_diff': (cur / vwap - 1) * 100 if cur is not None and vwap not in (None, 0) else None,
        'high': safe_last(h.cummax().tail(1)) if not h.dropna().empty else None,
        'low': safe_last(l.cummin().tail(1)) if not l.dropna().empty else None,
        'volume_ratio': vr
    }

def analyze(symbol, m):
    code = symbol.replace('.KL', '')
    is_bank = code in FINANCIAL_SECTOR

    t = yf.Ticker(symbol)
    try: info = t.info or {}
    except Exception: info = {}
    try: hist = t.history(period='1y', auto_adjust=False)
    except Exception: hist = pd.DataFrame()
    try: income = t.financials
    except Exception: income = pd.DataFrame()

    price = safe_last(hist['Close']) if not hist.empty and 'Close' in hist else None
    pe = num(info.get('trailingPE'))
    fpe = num(info.get('forwardPE'))
    pb = num(info.get('priceToBook'))
    eps = num(info.get('trailingEps'))
    roe = num(info.get('returnOnEquity'))
    rg = num(info.get('revenueGrowth'))
    pg = num(info.get('earningsGrowth'))
    dy = num(info.get('dividendYield'))
    pm = num(info.get('profitMargins'))
    fcf = num(info.get('freeCashflow'))
    de = num(info.get('debtToEquity'))

    if roe is not None and abs(roe) < 1: roe *= 100
    if rg is not None and abs(rg) < 1: rg *= 100
    if pg is not None and abs(pg) < 1: pg *= 100
    if dy is not None and abs(dy) < 1: dy *= 100
    if pm is not None and abs(pm) < 1: pm *= 100

    if de is not None: de /= 100
    if rg is None: rg = growth_from(income, ['Total Revenue', 'Operating Revenue'])
    if pg is None: pg = growth_from(income, ['Net Income', 'Net Income Common Stockholders'])

    epsg = pg
    peg = pe / pg if pe is not None and pg is not None and pg > 0 else None
    news_titles, news_score = news(t)
    wh = num(info.get('fiftyTwoWeekHigh'))
    wl = num(info.get('fiftyTwoWeekLow'))

    if not hist.empty and (wh is None or wl is None):
        try:
            one = hist.tail(252)
            wh = wh if wh is not None else num(one['High'].max())
            wl = wl if wl is not None else num(one['Low'].min())
        except Exception: pass

    # --- 评分模型（区分银行股与一般非银行股） ---
    score = 0
    if is_bank:
        # 🏦 银行/金融股专属价值评分 (侧重 高股息 + ROE + PB)
        if dy is not None: score += 30 if dy >= 6.0 else 22 if dy >= 5.0 else 14 if dy >= 4.0 else 6 if dy >= 3.0 else 0
        if roe is not None: score += 25 if roe >= 12.0 else 18 if roe >= 10.0 else 10 if roe >= 8.0 else 0
        if pb is not None: score += 20 if pb <= 0.85 else 15 if pb <= 1.05 else 8 if pb <= 1.3 else 0
        if pg is not None and pg > 0: score += 15
        elif rg is not None and rg > 0: score += 8
    else:
        # 🏢 普通股价值/高股息模型
        if dy is not None: score += 25 if dy >= 5.0 else 18 if dy >= 3.5 else 10 if dy >= 2.0 else 0
        if roe is not None: score += 20 if roe >= 15 else 12 if roe >= 10 else 5 if roe >= 6 else 0
        if peg is not None: score += 15 if peg <= 0.8 else 10 if peg <= 1.2 else 4 if peg <= 1.8 else 0
        if pm is not None: score += 10 if pm >= 15 else 5 if pm >= 8 else 0
        if fcf is not None and fcf > 0: score += 10
        if rg is not None: score += 5 if rg >= 10 else 2 if rg >= 4 else 0
        if pg is not None: score += 5 if pg >= 10 else 2 if pg >= 4 else 0
        if de is not None: score += 5 if de <= 0.5 else 2 if de <= 1.0 else 0

    # 技术面安全加分
    ma20 = ma50 = ma200 = rsi14 = None
    if not hist.empty and 'Close' in hist:
        c = pd.to_numeric(hist['Close'], errors='coerce').dropna()
        ma20 = num(c.rolling(20).mean().iloc[-1]) if len(c) >= 20 else None
        ma50 = num(c.rolling(50).mean().iloc[-1]) if len(c) >= 50 else None
        ma200 = num(c.rolling(200).mean().iloc[-1]) if len(c) >= 200 else None
        rsi14 = rsi(c, 14)
        if price is not None and ma50 is not None and price > ma50: score += 2.5
        if price is not None and ma200 is not None and price > ma200: score += 2.5

    score = round(min(100, score), 1)

    # --- 估值计算（银行使用 PB-ROE 与 DDM 综合估值） ---
    fair = buy = None
    if is_bank and price is not None:
        fair_candidates = []
        # 1. 股息折现 DDM 法（以 5.5% 目标股息率为要求回报率）
        if dy is not None and dy > 0:
            dps = price * (dy / 100.0)
            ddm_fair = dps / 0.055
            fair_candidates.append(ddm_fair)
        # 2. PB-ROE 戈登模型法 (假设 CoE = 9.5%)
        if pb is not None and pb > 0 and roe is not None and roe > 0:
            bvps = price / pb
            target_pb = roe / 9.5
            pbr_fair = bvps * target_pb
            fair_candidates.append(pbr_fair)
        
        if fair_candidates:
            fair = sum(fair_candidates) / len(fair_candidates)
            buy = fair * (1 - BUY_ZONE_DISCOUNT)
    else:
        # 普通成长/价值股估值法
        if eps is not None and eps > 0 and pg is not None and pg >= 5:
            fair = eps * min(max(pg, 5), MAX_FAIR_PE)
            buy = fair * (1 - BUY_ZONE_DISCOUNT)

    mos = (fair - price) / fair * 100 if fair is not None and price is not None else None
    
    # 评级分级
    if fair is not None and price is not None:
        status = '🟢 BUY' if score >= BUY_SCORE and price <= buy else '🔴 OVERVALUED' if price > fair * 1.05 else '🟡 WATCH' if score >= WATCH_SCORE else '🔴 AVOID'
    else:
        status = '🟢 BUY' if score >= BUY_SCORE else '🟡 WATCH' if score >= WATCH_SCORE else '🔴 AVOID'

    name = info.get('shortName') or info.get('longName') or STOCK_NAMES.get(code, code)
    name = f"{STOCK_NAMES.get(code, name)} ({code})" if code in STOCK_NAMES else (f"{name} ({code})" if name != code else code)
    intra = intraday(symbol)

    # 午盘预测
    ap = 0
    if intra.get('change') is not None: ap += 2 if intra['change'] > 1 else -2 if intra['change'] < -1 else 0
    if intra.get('vwap_diff') is not None: ap += 2 if intra['vwap_diff'] > .5 else -2 if intra['vwap_diff'] < -.5 else 0
    if price is not None and ma50 is not None: ap += 1 if price > ma50 else -1
    if intra.get('rsi') is not None: ap += 1 if 45 <= intra['rsi'] <= 65 else -1 if intra['rsi'] > 75 else 1 if intra['rsi'] < 30 else 0
    if intra.get('volume_ratio') is not None and intra['volume_ratio'] >= 1.5: ap += 1 if (intra.get('change') or 0) >= 0 else -1
    if m.get('chg') is not None: ap += 1 if m['chg'] > .3 else -1 if m['chg'] < -.3 else 0

    afternoon = '🟢 偏强' if ap >= 5 else '🟢 震荡偏强' if ap >= 2 else '🔴 偏弱' if ap <= -5 else '🔴 震荡偏弱' if ap <= -2 else '🟡 震荡'

    # 隔日预测
    np = 0
    np += 2 if score >= 80 else -2 if score < 55 else 0
    np += 1 if price is not None and ma20 is not None and price > ma20 else -1 if price is not None and ma20 is not None else 0
    np += 1 if price is not None and ma50 is not None and price > ma50 else -1 if price is not None and ma50 is not None else 0
    np += 1 if price is not None and ma200 is not None and price > ma200 else -1 if price is not None and ma200 is not None else 0
    if rsi14 is not None: np += 1 if 45 <= rsi14 <= 65 else -2 if rsi14 > 75 else 1 if rsi14 < 30 else 0
    if intra.get('volume_ratio') is not None and intra['volume_ratio'] >= 1.5: np += 1 if (intra.get('change') or 0) >= 0 else -1
    np += news_score
    if m.get('chg') is not None: np += 1 if m['chg'] > .3 else -1 if m['chg'] < -.3 else 0

    nextday = '🟢 偏强' if np >= 6 else '🟢 震荡偏强' if np >= 2 else '🔴 偏弱' if np <= -5 else '🔴 震荡偏弱' if np <= -2 else '🟡 震荡'

    return dict(
        symbol=name, price=price, score=score, pe=pe, fpe=fpe, pb=pb, peg=peg, eps=eps, epsg=epsg,
        roe=roe, dy=dy, pm=pm, fcf=fcf, rg=rg, pg=pg, de=de, wh=wh, wl=wl, ma20=ma20, ma50=ma50, ma200=ma200,
        rsi14=rsi14, fair=fair, buy=buy, mos=mos, status=status, news=news_titles, news_score=news_score,
        intra=intra, afternoon=afternoon, nextday=nextday, ap=ap, np=np, is_bank=is_bank
    )

def rsi_text(x):
    if x is None: return 'N/A'
    if x < 30: return '🔵 超卖 (具备吸引力)'
    if x < 45: return '🟢 估值合理区'
    if x < 60: return '🟢 健康整理'
    if x < 70: return '🟡 多头强劲'
    return '🔴 超买 (注意回调)'

def trend_text(x):
    p, a, b, c = x['price'], x['ma20'], x['ma50'], x['ma200']
    if None not in (p, a, b, c):
        return '🟢 多头强劲排列' if p > a > b > c else '🟢 处于多头趋势' if p > b else '🟡 震荡回调中' if p > c else '🔴 空头趋势'
    return '🟢 站上50日均线' if p is not None and b is not None and p > b else '🔴 跌破50日均线' if p is not None and b is not None else 'N/A'

def build(x):
    intra = x['intra']
    vol = intra.get('volume_ratio')
    vtxt = 'N/A' if vol is None else f'{vol:.2f}倍'
    fcf_desc = "金融股不适用" if x['is_bank'] else ("正向现金流 🟢" if x['fcf'] is not None and x['fcf'] > 0 else "现金流受压/暂无数据 🔴")
    de_desc = "金融股不适用" if x['is_bank'] else fmt(x['de'])
    
    text = (
        f"\n<b>{html(x['symbol'])}</b> | 现价: {money(x['price'])} | 价值评分: <b>{x['score']}/100</b>\n\n"
        f"💰 <b>估值分析与买点</b>\n市盈率 (PE): {fmt(x['pe'])} | 预估 PE: {fmt(x['fpe'])} | 市净率 (PB): {fmt(x['pb'])}\n"
        f"合理价值 (Fair Value): {money(x['fair'])}\n建议买入区 (Buy Zone): <b>{money(x['buy'])}</b>\n"
        f"安全边际 (Margin of Safety): <b>{pct(x['mos'])}</b>\n\n"
        f"📈 <b>价值与股息基本面</b>\n股息率 (Dividend Yield): <b>{pct(x['dy'])}</b> | ROE: <b>{pct(x['roe'])}</b>\n"
        f"每股收益 (EPS): {money(x['eps'])} | EPS增长率: {pct(x['epsg'])}\n"
        f"营收增长: {pct(x['rg'])} | 净利润率: {pct(x['pm'])}\n"
        f"债务/权益比 (D/E): {de_desc} | 自由现金流 (FCF): {fcf_desc}\n\n"
        f"📍 <b>52周区间</b>\n最高价: {money(x['wh'])} | 最低价: {money(x['wl'])}\n\n"
        f"📊 <b>技术与趋势</b>\nMA20: {money(x['ma20'])} | MA50: {money(x['ma50'])} | MA200: {money(x['ma200'])}\n"
        f"RSI14: {fmt(x['rsi14'])} ({rsi_text(x['rsi14'])})\n成交量比率: {vtxt} | 趋势判断: {trend_text(x)}\n"
    )
    if MODE in ('lunch', 'close') and intra:
        text += f"\n⏱ <b>盘中分时交易监测</b>\n今日涨跌: {pct(intra.get('change'))} | VWAP均价: {money(intra.get('vwap'))} ({pct(intra.get('vwap_diff'))})\n最高: {money(intra.get('high'))} | 最低: {money(intra.get('low'))}\n"
    if x['news']:
        text += '\n📰 <b>最新相关新闻</b>\n' + '\n'.join('• ' + html(n) for n in x['news'][:2]) + f"\n新闻情绪偏向: {'🟢 积极' if x['news_score'] > 0 else '🔴 谨慎' if x['news_score'] < 0 else '🟡 中性'}\n"
    if MODE == 'lunch':
        text += f"\n🔮 <b>AI 午盘趋势预测</b>\n{x['afternoon']} | 模型可信度: {min(90, 50 + abs(x['ap']) * 7)}%\n"
    else:
        text += f"\n🔮 <b>AI 隔日走势预测</b>\n{x['nextday']} | Model confidence: {min(92, 50 + abs(x['np']) * 6)}%\n"
    text += '⚠️ 本报告为AI定量情景模型分析，不构成任何买卖建议。\n'
    return text

def split_msgs(text, limit=4000):
    if len(text) <= limit:
        return [text]
    parts = text.split('\n\n')
    out = []
    cur = ''
    for p in parts:
        if cur and len(cur) + 2 + len(p) > limit:
            out.append(cur)
            cur = p
        else:
            cur = p if not cur else cur + '\n\n' + p
    if cur:
        out.append(cur)
    return out

def send(text):
    if not TOKEN or not CHAT_ID:
        raise RuntimeError('缺失 TELEGRAM_TOKEN 或 TELEGRAM_CHAT_ID')
    for m in split_msgs(text):
        r = requests.post(
            f'https://api.telegram.org/bot{TOKEN}/sendMessage',
            data={'chat_id': CHAT_ID, 'text': m, 'parse_mode': 'HTML', 'disable_web_page_preview': True},
            timeout=20
        )
        r.raise_for_status()

def main():
    mode = MODE if MODE in ('lunch', 'close') else 'close'
    syms = []
    with open('stocks.txt', encoding='utf8') as f:
        syms = [x.strip().upper().lstrip('$') for x in f if x.strip() and not x.strip().startswith('#')]
    syms = [x if x.endswith('.KL') else x + '.KL' for x in syms]
    m = macro()
    out = []
    for s in syms:
        try:
            z = analyze(s, m)
            if z.get('price') is not None:
                out.append(z)
        except Exception as e:
            print(f'跳过股票 {s}: {e}')
    if not out:
        print('未能获取到有效股票数据。')
        return
    out.sort(key=lambda x: x['score'], reverse=True)
    title = '☀️ 马股智能研报 — 午盘深度分析' if mode == 'lunch' else '🌙 马股智能研报 — 每日收盘总评'
    if mode == 'lunch':
        bp = sum(x['ap'] >= 2 for x in out)
        bw = sum(x['ap'] <= -2 for x in out)
        forecast = '🟢 午盘多头偏强' if bp > bw else '🔴 午盘空头偏强' if bw > bp else '🟡 午盘震荡观望'
    else:
        bp = sum(x['np'] >= 2 for x in out)
        bw = sum(x['np'] <= -2 for x in out)
        forecast = '🟢 明日走势偏强 (看多)' if bp > bw else '🔴 明日走势偏弱 (看空)' if bw > bp else '🟡 明日震荡格局'
    
    lines = [
        f'<b>{title}</b>',
        f"📅 报告时间: {datetime.now(TZ):%Y年%m月%d日 %H:%M}",
        '',
        macro_text(m),
        f'🔮 <b>AI 模型大盘概览</b>\n市场整体偏向: {forecast}\n多头候选股: {bp} 只 | 空头候选股: {bw} 只\n'
    ]
    for label, status in [('🟢 建议买入区间 (高安全边际)', '🟢 BUY'), ('🟡 密切关注清单 (优质标的)', '🟡 WATCH'), ('🔴 估值偏高 (建议逢高减仓)', '🔴 OVERVALUED'), ('🔴 暂宜回避 (基本面受压)', '🔴 AVOID')]:
        g = [x for x in out if x['status'] == status]
        if g:
            lines.append(f'<b>{label}</b>')
            lines.extend(build(x) for x in g)
    lines.append('\n⚠️ <b>免责声明</b>\n本机器人数据源自公开数据，模型基于定量逻辑计算，仅供投资参考，不构成任何招揽或操作建议。')
    send('\n'.join(lines))
    print(f'{mode} 模式研报发送成功！包含 {len(out)} 只股票。')

if __name__ == '__main__':
    main()
