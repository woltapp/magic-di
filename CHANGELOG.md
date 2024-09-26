# Changelog
All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/), and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]
### Added
- Added `magic_di.healthcheck.DependenciesHealthcheck` class to make health checks of injected dependencies that implement `magic_di.healthcheck.PingableProtocol` interface
### Fixed
- Inject dependencies inside of event loop in `magic_di.utils.inject_and_run` to prevent wrong event loop usage inside of the injected dependencies
### Changed
- Cruft update to get changes from the cookiecutter template
- Renamed LICENCE -> LICENSE, now it's automatically included in the wheel created by poetry

## [0.1.0] - 2024-03-28
### Changed
- Initial version

[Unreleased]: https://github.com/woltapp/magic-di/compare/0.1.0...master
[0.1.0]: https://github.com/woltapp/magic-di/tree/0.1.0
