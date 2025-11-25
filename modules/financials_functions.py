from tracemalloc import start
import pandas as pd
import numpy as np
import scipy.stats as stats
from .backend import market_prices

def portfolio_volatility(
        df:pd.DataFrame,
        vector_w:np.array
        ) -> float:
    '''
    Calculo de la volatilidad de un portafolio
    de inversiones

    df (pd.Dataframe):
        Dataframe de retornos del portafolio
    vector_w (np.array)
        vector de pesos de los intrumentos del portafolio
    
    Return (float): volatilidad del portafolio
    '''
    
    # matriz varianza covarianza
    m_cov = df.cov()

    #vector transpuesto
    vector_w_t = np.array(vector_w)

    #varianza
    vector_cov = np.dot(m_cov, vector_w)
    varianza = np.dot(vector_w_t, vector_cov)

    # volatilidad
    vol = np.sqrt(varianza)
    return vol

def portafolio_returns(
        tickers: list,
        start: str,
        end: str
        )-> pd.DataFrame:
    '''
    Descarga desde la base de datos los 
    precios de los intrumentos indicados en el rango de fechas

    ticker (list):
        lista de nemos de instrumentos que componen 
        el portafolio

    Start (str): 
        fecha de inicio precios

    end (str):
        fecha de termino de precios
    Return (pd.Dataframe): 
        Dataframe de retornos diarios
    '''
    #descargar precios
    df= market_prices(
    start_date= start,
    end_date = end,
    tickers=tickers
    )

    #pivot retornos
    df_pivot = pd.pivot_table(
    data=df, 
    index = 'FECHA',
        columns = 'TICKER',
        values = 'PRECIO_CIERRE', 
        aggfunc= 'max'
        )
    
    df_pivot = df_pivot = df_pivot.pct_change().dropna()
    return df_pivot

def VaR(sigma:float, confidence: float)-> float:
    '''
    calculo del value at risk al nivel 
    confianza indicado. con supuesto de media cero
    '''

    #estadistico z al nivel de confianza
    z_score = stats.norm.ppf(confidence)

    #VaR
    var= z_score * sigma
    return var
