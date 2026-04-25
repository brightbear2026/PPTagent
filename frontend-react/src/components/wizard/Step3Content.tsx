/* ============================================================
   Step3Content — Three-column content editor
   Left: page nav | Middle: editing | Right: live preview
   ============================================================ */

import React, { useState, Component } from 'react';
import {
  Card, Button, Input, Select, Tag, List, message, Space,
  Empty, Typography, Popconfirm,
} from 'antd';
import {
  DeleteOutlined, PlusOutlined, RedoOutlined,
  BarChartOutlined, ApartmentOutlined, ArrowLeftOutlined,
} from '@ant-design/icons';
import { updateStage, rerunPage, getStageResult } from '../../api/client';
import type { OutlineResult, ContentResult, SlideContent, TextBlock } from '../../types';
import ChartPreview from '../preview/ChartPreview';
import DiagramPreview from '../preview/DiagramPreview';

const { TextArea } = Input;
const { Text } = Typography;

interface Step3Props {
  taskId: string;
  content: ContentResult;
  outline: OutlineResult | null;
  generation?: number;
  onConfirm: () => void;
  onBack?: () => void;
  onGenerationUpdate?: (gen: number) => void;
  buildFailed?: boolean;
}

const STRUCTURAL_SLIDE_TYPES = new Set(['title', 'agenda', 'section_divider']);

