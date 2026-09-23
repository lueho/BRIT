# Public BRIT analysis API client. Tokens are read from the environment, never saved.
brit_origin <- function(url) {
  if (!grepl("^https?://[^/?#]+(?:/|$)", url, perl = TRUE)) stop("Expected an absolute HTTP(S) URL")
  tolower(sub("^(https?://[^/?#]+).*$", "\\1", url))
}

brit_http_json <- function(url, token = "") {
  handle <- curl::new_handle(timeout = 120, connecttimeout = 20, followlocation = FALSE)
  headers <- c(Accept = "application/json")
  if (nzchar(token)) headers <- c(headers, Authorization = paste("Token", token))
  curl::handle_setheaders(handle, .list = as.list(headers))
  for (attempt in seq_len(4)) {
    response <- curl::curl_fetch_memory(url, handle = handle)
    if (!response$status_code %in% c(429L, 502L, 503L, 504L) || attempt == 4L) break
    Sys.sleep(2^(attempt - 1))
  }
  if (response$status_code != 200L) {
    hint <- if (response$status_code == 404L) " Deploy BRIT's extended collection list first, or check BRIT_API_URL." else ""
    stop(sprintf("BRIT returned HTTP %d.%s", response$status_code, hint))
  }
  tryCatch(jsonlite::fromJSON(rawToChar(response$content), simplifyVector = FALSE),
           error = function(e) stop("BRIT response is not valid JSON"))
}

brit_collections <- function(base_url = Sys.getenv("BRIT_API_URL", "https://brit.bioresource-tools.net"),
                             filters = list(scope = "published"), page_size = 100L,
                             token = Sys.getenv("BRIT_API_TOKEN"), max_pages = 10000L,
                             fetch = brit_http_json) {
  base_url <- sub("/+$", "", base_url)
  origin <- brit_origin(base_url)
  if (nzchar(token) && !grepl("^https://", origin) &&
      !grepl("^http://(localhost|127\\.0\\.0\\.1)(:[0-9]+)?$", origin)) {
    stop("Use HTTPS for authenticated requests")
  }
  if (!is.list(filters) || is.null(names(filters))) stop("filters must be a named list")
  if (any(names(filters) %in% c("page", "page_size", "view", "token", "Authorization"))) {
    stop("Pagination, view and credentials must not be supplied as filters")
  }
  params <- c(list(view = "extended"), filters,
              list(page_size = min(200L, max(1L, as.integer(page_size)))))
  query <- unlist(lapply(names(params), function(key) {
    vapply(as.character(params[[key]]), function(value)
      paste0(utils::URLencode(key, reserved = TRUE), "=", utils::URLencode(value, reserved = TRUE)), "")
  }), use.names = FALSE)
  url <- paste0(base_url, "/waste_collection/api/collection/?", paste(query, collapse = "&"))
  initial_url <- url
  visited <- character(); rows <- list(); expected <- NULL
  started <- format(Sys.time(), tz = "UTC", usetz = TRUE)
  while (!is.null(url) && nzchar(url)) {
    if (brit_origin(url) != origin) stop("Pagination changed origin; request refused")
    if (url %in% visited) stop("Repeated pagination URL")
    if (length(visited) >= max_pages) stop("Maximum pages reached; incomplete result discarded")
    visited <- c(visited, url)
    page <- fetch(url, token)
    if (!identical(page$schema_version, "1.0")) stop("Unsupported or missing BRIT schema version")
    if (is.null(page$count) || !is.numeric(page$count) || length(page$count) != 1L || page$count < 0 ||
        is.null(page$results) || !is.list(page$results)) stop("Invalid paginated response")
    if (is.null(expected)) expected <- page$count
    if (page$count != expected) stop("Result count changed during download; retry and save a snapshot")
    rows <- c(rows, page$results)
    url <- page[["next"]]
  }
  # JSON null must remain a missing cell, including columns missing in every row.
  rows <- lapply(rows, function(row) lapply(row, function(value) if (is.null(value)) NA else value))
  data <- if (length(rows)) as.data.frame(dplyr::bind_rows(rows)) else data.frame()
  if (nrow(data) != expected) stop("Downloaded row count differs from API count")
  if (nrow(data) && (!"id" %in% names(data) || anyNA(data$id) || anyDuplicated(data$id))) {
    stop("Duplicate or missing collection identifiers")
  }
  attr(data, "brit_provenance") <- list(
    schema_version = "1.0", request_url = initial_url, filters = filters,
    download_started = started, download_finished = format(Sys.time(), tz = "UTC", usetz = TRUE),
    count = nrow(data), snapshot_isolation = FALSE,
    note = "Live paginated read; archive this result before publication. Not the historical factsheet dataset."
  )
  data
}

brit_save_snapshot <- function(data, path) {
  dir.create(dirname(path), recursive = TRUE, showWarnings = FALSE)
  saveRDS(data, path, version = 3)
  info <- list(sha256 = digest::digest(file = path, algo = "sha256"),
               provenance = attr(data, "brit_provenance"))
  jsonlite::write_json(info, paste0(path, ".json"), auto_unbox = TRUE, pretty = TRUE, null = "null")
  invisible(path)
}

brit_read_snapshot <- function(path) {
  info <- jsonlite::read_json(paste0(path, ".json"))
  if (!identical(info$sha256, digest::digest(file = path, algo = "sha256"))) stop("Snapshot checksum mismatch")
  readRDS(path)
}

brit_download_release <- function(base_url, destination = ".") {
  # Optional: use the same immutable release hosted on an ordinary HTTPS server.
  # The distributed ZIP already includes these files, so this is not needed offline.
  brit_origin(base_url)
  manifest <- brit_http_json(paste0(sub("/+$", "", base_url), "/data/manifest.json"))
  if (!identical(manifest$schema_version, "1.0")) stop("Unsupported release schema")
  for (file in manifest$files) {
    if (!grepl("^data/(raw|reference)/", file$path) || grepl("(^|/)\\.\\.(/|$)|[\\\\?#]", file$path)) stop("Unsafe release path")
    target <- file.path(destination, file$path)
    dir.create(dirname(target), recursive = TRUE, showWarnings = FALSE)
    url <- paste0(sub("/+$", "", base_url), "/", utils::URLencode(file$path, reserved = FALSE))
    tmp <- tempfile(tmpdir = dirname(target))
    tryCatch({
      curl::curl_download(url, tmp, quiet = TRUE)
      if (!identical(digest::digest(file = tmp, algo = "sha256"), file$sha256)) stop("Release checksum mismatch")
      if (!file.copy(tmp, target, overwrite = TRUE)) stop("Cannot save release file")
    }, finally = unlink(tmp))
  }
  dir.create(file.path(destination, "data"), recursive = TRUE, showWarnings = FALSE)
  jsonlite::write_json(manifest, file.path(destination, "data/manifest.json"), auto_unbox = TRUE, pretty = TRUE)
  invisible(manifest$release_id)
}
