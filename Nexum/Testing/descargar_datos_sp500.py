"""
Modelo Nexum - descarga de datos point-in-time para el backtest accionario
de Equity Momentum y Betting Against Beta (BAB).

Este script corre en TU computador (necesita internet, que esta sesion de
Claude no tiene). Genera 3 archivos que luego me subes de vuelta:

  1. sp500_constituyentes_actuales.csv   - lista actual de tickers del S&P 500
  2. sp500_cambios_historicos.csv        - historial de altas/bajas del indice
  3. sp500_precios_volumen.parquet       - precios ajustados de cierre y volumen
                                            diarios de todos los tickers que
                                            estuvieron en el indice en la
                                            ventana descargada (o .csv si no
                                            tienes pyarrow instalado)

Instalar dependencias:
    pip install yfinance pandas lxml requests pyarrow

Ejecutar:
    python descargar_datos_sp500.py

La descarga de precios es lo mas lento (cientos de tickers x ~15 anios de
historia diaria). Es resumible: si se corta a la mitad, correr de nuevo
retoma donde quedo (usa la carpeta cache_precios/ como cache por ticker).

LIMITACIONES QUE HEREDA EL BACKTEST FINAL (avisar a Claude si importan):
  - La membresia point-in-time se reconstruye a partir de la tabla de
    "cambios historicos" de Wikipedia, que es de buena calidad pero no
    perfecta (puede faltar algun cambio menor, especialmente antes de ~2005).
  - No se descarga capitalizacion bursatil historica (no hay fuente gratuita
    confiable); el filtro de liquidez del modelo (ADV minimo USD/dia) se
    puede calcular igual con precio x volumen.
  - Los precios de Yahoo Finance vienen ajustados por dividendos y splits
    (columna "Adj Close"), consistente con el resto del modelo (Total Return).
"""

import io
import time
from datetime import datetime
from pathlib import Path

import pandas as pd
import requests

START_DATE = "2011-01-01"   # mismo inicio que el resto del modelo (05_Datos_Historicos)
END_DATE = None             # None = hoy
CACHE_DIR = Path("cache_precios")
BATCH_SIZE = 40             # tickers por lote de descarga
PAUSE_BETWEEN_BATCHES = 2.0 # segundos, para no saturar la API

WIKI_URL = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"


def fetch_wikipedia_tables():
    headers = {"User-Agent": "Mozilla/5.0 (research script - Modelo Nexum)"}
    resp = requests.get(WIKI_URL, headers=headers, timeout=30)
    resp.raise_for_status()
    tables = pd.read_html(io.StringIO(resp.text))
    current = tables[0]
    changes = tables[1]
    return current, changes


def normalize_changes_table(changes: pd.DataFrame) -> pd.DataFrame:
    changes = changes.copy()
    changes.columns = ["_".join(c).strip() if isinstance(c, tuple) else c for c in changes.columns]
    cols = {c: c for c in changes.columns}
    date_col = next(c for c in changes.columns if "Date" in c)
    added_col = next((c for c in changes.columns if "Added" in c and "Ticker" in c), None)
    removed_col = next((c for c in changes.columns if "Removed" in c and "Ticker" in c), None)
    out = pd.DataFrame({
        "date": pd.to_datetime(changes[date_col], errors="coerce"),
        "added_ticker": changes[added_col] if added_col else None,
        "removed_ticker": changes[removed_col] if removed_col else None,
    })
    out = out.dropna(subset=["date"]).sort_values("date").reset_index(drop=True)
    return out


def build_membership_universe(current_tickers, changes_df, start_date):
    start = pd.Timestamp(start_date)
    relevant = changes_df[changes_df["date"] >= start]
    ever_added = set(relevant["added_ticker"].dropna())
    ever_removed = set(relevant["removed_ticker"].dropna())
    universe = set(current_tickers) | ever_added | ever_removed
    universe = {t.replace(".", "-") for t in universe if isinstance(t, str)}
    return sorted(universe)


def membership_snapshot(current_tickers, changes_df, as_of_date):
    tickers = set(current_tickers)
    for _, row in changes_df[changes_df["date"] > as_of_date].sort_values("date", ascending=False).iterrows():
        if isinstance(row["added_ticker"], str):
            tickers.discard(row["added_ticker"])
        if isinstance(row["removed_ticker"], str):
            tickers.add(row["removed_ticker"])
    return tickers


