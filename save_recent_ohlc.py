import pandas as pd
import yfinance as yf
import json
import time
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# 세션 설정으로 연결 재사용 및 안정성 향상
def create_session():
    session = requests.Session()
    retry_strategy = Retry(
        total=3,
        backoff_factor=1,
        status_forcelist=[429, 500, 502, 503, 504],
    )
    adapter = HTTPAdapter(max_retries=retry_strategy)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    return session

# 전역 세션 생성
session = create_session()

with open('tickers.json', 'r', encoding='utf-8') as f:
    tickers = json.load(f)

top300 = tickers[:300]
fail_log = open('fetch_fail.log', 'w', encoding='utf-8')

def fetch_single_optimized(symbol, name, try_count=1):
    """단일 심볼을 효율적으로 가져오는 함수"""
    try:
        # 세션 재사용으로 연결 속도 향상
        ticker = yf.Ticker(symbol, session=session)
        
        # 필요한 기간만 정확히 요청 (253일 = 약 1년 영업일)
        data = ticker.history(period='1y', auto_adjust=False, actions=False)
        
        if data.empty or len(data) < 2:
            fail_log.write(f"{symbol} (시도 {try_count}): 데이터 없음 or Too short\n")
            fail_log.flush()
            return None
            
        # 52주 고점 계산 (최대 252일)
        data['52whigh'] = data['High'].rolling(window=min(252, len(data)), min_periods=1).max()
        
        today = data.iloc[-1]
        yesterday = data.iloc[-2]
        
        return {
            "symbol": symbol,
            "name": name,
            "today_close": round(today['Close'], 2),
            "today_52whigh": round(today['52whigh'], 2),
            "yesterday_close": round(yesterday['Close'], 2),
            "yesterday_52whigh": round(yesterday['52whigh'], 2),
        }
        
    except Exception as e:
        fail_log.write(f"{symbol} (시도 {try_count}): {e}\n")
        fail_log.flush()
        return None

def fetch_adaptive_batch(batch, try_count=1):
    """적응형 배치 처리 - 실패 시 단일 요청으로 폴백"""
    if len(batch) == 1:
        # 단일 심볼 처리
        symbol_data = batch[0]
        result = fetch_single_optimized(symbol_data['symbol'], symbol_data['name'], try_count)
        return [result] if result else []
    
    # 배치 처리 시도
    batch_symbols = [t['symbol'] for t in batch]
    batch_names = {t['symbol']: t['name'] for t in batch}
    results = []
    
    try:
        # 배치 다운로드 시도
        data = yf.download(
            batch_symbols, 
            period='1y',  # 1년으로 변경
            auto_adjust=False, 
            group_by='ticker', 
            threads=False, 
            progress=False,
            session=session
        )
        
        successful_symbols = []
        
        for symbol in batch_symbols:
            try:
                # 멀티 심볼일 때 데이터 접근 방식
                if len(batch_symbols) > 1:
                    symbol_data = data[symbol] if symbol in data.columns.levels[0] else None
                else:
                    symbol_data = data
                
                if symbol_data is None or symbol_data.empty or len(symbol_data) < 2:
                    continue
                    
                symbol_data = symbol_data.copy()
                symbol_data['52whigh'] = symbol_data['High'].rolling(window=min(252, len(symbol_data)), min_periods=1).max()
                
                today = symbol_data.iloc[-1]
                yesterday = symbol_data.iloc[-2]
                
                results.append({
                    "symbol": symbol,
                    "name": batch_names[symbol],
                    "today_close": round(today['Close'], 2),
                    "today_52whigh": round(today['52whigh'], 2),
                    "yesterday_close": round(yesterday['Close'], 2),
                    "yesterday_52whigh": round(yesterday['52whigh'], 2),
                })
                successful_symbols.append(symbol)
                
            except Exception as e:
                continue
        
        # 실패한 심볼들을 단일 요청으로 재시도
        failed_symbols = [s for s in batch_symbols if s not in successful_symbols]
        
        if failed_symbols and try_count == 1:  # 첫 번째 시도에서만 단일 요청 폴백
            print(f"배치 실패 심볼 {len(failed_symbols)}개를 단일 요청으로 재시도...")
            for symbol in failed_symbols:
                name = batch_names[symbol]
                single_result = fetch_single_optimized(symbol, name, try_count)
                if single_result:
                    results.append(single_result)
        
        # 요청 간 딜레이
        time.sleep(0.5)  # 딜레이 단축
        return results
        
    except Exception as e:
        fail_log.write(f"배치 전체 에러 (시도 {try_count}): {batch_symbols} / {e}\n")
        fail_log.flush()
        
        # 배치 실패 시 단일 요청으로 폴백
        if try_count == 1:
            results = []
            for symbol_data in batch:
                single_result = fetch_single_optimized(symbol_data['symbol'], symbol_data['name'], try_count)
                if single_result:
                    results.append(single_result)
            return results
        
        time.sleep(1)
        return []

# 메인 실행 부분
batch_size = 5  # 배치 크기 줄임
max_workers = 3  # 워커 수 증가

batches = [top300[i:i+batch_size] for i in range(0, len(top300), batch_size)]
results = []
failed_symbols = []

for repeat in range(2):
    print(f"\n==== {repeat+1}차 시도 ====")
    current_batches = []
    
    if repeat == 0:
        current_batches = batches
    else:
        if not failed_symbols:
            break
        # 실패한 심볼들을 단일 배치로 처리
        current_batches = [[{'symbol': sym, 'name': next(t['name'] for t in top300 if t['symbol']==sym)}] 
                          for sym in failed_symbols]
        failed_symbols = []
    
    total = len(current_batches)
    completed = 0
    
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [executor.submit(fetch_adaptive_batch, batch, repeat+1) for batch in current_batches]
        
        for i, future in enumerate(as_completed(futures)):
            res = future.result()
            results.extend(res)
            
            # 누락 종목 체크
            batch_symbols = [t['symbol'] for t in current_batches[i]]
            successful_symbols = [r['symbol'] for r in res]
            
            for symbol in batch_symbols:
                if symbol not in successful_symbols:
                    failed_symbols.append(symbol)
            
            completed += 1
            progress = int(100 * completed / total)
            success_rate = len([r for r in res if r]) / len(batch_symbols) * 100 if batch_symbols else 0
            print(f"\r진행률: {completed}/{total} ({progress}%) | 현재 배치 성공률: {success_rate:.1f}%", end='', flush=True)
        
        print()  # 줄바꿈
    
    print(f"현재까지 수집: {len(results)}개 | 남은 실패 티커: {len(failed_symbols)}")

fail_log.close()
session.close()

# 결과 저장
df = pd.DataFrame(results).drop_duplicates(subset='symbol')
df.to_csv("recent_ohlc.csv", index=False, encoding='utf-8-sig')

print(f"\n완료! 총 {len(df)}개 종목 수집 성공")
print(f"성공률: {len(df)/len(top300)*100:.1f}%")
print("누락/에러시엔 fetch_fail.log 참고")