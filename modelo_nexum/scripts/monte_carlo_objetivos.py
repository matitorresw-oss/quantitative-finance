"""
Modelo Nexum - simulacion de Montecarlo sobre viabilidad de objetivos (v3).

v3: nucleo pasivo (bonos TLH + SPY, con glide path que baja el riesgo a medida
que se acercan los pagos) dedicado 100% a Educacion; satelite activo (Momentum
acciones + BAB + Momentum commodities) dedicado 100% a Propiedad + Herencia,
financiado con los aportes anuales. Bootstrap de retornos mensuales historicos
(no normal parametrico) sobre ambos sub-carteras.

Todo en USD REALES (dinero de hoy): los retornos historicos (nominales) se
deflactan con el supuesto de inflacion de largo plazo del modelo
(00_Inputs!D71) antes de acumular/descontar flujos.

Requiere: pandas, numpy. Re-correr con datos propios reemplazando
monthly_returns_all.csv (generado a partir de 05_Datos_Historicos y
07_Backtest_CMD) una vez que existan backtests reales de Momentum/BAB o
datos de TIPS para el nucleo pasivo.
"""

import numpy as np
import pandas as pd

N_SIMS = 20_000
SEED = 777
INFLATION_ANNUAL = 0.02          # 00_Inputs!D71
MONTHLY_INFLATION = (1 + INFLATION_ANNUAL) ** (1 / 12) - 1

VP_PASIVO_EDUCACION = 92747.03454098242    # 02_TIR_Objetivos!I7
CAPITAL_TOTAL = 150000.0                    # 00_Inputs!D24
LDI_BUFFER = 1.30                           # 09_Optimizador_Cartera!D10 (PENDIENTE de confirmar con el cliente/IPS)
CAPITAL_NUCLEO = VP_PASIVO_EDUCACION * LDI_BUFFER
CAPITAL_SATELITE = CAPITAL_TOTAL - CAPITAL_NUCLEO

APORTE_ANUAL = 10000.0                # 00_Inputs!D25
N_APORTES = 19                        # 00_Inputs!D26
PAGO_EDUC = 14257.981727848033        # 00_Inputs!K33 = K34 (mismo monto)
VILLARRICA = 470385.0751834344        # 00_Inputs!J35
HERENCIA = 500000.0                   # 00_Inputs!J36

LDI_FORWARD_REAL_ANNUAL = 0.0256764705882353  # 00_Inputs!D72, tasa real de los bonos del nucleo

# Retorno real de SPY a usar en el nucleo pasivo. La ventana historica
# disponible (2011-2026) rindio ~12,3% real/año (mercado alcista excepcional);
# usarla directamente overestimaria la probabilidad de exito. 6,5% real/año es
# el promedio historico de largo plazo de EEUU (Damodaran/Siegel) y es la base
# recomendada para decidir. Cambiar a None para usar la media historica cruda.
SPY_REAL_ANNUAL = 0.065

# Glide path del nucleo pasivo: peso en SPY por año desde hoy (resto en TLH).
GLIDE_START_YEAR = 8    # hasta este año, peso maximo en SPY
GLIDE_END_YEAR = 13     # desde este año, peso minimo en SPY (ventana de pagos 14-20)
GLIDE_MAX_SPY = 0.80
GLIDE_MIN_SPY = 0.20

# Anio -> lista de pagos de educacion ese anio (Vicente 14-18, Emilia 16-20)
EDUCATION_SCHEDULE = {14: 1, 15: 1, 16: 2, 17: 2, 18: 2, 19: 1, 20: 1}

SATELITE_WEIGHTS = {"MOM_EQ": 0.5638, "BAB_EQ": 0.0512, "MOM_CMD": 0.3850}


def glide_equity_weight(year):
    if year <= GLIDE_START_YEAR:
        return GLIDE_MAX_SPY
    if year >= GLIDE_END_YEAR:
        return GLIDE_MIN_SPY
    step = (GLIDE_MAX_SPY - GLIDE_MIN_SPY) / (GLIDE_END_YEAR - GLIDE_START_YEAR)
    return GLIDE_MAX_SPY - step * (year - GLIDE_START_YEAR)


