# BRIT-EU: eine Datei fuer den Abruf und die eigene Auswertung aktueller BRIT-Daten.
# In RStudio oeffnen und "Source" waehlen oder mit Rscript BRIT_Datenanalyse.R starten.
# Benutzername und Passwort werden beim Start abgefragt und nicht gespeichert.
# Fuer eigene Fragestellungen nur FILTER und die Auswertung am Ende anpassen.

BRIT_URL <- "https://brit.bioresource-tools.net"
FILTER <- list(scope = "all") # Alle fuer das eigene Konto sichtbaren Daten, ggf. auch private.
ERGEBNISORDNER <- "BRIT_Ergebnisse"
PAKETSTAND <- "https://packagemanager.posit.co/cran/2024-04-15"

brit_eu_packages <- function() {
  needed <- c("curl", "jsonlite", "digest", "askpass")
  missing <- needed[!vapply(needed, requireNamespace, logical(1), quietly = TRUE)]
  if (length(missing)) {
    user_library <- Sys.getenv("R_LIBS_USER")
    if (!nzchar(user_library)) user_library <- file.path(path.expand("~"), "R", "BRIT-library")
    dir.create(user_library, recursive = TRUE, showWarnings = FALSE)
    if (!dir.exists(user_library)) stop("Keine beschreibbare R-Paketbibliothek vorhanden.")
    .libPaths(c(user_library, .libPaths()))
    message("Installiere beim ersten Start die benoetigten R-Pakete: ", paste(missing, collapse = ", "))
    install.packages(missing, lib = user_library, repos = PAKETSTAND)
  }
  if (!all(vapply(needed, requireNamespace, logical(1), quietly = TRUE))) {
    stop("R-Pakete konnten nicht installiert werden. Bitte Internetzugang und Schreibrechte pruefen.")
  }
}

brit_eu_base <- function(base_url) {
  base_url <- sub("/+$", "", base_url)
  if (!grepl("^https?://[^/?#@]+$", base_url)) stop("BRIT_URL muss eine Serveradresse ohne Pfad sein.")
  if (!grepl("^https://", base_url) &&
      !grepl("^http://(localhost|127\\.0\\.0\\.1)(:[0-9]+)?$", base_url)) {
    stop("Fuer die Anmeldung ist HTTPS erforderlich (Ausnahme: lokaler Testserver).")
  }
  base_url
}

brit_eu_json <- function(url, token = "", form = NULL) {
  handle <- curl::new_handle(timeout = 120, connecttimeout = 20, followlocation = FALSE)
  headers <- c(Accept = "application/json")
  if (nzchar(token)) headers <- c(headers, Authorization = paste("Token", token))
  if (!is.null(form)) {
    headers <- c(headers, `Content-Type` = "application/x-www-form-urlencoded")
    body <- paste(vapply(names(form), function(name) {
      paste0(utils::URLencode(name, reserved = TRUE), "=",
             utils::URLencode(as.character(form[[name]]), reserved = TRUE))
    }, ""), collapse = "&")
    curl::handle_setopt(handle, post = TRUE, postfields = body)
  }
  curl::handle_setheaders(handle, .list = as.list(headers))
  response <- curl::curl_fetch_memory(url, handle = handle)
  if (response$status_code != 200L) {
    if (!is.null(form)) stop("BRIT-Anmeldung fehlgeschlagen (HTTP ", response$status_code, ").")
    hint <- if (response$status_code %in% c(404L, 500L)) {
      " Die erweiterte Listenansicht fehlt auf dieser Instanz moeglicherweise; bei HTTP 500 kann auch ein Serverfehler vorliegen."
    } else ""
    stop("BRIT-Datenabruf fehlgeschlagen (HTTP ", response$status_code, ").", hint)
  }
  tryCatch(jsonlite::fromJSON(rawToChar(response$content), simplifyVector = FALSE),
           error = function(e) stop("BRIT hat keine gueltige JSON-Antwort gesendet."))
}

