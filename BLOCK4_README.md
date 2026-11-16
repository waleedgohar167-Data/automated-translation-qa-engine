# Block 4: GitHub Actions CI

This update adds the assessment CI workflow for the current Block 3 state.

## CI coverage

The workflow runs on pushes and pull requests and tests:

- Python 3.11
- Python 3.13
- `unittest` discovery
- `pytest`
- CLI help/smoke checks

The workflow does not use application credentials, model APIs, or external runtime services.

## Local verification

Run these from the repository root before committing:

```powershell
python -m unittest discover -s tests
python -m pytest
python -m translation_qa --help
python -m translation_qa check --help
```

Remote GitHub Actions success should be captured after the workflow is committed and pushed.
