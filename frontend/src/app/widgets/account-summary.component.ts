import { CommonModule } from '@angular/common';
import { Component, EventEmitter, Input, Output } from '@angular/core';
import { AgentUI } from '../models/agent-ui.model';

@Component({
  selector: 'app-account-summary-widget',
  standalone: true,
  imports: [CommonModule],
  template: `
    <section class="widget-card">
      <div class="eyebrow">APPLICATION SUMMARY</div>
      <h2>{{ ui.title }}</h2>
      <p *ngIf="ui.description">{{ ui.description }}</p>
      <div class="review-accordions" *ngIf="reviewSections().length">
        <details class="review-section" *ngFor="let section of reviewSections()">
          <summary>
            <span class="review-section-title">{{ section.label }}</span>
            <span class="review-section-status"
                  [class.review-complete]="section.status === 'COMPLETED'"
                  [class.review-incomplete]="section.status === 'ACTION_REQUIRED'">
              {{ section.status.replace('_', ' ') }}
            </span>
          </summary>
          <div class="review-fields">
            <div class="summary-row" *ngFor="let item of section.fields"
                 [class.missing-field]="item.missing">
              <span>{{ item.label }} <em *ngIf="item.required">Required</em></span>
              <strong>{{ item.value }}</strong>
            </div>
          </div>
        </details>
      </div>
      <div class="approval-actions" *ngIf="ui.approvalRequired">
        <button class="approve" type="button" (click)="approve()">Confirm and create draft</button>
        <button class="reject" type="button" (click)="reject()">Reject / stop</button>
        <p class="approval-note">A draft is created only after you confirm. Rejecting creates no draft.</p>
      </div>
    </section>
  `,
  styles: [`
    .widget-card { display: grid; gap: 12px; }
    .eyebrow { font-size: 11px; letter-spacing: .08em; color: #64748b; }
    h2, p { margin: 0; }
    .summary-row { display: flex; justify-content: space-between; gap: 16px; padding: 9px 0; border-bottom: 1px solid #e2e8f0; }
    .summary-row span { color: #64748b; }
    .summary-row strong { text-align: right; overflow-wrap:anywhere; }
    .review-accordions { display:grid; gap:10px; }
    .review-section { border:1px solid #dce4ec; border-radius:10px; padding:0 14px; }
    .review-section summary { display:flex; align-items:center; justify-content:space-between; gap:12px; padding:14px 0; list-style:none; }
    .review-section summary::-webkit-details-marker { display:none; }
    .review-section summary::after { content:'+'; color:#24598f; font-size:18px; font-weight:700; }
    .review-section[open] summary::after { content:'−'; }
    .review-section-title { font-weight:700; color:#182230; }
    .review-section-status { margin-left:auto; font-size:10px; font-weight:800; letter-spacing:.04em; color:#64748b; }
    .review-complete { color:#13764f; }
    .review-incomplete { color:#985b0c; }
    .review-fields { padding:0 0 10px; }
    .missing-field { background:#fff8e8; }
    .missing-field strong { color:#985b0c; }
    .summary-row em { display:inline-block; margin-left:5px; color:#985b0c; font-size:9px; font-style:normal; text-transform:uppercase; }
    .approval-actions { display: flex; flex-wrap: wrap; gap: 10px; padding-top: 8px; }
    .approval-actions button { padding: 10px 14px; border: 0; border-radius: 8px; cursor: pointer; font: inherit; font-weight: 600; }
    .approve { background: #166534; color: white; }
    .reject { background: #e2e8f0; color: #1e293b; }
    .approval-note { flex-basis: 100%; color: #64748b; font-size: 12px; }
  `]
})
export class AccountSummaryComponent {
  @Input({ required: true }) ui!: AgentUI;
  @Output() submit = new EventEmitter<Record<string, unknown>>();

  approve(): void {
    this.submit.emit({ __approvalAction: 'APPROVE' });
  }

  reject(): void {
    this.submit.emit({ __approvalAction: 'REJECT' });
  }

  reviewSections(): Array<{
    id: string;
    label: string;
    status: string;
    fields: Array<{ label: string; value: string; required?: boolean; missing?: boolean }>;
  }> {
    const value = this.ui.data?.['reviewSections'];
    return Array.isArray(value) ? value as Array<{
      id: string;
      label: string;
      status: string;
      fields: Array<{ label: string; value: string; required?: boolean; missing?: boolean }>;
    }> : [];
  }

  entries(): Array<{ label: string; value: string }> {
    return Object.entries(this.ui.data ?? {})
      .filter(([key, value]) => key !== 'reviewSections' && (value === null || typeof value !== 'object'))
      .map(([key, value]) => ({
        label: key.replace(/([A-Z])/g, ' $1').replace(/^./, c => c.toUpperCase()),
        value: value === null || value === undefined ? '—' : String(value)
      }));
  }
}
