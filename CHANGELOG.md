# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project follows [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.1] - Unreleased

### Added
- CI checks for formatting, linting, type checking, tests, coverage, and security scans.
- `py.typed` marker for typed package consumers.
- Pre-commit configuration for local quality checks.

### Changed
- Moved debug-only `ipdb` dependency to development dependencies.
- Updated README metadata to match the package's supported Python version and license.

### Security
- Switched SEC XML parsing to `defusedxml` to avoid unsafe XML entity expansion.
