import { CommonModule } from '@angular/common';
import { Component, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { AguiClientService, AgUiEvent } from './agui-client.service';

@Component({
  selector: 'app-account-opening-agent',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './account-opening-agent.component.html',
})
export class AccountOpeningAgentComponent {
  prompt = signal('Open a joint brokerage account for client C12345 with USD as base currency.');
  ownerName = signal('');
  taxResidency = signal('');
  threadId = crypto.randomUUID();
  events = signal<AgUiEvent[]>([]);
  assistantText = signal<string[]>([]);
  uiState = signal<Record<string, any> | null>(null);
  busy = signal(false);
  error = signal('');

  constructor(private readonly agui: AguiClientService) {}

  start(): void {
    this.send(this.prompt());
  }

  submitJointOwner(): void {
    const text = `Joint owner name: ${this.ownerName()}, tax residency: ${this.taxResidency()}`;
    this.send(text);
  }

  private send(text: string): void {
    if (this.busy()) return;

    this.busy.set(true);
    this.error.set('');

    const input = {
      threadId: this.threadId,
      runId: crypto.randomUUID(),
      messages: [{
        id: crypto.randomUUID(),
        role: 'user' as const,
        content: text,
      }],
    };

    this.agui.run(input).subscribe({
      next: (event) => this.handleEvent(event),
      error: (err: Error) => {
        this.error.set(err.message);
        this.busy.set(false);
      },
      complete: () => this.busy.set(false),
    });
  }

  private handleEvent(event: AgUiEvent): void {
    this.events.update(current => [...current, event]);

    if (event.type === 'STATE_SNAPSHOT') {
      const snapshot = event['snapshot'] as Record<string, any> | undefined;
      if (snapshot?.ui) this.uiState.set(snapshot.ui);
    }

    if (event.type === 'STATE_DELTA') {
      // The integration may emit JSON Patch deltas. For this first slice,
      // inspect the event stream and add a standards-compliant patch reducer
      // once the exact state shape is confirmed in your pinned SDK version.
      const delta = event['delta'];
      if (delta) console.debug('AG-UI state delta', delta);
    }

    if (event.type === 'TEXT_MESSAGE_CONTENT') {
      const delta = String(event['delta'] ?? '');
      this.assistantText.update(items => {
        const copy = [...items];
        copy[copy.length - 1] = (copy[copy.length - 1] ?? '') + delta;
        return copy;
      });
    }

    if (event.type === 'TEXT_MESSAGE_START') {
      this.assistantText.update(items => [...items, '']);
    }

    if (event.type === 'RUN_ERROR') {
      this.error.set(String(event['message'] ?? 'Agent run failed'));
    }
  }
}
