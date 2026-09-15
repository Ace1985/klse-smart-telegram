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
    "LAC Med": "LACMED.KL"  # 使用通用代码或 5341.KL
}

def get_stock_prices():
    results = []
    for name, ticker in WATCHLIST.items():
        try:
            stock = yf.Ticker(ticker)
            df = stock.history(period="5d") # 抓取 5 天数据，防止遇到节假日无数据
            
            # 校验数据是否为空
            if df.empty or len(df) < 1:
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
            # 容错处理：单只股票出错不影响其他股票执行
            print(f"抓取 {name} 出错: {e}")
            results.append(f"⚠️ <b>{name}</b>: 获取失败")

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
    
    header = "📊 <b>【KLSE 精选股每日简报】</b>\n" \
             "──────────────────────\n"
    body = "\n\n".join(stock_lines)
    footer = "\n──────────────────────\n" \
             "💡 <i>数据来源：Yahoo Finance</i>"
    
    full_message = header + body + footer
    
    res = send_telegram_message(full_message)
    if res.get("ok"):
        print("消息成功发送至 Telegram！")
    else:
        print(f"发送失败: {res}")
