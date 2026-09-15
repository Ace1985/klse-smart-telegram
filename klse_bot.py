import os
import requests
import yfinance as yf

# Telegram 环境变量
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

# 精选 9 只目标股票字典
WATCHLIST = {
    "Maybank": "1155.KL",
    "Public Bank": "1295.KL",
    "Magni-Tech": "7087.KL",
    "Matrix Concepts": "5236.KL",
    "UMediC": "0256.KL",
    "CCK Consolidated": "7035.KL",
    "Teo Seng Capital": "7252.KL",
    "MR D.I.Y.": "5296.KL",
    "LAC Med": "5341.KL"
}

def get_stock_prices():
    results = []
    for name, ticker in WATCHLIST.items():
        try:
            stock = yf.Ticker(ticker)
            # 抓取近 7 天数据，防止碰上周末或假期无数据
            df = stock.history(period="7d")
            
            # 【关键防护 1】判断是否获取到了有效的股价列
            if df is None or df.empty or 'Close' not in df.columns or len(df['Close']) == 0:
                results.append(f"⚠️ <b>{name}</b> ({ticker.split('.')[0]}): 暂无最新数据")
                continue

            latest_price = df['Close'].iloc[-1]
            
            # 计算今日涨跌额与涨跌幅
            if len(df) >= 2:
                prev_close = df['Close'].iloc[-2]
                change = latest_price - prev_close
                pct_change = (change / prev_close) * 100
            else:
                change = 0.0
                pct_change = 0.0

            # 状态图标
            icon = "🔴" if change < 0 else "🟢" if change > 0 else "⚪"
            
            line = f"{icon} <b>{name}</b> ({ticker.split('.')[0]})\n" \
                   f"   └ 股价: <b>RM {latest_price:.2f}</b> ({change:+.2f} / {pct_change:+.2f}%)"
            results.append(line)

        except Exception as e:
            # 【关键防护 2】捕获所有异常，绝不让脚本崩溃退出
            print(f"[Error] 抓取 {name} ({ticker}) 异常: {e}")
            results.append(f"⚠️ <b>{name}</b> ({ticker.split('.')[0]}): 获取失败")

    return results

def send_telegram_message(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "HTML"
    }
    try:
        response = requests.post(url, json=payload, timeout=10)
        return response.json()
    except Exception as e:
        print(f"发送 Telegram 消息失败: {e}")
        return {}

if __name__ == "__main__":
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("错误：未设置 TELEGRAM_BOT_TOKEN 或 TELEGRAM_CHAT_ID 环境变量！")
        exit(1)

    print("开始获取精选 9 只马股最新数据...")
    stock_lines = get_stock_prices()
    
    header = "📊 <b>【KLSE 精选股每日简报】</b>\n" \
             "──────────────────────\n"
    body = "\n\n".join(stock_lines)
    footer = "\n──────────────────────\n" \
             "💡 <i>数据来源：Yahoo Finance</i>"
    
    full_message = header + body + footer
    
    res = send_telegram_message(full_message)
    if res.get("ok"):
        print("✅ 消息已成功发送至 Telegram！")
    else:
        print(f"❌ 发送失败，Telegram API 返回: {res}")
