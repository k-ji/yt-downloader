#!/usr/bin/env python3
"""Gap-down behaviour by year, month and day: does buying the dip at the open still pay?

A gap-down is a session that opens at least --gap % below the prior close.
Buying it at the open, per period:
  n      number of gap-downs (summed across tickers)
  gap    average gap
  d0     close / open - 1                    same day; < 0 means it sold off further
  green  share that closed above the open
  fill   share whose high got back to the prior close
  d1     next close / open - 1               held one more day
  d5     close 5 sessions later / open - 1   overstayed
Everything but n is in %.

  pip install pandas yfinance
  python gap_down.py SPY QQQ IWM            # full daily history via yfinance
  python gap_down.py data/*.csv --gap 3     # daily OHLC CSVs: one per ticker, or one file with a ticker/symbol column
"""
import argparse
from pathlib import Path

import pandas as pd

COLS = ['gap', 'd0', 'green', 'fill', 'd1', 'd5']


def load(src):
    if Path(src).is_file():
        df = pd.read_csv(src)
    else:
        import yfinance as yf
        df = yf.Ticker(src).history(period='max').reset_index()
    df.columns = df.columns.str.strip().str.lower()
    df = df.rename(columns={'symbol': 'ticker'})
    if 'ticker' not in df:
        df['ticker'] = Path(src).stem.upper()
    df['date'] = pd.to_datetime(df['date'], utc=True).dt.tz_localize(None)
    return df[['ticker', 'date', 'open', 'high', 'close']]


def gap_downs(df, pct):
    df = df.sort_values(['ticker', 'date']).reset_index(drop=True)
    close = df.groupby('ticker')['close']
    prev = close.shift()
    df = df.assign(gap=df.open / prev - 1, d0=df.close / df.open - 1, green=df.close > df.open,
                   fill=df.high >= prev, d1=close.shift(-1) / df.open - 1, d5=close.shift(-5) / df.open - 1)
    return df[df.gap <= -pct / 100]


def summary(ev, freq=None):
    key = ev.date.dt.to_period(freq) if freq else (lambda _: 'ALL')
    out = ev.groupby(key).agg(n=('gap', 'size'), **{c: (c, 'mean') for c in COLS})
    out[COLS] *= 100
    return out.round(2)


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('src', nargs='+', help='tickers or daily OHLC CSV files')
    ap.add_argument('--gap', type=float, default=0.5, help='minimum gap-down in %% (default 0.5)')
    ap.add_argument('--months', type=int, default=24, help='rows in the monthly table (default 24)')
    ap.add_argument('--days', type=int, default=30, help='rows in the daily table (default 30)')
    a = ap.parse_args()

    ev = gap_downs(pd.concat(map(load, a.src)), a.gap)
    for name, t in [('year', pd.concat([summary(ev, 'Y'), summary(ev)])),
                    ('month', summary(ev, 'M').tail(a.months)),
                    ('day', summary(ev, 'D').tail(a.days))]:
        print(f'\n== gap-downs <= -{a.gap}% by {name} ==\n{t.to_string()}')
