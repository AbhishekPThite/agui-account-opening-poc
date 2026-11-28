import { CommonModule } from '@angular/common';
import { Component, EventEmitter, Input, Output } from '@angular/core';
import { AgentUI } from '../models/agent-ui.model';

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