const Step3Content: React.FC<Step3Props> = ({ taskId, content, outline, generation, onConfirm, onBack, onGenerationUpdate, buildFailed }) => {
  const [slides, setSlides] = useState<SlideContent[]>(
    content.slides.filter(s => !STRUCTURAL_SLIDE_TYPES.has(s.slide_type))
  );
  const [selectedPage, setSelectedPage] = useState(0);
  const [saving, setSaving] = useState(false);
  const [confirmed, setConfirmed] = useState(false);
  const [rerunFeedback, setRerunFeedback] = useState('');
  const [lastRevisionNotes, setLastRevisionNotes] = useState<string | null>(null);

  React.useEffect(() => {
    if (buildFailed && confirmed) {
      setConfirmed(false);
    }
  }, [buildFailed]);

  const currentSlide = slides[selectedPage] || null;

  // Suppress unused outline warning — used for page context in future
  void outline;

  // ── Mutations ──

  const updateSlide = (index: number, updater: (s: SlideContent) => SlideContent) => {
    setSlides((prev) => prev.map((s, i) => (i === index ? updater(s) : s)));
  };

  const updateTextBlock = (slideIdx: number, blockIdx: number, field: keyof TextBlock, value: any) => {
    updateSlide(slideIdx, (s) => ({
      ...s,
      text_blocks: (s.text_blocks ?? []).map((b, i) => (i === blockIdx ? { ...b, [field]: value } : b)),
    }));
  };

  const addTextBlock = (slideIdx: number) => {
    updateSlide(slideIdx, (s) => ({
      ...s,
      text_blocks: [...(s.text_blocks ?? []), { content: '', level: 1, is_bold: false }],
    }));
  };

  const removeTextBlock = (slideIdx: number, blockIdx: number) => {
    updateSlide(slideIdx, (s) => ({
      ...s,
      text_blocks: (s.text_blocks ?? []).filter((_, i) => i !== blockIdx),
    }));
  };

  const updateTakeaway = (slideIdx: number, value: string) => {
    updateSlide(slideIdx, (s) => ({ ...s, takeaway_message: value }));
  };

  const handleRerunPage = async (slideIdx: number, feedback: string) => {
    const pageNum = slides[slideIdx].page_number;
    setLastRevisionNotes(null);
    try {
      const result = await rerunPage(taskId, pageNum, feedback);
      // Refresh slides from server so updated content and new generation are applied
      const stageData = await getStageResult(taskId, 'content');
      if (stageData?.result?.slides) {
        setSlides(stageData.result.slides.filter((s: SlideContent) => !STRUCTURAL_SLIDE_TYPES.has(s.slide_type)));
        if (onGenerationUpdate && stageData.generation != null) {
          onGenerationUpdate(stageData.generation);
        }
      }
      if (result?.slide?.revision_notes) {
        setLastRevisionNotes(result.slide.revision_notes);
      }
      setRerunFeedback('');
      message.success(`第${pageNum}页已重新生成`);
    } catch (err: any) {
      message.error(err.response?.data?.detail || '重跑失败');
    }
  };

  const handleSave = async () => {
    if (confirmed || saving) return;
    setSaving(true);
    try {
      await updateStage(taskId, 'content', {
        total_pages: slides.length,
        failed_pages: slides.filter((s) => s.is_failed).map((s) => s.page_number),
        slides: slides,
      }, generation);
      await onConfirm();
      setConfirmed(true);
      message.success('内容已确认，正在构建PPT...');
    } catch (err: any) {
      message.error(err.response?.data?.detail || '保存失败');
    } finally {
      setSaving(false);
    }
  };

  // ── Render ──

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: 'calc(100vh - 220px)' }}>
    <div style={{ display: 'flex', gap: 16, flex: 1, minHeight: 0 }}>
      {/* Left: page navigation */}
      <Card
        style={{ width: 200, flexShrink: 0, borderRadius: 2, overflow: 'auto' }}
        styles={{ body: { padding: 8 } }}
        title={<span style={{ fontSize: 14, color: '#002B4E' }}>页面导航</span>}
      >
        <List
          size="small"
          dataSource={slides}
          renderItem={(slide, idx) => (
            <List.Item
              onClick={() => setSelectedPage(idx)}
              style={{
                cursor: 'pointer',
                background: idx === selectedPage ? '#F0EBE0' : 'transparent',
                borderRadius: 2,
                padding: '6px 8px',
                marginBottom: 2,
                borderLeft: slide.is_failed ? '3px solid #ff4d4f' : '3px solid transparent',
              }}
            >
              <div style={{ width: '100%' }}>
                <div style={{ fontSize: 12, color: '#8B9DAF', marginBottom: 2 }}>
                  P{slide.page_number}
                  <Tag
                    style={{ marginLeft: 4, fontSize: 10, lineHeight: '16px', padding: '0 4px', borderRadius: 2 }}
                    color={slide.slide_type === 'data' ? 'blue' : slide.slide_type === 'diagram' ? 'cyan' : 'default'}
                  >
                    {slide.slide_type}
                  </Tag>
                </div>
                <div
                  style={{ fontSize: 12, color: '#002B4E', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}
                >
                  {slide.takeaway_message || '(空)'}
                </div>
              </div>
            </List.Item>
          )}
        />
      </Card>

      {/* Middle: editor */}
      <Card
        style={{ flex: 1, borderRadius: 2, overflow: 'auto' }}
        styles={{ body: { padding: 20 } }}
      >
        {currentSlide ? (
          <>
            {/* Takeaway */}
            <div style={{ marginBottom: 16 }}>
              <label style={{ fontSize: 13, fontWeight: 600, color: '#002B4E', display: 'block', marginBottom: 6 }}>
                核心论点 (Takeaway)
              </label>
              <Input
                value={currentSlide.takeaway_message}
                onChange={(e) => updateTakeaway(selectedPage, e.target.value)}
                style={{ borderRadius: 2, fontWeight: 500 }}
              />
            </div>

            {/* Text blocks */}
            <div style={{ marginBottom: 16 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
                <label style={{ fontSize: 13, fontWeight: 600, color: '#002B4E' }}>
                  文字内容
                </label>
                <Button size="small" type="dashed" icon={<PlusOutlined />} onClick={() => addTextBlock(selectedPage)}>
                  添加
                </Button>
              </div>

              {(currentSlide.text_blocks ?? []).map((block, bIdx) => (
                <div
                  key={bIdx}
                  style={{
                    display: 'flex',
                    gap: 8,
                    marginBottom: 8,
                    alignItems: 'flex-start',
                    paddingLeft: block.level * 20,
                  }}
                >
                  <Select
                    value={block.level}
                    onChange={(v) => updateTextBlock(selectedPage, bIdx, 'level', v)}
                    style={{ width: 80, flexShrink: 0 }}
                    size="small"
                    options={[
                      { label: '正文', value: 0 },
                      { label: '要点', value: 1 },
                      { label: '细节', value: 2 },
                    ]}
                  />
                  <TextArea
                    value={block.content}
                    onChange={(e) => updateTextBlock(selectedPage, bIdx, 'content', e.target.value)}
                    autoSize={{ minRows: 1, maxRows: 4 }}
                    style={{ flex: 1, borderRadius: 2, fontSize: 13 }}
                    placeholder="输入内容..."
                  />
                  <Popconfirm title="删除此条？" onConfirm={() => removeTextBlock(selectedPage, bIdx)}>
                    <Button size="small" type="text" danger icon={<DeleteOutlined />} style={{ flexShrink: 0, marginTop: 4 }} />
                  </Popconfirm>
                </div>
              ))}

              {(currentSlide.text_blocks ?? []).length === 0 && (
                <Empty description="暂无文字内容" image={Empty.PRESENTED_IMAGE_SIMPLE} />
              )}
            </div>

            {/* Chart suggestion */}
            {currentSlide.chart_suggestion && (
              <Card
                size="small"
                title={
                  <span style={{ fontSize: 13, fontWeight: 600 }}>
                    <BarChartOutlined style={{ marginRight: 6, color: '#005B96' }} />
                    图表: {currentSlide.chart_suggestion.title}
                  </span>
                }
                style={{ marginBottom: 12, borderRadius: 2 }}
              >
                <Space size={16} wrap>
                  <Tag color="blue">{currentSlide.chart_suggestion.chart_type}</Tag>
                  <Text style={{ fontSize: 13, color: '#5C5C5C' }}>
                    {currentSlide.chart_suggestion.so_what}
                  </Text>
                </Space>
              </Card>
            )}

            {/* Diagram spec */}
            {currentSlide.diagram_spec && (
              <Card
                size="small"
                title={
                  <span style={{ fontSize: 13, fontWeight: 600 }}>
                    <ApartmentOutlined style={{ marginRight: 6, color: '#48A9E6' }} />
                    概念图: {currentSlide.diagram_spec.title}
                  </span>
                }
                style={{ marginBottom: 12, borderRadius: 2 }}
              >
                <Tag color="cyan">{currentSlide.diagram_spec.diagram_type}</Tag>
              </Card>
            )}

            {/* Warnings / Failed */}
            {currentSlide.is_failed && (
              <div style={{ color: '#ff4d4f', marginTop: 8, fontSize: 13 }}>
                生成失败: {currentSlide.error_message}
              </div>
            )}

            {/* Rerun with feedback */}
            <div style={{ marginTop: 16, marginBottom: 8, paddingTop: 12, borderTop: '1px solid #f0f0f0' }}>
              <TextArea
                value={rerunFeedback}
                onChange={(e) => setRerunFeedback(e.target.value)}
                placeholder="告诉 AI 需要改进的方向（可选，直接点重跑也可以）"
                rows={2}
                style={{ borderRadius: 2, fontSize: 13, marginBottom: 6 }}
              />
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <Button
                  type="link"
                  size="small"
                  icon={<RedoOutlined />}
                  onClick={() => handleRerunPage(selectedPage, rerunFeedback)}
                  style={{ padding: 0, color: '#8B9DAF', fontSize: 12 }}
                >
                  重新生成本页
                </Button>
                {lastRevisionNotes && (
                  <span style={{ fontSize: 12, color: '#888' }}>
                    AI 说：{lastRevisionNotes}
                  </span>
                )}
              </div>
            </div>
          </>
        ) : (
          <Empty description="选择左侧页面进行编辑" style={{ marginTop: 80 }} />
        )}
      </Card>

      {/* Right: live preview */}
      <Card
        style={{ width: 380, flexShrink: 0, borderRadius: 2, overflow: 'auto' }}
        styles={{ body: { padding: 16 } }}
        title={
          <span style={{ fontSize: 14, color: '#002B4E' }}>
            内容预览
            <span style={{ fontSize: 11, color: '#8B9DAF', fontWeight: 400, marginLeft: 6 }}>
              （示意图，配色/排版以导出PPT为准）
            </span>
          </span>
        }
      >
        {currentSlide ? (
          <PreviewErrorBoundary key={currentSlide.page_number}>
            <SlidePreview slide={currentSlide} />
          </PreviewErrorBoundary>
        ) : (
          <Empty description="选择页面查看预览" style={{ marginTop: 80 }} />
        )}
      </Card>
    </div>

    {/* Global action bar — sticky at bottom */}
    <div style={{
      display: 'flex',
      alignItems: 'center',
      gap: 12,
      padding: '12px 0',
      borderTop: '1px solid #E8E4D9',
      marginTop: 8,
      flexShrink: 0,
    }}>
      {onBack && (
        <Button
          icon={<ArrowLeftOutlined />}
          onClick={onBack}
          disabled={confirmed || saving}
          style={{ borderRadius: 2 }}
        >
          返回大纲
        </Button>
      )}
      <div style={{ flex: 1 }} />
      <Button
        type="primary"
        onClick={handleSave}
        loading={saving || confirmed}
        disabled={confirmed}
        size="large"
        style={{
          background: '#C9A84C',
          borderColor: '#C9A84C',
          color: '#002B4E',
          fontWeight: 700,
          borderRadius: 2,
          height: 44,
          paddingInline: 32,
          fontSize: 15,
        }}
      >
        确认并生成 PPT
      </Button>
    </div>
    </div>
  );
};

// ── Error Boundary — prevents preview crash from blanking the page ──

class PreviewErrorBoundary extends Component<
  { children: React.ReactNode },
  { hasError: boolean }
> {
  state = { hasError: false };
  static getDerivedStateFromError() { return { hasError: true }; }
  componentDidCatch(error: Error, info: React.ErrorInfo) {
    console.error('[PreviewErrorBoundary]', error, info);
  }
  render() {
    if (this.state.hasError) {
      return (
        <div style={{ padding: 16, color: '#8B9DAF', fontSize: 12 }}>
          预览渲染失败（数据异常），请在左侧编辑区核对内容
        </div>
      );
    }
    return this.props.children;
  }
}

// ── Slide Preview Component ──

const SlidePreview: React.FC<{ slide: SlideContent }> = ({ slide }) => {
  const aspectRatio = 16 / 9;
  const width = 348;
  const height = width / aspectRatio; // ≈196

  const hasChart   = !!slide.chart_suggestion;
  const hasDiagram = !!slide.diagram_spec;
  const hasVisual  = hasChart || hasDiagram;

  // When there's a visual, allocate ~100px for it; text area shrinks accordingly
  const VISUAL_H = 100;
  const HEADER_H = 44; // takeaway + divider
  const textMaxH  = hasVisual ? height - HEADER_H - VISUAL_H - 16 : height - HEADER_H - 8;

  return (
    <div
      style={{
        width,
        height,
        background: '#fff',
        borderRadius: 2,
        boxShadow: '0 2px 12px rgba(0,0,0,0.1)',
        padding: 12,
        paddingTop: 15,
        overflow: 'hidden',
        display: 'flex',
        flexDirection: 'column',
        position: 'relative',
        border: '1px solid #e8e4d9',
      }}
    >
      {/* Top accent bar */}
      <div style={{
        position: 'absolute', top: 0, left: 0, right: 0,
        height: 3, background: '#003D6E',
      }} />

      {/* Takeaway */}
      <div style={{
        fontSize: 10,
        fontWeight: 700,
        color: '#003D6E',
        marginBottom: 5,
        lineHeight: 1.4,
        overflow: 'hidden',
        textOverflow: 'ellipsis',
        display: '-webkit-box',
        WebkitLineClamp: 2,
        WebkitBoxOrient: 'vertical',
        flexShrink: 0,
      }}>
        {slide.takeaway_message || '（无标题）'}
      </div>

      {/* Divider */}
      <div style={{ height: 1, background: '#C9A84C', marginBottom: 5, opacity: 0.5, flexShrink: 0 }} />

      {/* Text blocks */}
      <div style={{ overflow: 'hidden', maxHeight: textMaxH, flexShrink: 0 }}>
        {(slide.text_blocks ?? []).slice(0, 6).map((block, i) => (
          <div
            key={i}
            style={{
              fontSize: block.level === 0 ? 9 : 8.5,
              color: block.level === 0 ? '#2D3436' : '#5C5C5C',
              paddingLeft: block.level * 10,
              marginBottom: 2,
              lineHeight: 1.35,
              fontWeight: block.is_bold ? 600 : 400,
              overflow: 'hidden',
              textOverflow: 'ellipsis',
              whiteSpace: 'nowrap',
            }}
          >
            {block.level > 0 && <span style={{ color: '#C9A84C', marginRight: 3 }}>›</span>}
            {block.content}
          </div>
        ))}
      </div>

      {/* Spacer */}
      <div style={{ flex: 1 }} />

      {/* ── Chart Preview ── */}
      {hasChart && slide.chart_suggestion &&
        Array.isArray(slide.chart_suggestion.series) &&
        slide.chart_suggestion.series.length > 0 &&
        slide.chart_suggestion.series.some((s: any) =>
          Array.isArray(s.values ?? s.data) && (s.values ?? s.data).length > 0
        ) && (
        <div style={{ flexShrink: 0, overflow: 'hidden' }}>
          <div style={{ fontSize: 7.5, color: '#8B9DAF', marginBottom: 2, display: 'flex', alignItems: 'center', gap: 4 }}>
            <BarChartOutlined style={{ fontSize: 9 }} />
            <span>{slide.chart_suggestion.title}</span>
            <Tag color="blue" style={{ fontSize: 7, lineHeight: '14px', padding: '0 3px', margin: 0, marginLeft: 'auto' }}>
              {slide.chart_suggestion.chart_type}
            </Tag>
          </div>
          <ChartPreview chart={slide.chart_suggestion} width={width - 24} height={VISUAL_H - 14} />
        </div>
      )}

      {/* ── Diagram Preview ── */}
      {hasDiagram && slide.diagram_spec && slide.diagram_spec.diagram_type &&
        Array.isArray(slide.diagram_spec.nodes) && slide.diagram_spec.nodes.length > 0 && (
        <div style={{ flexShrink: 0, overflow: 'hidden' }}>
          <div style={{ fontSize: 7.5, color: '#8B9DAF', marginBottom: 2, display: 'flex', alignItems: 'center', gap: 4 }}>
            <ApartmentOutlined style={{ fontSize: 9 }} />
            <span>{slide.diagram_spec.title || '概念图'}</span>
            <Tag color="cyan" style={{ fontSize: 7, lineHeight: '14px', padding: '0 3px', margin: 0, marginLeft: 'auto' }}>
              {slide.diagram_spec.diagram_type}
            </Tag>
          </div>
          <DiagramPreview diagram={slide.diagram_spec} width={width - 24} height={VISUAL_H - 14} />
        </div>
      )}
    </div>
  );
};

export default Step3Content;
