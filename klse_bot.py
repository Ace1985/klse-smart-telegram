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
MODE = os.environ.get('REPORT_MODE', 'close').lower()

STOCK_NAMES = {
    '1155':'MAYBANK','1023':'CIMB','1295':'PBBANK','1146':'RHBBANK','4162':'HLBANK','4707':'AMBANK',
    '5347':'TENAGA','6742':'YTLPOWR','4677':'YTL','5211':'SUNWAY','5014':'GAMUDA','6947':'CelcomDigi',
    '6888':'AXIATA','5225':'IHH','5183':'PCHEM','0166':'INARI','0138':'MYEG','0097':'VITROX',
    '0208':'GREATEC','0273':'NATGATE','0256':'UMC','5341':'LACMED'
}

POSITIVE_NEWS = ['profit growth','profit rises','profit surge','earnings growth','earnings beat','revenue growth','contract win','new contract','dividend','upgrade','surge','growth','strong demand']
NEGATIVE_NEWS = ['profit drop','profit falls','profit decline','loss','downgrade','risk','lawsuit','weak','drop','decline','guidance cut','slowdown','warning']

def num(x):
    try:
        x=float(x); return x if math.isfinite(x) else None
    except (TypeError,ValueError): return None

def pct(x): return f'{x:.1f}%' if x is not None else 'N/A'
def money(x): return f'RM{x:.2f}' if x is not None else 'N/A'
def fmt(x, f='{:.2f}'): return f.format(x) if x is not None else 'N/A'
def safe_last(s):
    try:
        s=pd.to_numeric(s,errors='coerce').dropna(); return num(s.iloc[-1]) if not s.empty else None
    except Exception: return None

def growth_from(df,names):
    if df is None or df.empty: return None
    for name in names:
        if name in df.index:
            try:
                v=pd.to_numeric(df.loc[name],errors='coerce').dropna().tolist()
                if len(v)>=2 and v[-2]!=0: return (v[-1]/v[-2]-1)*100
            except Exception: pass
    return None

def html(s):
    s='' if s is None else str(s)
    return s.replace('&','&amp;').replace('<','&lt;').replace('>','&gt;')

def macro():
    out={'klci':None,'chg':None,'usd':None,'brent':None}
    try:
        c=pd.to_numeric(yf.Ticker('^KLSE').history(period='5d')['Close'],errors='coerce').dropna()
        if not c.empty:
            out['klci']=num(c.iloc[-1]); out['chg']=num((c.iloc[-1]/c.iloc[-2]-1)*100) if len(c)>=2 else None
    except Exception: pass
    try:
        c=pd.to_numeric(yf.Ticker('MYR=X').history(period='5d')['Close'],errors='coerce').dropna()
        out['usd']=safe_last(c)
    except Exception: pass
    try:
        c=pd.to_numeric(yf.Ticker('BZ=F').history(period='5d')['Close'],errors='coerce').dropna()
        out['brent']=safe_last(c)
    except Exception: pass
    return out

def macro_text(m):
    kc='N/A' if m['klci'] is None else f"{m['klci']:.2f} ({'+' if m['chg'] is not None and m['chg']>=0 else ''}{m['chg']:.2f}%)" if m['chg'] is not None else f"{m['klci']:.2f}"
    us='N/A' if m['usd'] is None else f"{m['usd']:.4f}"
    br='N/A' if m['brent'] is None else f"${m['brent']:.2f}"
    return f"🌐 <b>MARKET</b>\nKLCI: {kc}\nUSD/MYR: {us} | Brent: {br}\n"

def rsi(series,period=14):
    if series is None or len(series)<period+1: return None
    d=series.diff(); g=d.clip(lower=0); l=-d.clip(upper=0)
    ag=g.rolling(period).mean().iloc[-1]; al=l.rolling(period).mean().iloc[-1]
    if al==0: return 100.0 if ag>0 else 50.0
    return num(100-(100/(1+ag/al)))

