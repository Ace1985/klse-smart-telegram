import os
import requests
import yfinance as yf

# 从 GitHub Secrets / 环境变量获取 Token 和 Chat ID
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "").strip()

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
            # 抓取近 7 天数据，防止周末或节假日数据缺失
            df = stock.history(period="7d")
            
            # 校验数据是否获取成功
            if df is None or df.empty or 'Close' not in df.columns:
                results.append(f"⚠️ <b>{name}</b> ({ticker.split('.')[0]}): 暂无最新数据")
                continue

            latest_price = df['Close'].iloc[-1]
            
            # 计算涨跌额与涨跌幅
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
            print(f"[Error] 抓取 {name} ({ticker}) 失败: {e}")
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
        print(f"发送 Telegram 消息异常: {e}")
        return {}

if __name__ == "__main__":
    # 打印排查日志
    print("正在检查环境变量...")
    if not TELEGRAM_BOT_TOKEN:
        print("❌ 错误：TELEGRAM_BOT_TOKEN 未设置或为空！请检查 GitHub Repository Secrets。")
        exit(1)
    if not TELEGRAM_CHAT_ID:
        print("❌ 错误：TELEGRAM_CHAT_ID 未设置或为空！请检查 GitHub Repository Secrets。")
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
        print("✅ 消息已成功推送至 Telegram！")
    else:
        print(f"❌ 推送失败，Telegram 返回错误: {res}")
