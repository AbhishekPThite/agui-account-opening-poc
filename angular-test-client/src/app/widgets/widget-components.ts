import { CommonModule } from '@angular/common';
import { Component, EventEmitter, Input, Output, OnChanges, SimpleChanges } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { AgentUI, AgentUIField } from '../models/agent-ui.model';

@Component({
  selector: 'app-dynamic-form-widget',
  standalone: true,
  imports: [CommonModule, FormsModule],
  template: `
    <section class="widget-card">
      <div class="eyebrow">DYNAMIC FORM · {{ ui.widgetId }}</div>
      <h2>{{ ui.title }}</h2>
      <p *ngIf="ui.description">{{ ui.description }}</p>

      <div class="field" *ngFor="let field of ui.fields ?? []">
        <label [for]="field.name">
          {{ field.label }} <span *ngIf="field.required" aria-hidden="true">*</span>
        </label>

        <select
          *ngIf="field.type === 'select'; else textInput"
          [id]="field.name"
          [ngModel]="values[field.name] ?? field.defaultValue ?? ''"
          (ngModelChange)="values[field.name] = $event">
          <option value="">Select...</option>
          <option *ngFor="let option of field.options ?? []" [value]="option">
            {{ option }}
          </option>
        </select>

        <ng-template #textInput>
          <input
            [id]="field.name"
            [type]="field.type === 'number' ? 'number' : 'text'"
            [placeholder]="field.placeholder ?? ''"
            [required]="field.required ?? false"
            [ngModel]="values[field.name] ?? field.defaultValue ?? ''"
            (ngModelChange)="values[field.name] = $event">
        </ng-template>
      </div>

      <button class="primary" (click)="submitForm()" [disabled]="!isValid()">
        Continue
      </button>
    </section>
  `,
  styles: [`
    .widget-card { display: grid; gap: 12px; }
    .field { display: grid; gap: 6px; }
    label { font-weight: 600; }
    input, select { width: 100%; box-sizing: border-box; padding: 11px; border: 1px solid #cbd5e1; border-radius: 8px; font: inherit; }
    .eyebrow { font-size: 11px; letter-spacing: .08em; color: #64748b; }
    h2, p { margin: 0; }
    button { justify-self: start; }
  `]
})
export class DynamicFormComponent implements OnChanges {
  @Input({ required: true }) ui!: AgentUI;
  @Output() submit = new EventEmitter<Record<string, unknown>>();
  values: Record<string, unknown> = {};

  ngOnChanges(_changes: SimpleChanges): void {
    // Materialize backend defaults into the form model so they are both visible
    // and included in the structured submission, even when the user leaves them unchanged.
    for (const field of this.ui?.fields ?? []) {
      if (this.values[field.name] === undefined && field.defaultValue !== undefined) {
        this.values[field.name] = field.defaultValue;
      }
    }
  }

  isValid(): boolean {
    const fields = this.ui.fields ?? [];
    return fields.every((field: AgentUIField) => {
      if (!field.required) return true;
      const value = this.values[field.name] ?? field.defaultValue;
      return value !== undefined && value !== null && String(value).trim().length > 0;
    });
  }

  submitForm(): void {
    if (this.isValid()) this.submit.emit({ ...this.values });
  }
}

@Component({
  selector: 'app-account-summary-widget',
  standalone: true,
  imports: [CommonModule],
  template: `
    <section class="widget-card">
      <div class="eyebrow">APPLICATION SUMMARY</div>
      <h2>{{ ui.title }}</h2>
      <p *ngIf="ui.description">{{ ui.description }}</p>
      <div class="summary-row" *ngFor="let item of entries()">
        <span>{{ item.label }}</span>
        <strong>{{ item.value }}</strong>
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
    .summary-row strong { text-align: right; }
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

  entries(): Array<{ label: string; value: string }> {
    return Object.entries(this.ui.data ?? {}).map(([key, value]) => ({
      label: key.replace(/([A-Z])/g, ' $1').replace(/^./, c => c.toUpperCase()),
      value: value === null || value === undefined ? '—' : String(value)
    }));
  }
}

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

@Component({
  selector: 'app-information-alert-widget',
  standalone: true,
  imports: [CommonModule],
  template: `
    <section class="widget-card alert">
      <div class="eyebrow">INFORMATION</div>
      <h2>{{ ui.title }}</h2>
      <p>{{ ui.description ?? ui.data?.['message'] }}</p>
    </section>
  `,
  styles: [`
    .widget-card { display: grid; gap: 8px; padding: 12px; border-left: 4px solid #64748b; }
    .eyebrow { font-size: 11px; letter-spacing: .08em; color: #64748b; }
    h2, p { margin: 0; }
  `]
})
export class InformationAlertComponent {
  @Input({ required: true }) ui!: AgentUI;
}