def news(ticker):
    out=[]
    try:
        for n in (ticker.news or [])[:3]:
            title=n.get('title') if isinstance(n,dict) else None
            if not title and isinstance(n,dict) and isinstance(n.get('content'),dict): title=n['content'].get('title')
            if title: out.append(str(title))
    except Exception: pass
    text=' '.join(out).lower(); pos=sum(w in text for w in POSITIVE_NEWS); neg=sum(w in text for w in NEGATIVE_NEWS)
    return out, (1 if pos>neg else -1 if neg>pos else 0)

def intraday(symbol):
    try: df=yf.Ticker(symbol).history(period='1d',interval='5m',auto_adjust=False)
    except Exception: return {}
    if df.empty or 'Close' not in df: return {}
    c=pd.to_numeric(df['Close'],errors='coerce').dropna(); h=pd.to_numeric(df.get('High'),errors='coerce'); l=pd.to_numeric(df.get('Low'),errors='coerce'); v=pd.to_numeric(df.get('Volume'),errors='coerce')
    if c.empty: return {}
    cur=num(c.iloc[-1]); first=num(c.iloc[0]); chg=(cur/first-1)*100 if cur is not None and first not in (None,0) else None
    ma5=num(c.rolling(5).mean().iloc[-1]) if len(c)>=5 else None; ma20=num(c.rolling(20).mean().iloc[-1]) if len(c)>=20 else None
    irsi=rsi(c,14)
    vwap=None
    try:
        tp=(h+l+c)/3; cv=v.fillna(0).cumsum(); val=(tp*v.fillna(0)).cumsum(); vwap=num(val.iloc[-1]/cv.iloc[-1]) if cv.iloc[-1]>0 else None
    except Exception: pass
    vr=None
    try:
        vv=v.dropna(); vr=num(vv.iloc[-1]/vv.tail(20).mean()) if len(vv)>=20 and vv.tail(20).mean() else None
    except Exception: pass
    return {'current':cur,'change':chg,'ma5':ma5,'ma20':ma20,'rsi':irsi,'vwap':vwap,'vwap_diff':(cur/vwap-1)*100 if cur is not None and vwap not in (None,0) else None,'high':safe_last(h.cummax().tail(1)) if not h.dropna().empty else None,'low':safe_last(l.cummin().tail(1)) if not l.dropna().empty else None,'volume_ratio':vr}

