The viewer is deployed by `.github/workflows/pages.yml` (upload-pages-artifact
of `web/`; one-time repo setting: Pages -> Source: GitHub Actions). Locally it
needs any static server (`python -m http.server` from `web/`); `file://` is
unsupported by design.