def deflate(nominal_monthly_returns):
    return (1 + nominal_monthly_returns) / (1 + MONTHLY_INFLATION) - 1


def load_nucleo_series():
    rets = pd.read_csv("monthly_returns_all.csv", index_col=0, parse_dates=True)
    nucleo = rets[["LDI_TSY", "EQ_CORE"]].dropna()
    bond_real = deflate(nucleo["LDI_TSY"].values)
    monthly_bond_target = (1 + LDI_FORWARD_REAL_ANNUAL) ** (1 / 12) - 1
    bond_real_fwd = bond_real - bond_real.mean() + monthly_bond_target

    spy_real = deflate(nucleo["EQ_CORE"].values)
    if SPY_REAL_ANNUAL is not None:
        monthly_spy_target = (1 + SPY_REAL_ANNUAL) ** (1 / 12) - 1
        spy_real = spy_real - spy_real.mean() + monthly_spy_target
    return bond_real_fwd, spy_real


def load_satelite_returns():
    rets = pd.read_csv("monthly_returns_all.csv", index_col=0, parse_dates=True)
    cols = ["MOM_EQ", "BAB_EQ", "MOM_CMD"]
    a = rets[cols].dropna()
    w = np.array([SATELITE_WEIGHTS[c] for c in cols])
    port_nominal = a.values @ w
    return deflate(port_nominal)


def simulate_nucleo(bond_real, spy_real, n_sims, rng):
    n_months = 20 * 12
    balance = np.full(n_sims, CAPITAL_NUCLEO)
    shortfall = np.zeros(n_sims)
    fully_funded = np.ones(n_sims, dtype=bool)
    n = len(bond_real)
    for month in range(1, n_months + 1):
        year = (month - 1) // 12
        we = glide_equity_weight(year)
        idx = rng.integers(0, n, size=n_sims)
        port_ret = we * spy_real[idx] + (1 - we) * bond_real[idx]
        balance *= (1 + port_ret)
        y = month // 12
        if month % 12 == 0 and y in EDUCATION_SCHEDULE:
            need = PAGO_EDUC * EDUCATION_SCHEDULE[y]
            short = np.maximum(need - balance, 0)
            shortfall += short
            fully_funded &= (short <= 1e-6)
            balance = np.maximum(balance - need, 0)
    return balance, shortfall, fully_funded


def simulate_satelite(monthly_returns, n_sims, rng):
    n_months = 50 * 12
    balance = np.full(n_sims, CAPITAL_SATELITE)
    pool = monthly_returns
    villarrica_ok = np.zeros(n_sims, dtype=bool)
    herencia_ok = np.zeros(n_sims, dtype=bool)
    villarrica_shortfall = np.zeros(n_sims)
    herencia_shortfall = np.zeros(n_sims)
    balance_before_25 = None
    for month in range(1, n_months + 1):
        idx = rng.integers(0, len(pool), size=n_sims)
        balance *= (1 + pool[idx])
        year = month // 12
        if month % 12 == 4 % 12 and 1 <= year <= N_APORTES:  # aporte de abril
            balance += APORTE_ANUAL
        if month == 25 * 12:
            balance_before_25 = balance.copy()
            short = np.maximum(VILLARRICA - balance, 0)
            villarrica_shortfall = short
            villarrica_ok = short <= 1e-6
            balance = np.maximum(balance - VILLARRICA, 0)
        if month == 50 * 12:
            short = np.maximum(HERENCIA - balance, 0)
            herencia_shortfall = short
            herencia_ok = short <= 1e-6
            balance = np.maximum(balance - HERENCIA, 0)
    return {
        "final_balance": balance,
        "balance_before_25": balance_before_25,
        "villarrica_ok": villarrica_ok,
        "herencia_ok": herencia_ok,
        "villarrica_shortfall": villarrica_shortfall,
        "herencia_shortfall": herencia_shortfall,
    }


