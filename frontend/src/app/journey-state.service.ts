import { Injectable, signal } from '@angular/core';
import { AgUiEvent } from './agui-client.service';
import { AgentUI } from './models/agent-ui.model';

@Injectable({ providedIn: 'root' })
export class JourneyStateService {
  readonly events = signal<AgUiEvent[]>([]);
  readonly assistantText = signal<string[]>([]);
  readonly uiState = signal<AgentUI | null>(null);
  readonly busy = signal(false);
  readonly error = signal('');
  readonly pendingInterruptId = signal<string | null>(null);

  reset(): void {
    this.events.set([]);
    this.assistantText.set([]);
    this.uiState.set(null);
    this.pendingInterruptId.set(null);
    this.error.set('');
    this.busy.set(false);
  }

  recordEvent(event: AgUiEvent): void {
    this.events.update(items => [...items, event]);
  }

  applySnapshot(snapshot: Record<string, unknown> | undefined): void {
    const ui = snapshot?.['ui'];
    if (
      ui &&
      typeof ui === 'object' &&
      'widgetId' in ui &&
      'mode' in ui &&
      'title' in ui
    ) {
      this.uiState.set(ui as AgentUI);
    }
  }

  appendAssistantMessage(): void {
    this.assistantText.update(items => [...items, '']);
  }

  appendAssistantText(delta: string): void {
    this.assistantText.update(items => {
      const copy = [...items];
      if (copy.length === 0) copy.push(delta);
      else copy[copy.length - 1] = (copy[copy.length - 1] ?? '') + delta;
      return copy;
    });
  }

  setInterrupt(interruptId: string | null): void {
    this.pendingInterruptId.set(interruptId);
  }

  setError(message: string): void {
    this.error.set(message);
  }

  completionPercent(): number {
    const journey = this.uiState()?.journeyStatus;
    return journey?.totalCount
      ? Math.round((journey.completedCount / journey.totalCount) * 100)
      : 0;
  }
}
