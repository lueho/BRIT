# BRIT developer convenience targets.
#
# Static assets (SCSS -> CSS -> minified CSS/JS) are built in a pinned,
# Dockerized toolchain so developers, AI agents and CI all produce identical
# output. Compiled artifacts are committed to git; CI verifies they are in sync.

# Run the asset container as the host user so generated files aren't root-owned.
export UID := $(shell id -u)
export GID := $(shell id -g)

COMPOSE ?= docker compose
ASSETS_RUN := $(COMPOSE) run --rm assets

.DEFAULT_GOAL := help

.PHONY: help assets assets-watch assets-check

help: ## Show this help
	@grep -hE '^[a-zA-Z0-9_-]+:.*?## ' $(MAKEFILE_LIST) \
		| awk 'BEGIN {FS = ":.*?## "} {printf "  \033[36m%-16s\033[0m %s\n", $$1, $$2}'

assets: ## Build all static assets once (SCSS -> CSS -> min)
	$(ASSETS_RUN) node scripts/build_assets.mjs

assets-watch: ## Watch sources and rebuild changed assets (live dev feedback)
	$(ASSETS_RUN) node scripts/build_assets.mjs --watch

assets-check: ## Rebuild assets and fail if committed output is stale (used by CI)
	$(ASSETS_RUN) node scripts/build_assets.mjs
	@git diff --exit-code -- '*.css' '*.css.map' '*.min.css' '*.min.js' \
		|| { echo "\nERROR: compiled assets are out of date. Run 'make assets' and commit the result."; exit 1; }
