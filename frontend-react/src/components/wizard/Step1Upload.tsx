/* ============================================================
   Step1Upload — Input params + file/text upload
   ============================================================ */

import React, { useState } from 'react';
import {
  Card, Form, Input, Select, Button, Upload, Radio, Divider, message,
} from 'antd';
import {
  UploadOutlined, FileTextOutlined, InboxOutlined, RocketOutlined,
} from '@ant-design/icons';
import { generateFromText, generateFromFile } from '../../api/client';
import type { GenerateParams } from '../../types';

const SCENARIO_OPTIONS = [
  { value: '', label: '自动选择（根据材料判断）' },
  { value: '季度汇报', label: '季度汇报 — SCR框架' },
  { value: '战略提案', label: '战略提案 — SCQA框架' },
  { value: '竞标pitch', label: '竞标/销售 — AIDA框架' },
  { value: '内部分析', label: '内部分析 — Issue Tree' },
  { value: '培训材料', label: '培训材料 — ADDIE框架' },
  { value: '项目汇报', label: '项目汇报 — STAR框架' },
  { value: '产品发布', label: '产品发布 — Problem-Solution' },
];

interface Step1Props {
  onStart: (taskId: string) => void;
  loading: boolean;
  progress: number;
  stepMessage?: string;
}

const Step1Upload: React.FC<Step1Props> = ({ onStart, loading, progress, stepMessage }) => {
  const [form] = Form.useForm();
  const [inputMode, setInputMode] = useState<'text' | 'file'>('text');
  const [fileList, setFileList] = useState<any[]>([]);
  const [submitting, setSubmitting] = useState(false);

  const handleFinish = async (values: GenerateParams & { content?: string }) => {
    if (submitting) return;
    setSubmitting(true);
    try {
      let result;
      if (inputMode === 'file' && fileList.length > 0) {
        result = await generateFromFile(fileList[0].originFileObj, {
          title: values.title,
          target_audience: values.target_audience,
          scenario: values.scenario || '',
          language: values.language,
        });
      } else {
        if (!values.content?.trim()) {
          message.warning('请输入内容或上传文件');
          setSubmitting(false);
          return;
        }
        result = await generateFromText({
          title: values.title,
          content: values.content,
          target_audience: values.target_audience,
          scenario: values.scenario || '',
          language: values.language,
        });
      }
      onStart(result.task_id);
    } catch (err: any) {
      message.error(err.response?.data?.detail || '创建任务失败');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Form
      form={form}
      layout="vertical"
      initialValues={{
        title: '',
        content: '',
        target_audience: '管理层',
        scenario: '',
        language: 'zh',
      }}
      onFinish={handleFinish}
    >
      <div style={{ display: 'flex', gap: 24 }}>
        {/* Left: parameters */}
        <Card
          style={{ flex: '0 0 360px', borderRadius: 2 }}
          styles={{ body: { padding: 24 } }}
        >
          <h3 style={{ color: '#002B4E', fontWeight: 600, marginBottom: 20 }}>
            生成参数
          </h3>

          <Form.Item label="演示标题" name="title" rules={[{ required: true, message: '请输入PPT标题' }]}>
            <Input placeholder="输入PPT标题" style={{ borderRadius: 2 }} />
          </Form.Item>

          <Form.Item label="目标受众" name="target_audience">
            <Select style={{ borderRadius: 2 }}>
              <Select.Option value="管理层">管理层 (CEO/VP)</Select.Option>
              <Select.Option value="执行团队">执行团队</Select.Option>
              <Select.Option value="客户">客户</Select.Option>
              <Select.Option value="投资者">投资者</Select.Option>
              <Select.Option value="技术人员">技术人员</Select.Option>
            </Select>
          </Form.Item>

          <Form.Item label="汇报场景" name="scenario">
            <Select style={{ borderRadius: 2 }} options={SCENARIO_OPTIONS} />
          </Form.Item>

          <Form.Item label="语言" name="language">
            <Radio.Group>
              <Radio value="zh">中文</Radio>
              <Radio value="en">English</Radio>
            </Radio.Group>
          </Form.Item>

          <Divider style={{ margin: '16px 0' }} />

          <Form.Item>
            <Button
              type="primary"
              htmlType="submit"
              loading={loading || submitting}
              icon={<RocketOutlined />}
              block
              style={{
                height: 44,
                background: '#C9A84C',
                borderColor: '#C9A84C',
                color: '#002B4E',
                fontWeight: 700,
                borderRadius: 2,
              }}
            >
              {loading ? `${stepMessage || '处理中'} (${progress}%)` : '开始生成'}
            </Button>
          </Form.Item>
        </Card>

        {/* Right: input area */}
        <Card
          style={{ flex: 1, borderRadius: 2 }}
          styles={{ body: { padding: 24 } }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 20 }}>
            <h3 style={{ color: '#002B4E', fontWeight: 600, margin: 0 }}>
              输入内容
            </h3>
            <Radio.Group
              value={inputMode}
              onChange={(e) => setInputMode(e.target.value)}
              size="small"
            >
              <Radio.Button value="text">
                <FileTextOutlined /> 文本输入
              </Radio.Button>
              <Radio.Button value="file">
                <UploadOutlined /> 文件上传
              </Radio.Button>
            </Radio.Group>
          </div>

          {inputMode === 'text' ? (
            <Form.Item name="content" style={{ marginBottom: 0 }}>
              <Input.TextArea
                placeholder="在此粘贴材料内容：业务报告、数据分析、会议纪要等...&#10;&#10;支持 Markdown 格式"
                style={{
                  minHeight: 360,
                  borderRadius: 2,
                  fontFamily: 'inherit',
                  fontSize: 14,
                  lineHeight: 1.8,
                }}
              />
            </Form.Item>
          ) : (
            <Upload.Dragger
              fileList={fileList}
              onChange={({ fileList: fl }) => setFileList(fl.slice(-1))}
              beforeUpload={() => false}
              maxCount={1}
              accept=".docx,.xlsx,.csv,.pptx,.txt,.md"
              style={{ padding: '60px 20px', borderRadius: 2 }}
            >
              <p style={{ fontSize: 36, color: '#C9A84C', marginBottom: 12 }}>
                <InboxOutlined />
              </p>
              <p style={{ color: '#002B4E', fontWeight: 500, fontSize: 16 }}>
                点击或拖拽文件到此处
              </p>
              <p style={{ color: '#8B9DAF', fontSize: 13 }}>
                支持 .docx .xlsx .csv .pptx .txt .md
              </p>
            </Upload.Dragger>
          )}
        </Card>
      </div>
    </Form>
  );
};

export default Step1Upload;
