import { CommonModule } from '@angular/common';
import { Component, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { AgUiEvent, AguiClientService } from './agui-client.service';
import { AgentUI } from './models/agent-ui.model';
import { WidgetRendererComponent } from './widgets/widget-renderer.component';

@Component({
  selector: 'app-account-opening-agent',
  standalone: true,
  imports: [CommonModule, FormsModule, WidgetRendererComponent],
  templateUrl: './account-opening-agent.component.html',
})
export class AccountOpeningAgentComponent {
  prompt = signal(
    'Open a joint brokerage account for client C12345.'
  );
  conversationText = signal('');

  // Keep one thread for the multi-turn journey; create a new one for each new journey.
  threadId = crypto.randomUUID();

  events = signal<AgUiEvent[]>([]);
  assistantText = signal<string[]>([]);
  uiState = signal<AgentUI | null>(null);
  busy = signal(false);
  error = signal('');
  pendingInterruptId = signal<string | null>(null);

  constructor(private readonly agui: AguiClientService) {}

  start(): void {
    if (this.busy()) return;

    this.events.set([]);
    this.assistantText.set([]);
    this.uiState.set(null);
    this.pendingInterruptId.set(null);
    this.conversationText.set('');
    this.threadId = crypto.randomUUID();

    this.send(this.prompt());
  }

  submitWidget(payload: Record<string, unknown>): void {
    if (payload['__beneficiaryAction'] === 'SKIP') {
      this.send('POC_FORM_SUBMISSION:' + JSON.stringify({ formId: 'BENEFICIARY_SKIP' }));
      return;
    }
    if (payload['__profileAction'] === 'CONFIRM') {
      this.send('POC_FORM_SUBMISSION:' + JSON.stringify({ formId: 'PROFILE_CONFIRMATION' }));
      return;
    }
    if (payload['__profileAction'] === 'EDIT') {
      this.send('POC_FORM_SUBMISSION:' + JSON.stringify({ formId: 'PROFILE_CAPTURE_REQUEST' }));
      return;
    }
    const action = payload['__approvalAction'];
    if (action === 'APPROVE' || action === 'REJECT') {
      this.resumeApproval(action);
      return;
    }

    if (this.uiState()?.widgetId === 'ACCOUNT_SETUP_FORM') {
      this.send(`POC_FORM_SUBMISSION:${JSON.stringify({ ...payload, formId: 'ACCOUNT_SETUP' })}`);
      return;
    }
    if (this.uiState()?.widgetId === 'PROFILE_DATA_CAPTURE') {
      this.send(`POC_FORM_SUBMISSION:${JSON.stringify({ ...payload, formId: 'PROFILE_DATA_CAPTURE' })}`);
      return;
    }
    if (this.uiState()?.widgetId === 'BENEFICIARY_CAPTURE') {
      this.send(`POC_FORM_SUBMISSION:${JSON.stringify({ ...payload, formId: 'BENEFICIARY_CAPTURE' })}`);
      return;
    }
    if (this.uiState()?.widgetId === 'RISK_ASSESSMENT_FORM') {
      this.send(`POC_FORM_SUBMISSION:${JSON.stringify({ ...payload, formId: 'RISK_ASSESSMENT' })}`);
      return;
    }
    if (this.uiState()?.widgetId === 'PRODUCT_FEATURES_FORM') {
      this.send(`POC_FORM_SUBMISSION:${JSON.stringify({ ...payload, formId: 'PRODUCT_FEATURES' })}`);
      return;
    }

    const details = Object.entries(payload)
      .map(([key, value]) => `${key.replace(/([A-Z])/g, ' $1').toLowerCase()}: ${String(value)}`)
      .join(', ');

    this.send(`Here are the requested account-opening details: ${details}`);
  }

  sendEditRequest(): void {
    const message = this.conversationText().trim();
    const interruptId = this.pendingInterruptId();
    if (!message || !interruptId || this.busy()) return;

    this.conversationText.set('');
    this.resumeInterrupt(interruptId, {
      action: 'EDIT',
      message,
    });
  }

  private resumeApproval(action: 'APPROVE' | 'REJECT'): void {
    const interruptId = this.pendingInterruptId();
    if (!interruptId) {
      this.error.set('No pending approval was found. Start the account-opening journey again.');
      return;
    }

    const payload = action === 'APPROVE'
      ? { action: 'APPROVE', approved: true }
      : { action: 'REJECT', approved: false };

    this.resumeInterrupt(interruptId, payload);
  }

  private resumeInterrupt(interruptId: string, payload: unknown): void {
    if (this.busy()) return;
    // Keep the ID until RUN_FINISHED confirms whether the graph re-interrupted.
    // This also lets the user retry if the HTTP request fails.
    this.send('', [{
      interruptId,
      status: 'resolved',
      payload,
    }]);
  }

  private send(
    text: string,
    resume?: Array<{ interruptId: string; status: 'resolved'; payload: unknown }>
  ): void {
    if (this.busy()) return;

    this.busy.set(true);
    this.error.set('');

    this.agui.run({
      threadId: this.threadId,
      runId: crypto.randomUUID(),
      messages: text ? [{
        id: crypto.randomUUID(),
        role: 'user',
        content: text,
      }] : [],
      ...(resume ? { resume } : {}),
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
      const ui = snapshot?.['ui'];

      if (ui && typeof ui === 'object' && 'widgetId' in ui && 'mode' in ui && 'title' in ui) {
        console.log('[AG-UI UI STATE]', ui);
        this.uiState.set(ui as AgentUI);
      }
    }

    if (event.type === 'RUN_FINISHED') {
      const outcome = event['outcome'] as
        { type?: string; interrupts?: Array<{ id?: string }> } | undefined;
      if (outcome?.type === 'interrupt') {
        const interruptId = outcome.interrupts?.[0]?.id;
        if (interruptId) {
          this.pendingInterruptId.set(interruptId);
          console.log('[AG-UI INTERRUPT]', interruptId);
        } else {
          this.error.set('The agent paused, but no interrupt ID was returned.');
        }
      } else {
        this.pendingInterruptId.set(null);
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
