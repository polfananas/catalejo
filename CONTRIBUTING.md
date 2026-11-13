# Contributing

Thanks for taking a look. Bug reports, fixes and new CNMV sources are all welcome.
If you're planning something bigger than a small fix, open an issue first so we can
agree on the shape before you write the code.

## Setup

```bash
git clone https://github.com/polfananas/catalejo
cd catalejo
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev,mcp,pdf]"
```

## Before opening a pull request

```bash
ruff check src tests
ruff format src tests
mypy src
pytest
```

CI runs the same checks on Python 3.10 to 3.14.

## Tests don't touch the network

Parsers are tested against real CNMV pages saved in `tests/fixtures/`, trimmed to the
part that matters (see the README there). If you add or change a parser, save the
page you're parsing next to the others, note its URL in the fixtures README, and
test against it.

## Be gentle with the CNMV

catalejo only works because the CNMV publishes this data for free. Please keep it
polite:

- Go through `HttpClient` (`catalejo/_http.py`). It rate-limits to one request per
  second, caches on disk and sends an identifiable User-Agent. Don't bypass it or
  add concurrency.
- Before adding a new source, check what the CNMV actually publishes and that it's
  covered by its [legal notice](https://www.cnmv.es/Portal/utilidades/NotaLegal).
- Keep the data as the CNMV publishes it. Don't "fix" names or categories; add
  separate fields if something needs normalising.

## Style

- One change per pull request, with a test.
- Public API changes (function names, arguments, fields) get discussed in an issue first.
- Code and docs in English. Data stays in the language the CNMV and issuers use.

Good places to start: issues labelled
[`good first issue`](https://github.com/polfananas/catalejo/labels/good%20first%20issue)
and the roadmap in the README.
