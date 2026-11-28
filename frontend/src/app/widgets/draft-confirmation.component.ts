import { CommonModule } from '@angular/common';
import { Component, Input } from '@angular/core';
import { AgentUI } from '../models/agent-ui.model';

@Component({
  selector: 'app-draft-confirmation-widget',
  standalone: true,
  imports: [CommonModule],
  template: `
    <section class="widget-card success">
      <div class="eyebrow">POC COMPLETE</div>
      <h2>{{ ui.title }}</h2>
      <p>{{ ui.description ?? 'A mock account-opening draft was created. No real account has been opened.' }}</p>
      <div class="summary-row" *ngFor="let item of entries()">
        <span>{{ item.label }}</span>
        <strong>{{ item.value }}</strong>
      </div>
    </section>
  `,
  styles: [`
    .widget-card { display: grid; gap: 12px; }
    .success { border-left: 4px solid #16a34a; padding-left: 14px; }
    .eyebrow { font-size: 11px; letter-spacing: .08em; color: #64748b; }
    h2, p { margin: 0; }
    .summary-row { display: flex; justify-content: space-between; gap: 16px; padding: 7px 0; border-bottom: 1px solid #e2e8f0; }
    .summary-row span { color: #64748b; }
  `]
})
export class DraftConfirmationComponent {
  @Input({ required: true }) ui!: AgentUI;

  entries(): Array<{ label: string; value: string }> {
    return Object.entries(this.ui.data ?? {}).map(([key, value]) => ({
      label: key.replace(/([A-Z])/g, ' $1').replace(/^./, c => c.toUpperCase()),
      value: value === null || value === undefined ? '—' : String(value)
    }));
  }
}
