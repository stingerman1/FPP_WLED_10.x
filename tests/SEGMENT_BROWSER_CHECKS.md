# Segment input regression checks

These checks change only a disposable local fixture. Do not point them at a real player.
They require the renderer build and Python dependencies used by `tests/ui_fixture.py`.

Start a fresh fixture from the repository root on Linux/WSL:

```sh
PYTHONPATH=build/python-deps python3 tests/ui_fixture.py
```

In another terminal:

```sh
npx --yes --package @playwright/cli playwright-cli -s=fields open http://localhost:18787/
npx --yes --package @playwright/cli playwright-cli -s=fields run-code --filename tests/browser_segment_fields.js
npx --yes --package @playwright/cli playwright-cli -s=fields close
```

Stop the fixture afterward. For matrix checks, start a fresh fixture with
`WLED_TEST_MATRIX=1` in its environment, open `http://localhost:18788/`, and run
`tests/browser_matrix_fields.js` instead. Stop that fixture afterward too.

The checks cover drafts across periodic notifications, empty fields during typing,
name/start/end/grouping/spacing/offset persistence, unrelated color updates,
invalid end values, matrix bounds, maximum values, and Enter to apply.
