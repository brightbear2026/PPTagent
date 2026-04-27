/* ============================================================
   WizardPage — 4-step PPT creation wizard
   ============================================================ */

import React, { useState, useEffect, useRef, useCallback } from 'react';
import { useSearchParams } from 'react-router-dom';
import { Steps, message, Alert, Button } from 'antd';
import {
  UploadOutlined,
  FileSearchOutlined,
  EditOutlined,
  DownloadOutlined,
} from '@ant-design/icons';
import Step1Upload from '../components/wizard/Step1Upload';
import Step2Outline from '../components/wizard/Step2Outline';
import Step3Content from '../components/wizard/Step3Content';
import Step4Download from '../components/wizard/Step4Download';
import { useSSE } from '../hooks/useSSE';
import { getTaskStatus, getStageResult, confirmCheckpoint, resumePipeline } from '../api/client';
import type { WizardStep, TaskInfo, OutlineResult, ContentResult, SkippedPage } from '../types';

const stepItems = [
  { title: '上传输入', icon: <UploadOutlined /> },
  { title: '确认大纲', icon: <FileSearchOutlined /> },
  { title: '编辑内容', icon: <EditOutlined /> },
  { title: '下载PPT', icon: <DownloadOutlined /> },
];

const WizardPage: React.FC = () => {
  const [searchParams, setSearchParams] = useSearchParams();

  // Initialize state from URL params so navigating away and back restores wizard
  const [current, setCurrent] = useState<WizardStep>(
    () => (Number(searchParams.get('step')) || 1) as WizardStep,
  );
  const [taskId, setTaskId] = useState<string | null>(
    () => searchParams.get('task'),
  );
  const [taskInfo, setTaskInfo] = useState<TaskInfo | null>(null);
  const [outline, setOutline] = useState<OutlineResult | null>(null);
  const [outlineGeneration, setOutlineGeneration] = useState<number>(0);
  const [content, setContent] = useState<ContentResult | null>(null);
  const [contentGeneration, setContentGeneration] = useState<number>(0);
  const [buildFailed, setBuildFailed] = useState(false);
  const [failedError, setFailedError] = useState<string | null>(null);
  const [skippedPages, setSkippedPages] = useState<SkippedPage[]>([]);

  const sse = useSSE();

  // Use refs to avoid stale closures in SSE handler
  const taskIdRef = useRef<string | null>(taskId);
  const currentRef = useRef<WizardStep>(current);

  // Keep refs in sync
  useEffect(() => { taskIdRef.current = taskId; }, [taskId]);
  useEffect(() => { currentRef.current = current; }, [current]);

  // Sync state → URL params + localStorage so navigation preserves wizard progress
  useEffect(() => {
    const params: Record<string, string> = {};
    if (taskId) params.task = taskId;
    if (taskId && current > 1) params.step = String(current);
    setSearchParams(params, { replace: true });
    // Persist active task to localStorage for cross-page restoration
    if (taskId) {
      localStorage.setItem('ppt_active_task', JSON.stringify({ taskId, step: current }));
    } else {
      localStorage.removeItem('ppt_active_task');
    }
  }, [taskId, current, setSearchParams]);

  // Restore task data on mount: URL params take priority, fallback to localStorage
  useEffect(() => {
    const tid = searchParams.get('task');
    const step = Number(searchParams.get('step')) || 1;
    if (tid) {
      sse.connect(tid);
      restoreTaskData(tid, step);
    } else {
      // No URL param — check localStorage for active task
      const saved = localStorage.getItem('ppt_active_task');
      if (saved) {
        try {
          const { taskId: savedId, step: savedStep } = JSON.parse(saved);
          if (savedId) {
            setTaskId(savedId);
            setCurrent(savedStep || 1);
            sse.connect(savedId);
            restoreTaskData(savedId, savedStep || 1);
          }
        } catch {
          localStorage.removeItem('ppt_active_task');
        }
      }
    }
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const restoreTaskData = async (tid: string, step: number) => {
    try {
      const task = await getTaskStatus(tid);
      setTaskInfo(task);

      if (step >= 2) {
        try {
          const stageData = await getStageResult(tid, 'outline');
          if (stageData?.result) {
            setOutline(stageData.result);
            setOutlineGeneration(stageData.generation ?? 0);
          }
        } catch (e) { console.warn('恢复大纲数据失败:', e); }
      }
      if (step >= 3) {
        try {
          const stageData = await getStageResult(tid, 'content');
          if (stageData?.result) {
            setContent(stageData.result);
            setContentGeneration(stageData.generation ?? 0);
          }
        } catch (e) { console.warn('恢复内容数据失败:', e); }
      }
    } catch (e) { console.warn('恢复任务数据失败:', e); }
  };

  // Fetch outline data
  const fetchOutline = useCallback(async (tid?: string) => {
    const id = tid || taskIdRef.current;
    if (!id) return;
    try {
      const stageData = await getStageResult(id, 'outline');
      if (stageData?.result) {
        setOutline(stageData.result);
        setOutlineGeneration(stageData.generation ?? 0);
      }
    } catch (e) { console.warn('获取大纲失败:', e); }
  }, []);

  // Fetch content data
  const fetchContent = useCallback(async (tid?: string) => {
    const id = tid || taskIdRef.current;
    if (!id) return;
    try {
      const stageData = await getStageResult(id, 'content');
      if (stageData?.result) {
        setContent(stageData.result);
        setContentGeneration(stageData.generation ?? 0);
      }
    } catch (e) { console.warn('获取内容失败:', e); }
  }, []);

  // SSE progress handler — use sse.latest directly, deps on the whole object
  useEffect(() => {
    if (!sse.latest) return;

    const { status, current_step } = sse.latest;
    setTaskInfo(sse.latest as TaskInfo);

    const step = currentRef.current;

    if (status === 'checkpoint') {
      setFailedError(null);
      if (step <= 1 && (current_step?.includes('大纲') || current_step?.includes('outline'))) {
        setCurrent(2);
        fetchOutline();
      } else if (step <= 2 && (current_step?.includes('内容') || current_step?.includes('content'))) {
        setCurrent(3);
        fetchContent();
      }
    } else if (status === 'completed') {
      setFailedError(null);
      setCurrent(4);
      // Fetch design stage to surface any skipped-page warnings
      const id = taskIdRef.current;
      if (id) {
        getStageResult(id, 'design').then(stageData => {
          const pages: SkippedPage[] = stageData?.result?.skipped_pages ?? [];
          if (pages.length > 0) setSkippedPages(pages);
        }).catch(() => {});
      }
    } else if (status === 'failed') {
      const errMsg = sse.latest.error || '未知错误';
      setFailedError(errMsg);
      if (step === 3) setBuildFailed(true);
    }
  }, [sse.latest, fetchOutline, fetchContent]);

  // Step 1 → start generation
  const handleStart = (id: string) => {
    setTaskId(id);
    taskIdRef.current = id;
    sse.connect(id);
  };

  // Step 2 → confirm outline
  const handleOutlineConfirm = async () => {
    const tid = taskIdRef.current;
    if (!tid) return;
    try {
      await confirmCheckpoint(tid);
      message.info('正在生成内容...');
    } catch (err: any) {
      message.error(err.response?.data?.detail || '确认失败');
    }
  };

  // Step 3 → confirm content
  const handleContentConfirm = async () => {
    const tid = taskIdRef.current;
    if (!tid) return;
    try {
      setBuildFailed(false);
      await confirmCheckpoint(tid);
      message.info('正在构建PPT...');
    } catch (err: any) {
      message.error(err.response?.data?.detail || '确认失败');
    }
  };

  // Step 2 → back to Step 1 (re-upload)
  const handleBackToUpload = () => {
    setCurrent(1);
  };

  // Step 3 → back to Step 2 (re-edit outline, downstream stages will be reset)
  const handleBackToOutline = async () => {
    const tid = taskIdRef.current;
    if (!tid) return;
    try {
      // Backend resets downstream stages (content/design/render) but keeps outline intact
      await resumePipeline(tid, 'outline');
      await fetchOutline(tid);
      setContent(null);
      setContentGeneration(0);
      setCurrent(2);
      sse.connect(tid);
      message.info('已返回大纲编辑');
    } catch (err: any) {
      message.error(err.response?.data?.detail || '返回失败');
    }
  };

  // Reset
  const handleNew = () => {
    setTaskId(null);
    setOutline(null);
    setContent(null);
    setTaskInfo(null);
    setSkippedPages([]);
    setCurrent(1);
    setBuildFailed(false);
    setFailedError(null);
    sse.disconnect();
    localStorage.removeItem('ppt_active_task');
  };

  return (
    <div style={{ padding: '24px 32px', maxWidth: 1400, margin: '0 auto' }}>
      <Steps
        current={current - 1}
        items={stepItems}
        style={{ marginBottom: 32, padding: '0 20px' }}
      />

      {/* Progress bar — show during any processing phase */}
      {sse.progress > 0 && !sse.isFinished && (
        <div style={{
          background: '#fff', padding: '12px 20px', borderRadius: 2,
          marginBottom: 20, display: 'flex', alignItems: 'center', gap: 12,
        }}>
          <div style={{ flex: 1, height: 4, background: '#E8E4D9', borderRadius: 2, overflow: 'hidden' }}>
            <div style={{
              width: `${sse.progress}%`, height: '100%',
              background: 'linear-gradient(90deg, #003D6E, #C9A84C)',
              transition: 'width 0.3s ease',
            }} />
          </div>
          <span style={{ color: '#8B9DAF', fontSize: 13, whiteSpace: 'nowrap' }}>
            {sse.latest?.current_step || '处理中...'} ({sse.progress}%)
          </span>
        </div>
      )}

      {/* Error banner — persistent display when task fails */}
      {failedError && (
        <Alert
          type="error"
          showIcon
          closable
          onClose={() => setFailedError(null)}
          message="生成失败"
          description={failedError}
          action={
            <Button size="small" danger onClick={handleNew}>
              重新开始
            </Button>
          }
          style={{ marginBottom: 20 }}
        />
      )}

      {/* Step content */}
      <div style={{ minHeight: 500 }}>
        {current === 1 && (
          <Step1Upload
            onStart={handleStart}
            loading={!!taskId && !sse.isFinished && !failedError}
            progress={sse.progress}
          />
        )}
        {current === 2 && taskId && outline && (
          <Step2Outline
            taskId={taskId}
            outline={outline}
            generation={outlineGeneration}
            onConfirm={handleOutlineConfirm}
            onBack={handleBackToUpload}
          />
        )}
        {current === 3 && taskId && content && (
          <Step3Content
            taskId={taskId}
            content={content}
            outline={outline}
            generation={contentGeneration}
            onConfirm={handleContentConfirm}
            onBack={handleBackToOutline}
            onGenerationUpdate={setContentGeneration}
            buildFailed={buildFailed}
          />
        )}
        {current === 4 && taskId && (
          <Step4Download
            taskId={taskId}
            taskInfo={taskInfo}
            skippedPages={skippedPages}
            onNew={handleNew}
          />
        )}
      </div>
    </div>
  );
};

export default WizardPage;
