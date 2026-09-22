# Start python3 tests/http_fixture.py first. Docker tests use --network host.
source("R/brit_api.R")
for (attempt in seq_len(50)) {
  ready <- try(brit_http_json("http://127.0.0.1:18875/page2"), silent = TRUE)
  if (!inherits(ready, "try-error")) break
  Sys.sleep(0.1)
}
data <- brit_collections("http://127.0.0.1:18875")
stopifnot(nrow(data) == 2L, identical(data$nuts_or_lau_id, c("00123", "00456")),
          all(is.na(data$country)), data$connection_rate_2024[1] == 0,
          is.na(data$connection_rate_2024[2]), data$connection_rate_2024_unit[1] == "%")
error <- tryCatch(brit_http_json("http://127.0.0.1:18875/missing"), error = identity)
stopifnot(inherits(error, "error"), grepl("Deploy", conditionMessage(error)))
destination <- tempfile()
stopifnot(identical(brit_download_release("http://127.0.0.1:18875/release", destination), "http-test"))
downloaded <- read.csv2(file.path(destination, "data/raw/test.csv"))
stopifnot(downloaded$value == 0)
unlink(destination, recursive = TRUE)
cat("R HTTP integration tests passed\n")
