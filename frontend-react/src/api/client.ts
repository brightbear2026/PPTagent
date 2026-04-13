/* ============================================================
   PPT Agent — Axios API Client
   ============================================================ */

import axios from 'axios';
import type {
  TaskInfo,
  StageInfo,
  HistoryItem,
  PipelineModelConfig,
} from '../types';

const API_BASE = import.meta.env.VITE_API_BASE || '/api';

// ── Axios 实例 ──

const http = axios.create({
  baseURL: API_BASE,
  timeout: 30_000,
});

http.interceptors.request.use((config) => {
  const token = localStorage.getItem('token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

http.interceptors.response.use(
  (res) => res,
  (err) => {
    if (err.response?.status === 401) {
      localStorage.removeItem('token');
      window.location.href = '/login';
    }
    return Promise.reject(err);
  },
);

// ── Auth (matches backend AuthResponse format) ──

export interface BackendAuthResponse {
  user_id: string;
  username: string;
  token: string;
  expires_at: string;
}

export async function login(username: string, password: string): Promise<{ token: string; user: { id: string; username: string } }> {
  const { data } = await http.post<BackendAuthResponse>('/auth/login', { username, password });
  return {
    token: data.token,
    user: { id: data.user_id, username: data.username },
  };
}

export async function register(username: string, password: string): Promise<{ token: string; user: { id: string; username: string } }> {
  const { data } = await http.post<BackendAuthResponse>('/auth/register', { username, password });
  return {
    token: data.token,
    user: { id: data.user_id, username: data.username },
  };
}

// ── Health ──

export async function checkHealth() {
  const { data } = await http.get('/health');
  return data;
}

// ── Generate ──

export async function generateFromText(params: {
  title: string;
  content: string;
  target_audience: string;
  scenario?: string;
  language: string;
}) {
  const { data } = await http.post('/generate', params);
  return data as { task_id: string; status: string; message: string };
}

export async function generateFromFile(file: File, params: {
  title: string;
  target_audience: string;
  scenario?: string;
  language: string;
}) {
  const form = new FormData();
  form.append('file', file);
  form.append('title', params.title);
  form.append('target_audience', params.target_audience);
  if (params.scenario) form.append('scenario', params.scenario);
  form.append('language', params.language);
  const { data } = await http.post('/generate/file', form, {
    headers: { 'Content-Type': 'multipart/form-data' },
    timeout: 120_000,
  });
  return data as { task_id: string; status: string; message: string };
}

// ── Task Status ──

export async function getTaskStatus(taskId: string): Promise<TaskInfo> {
  const { data } = await http.get(`/status/${taskId}/json`);
  return data;
}

export async function getStages(taskId: string): Promise<StageInfo[]> {
  const { data } = await http.get(`/task/${taskId}/stages`);
  return data.stages;
}

export async function getStageResult(taskId: string, stage: string): Promise<any> {
  const { data } = await http.get(`/task/${taskId}/stage/${stage}`);
  return data;
}

// ── Checkpoint ──

export async function confirmCheckpoint(taskId: string) {
  const { data } = await http.post(`/task/${taskId}/confirm`);
  return data;
}

export async function resumePipeline(taskId: string, fromStage?: string) {
  const { data } = await http.post(`/task/${taskId}/resume`, null, {
    params: fromStage ? { from_stage: fromStage } : undefined,
  });
  return data;
}

// ── Edit Stage ──

export async function updateStage(taskId: string, stage: string, result: any) {
  const { data } = await http.put(`/task/${taskId}/stage/${stage}`, result);
  return data;
}

// ── Rerun Page ──

export async function rerunPage(taskId: string, pageNumber: number) {
  const { data } = await http.post(`/task/${taskId}/rerun-page/${pageNumber}`);
  return data;
}

// ── Supplement ──

export async function supplementData(taskId: string, body: {
  stage: string;
  page_number?: number | null;
  text_data: string;
}) {
  const { data } = await http.post(`/task/${taskId}/supplement`, body);
  return data;
}

// ── Model Config ──

export async function getModelConfig(): Promise<{ config: PipelineModelConfig; available_providers: string[] }> {
  const { data } = await http.get('/config/models');
  return data;
}

export async function updateModelConfig(stages: Record<string, any>) {
  const { data } = await http.put('/config/models', stages);
  return data;
}

// ── Download ──

export function getDownloadUrl(taskId: string): string {
  return `${API_BASE}/download/${taskId}`;
}

// ── History ──

export async function getHistory(limit = 20): Promise<{ total: number; items: HistoryItem[] }> {
  const { data } = await http.get('/history', { params: { limit } });
  return data;
}

// ── Delete Task ──

export async function deleteTask(taskId: string) {
  const { data } = await http.delete(`/task/${taskId}`);
  return data;
}
