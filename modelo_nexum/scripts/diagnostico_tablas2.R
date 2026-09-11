library(rvest)
library(stringr)

WIKI_URL <- "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
page <- read_html(WIKI_URL)

raw_tables <- html_elements(page, "table")
cat(sprintf("html_elements() encontro %d elementos <table> en la pagina\n\n", length(raw_tables)))

for (i in seq_along(raw_tables)) {
  tbl <- raw_tables[[i]]
  cls <- html_attr(tbl, "class")
  id  <- html_attr(tbl, "id")
  header_text <- tbl %>% html_elements("th") %>% html_text2() %>% head(8) %>% paste(collapse = " | ")
  nrows <- length(html_elements(tbl, "tr"))
  cat(sprintf("--- Tabla cruda %d --- id=%s class=%s filas=%d\n", i, id, cls, nrows))
  cat(sprintf("   encabezados: %s\n\n", header_text))
}

cat("\n--- Buscando encabezados de seccion que mencionen 'changes' o 'cambios' ---\n")
headings <- html_elements(page, "h2, h3")
for (h in headings) {
  txt <- html_text2(h)
  if (str_detect(str_to_lower(txt), "change")) {
    cat(" ->", txt, "\n")
  }
}
