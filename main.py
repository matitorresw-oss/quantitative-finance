import pandas as pd
import numpy as np
from modules.financials_functions import portfolio_volatility, portafolio_returns, VaR
from modules.backend import tickers_by_issuer


if __name__ == '__main__':

    # obtener tickers de ishares
    tickers = tickers_by_issuer(issuer = 'iShares')
    
    # portafolio de renta fija
    tickers_rf = tickers[tickers['CATEGORIA']=='ETF RF']
    list_tickers_rf = list(tickers_rf['TICKER'])

    # Portafolio de renta variable
    tickers_rv = tickers[tickers['CATEGORIA']== 'ETF RV']
    list_tickers_rv = list(tickers_rv['TICKER'])

    # rango de fechas
    start = '2024-01-01'
    end = '2024-12-31'

    # nivel de confianza
    confidence = 0.05

    for portafolio in [list_tickers_rf, list_tickers_rv]:
        print(portafolio)
      
      # obtener retornos
      df = portafolio_returns(tickers=portafolio, start=start, end=end)
      print(df.head(5))

      vector_w = np.array([1/len(portafolio)]*len(portafolio))
      print(vector_w)

      # calcular volatilidad
      sigma = portfolio_volatility(df=df, vector_w=vector_w)
      print(sigma)