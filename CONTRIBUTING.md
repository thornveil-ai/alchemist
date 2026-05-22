# Contributing to Alchemist

Pull requests welcome. Alchemist is Apache-2.0 — feel free to fork, experiment, and propose changes.

## Before submitting

1. `alchemist doctor` must print OK across the board for any change touching the pipeline
2. `pytest tests/ --ignore=tests/test_local_llm.py` must pass
3. New features require a test. The existing test suite is the floor.
4. The scrubber has fixture-backed rules in `tests/test_scrubber.py`. New scrubber rules follow the same pattern.
5. Domain plugins live in `alchemist/plugins/` with sibling tests in `tests/test_plugins.py`

## Commit style

- One concern per commit
- Imperative mood
- No Co-Authored-By or AI attribution
- Conventional commits welcome but not required

See the existing log for examples.

## Code of conduct

This project adopts the org-wide [code of conduct](https://github.com/thornveil-ai/.github/blob/main/CODE_OF_CONDUCT.md).

## License

By contributing, you agree that your contributions will be licensed under [Apache-2.0](LICENSE).
