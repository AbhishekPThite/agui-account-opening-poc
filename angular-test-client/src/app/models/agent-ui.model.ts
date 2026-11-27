export type AgentWidgetId =
  | 'JOINT_OWNER_FORM'
  | 'APPLICATION_SUMMARY'
  | 'DRAFT_CONFIRMATION'
  | 'INFORMATION_ALERT';

export type AgentUiMode = 'FORM' | 'SUMMARY' | 'COMPLETE' | 'ALERT';
export type AgentFieldType = 'text' | 'number' | 'select';

export interface AgentUIField {
  name: string;
  label: string;
  type: AgentFieldType;
  required?: boolean;
  placeholder?: string;
  options?: string[];
}

export interface AgentUI {
  mode: AgentUiMode;
  widgetId: AgentWidgetId | string;
  title: string;
  description?: string;
  fields?: AgentUIField[];
  data?: Record<string, unknown>;
  approvalRequired?: boolean;
}

export interface AgentWidgetInstance {
  ui: AgentUI;
  submit?: import('@angular/core').EventEmitter<Record<string, unknown>>;
}
