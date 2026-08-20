import os, math, time
from datetime import datetime
from zoneinfo import ZoneInfo
import pandas as pd
import requests
import yfinance as yf
from config import BUY_SCORE, WATCH_SCORE, BUY_ZONE_DISCOUNT, MAX_FAIR_PE

TZ=ZoneInfo('Asia/Kuala_Lumpur')
TOKEN=os.environ['TELEGRAM_TOKEN']; CHAT_ID=os.environ['TELEGRAM_CHAT_ID']

def num(x):
    try:
        x=float(x)
        return x if math.isfinite(x) else None
    except: return None

def pct(x): return f'{x:.1f}%' if x is not None else 'N/A'
def money(x): return f'RM{x:.2f}' if x is not None else 'N/A'

def growth_from(df,names):
    if df is None or df.empty: return None
    for n in names:
        if n in df.index:
            v=pd.to_numeric(df.loc[n],errors='coerce').dropna().tolist()
            if len(v)>=2 and v[-2]!=0: return (v[-1]/v[-2]-1)*100
    return None

def analyze(symbol):
    t=yf.Ticker(symbol)
    try: info=t.info or {}
    except: info={}
    try: hist=t.history(period='1y',auto_adjust=False)
    except: hist=pd.DataFrame()
    try: income=t.financials
    except: income=pd.DataFrame()
    try: balance=t.balance_sheet
    except: balance=pd.DataFrame()
    price=num(hist['Close'].dropna().iloc[-1]) if not hist.empty else None
    pe=num(info.get('trailingPE')); eps=num(info.get('trailingEps'))
    roe=num(info.get('returnOnEquity')); roe=roe*100 if roe is not None and abs(roe)<1 else roe
    rg=num(info.get('revenueGrowth')); rg=rg*100 if rg is not None and abs(rg)<1 else rg
    pg=num(info.get('earningsGrowth')); pg=pg*100 if pg is not None and abs(pg)<1 else pg
    if rg is None: rg=growth_from(income,['Total Revenue','Operating Revenue'])
    if pg is None: pg=growth_from(income,['Net Income','Net Income Common Stockholders'])
    de=num(info.get('debtToEquity')); de=de/100 if de is not None else None
    peg=pe/pg if pe is not None and pg is not None and pg>0 else None
    score=0
    if peg is not None: score += 25 if peg<=.8 else 15 if peg<=1.2 else 6 if peg<=1.8 else 0
    if roe is not None: score += 20 if roe>=15 else 10 if roe>=10 else 4 if roe>=5 else 0
    if rg is not None: score += 15 if rg>=15 else 8 if rg>=5 else 3 if rg>0 else 0
    if pg is not None: score += 15 if pg>=20 else 8 if pg>=10 else 3 if pg>0 else 0
    if de is not None: score += 10 if de<=.5 else 5 if de<=1 else 2 if de<=2 else 0
    tech=0
    if not hist.empty:
        c=hist['Close'].dropna(); ma50=c.rolling(50).mean().iloc[-1] if len(c)>=50 else None; ma200=c.rolling(200).mean().iloc[-1] if len(c)>=200 else None
        if price and ma50 and price>ma50: tech+=7.5
        if price and ma200 and price>ma200: tech+=7.5
        elif ma200 is None and price and ma50 and price>ma50: tech=15
    score=round(min(100,score+tech),1)
    fair_value=buy_zone=None
    if eps and eps>0 and pg is not None and pg>=5:
        fair_pe=min(max(pg,5),MAX_FAIR_PE); fair_value=eps*fair_pe; buy_zone=fair_value*(1-BUY_ZONE_DISCOUNT)
    discount=(fair_value-price)/fair_value*100 if fair_value and price else None
    if fair_value and price:
        status='🟢 BUY' if score>=BUY_SCORE and price<=buy_zone else '🔴 OVERVALUED' if price>fair_value*1.05 else '🟡 WATCH'
    else: status='🟢 BUY' if score>=BUY_SCORE else '🟡 WATCH' if score>=WATCH_SCORE else '🔴 AVOID'
    return dict(symbol=symbol.replace('.KL',''),price=price,score=score,fair_value=fair_value,buy_zone=buy_zone,discount=discount,peg=peg,roe=roe,rg=rg,pg=pg,status=status)

def send(text):
    r=requests.post(f'https://api.telegram.org/bot{TOKEN}/sendMessage',data={'chat_id':CHAT_ID,'text':text},timeout=20); r.raise_for_status()

def main():
    syms=[x.strip().upper() for x in open('stocks.txt',encoding='utf8') if x.strip() and not x.startswith('#')]
    syms=[x if x.endswith('.KL') else x+'.KL' for x in syms]
    out=[]
    for s in syms:
        try: out.append(analyze(s))
        except Exception as e: print(s,e)
    out.sort(key=lambda x:x['score'],reverse=True)
    lines=[f"📊 KLSE SMART REPORT\n{datetime.now(TZ):%d %b %Y %H:%M}"]
    for label,st in [('🟢 BUY ZONE','🟢 BUY'),('🟡 WATCHLIST','🟡 WATCH'),('🔴 OVERVALUED / AVOID','🔴 OVERVALUED'),('🔴 AVOID','🔴 AVOID')]:
        g=[x for x in out if x['status']==st]
        if not g: continue
        lines.append('\n'+label)
        for x in g:
            lines.append(f"\n{x['symbol']} | {money(x['price'])} | Score {x['score']}/100\nFair Value {money(x['fair_value'])} | Buy Zone {money(x['buy_zone'])}\nDiscount {pct(x['discount'])} | PEG {x['peg']:.2f} | ROE {pct(x['roe'])}\nRevenue G {pct(x['rg'])} | Profit G {pct(x['pg'])}")
    lines.append('\n⚠️ Screening tool only, not financial advice. Free-market data may be delayed/incomplete.')
    send('\n'.join(lines))
if __name__=='__main__': main()
