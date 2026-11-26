import { CommonModule } from '@angular/common';
import { Component, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { AgUiEvent, AguiClientService } from './agui-client.service';

@Component({
  selector: 'app-account-opening-agent',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './account-opening-agent.component.html',
})
export class AccountOpeningAgentComponent {
  prompt = signal(
    'Open a joint brokerage account for client C12345 with USD as base currency.'
  );
  ownerName = signal('');
  taxResidency = signal('');

  // Keep one thread for the multi-turn journey; create a new one for each new journey.
  threadId = crypto.randomUUID();

  events = signal<AgUiEvent[]>([]);
  assistantText = signal<string[]>([]);
  uiState = signal<Record<string, unknown> | null>(null);
  busy = signal(false);
  error = signal('');

  constructor(private readonly agui: AguiClientService) {}

  start(): void {
    if (this.busy()) return;

    this.events.set([]);
    this.assistantText.set([]);
    this.uiState.set(null);
    this.ownerName.set('');
    this.taxResidency.set('');
    this.threadId = crypto.randomUUID();

    this.send(this.prompt());
  }

  submitJointOwner(): void {
    const text =
      `Joint owner name: ${this.ownerName()}, tax residency: ${this.taxResidency()}`;
    this.send(text);
  }

  private send(text: string): void {
    if (this.busy()) return;

    this.busy.set(true);
    this.error.set('');

    this.agui.run({
      threadId: this.threadId,
      runId: crypto.randomUUID(),
      messages: [{
        id: crypto.randomUUID(),
        role: 'user',
        content: text,
      }],
    }).subscribe({
      next: event => this.handleEvent(event),
      error: (err: Error) => {
        console.error('[AG-UI REQUEST ERROR]', err);
        this.error.set(err.message);
        this.busy.set(false);
      },
      complete: () => this.busy.set(false),
    });
  }

  private handleEvent(event: AgUiEvent): void {
    console.log('[ANGULAR EVENT]', event.type, event);
    this.events.update(items => [...items, event]);

    if (event.type === 'STATE_SNAPSHOT') {
      const snapshot = event['snapshot'] as
        Record<string, unknown> | undefined;

      if (snapshot?.['ui']) {
        console.log('[AG-UI UI STATE]', snapshot['ui']);
        this.uiState.set(snapshot['ui'] as Record<string, unknown>);
      }
    }

    if (event.type === 'TEXT_MESSAGE_START') {
      this.assistantText.update(items => [...items, '']);
    }

    if (event.type === 'TEXT_MESSAGE_CONTENT') {
      const delta = String(event['delta'] ?? '');
      this.assistantText.update(items => {
        const copy = [...items];
        if (copy.length === 0) {
          copy.push(delta);
        } else {
          copy[copy.length - 1] = (copy[copy.length - 1] ?? '') + delta;
        }
        return copy;
      });
    }

    if (event.type === 'RUN_ERROR') {
      this.error.set(String(event['message'] ?? 'Agent run failed'));
    }
  }
}
