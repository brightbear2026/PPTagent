/* ============================================================
   Step2Outline — Card-based outline editor with drag reorder
   ============================================================ */

import React, { useState, useCallback } from 'react';
import {
  Card, Button, Tag, Input, message, Popconfirm,
  Typography, Badge,
} from 'antd';
import {
  CheckOutlined, DeleteOutlined, PlusOutlined, HolderOutlined,
  ArrowUpOutlined, ArrowDownOutlined, WarningOutlined, ArrowLeftOutlined,
} from '@ant-design/icons';
import {
  DndContext, closestCenter, PointerSensor, useSensor, useSensors,
} from '@dnd-kit/core';
import {
  SortableContext, verticalListSortingStrategy, useSortable,
  arrayMove,
} from '@dnd-kit/sortable';
import { CSS } from '@dnd-kit/utilities';
import { updateStage, supplementData } from '../../api/client';
import type { OutlineItem, OutlineResult } from '../../types';

const { TextArea } = Input;
const { Text } = Typography;

const SLIDE_TYPE_COLORS: Record<string, string> = {
  title:      '#C9A84C',
  agenda:     '#8B9DAF',
  content:    '#003D6E',
  data:       '#005B96',
  diagram:    '#48A9E6',
  comparison: '#FF6B35',
  summary:    '#2E7D32',
};

interface Step2Props {
  taskId: string;
  outline: OutlineResult;
  generation?: number;
  onConfirm: () => void;
  onBack?: () => void;
}

const Step2Outline: React.FC<Step2Props> = ({ taskId, outline, generation, onConfirm, onBack }) => {
  const [items, setItems] = useState<OutlineItem[]>(outline.items);
  const [gapSuggestions] = useState<string[]>(outline.data_gap_suggestions || []);
  const [supplementText, setSupplementText] = useState('');
  const [saving, setSaving] = useState(false);
  const [confirmed, setConfirmed] = useState(false);
  const [supplementing, setSupplementing] = useState(false);

  const sensors = useSensors(useSensor(PointerSensor, { activationConstraint: { distance: 5 } }));

  const handleDragEnd = useCallback((event: any) => {
    const { active, over } = event;
    if (active.id !== over?.id) {
      setItems((prev) => {
        const oldIdx = prev.findIndex((_, i) => `item-${i}` === active.id);
        const newIdx = prev.findIndex((_, i) => `item-${i}` === over.id);
        const moved = arrayMove(prev, oldIdx, newIdx);
        return moved.map((item, i) => ({ ...item, page_number: i + 1 }));
      });
    }
  }, []);

  const updateItem = (index: number, field: keyof OutlineItem, value: string) => {
    setItems((prev) => {
      const next = [...prev];
      next[index] = { ...next[index], [field]: value };
      return next;
    });
  };

  const removeItem = (index: number) => {
    setItems((prev) => {
      const next = prev.filter((_, i) => i !== index);
      return next.map((item, i) => ({ ...item, page_number: i + 1 }));
    });
  };

  const addItem = () => {
    setItems((prev) => [
      ...prev,
      {
        page_number: prev.length + 1,
        slide_type: 'content',
        takeaway_message: '',
        supporting_hint: '',
        data_source: '',
      },
    ]);
  };

  const moveItem = (index: number, direction: -1 | 1) => {
    const targetIdx = index + direction;
    if (targetIdx < 0 || targetIdx >= items.length) return;
    setItems((prev) => {
      const next = arrayMove(prev, index, targetIdx);
      return next.map((item, i) => ({ ...item, page_number: i + 1 }));
    });
  };

  const handleSave = async () => {
    if (confirmed || saving) return;
    setSaving(true);
    try {
      await updateStage(taskId, 'outline', {
        narrative_logic: outline.narrative_logic,
        items: items,
        data_gap_suggestions: gapSuggestions,
      }, generation);
      await onConfirm();
      setConfirmed(true);
      message.success('大纲已确认，正在生成内容...');
    } catch (err: any) {
      message.error(err.response?.data?.detail || '保存失败');
    } finally {
      setSaving(false);
    }
  };

  const handleSupplement = async () => {
    if (!supplementText.trim()) return;
    setSupplementing(true);
    try {
      await supplementData(taskId, {
        stage: 'outline',
        text_data: supplementText.trim(),
      });
      message.success('补充数据已保存');
      setSupplementText('');
    } catch (err: any) {
      message.error('补充数据保存失败');
    } finally {
      setSupplementing(false);
    }
  };

  return (
    <div>
      {/* Narrative logic */}
      <Card
        style={{ borderRadius: 2, marginBottom: 16 }}
        styles={{ body: { padding: '16px 20px' } }}
      >
        <div style={{ display: 'flex', alignItems: 'flex-start', gap: 12 }}>
          <Tag color="gold" style={{ marginTop: 2, flexShrink: 0 }}>叙事逻辑</Tag>
          <Text style={{ color: '#002B4E', fontSize: 14, lineHeight: 1.7 }}>
            {outline.narrative_logic}
          </Text>
        </div>
      </Card>

      {/* Outline cards */}
      <DndContext sensors={sensors} collisionDetection={closestCenter} onDragEnd={handleDragEnd}>
        <SortableContext items={items.map((_, i) => `item-${i}`)} strategy={verticalListSortingStrategy}>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 10, marginBottom: 16 }}>
            {items.map((item, index) => (
              <SortableCard
                key={`item-${index}`}
                id={`item-${index}`}
                item={item}
                index={index}
                onUpdate={updateItem}
                onRemove={removeItem}
                onMove={moveItem}
                total={items.length}
              />
            ))}
          </div>
        </SortableContext>
      </DndContext>

      {/* Add page */}
      <Button
        type="dashed"
        onClick={addItem}
        icon={<PlusOutlined />}
        block
        style={{
          borderColor: '#C9A84C',
          color: '#C9A84C',
          borderRadius: 2,
          height: 40,
          marginBottom: 20,
        }}
      >
        添加页面
      </Button>

      {/* Data gap suggestions + supplement */}
      {gapSuggestions.length > 0 && (
        <Card
          size="small"
          title={
            <span style={{ color: '#8B6D00' }}>
              <WarningOutlined style={{ marginRight: 6 }} />
              数据补充建议
            </span>
          }
          style={{ borderRadius: 2, marginBottom: 20 }}
          styles={{ body: { padding: '12px 16px' } }}
        >
          <ul style={{ margin: '0 0 12px', paddingLeft: 20 }}>
            {gapSuggestions.map((g, i) => (
              <li key={i} style={{ color: '#5C5C5C', fontSize: 13, marginBottom: 4 }}>{g}</li>
            ))}
          </ul>
          <div style={{ display: 'flex', gap: 8 }}>
            <TextArea
              value={supplementText}
              onChange={(e) => setSupplementText(e.target.value)}
              placeholder="粘贴补充数据或事实..."
              rows={2}
              style={{ borderRadius: 2, flex: 1 }}
            />
            <Button
              onClick={handleSupplement}
              loading={supplementing}
              style={{ alignSelf: 'flex-end', borderRadius: 2 }}
            >
              补充
            </Button>
          </div>
        </Card>
      )}

      {/* Action buttons */}
      <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12 }}>
        {onBack && (
          <Button
            icon={<ArrowLeftOutlined />}
            onClick={onBack}
            disabled={confirmed || saving}
            style={{ height: 44, borderRadius: 2 }}
          >
            返回上传
          </Button>
        )}
        <div style={{ flex: 1 }} />
        <Button
          type="primary"
          onClick={handleSave}
          loading={saving || confirmed}
          disabled={confirmed}
          icon={<CheckOutlined />}
          style={{
            background: '#C9A84C',
            borderColor: '#C9A84C',
            color: '#002B4E',
            fontWeight: 700,
            height: 44,
            paddingInline: 32,
            borderRadius: 2,
          }}
        >
          确认大纲，继续生成内容
        </Button>
      </div>
    </div>
  );
};

