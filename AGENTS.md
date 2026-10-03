# Repository Guidelines

## Project Structure & Module Organization

The current workspace contains `fuel-prices-for-be-assessment.csv`, a fuel-price dataset, at the repository root. There are no application modules, test directories, asset folders, or dependency manifests. Keep the dataset at its existing path so downstream consumers can locate it. Document any new source directories and their purpose when adding application code.

## Development & Validation Commands

Run these PowerShell commands from the workspace root:

- `Get-Content ./fuel-prices-for-be-assessment.csv -TotalCount 5` previews the header and sample records.
- `Import-Csv ./fuel-prices-for-be-assessment.csv | Measure-Object` counts parsed records.
- `Import-Csv ./fuel-prices-for-be-assessment.csv | Group-Object State` summarizes records by state.

No build, development server, or automated test command is currently configured. Add reproducible setup and execution instructions alongside any future tooling.

## Data Style & Naming Conventions

Preserve the existing column names and order: `OPIS Truckstop ID`, `Truckstop Name`, `Address`, `City`, `State`, `Rack ID`, and `Retail Price`. Use CSV-aware readers and writers; addresses contain commas and require quoting. Preserve numeric precision and existing identifiers. Do not silently deduplicate rows: repeated identifiers can have different truckstop names. No formatter or linter is configured.

## Testing Guidelines

There is no testing framework or coverage threshold. For dataset changes, verify successful CSV parsing, the seven-column schema, numeric price values, and the intended record-count difference. Review representative quoted addresses and repeated identifiers. When adding automated tests, document their framework, naming convention, and run command.

## Commit & Pull Request Guidelines

No Git metadata is present, so existing commit conventions cannot be established. Suggested commit subjects are concise and imperative, such as `Validate fuel price records`. Pull requests should describe the change, its rationale, validation performed, and any effect on schema or record counts. Link a relevant issue when available. Explain data corrections and their source so reviewers can reproduce them.
