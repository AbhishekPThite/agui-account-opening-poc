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