def analyze(symbol, m):
    t=yf.Ticker(symbol)
    try: info=t.info or {}
    except Exception: info={}
    try: hist=t.history(period='1y',auto_adjust=False)
    except Exception: hist=pd.DataFrame()
    try: income=t.financials
    except Exception: income=pd.DataFrame()
    price=safe_last(hist['Close']) if not hist.empty and 'Close' in hist else None
    pe=num(info.get('trailingPE')); fpe=num(info.get('forwardPE')); pb=num(info.get('priceToBook')); eps=num(info.get('trailingEps'))
    roe=num(info.get('returnOnEquity')); rg=num(info.get('revenueGrowth')); pg=num(info.get('earningsGrowth')); dy=num(info.get('dividendYield')); pm=num(info.get('profitMargins')); fcf=num(info.get('freeCashflow')); de=num(info.get('debtToEquity'))
    for key in ['roe','rg','pg','dy','pm']:
        val=locals()[key]
        if val is not None and abs(val)<1: locals()[key]=val*100
    if de is not None: de/=100
    if rg is None: rg=growth_from(income,['Total Revenue','Operating Revenue'])
    if pg is None: pg=growth_from(income,['Net Income','Net Income Common Stockholders'])
    epsg=pg; peg=pe/pg if pe is not None and pg is not None and pg>0 else None
    news_titles,news_score=news(t)
    wh=num(info.get('fiftyTwoWeekHigh')); wl=num(info.get('fiftyTwoWeekLow'))
    if not hist.empty and (wh is None or wl is None):
        try:
            one=hist.tail(252); wh=wh if wh is not None else num(one['High'].max()); wl=wl if wl is not None else num(one['Low'].min())
        except Exception: pass
    score=0
    if peg is not None: score+=20 if peg<=.8 else 12 if peg<=1.2 else 5 if peg<=1.8 else 0
    if roe is not None: score+=15 if roe>=15 else 8 if roe>=10 else 3 if roe>=5 else 0
    if dy is not None: score+=15 if dy>=4.5 else 10 if dy>=3 else 4 if dy>=1.5 else 0
    if pm is not None: score+=10 if pm>=15 else 5 if pm>=8 else 0
    if fcf is not None and fcf>0: score+=10
    if rg is not None: score+=10 if rg>=15 else 5 if rg>=5 else 0
    if pg is not None: score+=10 if pg>=20 else 5 if pg>=10 else 0
    if de is not None: score+=5 if de<=.5 else 2 if de<=1 else 0
    ma20=ma50=ma200=rsi14=None
    if not hist.empty and 'Close' in hist:
        c=pd.to_numeric(hist['Close'],errors='coerce').dropna(); ma20=num(c.rolling(20).mean().iloc[-1]) if len(c)>=20 else None; ma50=num(c.rolling(50).mean().iloc[-1]) if len(c)>=50 else None; ma200=num(c.rolling(200).mean().iloc[-1]) if len(c)>=200 else None; rsi14=rsi(c,14)
        if price is not None and ma50 is not None and price>ma50: score+=2.5
        if price is not None and ma200 is not None and price>ma200: score+=2.5
    score=round(min(100,score),1)
    fair=buy=None
    if eps is not None and eps>0 and pg is not None and pg>=5:
        fair=eps*min(max(pg,5),MAX_FAIR_PE); buy=fair*(1-BUY_ZONE_DISCOUNT)
    mos=(fair-price)/fair*100 if fair is not None and price is not None else None
    status='🟢 BUY' if score>=BUY_SCORE and price is not None and buy is not None and price<=buy else '🔴 OVERVALUED' if fair is not None and price is not None and price>fair*1.05 else '🟡 WATCH' if score>=WATCH_SCORE else '🔴 AVOID'
    code=symbol.replace('.KL',''); name=info.get('shortName') or info.get('longName') or STOCK_NAMES.get(code,code); name=f'{name} ({code})' if name!=code else code
    intra=intraday(symbol)
    # Afternoon forecast: morning momentum + VWAP + volume + market
    ap=0; ar=[]
    if intra.get('change') is not None: ap += 2 if intra['change']>1 else -2 if intra['change']<-1 else 0
    if intra.get('vwap_diff') is not None: ap += 2 if intra['vwap_diff']>.5 else -2 if intra['vwap_diff']<-.5 else 0
    if price is not None and ma50 is not None: ap += 1 if price>ma50 else -1
    if intra.get('rsi') is not None:
        ap += 1 if 45<=intra['rsi']<=65 else -1 if intra['rsi']>75 else 1 if intra['rsi']<30 else 0
    if intra.get('volume_ratio') is not None and intra['volume_ratio']>=1.5: ap += 1 if (intra.get('change') or 0)>=0 else -1
    if m.get('chg') is not None: ap += 1 if m['chg']>.3 else -1 if m['chg']<-.3 else 0
    afternoon='🟢 偏强' if ap>=5 else '🟢 震荡偏强' if ap>=2 else '🔴 偏弱' if ap<=-5 else '🔴 震荡偏弱' if ap<=-2 else '🟡 震荡'
    # Next-day forecast: broader trend + fundamentals + close momentum + news + market
    np=0; nr=[]
    np += 2 if score>=80 else -2 if score<55 else 0
    np += 1 if price is not None and ma20 is not None and price>ma20 else -1 if price is not None and ma20 is not None else 0
    np += 1 if price is not None and ma50 is not None and price>ma50 else -1 if price is not None and ma50 is not None else 0
    np += 1 if price is not None and ma200 is not None and price>ma200 else -1 if price is not None and ma200 is not None else 0
    if rsi14 is not None: np += 1 if 45<=rsi14<=65 else -2 if rsi14>75 else 1 if rsi14<30 else 0
    if intra.get('volume_ratio') is not None and intra['volume_ratio']>=1.5: np += 1 if (intra.get('change') or 0)>=0 else -1
    np += news_score
    if m.get('chg') is not None: np += 1 if m['chg']>.3 else -1 if m['chg']<-.3 else 0
    nextday='🟢 偏强' if np>=6 else '🟢 震荡偏强' if np>=2 else '🔴 偏弱' if np<=-5 else '🔴 震荡偏弱' if np<=-2 else '🟡 震荡'
    return dict(symbol=name,price=price,score=score,pe=pe,fpe=fpe,pb=pb,peg=peg,eps=eps,epsg=epsg,roe=roe,dy=dy,pm=pm,fcf=fcf,rg=rg,pg=pg,de=de,wh=wh,wl=wl,ma20=ma20,ma50=ma50,ma200=ma200,rsi14=rsi14,fair=fair,buy=buy,mos=mos,status=status,news=news_titles,news_score=news_score,intra=intra,afternoon=afternoon,nextday=nextday,ap=ap,np=np)

