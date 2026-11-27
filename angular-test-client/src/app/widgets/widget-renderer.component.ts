import {
  Component,
  ComponentRef,
  EventEmitter,
  Input,
  OnChanges,
  OnDestroy,
  Output,
  SimpleChanges,
  Type,
  ViewContainerRef
} from '@angular/core';
import { AgentUI, AgentWidgetInstance } from '../models/agent-ui.model';
import { WIDGET_REGISTRY } from './widget-registry';

@Component({
  selector: 'app-widget-renderer',
  standalone: true,
  template: `
    <ng-container #widgetHost></ng-container>
    <section class="unsupported" *ngIf="unsupportedWidget">
      This UI widget is not registered: {{ unsupportedWidget }}
    </section>
  `,
  styles: [`
    .unsupported { padding: 12px; border: 1px solid #d97706; border-radius: 8px; color: #92400e; }
  `]
})
export class WidgetRendererComponent implements OnChanges, OnDestroy {
  @Input() ui: AgentUI | null = null;
  @Output() submit = new EventEmitter<Record<string, unknown>>();

  private componentRef?: ComponentRef<AgentWidgetInstance>;
  private activeWidgetId?: string;
  private submitSubscription?: { unsubscribe(): void };
  unsupportedWidget = '';

  constructor(private readonly viewContainer: ViewContainerRef) {}

  ngOnChanges(_changes: SimpleChanges): void {
    if (!this.ui) {
      this.clearWidget();
      return;
    }

    const widgetId = this.ui.widgetId;
    const componentType = WIDGET_REGISTRY[widgetId];

    if (!componentType) {
      this.clearWidget();
      this.unsupportedWidget = widgetId;
      return;
    }

    this.unsupportedWidget = '';

    if (!this.componentRef || this.activeWidgetId !== widgetId) {
      this.clearWidget();
      this.componentRef = this.viewContainer.createComponent(
        componentType as Type<AgentWidgetInstance>
      );
      this.activeWidgetId = widgetId;

      const output = this.componentRef.instance.submit;
      if (output) {
        this.submitSubscription = output.subscribe(value => this.submit.emit(value));
      }
    }

    this.componentRef.setInput('ui', this.ui);
  }

  ngOnDestroy(): void {
    this.clearWidget();
  }

  private clearWidget(): void {
    this.submitSubscription?.unsubscribe();
    this.submitSubscription = undefined;
    this.viewContainer.clear();
    this.componentRef = undefined;
    this.activeWidgetId = undefined;
  }
}
