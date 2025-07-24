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
top500 = tickers[:501]
symbols = [t['symbol'] for t in top500]
name_map = {t['symbol']: t['name'] for t in top500}

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

# 기존 코드의 df_out 생성 후 이어서 추가

# df_out에 데이터가 제대로 들어갔는지 확인 (예: 'today_close' 컬럼 기준)
missing_data_tickers = df_out[df_out['today_close'].isna()]

if not missing_data_tickers.empty:
    print("\n--- 'today_close' 데이터가 누락된 종목 ---")
    for index, row in missing_data_tickers.iterrows():
        print(f"- {row['symbol']} ({row['name']})")
    print(f"총 {len(missing_data_tickers)}개 종목의 'today_close' 데이터가 누락되었습니다.")
else:
    print("\n'today_close' 데이터가 누락된 종목이 없습니다.")

# 또는 모든 컬럼을 대상으로 NaN 값 확인 (좀 더 광범위한 확인)
# df_out.isnull().sum()
# df_out[df_out.isnull().any(axis=1)] # 어느 하나라도 NaN인 행 찾기