def rsi_text(x):
    if x is None:return 'N/A'
    if x<30:return '🔵 Oversold'
    if x<45:return '🟢 Attractive'
    if x<60:return '🟢 Healthy'
    if x<70:return '🟡 Strong'
    return '🔴 Overbought'

def trend_text(x):
    p,a,b,c=x['price'],x['ma20'],x['ma50'],x['ma200']
    if None not in (p,a,b,c): return '🟢 Strong Bullish' if p>a>b>c else '🟢 Bullish' if p>b else '🟡 Pullback' if p>c else '🔴 Bearish'
    return '🟢 Above MA50' if p is not None and b is not None and p>b else '🔴 Below MA50' if p is not None and b is not None else 'N/A'

def build(x):
    intra=x['intra']; vol=intra.get('volume_ratio'); vtxt='N/A' if vol is None else f'{vol:.2f}x'
    text=(f"\n<b>{html(x['symbol'])}</b> | {money(x['price'])} | Score {x['score']}/100\n\n"
          f"💰 <b>VALUATION</b>\nPE {fmt(x['pe'])} | Forward PE {fmt(x['fpe'])} | P/B {fmt(x['pb'])}\nPEG {fmt(x['peg'])}\nFair Value {money(x['fair'])} | Buy Zone {money(x['buy'])}\nMargin of Safety {pct(x['mos'])}\n\n"
          f"📈 <b>FUNDAMENTAL</b>\nEPS {money(x['eps'])} | EPS Growth {pct(x['epsg'])}\nROE {pct(x['roe'])} | DY {pct(x['dy'])} | Margin {pct(x['pm'])}\nRevenue G {pct(x['rg'])} | Profit G {pct(x['pg'])}\nDebt/Equity {fmt(x['de'])} | FCF {'Positive' if x['fcf'] is not None and x['fcf']>0 else 'N/A/Negative'}\n\n"
          f"📍 <b>52 WEEK</b>\nHigh {money(x['wh'])} | Low {money(x['wl'])}\n\n"
          f"📊 <b>TECHNICAL</b>\nMA20 {money(x['ma20'])} | MA50 {money(x['ma50'])} | MA200 {money(x['ma200'])}\nRSI14 {fmt(x['rsi14'])} {rsi_text(x['rsi14'])}\nVolume {vtxt}\nTrend {trend_text(x)}\n")
    if MODE in ('lunch','close') and intra:
        text += f"\n⏱ <b>SESSION</b>\nIntraday {pct(intra.get('change'))} | VWAP {money(intra.get('vwap'))} ({pct(intra.get('vwap_diff'))})\n5-bar MA {money(intra.get('ma5'))} | 20-bar MA {money(intra.get('ma20'))}\nSession High {money(intra.get('high'))} | Low {money(intra.get('low'))}\n"
    if x['news']:
        text += '\n📰 <b>NEWS</b>\n'+'\n'.join('• '+html(n) for n in x['news'][:2])+f"\n{'🟢' if x['news_score']>0 else '🔴' if x['news_score']<0 else '🟡'} News tone\n"
    if MODE=='lunch': text += f"\n🔮 <b>AI MODEL — AFTERNOON</b>\n{x['afternoon']} | Model confidence {min(90,50+abs(x['ap'])*7)}%\n"
    else: text += f"\n🔮 <b>AI MODEL — NEXT TRADING DAY</b>\n{x['nextday']} | Model confidence {min(92,50+abs(x['np'])*6)}%\n"
    text += '⚠️ 模型情景判断，不是保证上涨/下跌的概率。\n'
    return text

