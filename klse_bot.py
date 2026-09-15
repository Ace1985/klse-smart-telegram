import os
import requests
import yfinance as yf

# Telegram 环境变量
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

# 精选 9 只目标股票字典 (包含股票名称与 Yahoo Finance 代码)
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
            # 获取最新行情
            df = stock.history(period="2d")
            if len(df) >= 1:
                latest_price = df['Close'].iloc[-1]
                
                # 计算今日涨跌额与涨跌幅
                if len(df) >= 2:
                    prev_close = df['Close'].iloc[-2]
                    change = latest_price - prev_close
                    pct_change = (change / prev_close) * 100
                else:
                    change = 0.0
                    pct_change = 0.0

                # 根据涨跌显示不同图标
                icon = "🔴" if change < 0 else "🟢" if change > 0 else "⚪"
                
                # 格式化每条数据
                line = f"{icon} <b>{name}</b> ({ticker.split('.')[0]})\n" \
                       f"   └ 股价: <b>RM {latest_price:.2f}</b> ({change:+.2f} / {pct_change:+.2f}%)"
                results.append(line)
        except Exception as e:
            results.append(f"⚠️ {name}: 获取失败 ({str(e)})")

    return results

def send_telegram_message(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "HTML"
    }
    response = requests.post(url, json=payload)
    return response.json()

if __name__ == "__main__":
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("错误：未找到 Telegram Token 或 Chat ID 环境变量")
        exit(1)

    print("正在抓取精选 9 只股票数据...")
    stock_lines = get_stock_prices()
    
    # 组合最终消息
    header = "📊 <b>【KLSE 精选股每日简报】</b>\n" \
             "──────────────────────\n"
    body = "\n\n".join(stock_lines)
    footer = "\n──────────────────────\n" \
             "💡 <i>注：数据由 Yahoo Finance 提供，可能有 15 分钟延迟。</i>"
    
    full_message = header + body + footer
    
    # 发送通知
    res = send_telegram_message(full_message)
    if res.get("ok"):
        print("消息成功发送至 Telegram！")
    else:
        print(f"发送失败: {res}")
