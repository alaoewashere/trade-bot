import yfinance as yf

df = yf.download('BTC-USD', period='1d', interval='1h', progress=False, auto_adjust=True)
print(f'Got {len(df)} rows, columns: {list(df.columns)}')

candles = []
for _, row in df.iterrows():
    try:
        def val(x):
            return float(x.iloc[0] if hasattr(x, 'iloc') else x)
        candles.append({
            'open': val(row['Open']),
            'high': val(row['High']),
            'low': val(row['Low']),
            'close': val(row['Close']),
            'volume': val(row['Volume']),
        })
    except Exception as e:
        print(f'Row error: {e}')

print(f'Parsed {len(candles)} candles')
if candles:
    print(f'Last: close={candles[-1]["close"]:.2f}')
print('SUCCESS')
