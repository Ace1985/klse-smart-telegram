# KLSE Smart Telegram Bot v2

Free GitHub Actions + Telegram KLSE watchlist screener.

## Setup
1. Upload these files to a GitHub repository.
2. GitHub -> Settings -> Secrets and variables -> Actions.
3. Add TELEGRAM_TOKEN (from BotFather).
4. Add TELEGRAM_CHAT_ID = 1784673116.
5. Actions -> KLSE Smart Daily Report -> Run workflow to test.
6. It will also run Mon-Fri at 18:30 Asia/Kuala_Lumpur.

Edit stocks.txt to change the watchlist.

## Scoring
PEG 25, ROE 20, Revenue Growth 15, Profit Growth 15, Debt/Equity 10, Technical Trend 15.

Fair value is a simple EPS x growth-based fair PE estimate, capped at 30, with a 15% buy-zone discount. This is a screening model, not financial advice. Yahoo Finance/yfinance data can be delayed or incomplete; sector-specific treatment for banks/REITs should be added after the basic version is running.
