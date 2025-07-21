import os
import pandas as pd
import yfinance as yf
import json


# 저장할 디렉토리 목록
output_dirs = [
    r"C:\Users\canmanmo\Desktop\flask-stock-analyzer",
    r"C:\Users\canmanmo\Desktop\ma200_history"
]
for d in output_dirs:
    os.makedirs(d, exist_ok=True)

# 티커 불러오기
with open('tickers.json', 'r', encoding='utf-8') as f:
    tickers = json.load(f)

# 분석 대상 상위 400개
top400 = tickers[:400]
symbols = [t['symbol'] for t in top400]
name_map = {t['symbol']: t['name'] for t in top400}

# 최근 1년치 데이터 다운로드
print("데이터 다운로드 중... (1년 6개월)")
data = yf.download(
    symbols,
    period='18mo',
    auto_adjust=False,
    group_by='ticker',
    threads=False,
    progress=True
)

results = []
for symbol in symbols:
    try:
        df = data[symbol] if symbol in data.columns.levels[0] else pd.DataFrame()
        if df.empty or len(df) < 2:
            continue
        df = df.copy()
        # 52주 최고치
        df['52whigh'] = df['High'].rolling(window=252, min_periods=252).max()
        # 200일 이동평균
        df['200ma'] = df['Close'].rolling(window=200, min_periods=200).mean()

        today = df.iloc[-1]
        yesterday = df.iloc[-2]
        results.append({
            'symbol': symbol,
            'name': name_map[symbol],
            'today_close': round(today['Close'], 2),
            'yesterday_close': round(yesterday['Close'], 2),
            'today_52whigh': round(today['52whigh'], 2),
            'yesterday_52whigh': round(yesterday['52whigh'], 2),
            'today_200ma': round(today['200ma'], 2),
            'yesterday_200ma': round(yesterday['200ma'], 2)
        })
    except Exception as e:
        print(f"{symbol} 처리 에러: {e}")

# 결과 DataFrame 생성 및 저장
df_out = pd.DataFrame(results).drop_duplicates(subset='symbol')
for d in output_dirs:
    path = os.path.join(d, 'recent_ohlc.csv')
    df_out.to_csv(path, index=False, encoding='utf-8-sig')
    print(f"저장 완료: {path}")
print(f"총 {len(df_out)}개 종목 저장 완료.")