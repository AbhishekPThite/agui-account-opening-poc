import { CommonModule } from '@angular/common';
import { Component, Input } from '@angular/core';
import { AgentUI } from '../models/agent-ui.model';

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
