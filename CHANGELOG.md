# Changelog

All notable changes to this project are documented here.
Format inspired by Keep a Changelog; versions are 0.x while the tool stabilizes.

## [0.1.1] - 2026-10-13

### Changed
- Second-round revision after a full self-audit (rules 85-100 alignment pass):
  markdown empty alt reclassified as missing-alt (matches screen-reader behavior and anchor semantics) while HTML alt="" stays decorative; alt=None crash in text renderer fixed; classification table (11 rows) added

### Fixed
- Self-test suite hardened to 54 cases across three classes
  (functional / error-path / extreme-edge); final run `SUMMARY: PASS 54/54`.

## [0.1.0] - 2026-10-13

### Added
- Initial release: pure-stdlib core, argparse CLI, three-tier finding model,
  text and JSON output, and an article-level README with measured
  performance, Minimal Fallback, Design Trade-offs, Limits & Second-order
  Effects, FAQ, and Core Assumptions.
