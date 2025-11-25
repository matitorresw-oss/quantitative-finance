"""
Clase Database que maneja la conexion a una base de datos SQLite.
Incluye metodos para conectar, crear tablas, insertar y consultar datos.

crea una segunda clase DB_Investments que hereda de Database,  que inicialice
la conexion a la base de datos "backend/db_investments.db", y que tenga un método:
-   execute_query(query: str) -> pd.DataFrame: que ejecute una consulta SQL y retorne los resultados como un DataFrame de pandas.

"""

import sqlite3
import pandas as pd
from typing import List, Dict, Any, Optional, Union
import logging
from contextlib import contextmanager

class Database:
    """Clase para manejar operaciones con base de datos SQLite."""
    
    def __init__(self, db_path: str):
        """Inicializa la clase Database."""
        self.db_path = db_path
        self.connection = None
        self.logger = logging.getLogger(__name__)
        logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    
    def connect(self) -> bool:
        """Conecta a la base de datos SQLite."""
        try:
            self.connection = sqlite3.connect(self.db_path)
            self.connection.row_factory = sqlite3.Row
            self.logger.info(f"Conexion exitosa a la base de datos: {self.db_path}")
            return True
        except sqlite3.Error as e:
            self.logger.error(f"Error al conectar a la base de datos: {e}")
            return False
    
    def disconnect(self) -> None:
        """Cierra la conexion a la base de datos."""
        if self.connection:
            self.connection.close()
            self.connection = None
            self.logger.info("Conexion a la base de datos cerrada")
    
    @contextmanager
    def get_cursor(self):
        """Context manager para manejo seguro de cursores."""
        if not self.connection:
            raise RuntimeError("No hay conexion activa a la base de datos")
        
        cursor = self.connection.cursor()
        try:
            yield cursor
        finally:
            cursor.close()
    
    def create_table(self, table_name: str, schema: str) -> bool:
        """Crea una tabla si no existe."""
        try:
            with self.get_cursor() as cursor:
                query = f"CREATE TABLE IF NOT EXISTS {table_name} ({schema})"
                cursor.execute(query)
                self.connection.commit()
                self.logger.info(f"Tabla '{table_name}' creada o verificada exitosamente")
                return True
        except sqlite3.Error as e:
            self.logger.error(f"Error al crear la tabla '{table_name}': {e}")
            return False
    
    def insert_data(self, table_name: str, data: Union[Dict[str, Any], List[Dict[str, Any]]], 
                    replace_on_conflict: bool = False) -> bool:
        """Inserta datos en una tabla."""
        try:
            if isinstance(data, dict):
                data = [data]
            
            if not data:
                self.logger.warning("No hay datos para insertar")
                return True
            
            columns = list(data[0].keys())
            placeholders = ', '.join(['?' for _ in columns])
            
            insert_type = "INSERT OR REPLACE" if replace_on_conflict else "INSERT"
            query = f"{insert_type} INTO {table_name} ({', '.join(columns)}) VALUES ({placeholders})"
            
            values = [[row[col] for col in columns] for row in data]
            
            with self.get_cursor() as cursor:
                cursor.executemany(query, values)
                self.connection.commit()
                
            self.logger.info(f"Insertados {len(data)} registros en la tabla '{table_name}'")
            return True
            
        except sqlite3.Error as e:
            self.logger.error(f"Error al insertar datos en '{table_name}': {e}")
            return False
    
    def query_data(self, query: str, params: Optional[tuple] = None, 
                   return_dataframe: bool = False) -> Union[List[sqlite3.Row], pd.DataFrame, None]:
        """Consulta datos de la base de datos."""
        try:
            if return_dataframe:
                return pd.read_sql_query(query, self.connection, params=params)
            else:
                with self.get_cursor() as cursor:
                    if params:
                        cursor.execute(query, params)
                    else:
                        cursor.execute(query)
                    results = cursor.fetchall()
                    self.logger.info(f"Consulta ejecutada: {len(results)} registros encontrados")
                    return results
                    
        except sqlite3.Error as e:
            self.logger.error(f"Error en la consulta: {e}")
            return None
        except Exception as e:
            self.logger.error(f"Error inesperado en la consulta: {e}")
            return None
    
    def execute_query(self, query: str, params: Optional[tuple] = None) -> bool:
        """Ejecuta una consulta SQL (INSERT, UPDATE, DELETE)."""
        try:
            with self.get_cursor() as cursor:
                if params:
                    cursor.execute(query, params)
                else:
                    cursor.execute(query)
                self.connection.commit()
                self.logger.info(f"Consulta ejecutada exitosamente. Filas afectadas: {cursor.rowcount}")
                return True
                
        except sqlite3.Error as e:
            self.logger.error(f"Error al ejecutar la consulta: {e}")
            return False
    
    def get_table_info(self, table_name: str) -> Optional[List[sqlite3.Row]]:
        """Obtiene informacion sobre la estructura de una tabla."""
        return self.query_data(f"PRAGMA table_info({table_name})")
    
    def table_exists(self, table_name: str) -> bool:
        """Verifica si una tabla existe en la base de datos."""
        query = "SELECT name FROM sqlite_master WHERE type='table' AND name=?"
        result = self.query_data(query, (table_name,))
        return len(result) > 0 if result else False
    
    def get_record_count(self, table_name: str, condition: str = "") -> Optional[int]:
        """Obtiene el numero de registros en una tabla."""
        query = f"SELECT COUNT(*) FROM {table_name}"
        if condition:
            query += f" WHERE {condition}"
        
        result = self.query_data(query)
        return result[0][0] if result else None
    
    def backup_table(self, table_name: str, backup_path: str) -> bool:
        """Crea un respaldo de una tabla en un archivo CSV."""
        try:
            df = self.query_data(f"SELECT * FROM {table_name}", return_dataframe=True)
            if df is not None:
                df.to_csv(backup_path, index=False)
                self.logger.info(f"Respaldo de la tabla '{table_name}' creado en: {backup_path}")
                return True
            return False
        except Exception as e:
            self.logger.error(f"Error al crear respaldo de '{table_name}': {e}")
            return False
    
    def __enter__(self):
        """Context manager entry."""
        self.connect()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.disconnect()
    
    def __del__(self):
        """Destructor para asegurar que la conexion se cierre."""
        if hasattr(self, 'connection'):
            self.disconnect()


