# Contributing

Thanks for contributing to `sec13f-analyzer`.

## Development setup

```bash
poetry install --with dev,test
poetry run pre-commit install
```

## Quality checks

Run these before opening a pull request:

```bash
poetry run black src/ tests/
poetry run isort src/ tests/
poetry run flake8 src/ tests/
poetry run mypy src/
poetry run pytest --cov=src/sec13f_analyzer --cov-report=term-missing
poetry run bandit -r src/
poetry run pip-audit
```

## SEC API usage

Tests should mock SEC API calls unless they are explicitly marked as integration
tests. Runtime SEC requests must use a User-Agent with contact information.
