from flask import Flask, render_template, request, jsonify
import yfinance as yf
import pandas as pd
import numpy as np
import json
from datetime import timedelta
import math

app = Flask(__name__)

with open('tickers.json', 'r', encoding='utf-8') as f:
    ticker_data = json.load(f)

def analyze_stock(ticker, drawdown_pct, target_increase_pct, check_period_days):
    data = yf.download(ticker, start='2020-01-01', end='2030-07-01', auto_adjust=False)

    if isinstance(data.columns, pd.MultiIndex):
        data.columns = data.columns.droplevel('Ticker')

    data['52W_High'] = data['High'].rolling(window=252, min_periods=1).max()
    data['Drawdown'] = (data['Close'] - data['52W_High']) / data['52W_High']
    data['Prev_Drawdown'] = data['Drawdown'].shift(1)

    buy_points = data[
        (data['Drawdown'] <= drawdown_pct) &
        (data['Prev_Drawdown'] > drawdown_pct)
    ]

    results = []
    for buy_date in buy_points.index:
        try:
            buy_price = data.loc[buy_date, 'Close']
            target_price = buy_price * (1 + target_increase_pct)
            high_52w = data.loc[buy_date, '52W_High']
            idx = data.index.get_loc(buy_date)

            if idx >= len(data) - 1:
                continue

            start_date = data.index[idx + 1]
            end_date = start_date + timedelta(days=check_period_days)
            if end_date > data.index[-1]:
                end_date = data.index[-1]

            check_data = data.loc[start_date:end_date]
            hit = check_data[check_data['High'] >= target_price]

            if not hit.empty:
                achieve_date = hit.index[0]
                days_to_achieve = len(data.loc[buy_date:achieve_date]) - 1
                results.append({
                    'buy_date': buy_date.date(),
                    'buy_price': round(buy_price, 2),
                    'target_price': round(target_price, 2),
                    'high_52w': round(high_52w, 2),
                    'achieve_date': achieve_date.date(),
                    'days_to_achieve': days_to_achieve,
                    'achieved': True
                })
            else:
                results.append({
                    'buy_date': buy_date.date(),
                    'buy_price': round(buy_price, 2),
                    'target_price': round(target_price, 2),
                    'high_52w': round(high_52w, 2),
                    'achieve_date': None,
                    'days_to_achieve': None,
                    'achieved': False
                })
        except:
            continue

    df = pd.DataFrame(results)
    success = df[df['achieved']]
    current_close = round(data['Close'].iloc[-1], 2)
    current_date = data.index[-1].date()
    current_high_52w = round(data['52W_High'].iloc[-1], 2)

    return {
        'result_table': df.to_dict(orient='records'),
        'total_cases': len(df),
        'success_cases': len(success),
        'success_rate': round(len(success) / len(df) * 100, 2) if len(df) > 0 else 0,
        'avg_days': round(success['days_to_achieve'].mean(), 1) if not success.empty else None,
        'current_close': current_close,
        'current_date': current_date,
        'current_high_52w': current_high_52w
    }

@app.route('/search')
def search():
    query = request.args.get('q', '').lower()
    results = [t for t in ticker_data if query in t['symbol'].lower()]
    return jsonify(results[:10])

@app.route('/', methods=['GET', 'POST'])
def index():
    result = None
    form_data = {'ticker': '', 'drawdown': '', 'target': '', 'days': ''}
    page = int(request.args.get('page', 1))

    if request.method == 'POST':
        form_data['ticker'] = request.form.get('ticker', '')
        form_data['drawdown'] = request.form.get('drawdown', '')
        form_data['target'] = request.form.get('target', '')
        form_data['days'] = request.form.get('days', '')

        try:
            drawdown = float(form_data['drawdown']) / 100 * -1
            target = float(form_data['target']) / 100
            days = int(form_data['days'])

            full_result = analyze_stock(form_data['ticker'], drawdown, target, days)
            full_result['ticker'] = form_data['ticker']
            full_result['drawdown'] = abs(drawdown * 100)
            full_result['target'] = target * 100
            full_result['days'] = days

            full_result['result_table'] = sorted(full_result['result_table'], key=lambda x: x['buy_date'], reverse=True)

            per_page = 15
            total = len(full_result['result_table'])
            start = (page - 1) * per_page
            end = start + per_page
            full_result['paged_table'] = full_result['result_table'][start:end]
            full_result['current_page'] = page
            full_result['total_pages'] = (total + per_page - 1) // per_page

            result = full_result
        except:
            result = {'error': '입력 값을 확인해주세요.'}

    return render_template('index.html', result=result, form_data=form_data)

if __name__ == '__main__':
    app.run(debug=True)
