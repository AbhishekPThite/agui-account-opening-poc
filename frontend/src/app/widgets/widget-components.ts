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
            [type]="field.type === 'number' || field.type === 'date' ? field.type : 'text'"
            [placeholder]="field.placeholder ?? ''"
            [required]="field.required ?? false"
            [ngModel]="values[field.name] ?? field.defaultValue ?? ''"
            (ngModelChange)="values[field.name] = $event">
        </ng-template>
      </div>

      <div class="form-actions">
        <button class="primary" (click)="submitForm()" [disabled]="!isValid()">Continue</button>
        <button *ngIf="ui.widgetId === 'BENEFICIARY_CAPTURE'" type="button" class="secondary" (click)="skipOptional()">Skip beneficiary</button>
      </div>
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
    .form-actions { display: flex; flex-wrap: wrap; gap: 10px; }
    .secondary { border: 1px solid #cbd5e1; background: white; border-radius: 8px; padding: 10px 14px; font: inherit; }
  `]
})
export class DynamicFormComponent implements OnChanges {
  @Input({ required: true }) ui!: AgentUI;
  @Output() submit = new EventEmitter<Record<string, unknown>>();
  values: Record<string, unknown> = {};

  ngOnChanges(_changes: SimpleChanges): void {
    // A new backend UI snapshot is authoritative. Rebuild the form model so
    // conversationally extracted values replace the previous defaults.
    this.values = {};
    for (const field of this.ui?.fields ?? []) {
      if (field.defaultValue !== undefined) {
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

  skipOptional(): void {
    this.submit.emit({ __beneficiaryAction: 'SKIP' });
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
  selector: 'app-profile-assessment-widget',
  standalone: true,
  imports: [CommonModule],
  template: `
    <section class="widget-card">
      <div class="eyebrow">CLIENT PROFILE · ADAPTIVE REVIEW</div>
      <h2>{{ ui.title }}</h2><p *ngIf="ui.description">{{ ui.description }}</p>
      <div class="status-grid">
        <div><strong>{{ completed().length }}</strong><span>Completed</span></div>
        <div><strong>{{ confirmationRequired().length }}</strong><span>Confirmation required</span></div>
        <div><strong>{{ actionRequired().length }}</strong><span>Action required</span></div>
      </div>
      <section class="profile-group"><h3>Completed</h3>
        <div class="profile-row" *ngFor="let item of completed()"><span>{{ item.label }}</span><strong>{{ item.value }}</strong></div>
      </section>
      <section class="profile-group"><h3>Confirmation required</h3>
        <div class="profile-row" *ngFor="let item of confirmationRequired()"><span>{{ item.label }}</span><strong>{{ item.value }}</strong></div>
        <p *ngIf="confirmationRequired().length === 0">No populated profile fields need confirmation.</p>
      </section>
      <section class="profile-group" *ngIf="actionRequired().length"><h3>Action required</h3>
        <div class="profile-row" *ngFor="let item of actionRequired()"><span>{{ item.label }}</span><strong>{{ item.value }}</strong></div>
      </section>
      <details><summary>Profile section breakdown</summary>
        <div class="profile-section" *ngFor="let section of sections()">
          <strong>{{ section.name }} · {{ section.status.replace('_', ' ') }}</strong>
          <div class="profile-row" *ngFor="let field of section.fields"><span>{{ field.label }}</span><strong>{{ field.value }}</strong></div>
        </div>
      </details>
      <div class="profile-actions">
        <button type="button" (click)="editProfile()">Review or update profile details</button>
        <button class="primary" type="button" (click)="confirmProfile()" [disabled]="actionRequired().length > 0">Confirm profile and continue</button>
      </div>
      <p class="note" *ngIf="actionRequired().length">Required profile information is missing. Complete it before continuing.</p>
    </section>`,
  styles: [`
    .widget-card { display: grid; gap: 14px; }
    .eyebrow { font-size: 11px; letter-spacing: .08em; color: #64748b; }
    h2, h3, p { margin: 0; }
    .status-grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 8px; }
    .status-grid div { display: grid; gap: 4px; padding: 12px; border: 1px solid #e2e8f0; border-radius: 8px; }
    .status-grid strong { font-size: 20px; }.status-grid span, .note { color: #64748b; font-size: 12px; }
    .profile-group, .profile-section { display: grid; gap: 8px; }.profile-group h3 { font-size: 14px; }
    .profile-row { display: flex; justify-content: space-between; gap: 16px; padding: 7px 0; border-bottom: 1px solid #e2e8f0; }
    .profile-row span { color: #64748b; }.profile-row strong { text-align: right; overflow-wrap: anywhere; }
    details { border-top: 1px solid #e2e8f0; padding-top: 10px; } summary { cursor: pointer; font-weight: 600; }
    .profile-actions { display: flex; flex-wrap: wrap; gap: 10px; }.profile-actions button { justify-self: start; }
  `]
})
export class ProfileAssessmentComponent {
  @Input({ required: true }) ui!: AgentUI;
  @Output() submit = new EventEmitter<Record<string, unknown>>();
  private list(key: string): Array<{ label: string; value: string }> {
    const value = this.ui.data?.[key];
    return Array.isArray(value) ? value as Array<{ label: string; value: string }> : [];
  }
  completed() { return this.list('completed'); }
  confirmationRequired() { return this.list('confirmationRequired'); }
  actionRequired() { return this.list('actionRequired'); }
  sections(): Array<{ name: string; status: string; fields: Array<{ label: string; value: string }> }> {
    const value = this.ui.data?.['sections'];
    return Array.isArray(value) ? value as Array<{ name: string; status: string; fields: Array<{ label: string; value: string }> }> : [];
  }
  editProfile(): void {
    this.submit.emit({ __profileAction: 'EDIT' });
  }
  confirmProfile(): void {
    if (!this.actionRequired().length) this.submit.emit({ __profileAction: 'CONFIRM' });
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