class DB_Investments(Database):
    """Clase especializada para manejar la base de datos de inversiones."""
    
    def __init__(self):
        """Inicializa la conexion a la base de datos de inversiones."""
        super().__init__("backend/db_investments.db")
    
    def execute_query(self, query: str) -> pd.DataFrame:
        """
        Ejecuta una consulta SQL y retorna los resultados como un DataFrame de pandas.
        
        Args:
            query (str): Consulta SQL a ejecutar
            
        Returns:
            pd.DataFrame: Resultados de la consulta como DataFrame
            
        Raises:
            RuntimeError: Si no hay conexion activa
            Exception: Si hay error en la consulta
        """
        if not self.connection:
            if not self.connect():
                raise RuntimeError("No se pudo establecer conexion con la base de datos")
        
        try:
            df = pd.read_sql_query(query, self.connection)
            self.logger.info(f"Consulta ejecutada exitosamente. Filas retornadas: {len(df)}")
            return df
        except Exception as e:
            self.logger.error(f"Error al ejecutar la consulta: {e}")
            raise e

def market_prices(start_date: str=None, end_date: str=None, tickers: list=None) -> pd.DataFrame:
    """Obtiene los precios de mercado para los tickers dados en el rango de fechas especificado.
    
    Args:
        start_date (str): Fecha de inicio en formato 'YYYY-MM-DD'
        end_date (str): Fecha de fin en formato 'YYYY-MM-DD'
        tickers (list): Lista de tickers para los cuales obtener los precios
        
    Returns:
        pd.DataFrame: DataFrame con los precios de mercado
    """
    query = f"""
    SELECT 
    FT.FECHA, FT.TICKER, DM.EMISOR, FT.PRECIO_CIERRE, DM.SECTOR, DM.MONEDA, DM.TIPO
    FROM FT_PRICES FT
    LEFT JOIN DM_INSTRUMENTOS DM ON FT.TICKER = DM.TICKER
    WHERE FT.FECHA >= '{start_date}' AND FT.FECHA <= '{end_date}'
    AND FT.TICKER IN {tuple(tickers)}
    """
    
    db = DB_Investments()
    df = db.execute_query(query)
    
    return df
