# Backend layout

- Root modules: FastAPI entry point and stable compatibility imports.
- `workflow/`: LangGraph node implementations (`nodes.py`) and graph topology/routing (`graph.py`).
- `tests/unit/domain/`: domain validation, requirements, assessment and product/risk rules.
- `tests/unit/application/`: request pipeline, workflow actions and state projection.
- `tests/workflow/`: graph routing, journey status and end-to-end conversational workflow behavior.

Run the regression suite from this directory:

```bash
python -m unittest discover -s tests -t . -v
```

Or, if pytest is installed:

```bash
pytest -q
```

The root-level `graph.py` remains a compatibility facade so existing imports and API wiring continue to work.
