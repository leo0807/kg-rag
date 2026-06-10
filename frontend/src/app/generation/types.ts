export interface GenerationTask {
  id: string;
  task_name: string;
  spec_type: string;
  template_id: string;
  status: "pending" | "running" | "done" | "failed" | "finalized";
  progress: number;
  current_step: string;
  inputs: GenerationInput;
  result_sections: Record<string, string> | null;
  validation_report: ValidationReport | null;
  error: string;
  created_at: string;
  completed_at: string | null;
}

export interface GenerationInput {
  spec_name: string;
  spec_type: string;
  template_id: string;
  reference_docs: string[];
  test_data: unknown | null;
  user_requirements: string;
  target_application: string;
  must_reference: string[];
  must_include_sections: string[];
}

export interface SpecTemplate {
  id: string;
  template_id: string;
  name: string;
  applicable_to: string[];
  structure: { sections: TemplateSection[] };
  sample_doc_ids: string[];
  created_at: string;
}

export interface TemplateSection {
  number?: string;
  title: string;
  required: boolean;
  min_words?: number;
}

export interface ValidationReport {
  overall_score: number;
  requires_human_review: boolean;
  issues: ValidationIssue[];
  suggestions: string[];
}

export interface ValidationIssue {
  severity: "critical" | "major" | "minor";
  section: string;
  description: string;
  suggestion: string;
}

export const STATUS_LABELS: Record<string, string> = {
  pending:   "待启动",
  running:   "生成中",
  done:      "已完成",
  failed:    "失败",
  finalized: "已定稿",
};

export const STATUS_COLORS: Record<string, string> = {
  pending:   "bg-gray-700 text-gray-300",
  running:   "bg-blue-900/50 text-blue-300",
  done:      "bg-green-900/50 text-green-300",
  failed:    "bg-red-900/50 text-red-400",
  finalized: "bg-indigo-900/50 text-indigo-300",
};
