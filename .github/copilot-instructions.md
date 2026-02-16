# SEC 13F Holdings Analyzer - Development Guide

## Build, Test, and Lint

### Running Tests

```bash
# Run all tests
poetry run pytest

# Run with coverage report
poetry run pytest --cov=src/sec13f_analyzer --cov-report=term-missing

# Run specific test module
poetry run pytest tests/test_analyzer.py -v

# Run specific test function
poetry run pytest tests/test_analyzer.py::test_get_holdings -v

# Run only unit tests (skip integration/slow tests)
poetry run pytest -m "unit"
```

### Code Quality

```bash
# Format code (Black + isort)
poetry run black src/ tests/
poetry run isort src/ tests/

# Type checking
poetry run mypy src/

# Linting
poetry run flake8 src/ tests/
```

### Running the CLI

```bash
# All CLI commands use poetry run
poetry run sec13f-cli --help

# Example: Search for a fund
poetry run sec13f-cli search --fund-name "Berkshire"

# Example: Fetch holdings
poetry run sec13f-cli fetch --cik 0001067983 --quarter 2024Q3
```

## Architecture Overview

### Data Flow Pipeline

```
CLI Command → SEC13FAnalyzer → SEC13FDataFetcher → SEC EDGAR API
                    ↓
            XML Parsing → Holdings Model
                    ↓
        Analysis → HoldingsChange Model
                    ↓
    Visualization/Export → Charts/Excel/CSV
```

### Core Modules

1. **models.py** - Data structures (`Holding`, `Holdings`, `HoldingChange`)
2. **data_fetcher.py** - SEC EDGAR data retrieval and XML parsing
3. **analyzer.py** - Holdings analysis and change detection
4. **visualizer.py** - Chart generation (matplotlib/plotly)
5. **exporter.py** - Data export (Excel/CSV/JSON)
6. **cli.py** - Command-line interface (Click framework)
7. **config.py** - Configuration management

### Key Data Models

- **Holding**: Single position with CUSIP, market value, shares, voting authority
- **Holdings**: Complete 13F report with fund metadata, period, and list of holdings
- **HoldingChange**: Position changes between quarters (new/closed/increased/decreased)

## Important Conventions

### Quarter Format
Always use `YYYYQN` format (e.g., `2024Q3`). Quarter parsing and validation is handled in `data_fetcher.py`.

### CIK Format
CIKs are 10-digit strings with leading zeros (e.g., `0001067983`). The fetcher normalizes CIK input automatically.

### Information Table File Detection
The data fetcher uses a prioritized pattern matching system to identify the correct XML file in 13F reports:
1. `form13fInfoTable.xml` (standard format, priority 100)
2. `infotable.xml` (simplified format, priority 90)
3. Files matching `.*13f.*info.*table.*\.xml` (priority 80)
4. Numbered XML files `\d+\.xml` (priority 70)

This handles various SEC filing formats across different institutions.

### SEC API Rate Limiting
- Default request delay: 0.2 seconds
- Max retries: 3
- Timeout: 30 seconds
- Always include proper User-Agent with company name and email

### User-Agent Requirements
SEC requires User-Agent headers with real contact information. Configure in `config.ini`:
```ini
[fetcher]
company_name = YourCompany Research
email = your-email@company.com
```

### Error Handling Pattern
Use custom exceptions from the codebase:
- Network errors: Automatic retry with exponential backoff
- 403 Forbidden: Check User-Agent configuration
- XML parsing errors: Tolerant parsing, skip invalid records
- Missing data: Return `None` or empty structures, not exceptions

### Testing Strategy
- **Unit tests**: Mock SEC API responses, test individual functions
- **Integration tests**: Use cached test data in `tests/test_data/`
- **Fixtures**: Common test data in `conftest.py` (sample holdings, changes)
- **Markers**: `@pytest.mark.integration`, `@pytest.mark.unit`, `@pytest.mark.slow`

### Data Export Conventions
- Excel: Multi-sheet format with summary, holdings, and optional charts
- CSV: Flat format, one holding per row
- JSON: Nested structure preserving full object hierarchy
- Default filenames: `{fund_name}_{quarter}_{type}.{ext}`

### Visualization Defaults
- Style: seaborn
- Figure size: 12x8 inches
- Color palette: Set2
- Charts auto-show unless `show=False` parameter

## Common Patterns

### Adding a New Analysis Function

1. Add method to `SEC13FAnalyzer` class in `analyzer.py`
2. Return appropriate data model or dict
3. Add corresponding export method in `exporter.py` if needed
4. Add CLI command in `cli.py` if exposing to users
5. Write unit tests with mocked data fetcher

### Adding a CLI Command

```python
@cli.command()
@click.option('--cik', '-c', required=True, help='Fund CIK')
@click.option('--quarter', '-q', required=True, help='Quarter (YYYYQN)')
@click.pass_context
def your_command(ctx, cik, quarter):
    """Command description"""
    user_agent = ctx.obj['user_agent']
    analyzer = SEC13FAnalyzer(user_agent)
    # Implementation
```

### Working with Holdings Data

```python
# Get holdings
holdings = analyzer.get_holdings(cik, quarter)

# Access properties
top_10 = holdings.top_holdings(10)
total_value = holdings.total_value
count = holdings.holdings_count

# Convert to DataFrame for analysis
df = holdings.to_dataframe()

# Iterate holdings
for holding in holdings.holdings:
    print(f"{holding.issuer_name}: ${holding.market_value:,.0f}")
```

## Development Tips

- **Mock SEC API calls** in tests using `@patch.object(fetcher, 'get_13f_data')`
- **Use test fixtures** from `conftest.py` for sample holdings/changes
- **Check test_data/** directory for real SEC XML samples before adding new ones
- **Run integration tests** sparingly to avoid SEC rate limiting
- **Add type hints** to all new functions/methods
- **Use loguru** for logging, not print statements
- **Configuration precedence**: CLI args > config.ini > defaults
