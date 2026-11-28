import { CommonModule } from '@angular/common';
import { Component, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { ConversationService } from './conversation.service';
import { JourneyStateService } from './journey-state.service';
import { WidgetInteractionService } from './widget-interaction.service';
import { WidgetRendererComponent } from './widgets/widget-renderer.component';

@Component({
  selector: 'app-account-opening-agent',
  standalone: true,
  imports: [CommonModule, FormsModule, WidgetRendererComponent],
  templateUrl: './account-opening-agent.component.html'
})
export class AccountOpeningAgentComponent {
  prompt = signal('Open a joint brokerage account for client C12345.');
  conversationText = signal('');

  readonly events = this.journey.events;
  readonly assistantText = this.journey.assistantText;
  readonly uiState = this.journey.uiState;
  readonly busy = this.journey.busy;
  readonly error = this.journey.error;
  readonly pendingInterruptId = this.journey.pendingInterruptId;

  constructor(
    private readonly conversation: ConversationService,
    private readonly journey: JourneyStateService,
    private readonly widgetInteractions: WidgetInteractionService
  ) {}

  start(): void {
    if (this.busy()) return;
    this.conversationText.set('');
    this.conversation.start(this.prompt());
  }

  submitWidget(payload: Record<string, unknown>): void {
    const command = this.widgetInteractions.toCommand(payload, this.uiState());
    if (command.type === 'resume') {
      const interruptId = this.pendingInterruptId();
      if (!interruptId) {
        this.journey.setError('No pending approval was found. Start the account-opening journey again.');
        return;
      }
      this.conversation.resume(interruptId, command.payload);
      return;
    }
    this.conversation.sendMessage(command.text);
  }

  completionPercent(): number {
    return this.journey.completionPercent();
  }

  openSection(sectionId: string): void {
    if (this.busy() || this.pendingInterruptId()) return;
    const allowed = new Set([
      'PROFILE', 'ACCOUNT_DETAILS', 'RISK_PROFILE',
      'FEATURES', 'SUMMARY', 'DASHBOARD'
    ]);
    if (!allowed.has(sectionId)) {
      this.journey.setError('That application section is not supported.');
      return;
    }
    this.conversation.sendMessage('POC_FORM_SUBMISSION:' + JSON.stringify({
      formId: 'DASHBOARD_NAVIGATION',
      section: sectionId
    }));
  }

  returnToDashboard(): void {
    this.openSection('DASHBOARD');
  }

  sendJourneyMessage(): void {
    const message = this.conversationText().trim();
    if (!message || this.busy() || !this.uiState()) return;
    this.conversationText.set('');
    this.conversation.sendMessage(message);
  }
}
