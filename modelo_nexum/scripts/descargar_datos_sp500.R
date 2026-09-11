# Modelo Nexum - descarga de datos point-in-time para el backtest accionario
# de Equity Momentum y Betting Against Beta (BAB).
#
# Corre esto en TU computador (necesita internet). Genera los mismos 4
# archivos que la version en Python; subime los que te queden y construyo
# el backtest real de Momentum/BAB con eso.
#
# install.packages(c("rvest","dplyr","purrr","lubridate","stringr","readr","tidyquant","arrow"))
#
# Rscript descargar_datos_sp500.R

library(rvest)
library(dplyr)
library(purrr)
library(lubridate)
library(stringr)
library(readr)
library(tidyquant)
library(arrow)

START_DATE  <- as.Date("2011-01-01")   # mismo inicio que el resto del modelo
END_DATE    <- Sys.Date()
CACHE_DIR   <- "cache_precios"
PAUSE_SECS  <- 0.3

WIKI_URL <- "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"

fetch_wiki_tables <- function() {
  page <- read_html(WIKI_URL)
  tables <- html_table(page, fill = TRUE)
  list(current = tables[[1]], changes = tables[[2]])
}

normalize_changes <- function(changes) {
  cat("   [diagnostico] columnas crudas de la tabla de cambios:\n")
  print(names(changes))

  names(changes) <- make.unique(gsub("\\s+", "_", names(changes)))
  date_col    <- names(changes)[str_detect(names(changes), regex("Date", ignore_case = TRUE))][1]
  added_col   <- names(changes)[str_detect(names(changes), regex("Added",   ignore_case = TRUE)) & str_detect(names(changes), regex("Ticker", ignore_case = TRUE))][1]
  removed_col <- names(changes)[str_detect(names(changes), regex("Removed", ignore_case = TRUE)) & str_detect(names(changes), regex("Ticker", ignore_case = TRUE))][1]

  # Respaldo: rvest a veces no antepone el encabezado padre (Added/Removed) a
  # las columnas hijas (Ticker/Security), y la busqueda por texto falla.
  # En ese caso la tabla de Wikipedia trae, en orden posicional:
  # Date, Added-Ticker, Added-Security, Removed-Ticker, Removed-Security, Reason
  if (is.na(date_col) || is.na(added_col) || is.na(removed_col)) {
    cat("   [aviso] no encontre las columnas por nombre; uso posicion (1=Date, 2=Added Ticker, 4=Removed Ticker)\n")
    if (ncol(changes) < 4) stop("La tabla de cambios tiene menos columnas de las esperadas; revisa 'names(changes)' arriba y avisale a Claude.")
    date_col    <- names(changes)[1]
    added_col   <- names(changes)[2]
    removed_col <- names(changes)[4]
  }

  tibble(
    date           = mdy(changes[[date_col]]),
    added_ticker   = changes[[added_col]],
    removed_ticker = changes[[removed_col]]
  ) %>%
    filter(!is.na(date)) %>%
    arrange(date)
}

build_universe <- function(current_tickers, changes, start_date) {
  relevant <- changes %>% filter(date >= start_date)
  ever <- union(current_tickers, union(na.omit(relevant$added_ticker), na.omit(relevant$removed_ticker)))
  ever <- str_replace_all(ever, "\\.", "-")
  sort(unique(ever))
}

membership_snapshot <- function(current_tickers, changes, as_of) {
  tickers <- current_tickers
  chg <- changes %>% filter(date > as_of) %>% arrange(desc(date))
  if (nrow(chg) > 0) {
    for (i in seq_len(nrow(chg))) {
      if (!is.na(chg$added_ticker[i]))   tickers <- setdiff(tickers, chg$added_ticker[i])
      if (!is.na(chg$removed_ticker[i])) tickers <- union(tickers, chg$removed_ticker[i])
    }
  }
  tickers
}

build_membership_table <- function(current_tickers, changes, start_date, end_date) {
  months <- seq(as.Date(start_date), as.Date(end_date), by = "month")
  map_dfr(months, function(m) {
    snap <- membership_snapshot(current_tickers, changes, m)
    tibble(month = m, ticker = str_replace_all(snap, "\\.", "-"))
  })
}

download_prices <- function(tickers, start_date, end_date) {
  dir.create(CACHE_DIR, showWarnings = FALSE)
  cache_files <- file.path(CACHE_DIR, paste0(tickers, ".parquet"))
  pending <- tickers[!file.exists(cache_files)]
  cat(sprintf("%d tickers totales, %d pendientes de descargar\n", length(tickers), length(pending)))

  for (t in pending) {
    res <- tryCatch(
      tq_get(t, from = start_date, to = end_date, get = "stock.prices"),
      error = function(e) NULL
    )
    if (is.null(res) || nrow(res) == 0) {
      cat(sprintf("  %s: sin datos\n", t))
      next
    }
    out <- res %>% transmute(date, adj_close = adjusted, volume, ticker = t)
    write_parquet(out, file.path(CACHE_DIR, paste0(t, ".parquet")))
    cat(sprintf("  %s: %d filas\n", t, nrow(out)))
    Sys.sleep(PAUSE_SECS)
  }

  files <- file.path(CACHE_DIR, paste0(tickers, ".parquet"))
  files <- files[file.exists(files)]
  if (length(files) == 0) stop("No se descargo ningun ticker")
  map_dfr(files, read_parquet)
}

main <- function() {
  cat("1/4 - Descargando tablas de Wikipedia (constituyentes y cambios historicos)...\n")
  wiki <- fetch_wiki_tables()
  write_csv(wiki$current, "sp500_constituyentes_actuales.csv")
  changes <- normalize_changes(wiki$changes)
  write_csv(changes, "sp500_cambios_historicos.csv")
  cat(sprintf("   %d constituyentes actuales, %d eventos de cambio\n", nrow(wiki$current), nrow(changes)))

  cat("2/4 - Reconstruyendo universo de tickers relevante desde", format(START_DATE), "...\n")
  current_tickers <- wiki$current$Symbol
  universe <- build_universe(current_tickers, changes, START_DATE)
  cat(sprintf("   %d tickers distintos estuvieron en el indice en la ventana\n", length(universe)))

  cat("3/4 - Generando tabla de pertenencia mensual (point-in-time)...\n")
  membership <- build_membership_table(current_tickers, changes, START_DATE, END_DATE)
  write_csv(membership, "sp500_membresia_mensual.csv")
  cat(sprintf("   %d filas (ticker-mes)\n", nrow(membership)))

  cat("4/4 - Descargando precios y volumen diarios (esto puede tardar bastante)...\n")
  prices <- download_prices(universe, START_DATE, END_DATE)
  write_parquet(prices, "sp500_precios_volumen.parquet")
  cat(sprintf("Listo: sp500_precios_volumen.parquet (%d filas)\n", nrow(prices)))

  cat("\nSube estos archivos de vuelta a Claude:\n")
  cat("  - sp500_constituyentes_actuales.csv\n")
  cat("  - sp500_cambios_historicos.csv\n")
  cat("  - sp500_membresia_mensual.csv\n")
  cat("  - sp500_precios_volumen.parquet\n")
}

main()
