@echo off
chcp 65001
cd /d "C:\Users\canmanmo\Desktop\flask-stock-analyzer"
python save_recent_ohlc.py
git add .
git commit -m "자동 갱신: 최신 ohlc 데이터" || exit /b 0
git push origin main