brit_eu_login <- function(base_url, username, password) {
  base_url <- brit_eu_base(base_url)
  if (length(username) != 1L || length(password) != 1L || is.na(username) ||
      is.na(password) || !nzchar(username) || !nzchar(password)) {
    stop("Benutzername und Passwort sind erforderlich.")
  }
  reply <- brit_eu_json(paste0(base_url, "/api-token-auth/"),
                        form = list(username = username, password = password))
  if (!is.character(reply$token) || length(reply$token) != 1L || !nzchar(reply$token)) {
    stop("BRIT hat kein API-Token zurueckgegeben.")
  }
  reply$token
}

brit_eu_column <- function(rows, field) {
  values <- lapply(rows, function(row) row[[field]])
  nonmissing <- Filter(Negate(is.null), values)
  scalar <- function(x) is.atomic(x) && length(x) == 1L
  if (length(nonmissing) && all(vapply(nonmissing, function(x) scalar(x) && is.numeric(x), logical(1)))) {
    return(vapply(values, function(x) if (is.null(x)) NA_real_ else as.numeric(x), numeric(1)))
  }
  if (length(nonmissing) && all(vapply(nonmissing, function(x) scalar(x) && is.logical(x), logical(1)))) {
    return(vapply(values, function(x) if (is.null(x)) NA else as.logical(x), logical(1)))
  }
  vapply(values, function(x) {
    if (is.null(x)) return(NA_character_)
    if (scalar(x)) return(as.character(x))
    as.character(jsonlite::toJSON(x, auto_unbox = TRUE, null = "null"))
  }, "")
}

brit_eu_collections <- function(base_url, filters, token, page_size = 200L, max_pages = 10000L) {
  base_url <- brit_eu_base(base_url)
  if (!is.list(filters) || is.null(names(filters)) || any(!nzchar(names(filters))) ||
      any(names(filters) %in% c("page", "page_size", "view", "token", "Authorization"))) {
    stop("FILTER muss eine benannte Liste gueltiger BRIT-Filter sein.")
  }
  params <- c(list(view = "extended"), filters,
              list(page_size = min(200L, max(1L, as.integer(page_size)))))
  query <- unlist(lapply(names(params), function(name) {
    vapply(as.character(params[[name]]), function(value) {
      paste0(utils::URLencode(name, reserved = TRUE), "=",
             utils::URLencode(value, reserved = TRUE))
    }, "")
  }), use.names = FALSE)
  url <- paste0(base_url, "/waste_collection/api/collection/?", paste(query, collapse = "&"))
  requested <- url
  visited <- character()
  rows <- list()
  count <- NULL
  while (!is.null(url) && nzchar(url)) {
    if (!startsWith(url, paste0(base_url, "/"))) stop("Seitenumbruch wechselte den BRIT-Server.")
    if (url %in% visited || length(visited) >= max_pages) stop("Seitenumbruch unvollstaendig oder wiederholt.")
    visited <- c(visited, url)
    page <- brit_eu_json(url, token = token)
    if (!identical(page$schema_version, "1.0") || is.null(page$count) ||
        is.null(page$results) || !is.list(page$results)) stop("BRIT-API-Schema unerwartet.")
    if (is.null(count)) count <- page$count
    if (page$count != count) stop("Datensatz wurde waehrend des Abrufs veraendert. Bitte erneut versuchen.")
    rows <- c(rows, page$results)
    url <- page[["next"]]
  }
  fields <- unique(unlist(lapply(rows, names), use.names = FALSE))
  data <- if (length(fields)) {
    columns <- setNames(lapply(fields, function(field) brit_eu_column(rows, field)), fields)
    as.data.frame(columns, stringsAsFactors = FALSE, optional = TRUE)
  } else data.frame()
  if (nrow(data) != count || (nrow(data) &&
      (!"id" %in% names(data) || anyNA(data$id) || anyDuplicated(data$id)))) {
    stop("Datensatz unvollstaendig oder mit doppelten IDs. Bitte erneut versuchen.")
  }
  attr(data, "brit_provenance") <- list(abruf_utc = format(Sys.time(), tz = "UTC", usetz = TRUE),
                                         anfrage = requested, filter = filters,
                                         anzahl = nrow(data), schema_version = "1.0",
                                         hinweis = "Live-Abruf; kein transaktionaler Snapshot und kein historischer Factsheet-Datenstand.")
  data
}

