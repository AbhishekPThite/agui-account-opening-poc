import { Injectable } from '@angular/core';
import { AguiClientService, RunAgentInput } from './agui-client.service';
import { AgUiEventProcessor } from './ag-ui-event-processor.service';
import { JourneyStateService } from './journey-state.service';

type InterruptResolution = Array<{
  interruptId: string;
  status: 'resolved';
  payload: unknown;
}>;

@Injectable({ providedIn: 'root' })
export class ConversationService {
  private threadId = crypto.randomUUID();

  constructor(
    private readonly agui: AguiClientService,
    private readonly events: AgUiEventProcessor,
    private readonly journey: JourneyStateService
  ) {}

  start(prompt: string): void {
    if (this.journey.busy()) return;
    this.journey.reset();
    this.threadId = crypto.randomUUID();
    this.send(prompt);
  }

  sendMessage(message: string): void {
    const text = message.trim();
    if (!text || this.journey.busy()) return;

    const interruptId = this.journey.pendingInterruptId();
    if (interruptId) {
      this.resume(interruptId, { action: 'EDIT', message: text });
      return;
    }
    this.send(text);
  }

  resume(interruptId: string, payload: unknown): void {
    if (this.journey.busy()) return;
    this.send('', [{ interruptId, status: 'resolved', payload }]);
  }

  private send(text: string, resume?: InterruptResolution): void {
    if (this.journey.busy()) return;

    this.journey.busy.set(true);
    this.journey.error.set('');

    const input: RunAgentInput = {
      threadId: this.threadId,
      runId: crypto.randomUUID(),
      messages: text
        ? [{ id: crypto.randomUUID(), role: 'user', content: text }]
        : [],
      ...(resume ? { resume } : {})
    };

    this.agui.run(input).subscribe({
      next: event => this.events.process(event),
      error: (err: Error) => {
        console.error('[AG-UI REQUEST ERROR]', err);
        this.journey.setError(err.message);
        this.journey.busy.set(false);
      },
      complete: () => this.journey.busy.set(false)
    });
  }
}
