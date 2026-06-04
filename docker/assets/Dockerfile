# Build image for BRIT static assets (SCSS -> CSS -> minified CSS/JS).
#
# Tooling is pinned here so developers, AI agents and CI all produce
# byte-identical output. The image is dev/CI-only and is never part of the
# Python runtime image.
FROM node:22-alpine

# Pinned, deterministic toolchain:
#   - sass    : Dart Sass (pure JS build) compiles SCSS -> CSS
#   - esbuild : minifies CSS and JS
RUN npm install --global --no-fund --no-audit \
    sass@1.100.0 \
    esbuild@0.28.0

WORKDIR /app

# The repository is bind-mounted at runtime (see compose.yml `assets` service);
# the build script itself lives under scripts/ and uses only Node built-ins.
CMD ["node", "scripts/build_assets.mjs", "--watch"]
