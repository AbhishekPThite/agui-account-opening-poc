# Backend layout

- `main.py`: FastAPI application and AG-UI endpoint lifecycle.
- `workflow/`: LangGraph state contract, node implementations and graph topology.
- `application/`: request extraction/classification, workflow actions and state-update projection.
- `domain/`: deterministic validation, application assessment and product requirements.
- `presentation/`: projection of domain/workflow state into the Angular widget contract.
- `integrations/llm/`: model client and extraction/assessment prompts.
- `integrations/java/`: Java Experience API adapter.
- `infrastructure/`: checkpointer setup and lifecycle.
- `tests/unit/domain/`, `tests/unit/application/`, `tests/workflow/`: regression tests by responsibility.

There are no root-level compatibility shims: application code and tests import modules from their owning packages. Use package-qualified imports (for example, `from integrations.llm.model_client import ...` from `main.py`, or relative imports inside packages).

Run the complete regression suite from this directory:

```bash
python -m unittest discover -s tests -t . -v
```

Or, if pytest is installed:

```bash
pytest -q
```