// ── Sortable Card ──

interface SortableCardProps {
  id: string;
  item: OutlineItem;
  index: number;
  total: number;
  onUpdate: (index: number, field: keyof OutlineItem, value: string) => void;
  onRemove: (index: number) => void;
  onMove: (index: number, direction: -1 | 1) => void;
}

const SortableCard: React.FC<SortableCardProps> = ({
  id, item, index, total, onUpdate, onRemove, onMove,
}) => {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } = useSortable({ id });
  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
    opacity: isDragging ? 0.5 : 1,
  };

  const typeColor = SLIDE_TYPE_COLORS[item.slide_type] || '#8B9DAF';

  return (
    <div ref={setNodeRef} style={style}>
      <Card
        size="small"
        style={{
          borderRadius: 2,
          borderLeft: `3px solid ${typeColor}`,
        }}
        styles={{ body: { padding: '12px 16px' } }}
      >
        <div style={{ display: 'flex', alignItems: 'flex-start', gap: 12 }}>
          {/* Drag handle + order */}
          <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 2, paddingTop: 4 }}>
            <span {...attributes} {...listeners} style={{ cursor: 'grab', color: '#C9A84C', fontSize: 16 }}>
              <HolderOutlined />
            </span>
            <span style={{ fontSize: 11, color: '#8B9DAF', fontWeight: 600 }}>P{item.page_number}</span>
          </div>

          {/* Content */}
          <div style={{ flex: 1 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
              <Badge color={typeColor} text={null} />
              <Tag style={{ background: typeColor, color: '#fff', border: 'none', margin: 0, borderRadius: 2 }}>
                {item.slide_type}
              </Tag>
            </div>

            <Input
              value={item.takeaway_message}
              onChange={(e) => onUpdate(index, 'takeaway_message', e.target.value)}
              placeholder="核心论点 (takeaway)"
              style={{ borderRadius: 2, marginBottom: 6, fontWeight: 500 }}
              variant="borderless"
            />

            {item.slide_type !== 'title' && (
              <Input
                value={item.supporting_hint}
                onChange={(e) => onUpdate(index, 'supporting_hint', e.target.value)}
                placeholder="支撑材料提示"
                style={{ borderRadius: 2, fontSize: 13, color: '#8B9DAF' }}
                variant="borderless"
              />
            )}

            {item.data_source && (
              <Text style={{ fontSize: 12, color: '#8B9DAF' }}>
                数据来源: {item.data_source}
              </Text>
            )}
          </div>

          {/* Actions */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: 4, flexShrink: 0 }}>
            <Button
              size="small" type="text" icon={<ArrowUpOutlined />}
              disabled={index === 0}
              onClick={() => onMove(index, -1)}
            />
            <Button
              size="small" type="text" icon={<ArrowDownOutlined />}
              disabled={index === total - 1}
              onClick={() => onMove(index, 1)}
            />
            {item.slide_type !== 'title' && (
              <Popconfirm title="确定删除此页？" onConfirm={() => onRemove(index)}>
                <Button size="small" type="text" danger icon={<DeleteOutlined />} />
              </Popconfirm>
            )}
          </div>
        </div>
      </Card>
    </div>
  );
};

export default Step2Outline;
