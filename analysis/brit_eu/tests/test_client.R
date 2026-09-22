# Run with Rscript tests/test_client.R from the analysis package directory.
source("R/brit_api.R")

expect_error <- function(expr, pattern) {
  result <- tryCatch({ force(expr); NULL }, error = identity)
  stopifnot(inherits(result, "error"), grepl(pattern, conditionMessage(result)))
}
pages <- list(
  list(schema_version = "1.0", count = 2, next_url = "https://example.org/page2",
       results = list(list(id = 1L, nuts_or_lau_id = "00123", connection_rate_2024 = 0, country = NULL))),
  list(schema_version = "1.0", count = 2, next_url = NULL,
       results = list(list(id = 2L, nuts_or_lau_id = "00456", specific_waste_collected_2024 = 42, country = NULL)))
)
for (i in seq_along(pages)) {
  pages[[i]]["next"] <- list(pages[[i]]$next_url)
  pages[[i]]$next_url <- NULL
}
fetch <- local({ i <- 0L; function(url, token) { i <<- i + 1L; pages[[i]] } })
data <- brit_collections("https://example.org", fetch = fetch)
stopifnot(nrow(data) == 2L, identical(data$nuts_or_lau_id, c("00123", "00456")),
          data$connection_rate_2024[1] == 0, is.na(data$connection_rate_2024[2]),
          data$specific_waste_collected_2024[2] == 42,
          "country" %in% names(data), all(is.na(data$country)))
expect_error(brit_collections("https://example.org", fetch = function(...) {
  page <- pages[[1]]; page$schema_version <- "2.0"; page
}), "schema")
expect_error(brit_collections("https://example.org", token = "private-token", fetch = function(...) {
  page <- pages[[1]]; page[["next"]] <- "https://evil.invalid/page2"; page
}), "origin")
expect_error(brit_collections("https://example.org", fetch = function(...) pages[[1]]), "Repeated|Duplicate")
expect_error(brit_collections("https://example.org", fetch = function(...) {
  page <- pages[[2]]; page$count <- 3; page
}), "count")
empty <- brit_collections("https://example.org", fetch = function(...) {
  list(schema_version = "1.0", count = 0, results = list())
})
stopifnot(nrow(empty) == 0L)
path <- tempfile(fileext = ".rds")
brit_save_snapshot(data, path)
reloaded <- brit_read_snapshot(path)
stopifnot(identical(data, reloaded))
writeBin(as.raw(0), path)
expect_error(brit_read_snapshot(path), "checksum")
unlink(c(path, paste0(path, ".json")))
cat("R client contract tests passed\n")