brit_eu_save <- function(data, output_dir, filters) {
  dir.create(output_dir, recursive = TRUE, showWarnings = FALSE)
  stem <- file.path(output_dir, paste0("BRIT-Sammlungen-", format(Sys.time(), "%Y%m%dT%H%M%SZ", tz = "UTC")))
  if (file.exists(paste0(stem, ".rds"))) stem <- paste0(stem, "-", sample.int(999999L, 1L))
  files <- list(csv = paste0(stem, ".csv"), rds = paste0(stem, ".rds"),
                metadata = paste0(stem, ".json"))
  saveRDS(data, files$rds, version = 3)
  utils::write.csv(data, files$csv, row.names = FALSE, na = "", fileEncoding = "UTF-8")
  metadata <- list(release = "BRIT-Live-API", abgerufen = attr(data, "brit_provenance"),
                   filter = filters, rds_sha256 = digest::digest(file = files$rds, algo = "sha256"),
                   csv_sha256 = digest::digest(file = files$csv, algo = "sha256"))
  jsonlite::write_json(metadata, files$metadata, auto_unbox = TRUE, pretty = TRUE, null = "null")
  files
}

brit_eu_password <- function(input = NULL) {
  if (.Platform$OS.type == "unix" && !interactive() && isatty(stdin()) && !is.null(input)) {
    status <- suppressWarnings(system("stty -echo < /dev/tty", ignore.stdout = TRUE,
                                      ignore.stderr = TRUE))
    if (status == 0L) {
      on.exit(system("stty echo < /dev/tty", ignore.stdout = TRUE,
                     ignore.stderr = TRUE))
      cat("BRIT-Passwort: ", file = stderr())
      answer <- readLines(input, n = 1L, warn = FALSE)
      cat("\n", file = stderr())
      if (length(answer) == 1L) return(answer)
      return(NULL)
    }
  }
  askpass::askpass("BRIT-Passwort: ")
}

brit_eu_main <- function(username = NULL, password = NULL) {
  if (getRversion() < "4.3.3") stop("Mindestens R 4.3.3 ist erforderlich.")
  brit_eu_packages()
  input <- if (!interactive()) file("stdin", open = "r") else NULL
  if (!is.null(input)) on.exit(close(input))
  if (is.null(username)) username <- if (interactive()) readline("BRIT-Benutzername: ") else {
    cat("BRIT-Benutzername: ")
    readLines(input, n = 1L, warn = FALSE)
  }
  if (is.null(password)) password <- brit_eu_password(input)
  if (is.null(password)) stop("Passworteingabe abgebrochen.")
  token <- brit_eu_login(BRIT_URL, username, password)
  rm(username, password)
  data <- brit_eu_collections(BRIT_URL, FILTER, token)
  rm(token)
  files <- brit_eu_save(data, ERGEBNISORDNER, FILTER)
  message(nrow(data), " Sammlungen gespeichert: ", normalizePath(files$csv))
  message("R-Objekt fuer eigene Analysen: ", normalizePath(files$rds))
  if (nrow(data) && all(c("country", "waste_category") %in% names(data))) {
    # Beispielauswertung: Anzahl der Sammlungen je Land und Abfallkategorie.
    summary <- as.data.frame(table(Land = data$country, Abfallkategorie = data$waste_category,
                                   useNA = "ifany"), stringsAsFactors = FALSE)
    names(summary)[3] <- "Sammlungen"
    summary <- summary[summary$Sammlungen > 0L, , drop = FALSE]
    print(summary)
    utils::write.csv(summary, file.path(ERGEBNISORDNER, "Zusammenfassung.csv"),
                     row.names = FALSE, fileEncoding = "UTF-8")
  }
  invisible(data)
}

if (sys.nframe() == 0L) brit_eu_main()
