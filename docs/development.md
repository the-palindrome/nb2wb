# Development

## Local Setup

```bash
git clone https://github.com/the-palindrome/nb2wb.git
cd nb2wb
pip install -e ".[dev]"
```

## Run Tests

```bash
pytest
pytest tests/unit/
pytest tests/integration/
pytest tests/workflow/
```

## Formatting

```bash
black nb2wb tests
isort nb2wb tests
```

## Build Docs Locally

Install docs dependencies:

```bash
pip install -e ".[docs]"
```

Build:

```bash
sphinx-build -b html docs docs/_build/html
```

## Read the Docs Build

The repo includes `.readthedocs.yaml` configured to:

- install package with `docs` extra
- build Sphinx docs from `docs/conf.py`

If a RTD build fails, verify:

- docs dependencies in `pyproject.toml`
- valid Sphinx config and toctree targets
