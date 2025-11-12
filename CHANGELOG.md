# Changelog

## [1.1.0] - 2025-11-10

### Fixed

- **Language Detection Regression:** The language detection pipeline now uses a deterministic, no-VAD path, which significantly improves the accuracy and consistency of language identification.
- **Dashboard Modal Overflow:** The job result modal in the dashboard now correctly handles long JSON results without overflowing or stretching the background.
- **Maintenance Script:** The `purge_db.py` script has been fixed to run correctly with SQLite.

### Added

- **Golden Samples and Tests:** A set of golden audio samples has been added to the test suite to verify the correctness of the language detection model.
- **Deterministic Testing:** The test suite has been updated to use a synchronous, deterministic testing strategy, which eliminates flaky tests and improves the reliability of the test suite.
- **Enhanced Observability and Metrics:** The service now exposes a set of Prometheus-formatted metrics for monitoring and observability.
- **Structured Logging:** The service now uses structured logging to provide more detailed and actionable log messages.

### Changed

- **API Improvements:** The `/jobs/by-url` endpoint now accepts a plain JSON string for the URL, and the service now returns proper 4xx errors for invalid or oversized URLs and incomplete jobs.
- **Configuration:** The service configuration has been centralized in `langid_service/app/config.py`, and the service now reads configuration values from environment variables.

### Security

- **NPM Vulnerabilities:** While a complete fix was not possible without introducing breaking changes, several vulnerable npm packages have been updated to their latest non-breaking minor versions.
