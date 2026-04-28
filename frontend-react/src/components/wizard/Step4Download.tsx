/* ============================================================
   Step4Download — Success + download + actions
   ============================================================ */

import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Button, Typography, Card, Space, Alert, Descriptions, Statistic } from 'antd';
import {
  CheckCircleOutlined, DownloadOutlined, PlusOutlined, HistoryOutlined,
  FilePptOutlined, DollarOutlined,
} from '@ant-design/icons';
import { getDownloadUrl, getTaskCost, type TaskCost } from '../../api/client';
import type { TaskInfo, SkippedPage } from '../../types';

const { Paragraph } = Typography;

interface Step4Props {
  taskId: string;
  taskInfo: TaskInfo | null;
  skippedPages?: SkippedPage[];
  onNew: () => void;
}

const Step4Download: React.FC<Step4Props> = ({ taskId, taskInfo, skippedPages = [], onNew }) => {
  const navigate = useNavigate();
  const downloadUrl = getDownloadUrl(taskId);
  const [cost, setCost] = useState<TaskCost | null>(null);

  useEffect(() => {
    getTaskCost(taskId).then(setCost).catch(() => {});
  }, [taskId]);

  return (
    <div style={{ display: 'flex', justifyContent: 'center', paddingTop: 40 }}>
      <Card
        style={{ width: 560, borderRadius: 2, textAlign: 'center' }}
        styles={{ body: { padding: '48px 40px' } }}
      >
        <CheckCircleOutlined
          style={{ fontSize: 64, color: '#2E7D32', marginBottom: 16 }}
        />

        <h2 style={{ color: '#002B4E', fontSize: 24, fontWeight: 700, marginBottom: 8 }}>
          PPT 生成完成
        </h2>

        <Paragraph style={{ color: '#8B9DAF', fontSize: 14, marginBottom: 24 }}>
          您的专业PPT已生成完毕，点击下方按钮下载。
        </Paragraph>

        {/* Stats */}
        {taskInfo?.narrative && (
          <div style={{
            background: '#F7F8FA',
            borderRadius: 2,
            padding: '12px 20px',
            marginBottom: 24,
            display: 'flex',
            justifyContent: 'center',
            gap: 32,
          }}>
            <div>
              <div style={{ fontSize: 20, fontWeight: 700, color: '#003D6E' }}>
                {taskInfo.narrative.page_count}
              </div>
              <div style={{ fontSize: 12, color: '#8B9DAF' }}>页</div>
            </div>
            <div>
              <div style={{ fontSize: 20, fontWeight: 700, color: '#C9A84C' }}>
                <FilePptOutlined />
              </div>
              <div style={{ fontSize: 12, color: '#8B9DAF' }}>PPTX格式</div>
            </div>
          </div>
        )}

        {/* Skipped pages warning */}
        {skippedPages.length > 0 && (
          <Alert
            type="warning"
            showIcon
            style={{ marginBottom: 20, textAlign: 'left' }}
            message={`${skippedPages.length} 页内容生成失败，已跳过`}
            description={
              <span>
                跳过页码：{skippedPages.map(p => p.page_number).join('、')}。
                可在历史记录中重新生成这些页面。
              </span>
            }
          />
        )}

        {/* Token cost summary */}
        {cost && cost.total_tokens > 0 && (
          <div style={{
            background: '#F7F8FA',
            borderRadius: 2,
            padding: '16px 20px',
            marginBottom: 24,
            textAlign: 'left',
          }}>
            <div style={{ fontSize: 12, color: '#8B9DAF', marginBottom: 8, fontWeight: 500 }}>
              AI 资源消耗
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-around' }}>
              <Statistic
                title="总 Token"
                value={cost.total_tokens}
                formatter={(v) => `${((v as number) / 1000).toFixed(1)}K`}
                valueStyle={{ fontSize: 16, color: '#003D6E' }}
              />
              <Statistic
                title="预估成本"
                value={cost.estimated_cost_usd}
                  prefix={<DollarOutlined />}
                precision={4}
                valueStyle={{ fontSize: 16, color: '#C9A84C' }}
              />
            </div>
            {Object.keys(cost.by_stage).length > 0 && (
              <Descriptions
                size="small"
                column={2}
                style={{ marginTop: 12 }}
                contentStyle={{ fontSize: 12, color: '#595959' }}
                labelStyle={{ fontSize: 12, color: '#8B9DAF' }}
              >
                {Object.entries(cost.by_stage).map(([stage, s]) => (
                  <Descriptions.Item key={stage} label={stage}>
                    {(s.tokens_total / 1000).toFixed(1)}K tokens / ${s.cost_usd.toFixed(4)}
                  </Descriptions.Item>
                ))}
              </Descriptions>
            )}
          </div>
        )}

        {/* Download button */}
        <Button
          type="primary"
          size="large"
          icon={<DownloadOutlined />}
          href={downloadUrl}
          target="_blank"
          style={{
            background: '#C9A84C',
            borderColor: '#C9A84C',
            color: '#002B4E',
            fontWeight: 700,
            height: 48,
            paddingInline: 40,
            fontSize: 16,
            borderRadius: 2,
            marginBottom: 16,
          }}
          block
        >
          下载 PPT 文件
        </Button>

        {/* Actions */}
        <Space style={{ marginTop: 8 }}>
          <Button icon={<PlusOutlined />} onClick={onNew}>
            创建新PPT
          </Button>
          <Button icon={<HistoryOutlined />} onClick={() => navigate('/history')}>
            查看历史
          </Button>
        </Space>
      </Card>
    </div>
  );
};

export default Step4Download;
