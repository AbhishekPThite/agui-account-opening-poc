# Angular integration notes

- Copy `agui-client.service.ts`, `account-opening-agent.component.ts`, and its HTML template into your Angular workspace.
- Import the standalone component into the route or parent component.
- Update the endpoint URL and CORS origin for your local environment.
- The initial adapter parses SSE frames for demonstration. Pin a compatible official AG-UI TypeScript SDK for production.
- Confirm the exact emitted `STATE_SNAPSHOT` shape against the installed `ag-ui-langgraph` version. The component logs state deltas rather than applying arbitrary patches.
- `MemorySaver` is single-process demo persistence only. Use durable persistence for real resumable workflows.