def split_msgs(text,limit=4000):
    if len(text)<=limit:return [text]
    parts=text.split('\n\n'); out=[]; cur=''
    for p in parts:
        if cur and len(cur)+2+len(p)>limit: out.append(cur); cur=p
        else: cur=p if not cur else cur+'\n\n'+p
    if cur:out.append(cur)
    return out

def send(text):
    if not TOKEN or not CHAT_ID: raise RuntimeError('Missing TELEGRAM_TOKEN/TELEGRAM_CHAT_ID')
    for m in split_msgs(text):
        r=requests.post(f'https://api.telegram.org/bot{TOKEN}/sendMessage',data={'chat_id':CHAT_ID,'text':m,'parse_mode':'HTML','disable_web_page_preview':True},timeout=20); r.raise_for_status()

def main():
    if MODE not in ('lunch','close'): MODE='close'
    syms=[]
    with open('stocks.txt',encoding='utf8') as f:
        syms=[x.strip().upper().lstrip('$') for x in f if x.strip() and not x.strip().startswith('#')]
    syms=[x if x.endswith('.KL') else x+'.KL' for x in syms]
    m=macro(); out=[]
    for s in syms:
        try:
            z=analyze(s,m)
            if z.get('price') is not None: out.append(z)
        except Exception as e: print(f'Skipping {s}: {e}')
    if not out: print('No valid stock data returned.'); return
    out.sort(key=lambda x:x['score'],reverse=True)
    title='☀️ KLSE SMART — LUNCH REPORT' if MODE=='lunch' else '🌙 KLSE SMART — MARKET CLOSE REPORT'
    if MODE=='lunch':
        bp=sum(x['ap']>=2 for x in out); bw=sum(x['ap']<=-2 for x in out); forecast='🟢 Afternoon bias stronger' if bp>bw else '🔴 Afternoon bias weaker' if bw>bp else '🟡 Afternoon mixed'
    else:
        bp=sum(x['np']>=2 for x in out); bw=sum(x['np']<=-2 for x in out); forecast='🟢 Next-day bias stronger' if bp>bw else '🔴 Next-day bias weaker' if bw>bp else '🟡 Next-day mixed'
    lines=[f'<b>{title}</b>',f"{datetime.now(TZ):%d %b %Y %H:%M}",'',macro_text(m),f'🔮 <b>MODEL OUTLOOK</b>\n{forecast}\nBullish candidates: {bp} | Bearish candidates: {bw}\n']
    for label,status in [('🟢 BUY ZONE','🟢 BUY'),('🟡 WATCHLIST','🟡 WATCH'),('🔴 OVERVALUED','🔴 OVERVALUED'),('🔴 AVOID','🔴 AVOID')]:
        g=[x for x in out if x['status']==status]
        if g:
            lines.append(f'<b>{label}</b>'); lines.extend(build(x) for x in g)
    lines.append('\n⚠️ <b>DISCLAIMER</b>\n模型预测是规则化情景分析，不是保证收益；免费行情可能延迟、缺失或与正式Bursa实时数据不同。')
    send('\n'.join(lines)); print(f'{MODE} report sent: {len(out)} stocks')

if __name__=='__main__': main()
