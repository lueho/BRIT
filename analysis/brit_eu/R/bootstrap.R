# All scripts are run from the project root (run.R also supports arbitrary cwd).
brit_path <- function(...) file.path(getOption("brit.root", getwd()), ...)
for (folder in c("NRW", "RLP", "Sweden", "Alto Adige", "South Tyrol", "Catalonia", "RLP_BW")) {
  dir.create(brit_path("results", "figures", folder), recursive = TRUE, showWarnings = FALSE)
  dir.create(brit_path("data", "processed", folder), recursive = TRUE, showWarnings = FALSE)
}

brit_verify_inputs <- function(allow_custom_data = FALSE) {
  manifest <- jsonlite::read_json(brit_path("data", "manifest.json"))
  modified <- character()
  for (entry in manifest$files) {
    path <- brit_path(entry$path)
    if (!file.exists(path)) stop("Missing input: ", entry$path, ". Use the complete release ZIP.")
    if (digest::digest(file = path, algo = "sha256") != entry$sha256) modified <- c(modified, entry$path)
  }
  if (length(modified) && !allow_custom_data) {
    stop("Modified project inputs: ", paste(modified, collapse = ", "),
         ". Use --allow-custom-data intentionally for your own analysis.")
  }
  list(release_id = manifest$release_id, custom_data = length(modified) > 0L, modified_files = modified)
}
