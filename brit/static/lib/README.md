# Vendored frontend assets

Third-party assets are self-hosted here instead of loaded from public CDNs.
They bypass the asset minification pipeline and are served as-is via
`collectstatic`. When updating an entry, replace the files and bump the
version in this table — nothing else tracks these versions.

| Directory      | Package                     | Version | Source                                                        | License                          |
| -------------- | --------------------------- | ------- | ------------------------------------------------------------- | -------------------------------- |
| `bootstrap/`   | Bootstrap                   | 5.3.6   | https://github.com/twbs/bootstrap (full dist incl. `scss/`)   | MIT                              |
| `fontawesome/` | Font Awesome Free           | 6.6.0   | https://www.npmjs.com/package/@fortawesome/fontawesome-free   | Icons CC BY 4.0, fonts SIL OFL 1.1, code MIT (`LICENSE.txt`) |
| `nouislider/`  | noUiSlider                  | 15.8.1  | https://www.npmjs.com/package/nouislider                      | MIT                              |
| `nunito/`      | Nunito (Google Fonts, woff2)| 400     | https://fonts.google.com/specimen/Nunito                      | SIL OFL 1.1                      |

Notes:

- `fontawesome/css/all.min.css` references the complete webfont set under
  `webfonts/` (`.woff2` + `.ttf`). All referenced files must be committed —
  `S3ManifestStaticStorage` resolves every `url(...)` at collectstatic time
  and the release fails on missing targets (covered by
  `brit.tests.test_staticfiles.CollectstaticManifestTests`).
- `nunito/nunito.css` is a static copy of the Google Fonts `@font-face`
  response with local paths and `font-display: swap`. The font is used by
  Waste Atlas SVG charts.
- `bootstrap/` ships the full distribution because `scss/brit-theme.scss`
  compiles the themed build directly from `bootstrap/scss/`.
