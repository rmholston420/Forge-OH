# Changelog

## [Unreleased]

### Added
- Dedicated `.venv-bff` virtual environment for the Forge-OH BFF runtime.[file:221]
- `bff/README.md` documenting the pinned stack and local workflow.[file:221]

### Changed
- Pinned BFF runtime dependencies in `bff/requirements.txt` and regenerated `bff/requirements.lock` from a clean environment.[file:220][file:221]
- Updated `docs/Forge-OH-Build-Plan-Definitive.md` to match the validated BFF versions and `uvicorn bff.main:app` startup command.[file:220]