def pct(x):
    return f"{100 * x:.1f}%"


def main():
    rng = np.random.default_rng(SEED)
    bond_real, spy_real = load_nucleo_series()
    satelite_rets = load_satelite_returns()

    print(f"Capital nucleo pasivo (Educacion): ${CAPITAL_NUCLEO:,.0f}  "
          f"(VP ${VP_PASIVO_EDUCACION:,.0f} x buffer {LDI_BUFFER:.2f})")
    print(f"Capital satelite activo (Propiedad+Herencia): ${CAPITAL_SATELITE:,.0f}")
    print(f"Retorno real SPY usado: {'media historica cruda' if SPY_REAL_ANNUAL is None else f'{SPY_REAL_ANNUAL*100:.1f}%/año (recentrado)'}")
    print(f"Simulaciones: {N_SIMS:,}\n")

    nucleo_balance, nucleo_shortfall, nucleo_ok = simulate_nucleo(bond_real, spy_real, N_SIMS, rng)
    satelite = simulate_satelite(satelite_rets, N_SIMS, rng)

    all_ok = nucleo_ok & satelite["villarrica_ok"] & satelite["herencia_ok"]

    print("=== RESULTADOS ===\n")
    print(f"Educacion (Vicente + Emilia) financiada en su totalidad: {pct(nucleo_ok.mean())}")
    if (~nucleo_ok).any():
        print(f"  Shortfall promedio cuando falla: ${nucleo_shortfall[~nucleo_ok].mean():,.0f}")
    print(f"  Percentil 10 / 50 / 90 del saldo final (tras ultimo pago): "
          f"${np.percentile(nucleo_balance,10):,.0f} / ${np.percentile(nucleo_balance,50):,.0f} / "
          f"${np.percentile(nucleo_balance,90):,.0f}\n")

    print(f"Propiedad Villarrica (año 25) financiada en su totalidad: {pct(satelite['villarrica_ok'].mean())}")
    vs = satelite["villarrica_shortfall"]
    if (vs > 0).any():
        print(f"  Shortfall promedio cuando falla: ${vs[vs>0].mean():,.0f}")
    b25 = satelite["balance_before_25"]
    print(f"  Percentil 10 / 50 / 90 del saldo en año 25 (antes de pagar, necesita ${VILLARRICA:,.0f}): "
          f"${np.percentile(b25,10):,.0f} / ${np.percentile(b25,50):,.0f} / ${np.percentile(b25,90):,.0f}\n")

    print(f"Herencia (año 50) financiada en su totalidad: {pct(satelite['herencia_ok'].mean())}")
    hs = satelite["herencia_shortfall"]
    if (hs > 0).any():
        print(f"  Shortfall promedio cuando falla: ${hs[hs>0].mean():,.0f}")
    print(f"  Percentil 10 / 50 / 90 del saldo final (año 50): "
          f"${np.percentile(satelite['final_balance'],10):,.0f} / "
          f"${np.percentile(satelite['final_balance'],50):,.0f} / "
          f"${np.percentile(satelite['final_balance'],90):,.0f}\n")

    print(f"LOS TRES OBJETIVOS CUMPLIDOS EN SU TOTALIDAD: {pct(all_ok.mean())}")

    out = pd.DataFrame({
        "nucleo_balance_final": nucleo_balance,
        "nucleo_shortfall": nucleo_shortfall,
        "educacion_ok": nucleo_ok,
        "satelite_balance_25": satelite["balance_before_25"],
        "villarrica_ok": satelite["villarrica_ok"],
        "villarrica_shortfall": satelite["villarrica_shortfall"],
        "satelite_balance_final": satelite["final_balance"],
        "herencia_ok": satelite["herencia_ok"],
        "herencia_shortfall": satelite["herencia_shortfall"],
        "todos_ok": all_ok,
    })
    out.to_csv("monte_carlo_resultados.csv", index=False)
    print("\nDetalle de las simulaciones guardado en monte_carlo_resultados.csv")


if __name__ == "__main__":
    main()
