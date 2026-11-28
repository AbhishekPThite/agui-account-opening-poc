import { Injectable } from '@angular/core';
import { AgUiEvent } from './agui-client.service';
import { JourneyStateService } from './journey-state.service';

@Injectable({ providedIn: 'root' })
export class AgUiEventProcessor {
  constructor(private readonly journey: JourneyStateService) {}

  process(event: AgUiEvent): void {
    console.log('[ANGULAR EVENT]', event.type, event);
    this.journey.recordEvent(event);

    if (event.type === 'STATE_SNAPSHOT') {
      const snapshot = event['snapshot'] as Record<string, unknown> | undefined;
      this.journey.applySnapshot(snapshot);
    }

    if (event.type === 'RUN_FINISHED') {
      const outcome = event['outcome'] as
        { type?: string; interrupts?: Array<{ id?: string }> } | undefined;
      if (outcome?.type === 'interrupt') {
        const interruptId = outcome.interrupts?.[0]?.id;
        if (interruptId) {
          this.journey.setInterrupt(interruptId);
          console.log('[AG-UI INTERRUPT]', interruptId);
        } else {
          this.journey.setError('The agent paused, but no interrupt ID was returned.');
        }
      } else {
        this.journey.setInterrupt(null);
      }
    }

    if (event.type === 'TEXT_MESSAGE_START') {
      this.journey.appendAssistantMessage();
    }

    if (event.type === 'TEXT_MESSAGE_CONTENT') {
      this.journey.appendAssistantText(String(event['delta'] ?? ''));
    }

    if (event.type === 'RUN_ERROR') {
      this.journey.setError(String(event['message'] ?? 'Agent run failed'));
    }
  }
}
