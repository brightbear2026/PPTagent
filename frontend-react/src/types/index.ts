/* ============================================================
   PPT Agent — TypeScript 类型定义
   ============================================================ */

// ── 用户与认证 ──

export interface User {
  id: string;
  username: string;
  created_at: string;
}

export interface AuthResponse {
  access_token: string;
  token_type: string;
  user: User;
}

// ── 任务状态 ──

export type TaskStatusEnum =
  | 'pending'
  | 'processing'
  | 'checkpoint'
  | 'completed'
  | 'failed'
  | 'cancelled';

export type PipelineStageName = 'parse' | 'analyze' | 'outline' | 'content' | 'design' | 'render';

export interface TaskInfo {
  task_id: string;
  title: string;
  status: TaskStatusEnum;
  progress: number;          // 0-100
  current_step: string;
  current_stage?: PipelineStageName;
  message: string;
  created_at: string;
  output_file?: string | null;
  error?: string | null;
  narrative?: { narrative_logic: string; page_count: number };
  slides?: { total_pages: number; failed_pages: number[] };
}

export interface StageInfo {
  stage: PipelineStageName;
  status: 'pending' | 'running' | 'completed' | 'failed';
  started_at?: string | null;
  completed_at?: string | null;
  error?: string | null;
}

export interface SkippedPage {
  page_number: number;
  reason: string;
}

// ── 大纲 ──

export interface OutlineItem {
  page_number: number;
  slide_type: string;       // "title" | "content" | "data" | "diagram" | "comparison" | "summary"
  takeaway_message: string;
  supporting_hint: string;
  data_source: string;
}

export interface OutlineResult {
  narrative_logic: string;
  items: OutlineItem[];
  data_gap_suggestions: string[];
}

// ── 内容 ──

export interface TextBlock {
  content: string;
  level: number;            // 0=paragraph, 1=bullet, 2=sub-bullet
  is_bold: boolean;
}

export interface ChartSuggestion {
  chart_type: string;       // "column" | "bar" | "line" | "pie" | "combo" | "area" | "scatter" | "waterfall"
  data_feature?: string;
  title: string;
  categories: string[];
  series: ChartSeriesData[];
  so_what: string;
}

export interface ChartSeriesData {
  name: string;
  values: number[];
}

export interface ContentDiagramSpec {
  diagram_type: string;     // "process_flow" | "architecture" | "relationship" | "framework"
  title: string;
  direction?: string;
  nodes?: DiagramNodeData[];
  connections?: DiagramConnectionData[];
  layers?: DiagramLayerData[];
  edges?: DiagramEdgeData[];
  variant?: string;
  // framework variants
  x_axis?: { label: string; low: string; high: string };
  y_axis?: { label: string; low: string; high: string };
  quadrants?: DiagramQuadrantData[];
  pyramid_levels?: DiagramLevelData[];
  funnel_stages?: DiagramStageData[];
}

export interface DiagramNodeData {
  id: string;
  label: string;
  desc?: string;
  role?: string;
}

export interface DiagramConnectionData {
  from: string;
  to: string;
  label?: string;
}

export interface DiagramLayerData {
  label: string;
  items: string[];
}

export interface DiagramEdgeData {
  from: string;
  to: string;
  label?: string;
  type?: string;
}

export interface DiagramQuadrantData {
  position: string;
  label: string;
  items: string[];
}

export interface DiagramLevelData {
  label: string;
  desc?: string;
}

export interface DiagramStageData {
  label: string;
  value?: number;
}

export interface SlideContent {
  page_number: number;
  slide_type: string;
  takeaway_message: string;
  text_blocks: TextBlock[];
  chart_suggestion: ChartSuggestion | null;
  diagram_spec: ContentDiagramSpec | null;
  source_note: string;
  is_failed?: boolean;
  error_message?: string;
  warnings?: string[];
}

export interface ContentResult {
  total_pages: number;
  failed_pages: number[];
  slides: SlideContent[];
}

// ── 分析结果 ──

export interface DerivedMetric {
  name: string;
  formatted_value: string;
  metric_type: string;
  context?: string;
}

export interface AnalysisResult {
  derived_metrics: DerivedMetric[];
  key_findings: string[];
  data_gaps: DataGap[];
  validation_warnings: ValidationWarning[];
}

export interface DataGap {
  gap_description: string;
  importance: string;
}

export interface ValidationWarning {
  message: string;
  severity: string;
}

// ── 模型配置 ──

export interface StageModelConfig {
  provider: string;
  model: string;
  api_key: string;
  base_url?: string;
  has_api_key: boolean;
  temperature: number;
  max_tokens: number;
}

export interface PipelineModelConfig {
  config_mode?: 'universal' | 'advanced';
  analyze: StageModelConfig;
  outline: StageModelConfig;
  content: StageModelConfig;
  design: StageModelConfig;
  build: StageModelConfig;   // backward compat alias for design
}

// ── SSE ──

export interface SSEProgressEvent {
  task_id: string;
  status: TaskStatusEnum;
  progress: number;
  current_step: string;
  message: string;
  output_file?: string | null;
  error?: string | null;
}

// ── 历史 ──

export interface HistoryItem {
  task_id: string;
  title: string;
  status: TaskStatusEnum;
  created_at: string;
  output_file?: string | null;
}

// ── 向导步骤 ──

export type WizardStep = 1 | 2 | 3 | 4;

export interface GenerateParams {
  title: string;
  target_audience: string;
  scenario?: string;
  language: string;
}
