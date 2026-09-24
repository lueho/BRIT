# Start python3 tests/http_fixture.py before this integration test.
options(brit_eu.autorun = FALSE)
source("BRIT_Datenanalyse.R")

expect_error <- function(expr, pattern) {
  result <- tryCatch({ force(expr); NULL }, error = identity)
  stopifnot(inherits(result, "error"), grepl(pattern, conditionMessage(result)))
}

base <- "http://127.0.0.1:18875"
for (attempt in seq_len(50)) {
  ready <- try(brit_eu_json(paste0(base, "/page2")), silent = TRUE)
  if (!inherits(ready, "try-error")) break
  Sys.sleep(0.1)
}
token <- brit_eu_login(base, "demo", "päss&word")
stopifnot(identical(token, "fixture-secret"))
expect_error(brit_eu_login(base, "demo", "wrong-secret"), "Anmeldung|credentials")
expect_error(brit_eu_login("http://example.org", "demo", "secret"), "HTTPS")
expect_error(brit_eu_json(paste0(base, "/server-error")), "Listenansicht.*fehlt")

data <- brit_eu_collections(base, list(scope = "private"), token)
stopifnot(nrow(data) == 2L, identical(data$nuts_or_lau_id, c("00123", "00456")),
          is.numeric(data$connection_rate_2024), data$connection_rate_2024[1] == 0,
          is.na(data$connection_rate_2024[2]), "country" %in% names(data),
          all(is.na(data$country)))
expect_error(brit_eu_collections(base, list(scope = "private"), "invalid"), "HTTP 401")
all_visible <- brit_eu_collections(base, list(scope = "all"), token)
stopifnot(nrow(all_visible) == 2L)

dir <- tempfile()
dir.create(dir)
files <- brit_eu_save(data, dir, list(scope = "private"))
stopifnot(file.exists(files$csv), file.exists(files$rds), file.exists(files$metadata),
          identical(readRDS(files$rds), data))
metadata <- paste(readLines(files$metadata, warn = FALSE), collapse = "")
stopifnot(!grepl("päss&word|fixture-secret|wrong-secret", metadata),
          grepl("sha256", metadata, fixed = TRUE))
unlink(dir, recursive = TRUE)

BRIT_URL <- base
FILTER <- list(scope = "all")
ERGEBNISORDNER <- tempfile()
invisible(brit_eu_main(username = "demo", password = "päss&word"))
stopifnot(length(list.files(ERGEBNISORDNER, pattern = "\\.csv$")) >= 1L,
          length(list.files(ERGEBNISORDNER, pattern = "\\.rds$")) == 1L)
unlink(ERGEBNISORDNER, recursive = TRUE)
cat("Standalone BRIT download test passed\n")
