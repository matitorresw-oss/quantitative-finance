# Modelo Nexum

Modelo financiero del mandato (educación, propiedad, herencia) trabajado con Claude.

## Archivos

- `Modelo_Nexum.xlsx` — el modelo completo. Hojas relevantes agregadas/corregidas con Claude:
  - `03_LDI_Educacion` — corregida (faltaba el instrumento GOVZ/STRIPS).
  - `09_Optimizador_Cartera` — v3: núcleo pasivo (bonos TLH + SPY, con glide path) dedicado a Educación; satélite activo (Momentum acciones + BAB + Momentum commodities) dedicado a Propiedad + Herencia. Tiene un banner de PENDIENTES en la fila 4.
  - `10_Monte_Carlo` — resultados de viabilidad de los 3 objetivos (20.000 simulaciones), sensibilidad al buffer de capital, y las limitaciones/supuestos.

- `scripts/monte_carlo_objetivos.py` — simulación de Montecarlo (requiere `monthly_returns_all.csv`, incluido). Correr con `python monte_carlo_objetivos.py`.
- `scripts/descargar_datos_sp500.py` / `.R` — scripts para descargar membresía histórica point-in-time del S&P 500 y precios diarios (Wikipedia + Yahoo Finance). Requieren internet — correr en tu máquina, no en esta sesión de Claude.
- `scripts/diagnostico_tablas2.R` — diagnóstico para depurar el scraping de la tabla de cambios de Wikipedia (pendiente de terminar de resolver).

## Pendientes principales

1. Validar los pesos de `09_Optimizador_Cartera` con Solver real en Excel donde aplique (el núcleo pasivo usa un glide path dinámico que Solver no puede optimizar directamente — usar el script de Montecarlo para eso).
2. Confirmar con el cliente/IPS el buffer de capital del núcleo pasivo y el diseño del glide path.
3. Reemplazar las proxies ETF de Momentum/BAB por backtests point-in-time reales (requiere terminar los scripts de descarga).
4. Sumar TIPS (LTPZ/TIP/SCHP) al núcleo pasivo — mejor cobertura de inflación que bonos nominales para un pasivo en USD reales.
