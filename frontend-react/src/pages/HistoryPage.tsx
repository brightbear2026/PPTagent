/* ============================================================
   HistoryPage — Task history with status badges
   ============================================================ */

import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Table, Tag, Button, Empty, message, Popconfirm, Space } from 'antd';
import { DownloadOutlined, DeleteOutlined, RedoOutlined } from '@ant-design/icons';
import type { ColumnsType } from 'antd/es/table';
import { getHistory, deleteTask, getDownloadUrl } from '../api/client';
import type { HistoryItem, TaskStatusEnum } from '../types';

const STATUS_MAP: Record<TaskStatusEnum, { color: string; label: string }> = {
  pending:     { color: 'default',    label: '等待中' },
  processing:  { color: 'processing', label: '生成中' },
  checkpoint:  { color: 'warning',    label: '待确认' },
  completed:   { color: 'success',    label: '已完成' },
  failed:      { color: 'error',      label: '失败' },
  cancelled:   { color: 'default',    label: '已取消' },
};

const HistoryPage: React.FC = () => {
  const navigate = useNavigate();
  const [data, setData] = useState<HistoryItem[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);

  const fetchHistory = async () => {
    setLoading(true);
    try {
      const res = await getHistory(50);
      setData(res.items);
      setTotal(res.total);
    } catch {
      message.error('获取历史记录失败');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { fetchHistory(); }, []);

  const handleDelete = async (taskId: string) => {
    try {
      await deleteTask(taskId);
      message.success('已删除');
      fetchHistory();
    } catch {
      message.error('删除失败');
    }
  };

  const columns: ColumnsType<HistoryItem> = [
    {
      title: '标题',
      dataIndex: 'title',
      key: 'title',
      ellipsis: true,
      render: (text: string, record: HistoryItem) => {
        const clickable = ['checkpoint', 'completed', 'failed', 'processing'].includes(record.status);
        const handleClick = () => {
          if (record.status === 'completed') {
            navigate(`/?task=${record.task_id}&step=4`);
          } else if (record.status === 'checkpoint') {
            navigate(`/?task=${record.task_id}&step=2`);
          } else {
            navigate(`/?task=${record.task_id}`);
          }
        };
        return clickable ? (
          <a onClick={handleClick}>{text || '未命名'}</a>
        ) : (
          <span>{text || '未命名'}</span>
        );
      },
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      width: 100,
      render: (status: TaskStatusEnum) => {
        const info = STATUS_MAP[status] || { color: 'default', label: status };
        return <Tag color={info.color}>{info.label}</Tag>;
      },
    },
    {
      title: '创建时间',
      dataIndex: 'created_at',
      key: 'created_at',
      width: 180,
      render: (text: string) => {
        try {
          return new Date(text).toLocaleString('zh-CN');
        } catch {
          return text;
        }
      },
    },
    {
      title: '操作',
      key: 'actions',
      width: 160,
      render: (_: any, record: HistoryItem) => (
        <Space size={4}>
          {record.status === 'completed' && record.output_file && (
            <Button
              type="link"
              size="small"
              icon={<DownloadOutlined />}
              href={getDownloadUrl(record.task_id)}
              target="_blank"
            >
              下载
            </Button>
          )}
          {record.status === 'failed' && (
            <Button
              type="link"
              size="small"
              icon={<RedoOutlined />}
              onClick={() => navigate(`/?task=${record.task_id}`)}
            >
              重试
            </Button>
          )}
          <Popconfirm title="确定删除此任务？" onConfirm={() => handleDelete(record.task_id)}>
            <Button type="link" size="small" danger icon={<DeleteOutlined />}>
              删除
            </Button>
          </Popconfirm>
        </Space>
      ),
    },
  ];

  return (
    <div style={{ padding: 32, maxWidth: 1200, margin: '0 auto' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 24 }}>
        <h2 style={{ margin: 0, color: '#002B4E', fontSize: 22, fontWeight: 600 }}>
          历史记录
        </h2>
        <span style={{ color: '#8B9DAF', fontSize: 13 }}>共 {total} 条</span>
      </div>

      {data.length === 0 && !loading ? (
        <Empty
          description="暂无生成记录"
          style={{ marginTop: 80 }}
        >
          <Button type="primary" onClick={() => navigate('/')}>
            创建第一份PPT
          </Button>
        </Empty>
      ) : (
        <Table<HistoryItem>
          columns={columns}
          dataSource={data}
          rowKey="task_id"
          loading={loading}
          pagination={false}
          style={{ background: '#fff', borderRadius: 2 }}
        />
      )}
    </div>
  );
};

export default HistoryPage;
