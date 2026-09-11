# Proyecto Nexum

Modelo financiero del mandato (Educación, Propiedad, Herencia) trabajado con Claude.

## Estructura

- **`Excel/`** — `Modelo_Nexum.xlsx`, el modelo completo. Hojas agregadas/corregidas con Claude:
  - `03_LDI_Educacion` — corregida (faltaba el instrumento GOVZ/STRIPS) y actualizada con la estrategia de calce exacto.
  - `09_Optimizador_Cartera` (v4) — Educación se financia con un **calce exacto de bonos a vencimiento** (determinístico, sección 2a) en vez de una cartera marcada a mercado; el **satélite activo** (Momentum acciones + BAB + Momentum commodities) financia Propiedad y Herencia (sección 3). Banner de PENDIENTES en la fila 4.
  - `10_Monte_Carlo` — resultados de viabilidad: Educación ~100% (calce exacto), Propiedad/Herencia ~99%+ (satélite activo, Montecarlo de 20.000 simulaciones), más un "Plan B" (ETF + glide path) por si el calce exacto no es viable en la práctica.

- **`Testing/`** — scripts para descargar datos point-in-time del S&P 500 (membresía histórica + precios diarios, vía Wikipedia + Yahoo Finance) y depurar el scraping. Requieren internet — correr en tu máquina.
  - `descargar_datos_sp500.py` / `.R`
  - `diagnostico_tablas2.R` — diagnóstico para la tabla de cambios de Wikipedia (scraping pendiente de terminar de resolver).

- **`MonteCarlo/`** — `monte_carlo_objetivos.py`, la simulación de viabilidad de los 3 objetivos. Correr con `python monte_carlo_objetivos.py` (requiere `monthly_returns_all.csv`, incluido). `monte_carlo_resultados.csv` es la salida de la última corrida.

## Por qué Educación se calza distinto a Propiedad/Herencia

Educación es la prioridad 1 del IPS y tiene el horizonte más corto (primer pago en el año 14). Un objetivo así **no debe depender de acertar retornos de mercado** — se financia comprando bonos (idealmente TIPS) que vencen exactamente en cada fecha de pago y manteniéndolos hasta el vencimiento: la volatilidad de precio en el camino no importa porque no se venden antes. Esto da una probabilidad de éxito ≈100%, coherente con ser el objetivo más importante.

Propiedad y Herencia (prioridades 2-3, horizontes de 25 y 50 años) sí buscan crecimiento, así que se financian con el satélite activo — que tiene riesgo de mercado real, mitigado por el horizonte largo y los aportes anuales constantes.

## Pendientes principales

1. Confirmar en la plataforma (StockTrak, `00_Inputs!D47`) que existan bonos/TIPS con los vencimientos exactos necesarios (2029-2035) y suficiente liquidez.
2. Sumar TIPS reales al calce de Educación cuando haya datos — mejor cobertura de inflación que bonos nominales para un pasivo en USD reales.
3. Validar los pesos del satélite activo con Solver real en Excel (`09_Optimizador_Cartera`, sección 5).
4. Reemplazar las proxies ETF de Momentum/BAB por backtests point-in-time reales (terminar los scripts de `Testing/`).