def build_full_membership_table(current_tickers, changes_df, start_date):
    """Genera intervalos (ticker, start, end) de pertenencia al indice,
    tomando una foto mensual (suficiente para un backtest mensual)."""
    dates = pd.date_range(start_date, datetime.today(), freq="MS")
    rows = []
    for d in dates:
        snap = membership_snapshot(current_tickers, changes_df, d)
        for t in snap:
            rows.append({"month": d, "ticker": t.replace(".", "-")})
    return pd.DataFrame(rows)


def download_prices(tickers, start_date, end_date):
    import yfinance as yf

    CACHE_DIR.mkdir(exist_ok=True)
    pending = [t for t in tickers if not (CACHE_DIR / f"{t}.parquet").exists()]
    print(f"{len(tickers)} tickers totales, {len(pending)} pendientes de descargar")

    for i in range(0, len(pending), BATCH_SIZE):
        batch = pending[i:i + BATCH_SIZE]
        print(f"Descargando lote {i // BATCH_SIZE + 1} / {(len(pending) - 1) // BATCH_SIZE + 1}: {batch}")
        try:
            data = yf.download(
                batch, start=start_date, end=end_date, auto_adjust=False,
                group_by="ticker", threads=True, progress=False,
            )
        except Exception as e:
            print(f"  ERROR en el lote, reintentando en 10s: {e}")
            time.sleep(10)
            continue

        for t in batch:
            try:
                if len(batch) == 1:
                    sub = data
                else:
                    sub = data[t]
                sub = sub[["Adj Close", "Volume"]].dropna(how="all")
                if sub.empty:
                    continue
                sub = sub.reset_index()
                sub.columns = ["date", "adj_close", "volume"]
                sub["ticker"] = t
                sub.to_parquet(CACHE_DIR / f"{t}.parquet", index=False)
            except Exception as e:
                print(f"  {t}: sin datos ({e})")
        time.sleep(PAUSE_BETWEEN_BATCHES)

    frames = []
    for t in tickers:
        f = CACHE_DIR / f"{t}.parquet"
        if f.exists():
            frames.append(pd.read_parquet(f))
    if not frames:
        raise RuntimeError("No se descargo ningun ticker")
    return pd.concat(frames, ignore_index=True)


def main():
    print("1/4 - Descargando tablas de Wikipedia (constituyentes y cambios historicos)...")
    current, changes_raw = fetch_wikipedia_tables()
    current.to_csv("sp500_constituyentes_actuales.csv", index=False)
    changes = normalize_changes_table(changes_raw)
    changes.to_csv("sp500_cambios_historicos.csv", index=False)
    print(f"   {len(current)} constituyentes actuales, {len(changes)} eventos de cambio")

    print("2/4 - Reconstruyendo universo de tickers relevante desde", START_DATE, "...")
    current_tickers = current["Symbol"].tolist()
    universe = build_membership_universe(current_tickers, changes, START_DATE)
    print(f"   {len(universe)} tickers distintos estuvieron en el indice en la ventana")

    print("3/4 - Generando tabla de pertenencia mensual (point-in-time)...")
    membership = build_full_membership_table(current_tickers, changes, START_DATE)
    membership.to_csv("sp500_membresia_mensual.csv", index=False)
    print(f"   {len(membership)} filas (ticker-mes)")

    print("4/4 - Descargando precios y volumen diarios (esto puede tardar bastante)...")
    prices = download_prices(universe, START_DATE, END_DATE)
    try:
        prices.to_parquet("sp500_precios_volumen.parquet", index=False)
        print(f"Listo: sp500_precios_volumen.parquet ({len(prices):,} filas)")
    except Exception:
        prices.to_csv("sp500_precios_volumen.csv", index=False)
        print(f"Listo: sp500_precios_volumen.csv ({len(prices):,} filas) [pyarrow no disponible, se uso CSV]")

    print("\nSube estos archivos de vuelta a Claude:")
    print("  - sp500_constituyentes_actuales.csv")
    print("  - sp500_cambios_historicos.csv")
    print("  - sp500_membresia_mensual.csv")
    print("  - sp500_precios_volumen.parquet (o .csv)")


if __name__ == "__main__":
    main()
