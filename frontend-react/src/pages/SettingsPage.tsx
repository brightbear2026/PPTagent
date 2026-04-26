/* ============================================================
   SettingsPage — LLM model configuration
   Two modes: Universal (1 key for all) / Advanced (per-stage)
   ============================================================ */

import React, { useEffect, useState } from 'react';
import { Form, Select, Input, Button, message, Card, Space, Typography, Switch, Radio, Alert, AutoComplete } from 'antd';
import { KeyOutlined, SaveOutlined, ApiOutlined, ThunderboltOutlined, ExperimentOutlined, CheckCircleFilled, WarningFilled } from '@ant-design/icons';
import { getModelConfig, updateModelConfig } from '../api/client';
import type { PipelineModelConfig, StageModelConfig } from '../types';

const { Text } = Typography;

interface ProviderPreset {
  label: string;
  base_url: string;
  models: string[];
}

const PROVIDER_PRESETS: Record<string, ProviderPreset> = {
  zhipu: {
    label: '智谱GLM',
    base_url: '',
    models: ['glm-4-plus', 'glm-4-flash', 'glm-4-long', 'glm-4'],
  },
  deepseek: {
    label: 'DeepSeek',
    base_url: 'https://api.deepseek.com/v1',
    models: ['deepseek-reasoner', 'deepseek-chat'],
  },
  tongyi: {
    label: '通义千问',
    base_url: 'https://dashscope.aliyuncs.com/compatible-mode/v1',
    models: ['qwen-max', 'qwen-plus', 'qwen-turbo', 'qwen-long'],
  },
  moonshot: {
    label: 'Moonshot',
    base_url: 'https://api.moonshot.cn/v1',
    models: ['moonshot-v1-8k', 'moonshot-v1-32k', 'moonshot-v1-128k'],
  },
  openai: {
    label: 'OpenAI',
    base_url: 'https://api.openai.com/v1',
    models: ['gpt-4o', 'gpt-4o-mini', 'gpt-4-turbo', 'o1', 'o3-mini'],
  },
  custom: {
    label: '自定义 (OpenAI兼容)',
    base_url: '',
    models: [],
  },
};

const STAGE_INFO: Record<string, { label: string; desc: string }> = {
  analyze: {
    label: '策略分析',
    desc: 'LLM读取文档概要，分析受众和场景，制定叙事策略框架',
  },
  outline: {
    label: '大纲生成',
    desc: '需要强推理能力，推荐 DeepSeek-R1',
  },
  content: {
    label: '内容填充',
    desc: '需要中文理解 + 结构化输出',
  },
  design: {
    label: '视觉设计',
    desc: '图表叙事与 so-what 生成，推荐通义千问',
  },
};

type ConfigMode = 'universal' | 'advanced';

const SettingsPage: React.FC = () => {
  const [config, setConfig] = useState<PipelineModelConfig | null>(null);
  const [mode, setMode] = useState<ConfigMode>('advanced');
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);

  useEffect(() => { fetchConfig(); }, []);

  const fetchConfig = async () => {
    setLoading(true);
    try {
      const res = await getModelConfig();
      setConfig(res.config);
      const savedMode = (res.config as any).config_mode as ConfigMode || 'advanced';
      // 未配置任何key时自动切到通用模式
      const anyKey = res.config.analyze.has_api_key || res.config.outline.has_api_key
        || res.config.content.has_api_key || (res.config.design || res.config.build)?.has_api_key;
      setMode(anyKey ? savedMode : 'universal');
    } catch {
      message.error('获取模型配置失败');
    } finally {
      setLoading(false);
    }
  };

  const handleUniversalSave = async (values: {
    provider: string; model: string; api_key: string; base_url: string;
  }) => {
    setSaving(true);
    try {
      await updateModelConfig({
        config_mode: 'universal',
        universal_provider: values.provider,
        universal_model: values.model,
        universal_api_key: values.api_key,
        universal_base_url: values.base_url || undefined,
      });
      message.success('通用配置已保存，所有阶段使用同一模型');
      fetchConfig();
    } catch (err: any) {
      message.error(err.response?.data?.detail || '保存失败');
    } finally {
      setSaving(false);
    }
  };

  const handleAdvancedSave = async (stage: string, values: {
    provider: string; model: string; api_key: string; base_url: string;
  }) => {
    setSaving(true);
    try {
      await updateModelConfig({
        config_mode: 'advanced',
        [stage]: {
          provider: values.provider,
          model: values.model,
          api_key: values.api_key,
          base_url: values.base_url || undefined,
        },
      });
      message.success(`${STAGE_INFO[stage]?.label || stage} 配置已保存`);
      fetchConfig();
    } catch (err: any) {
      message.error(err.response?.data?.detail || '保存失败');
    } finally {
      setSaving(false);
    }
  };

  if (loading && !config) {
    return (
      <div style={{ padding: 32, textAlign: 'center', marginTop: 100 }}>
        <Text style={{ color: '#8B9DAF' }}>加载配置中...</Text>
      </div>
    );
  }

  const stages = config
    ? [
        { key: 'analyze', data: config.analyze },
        { key: 'outline', data: config.outline },
        { key: 'content', data: config.content },
        { key: 'design', data: config.design || config.build },
      ]
    : [];

  // Compute config status for the overview bar
  const anyKey = stages.some(s => s.data?.has_api_key);
  const allKeys = stages.every(s => s.data?.has_api_key);
  const configuredCount = stages.filter(s => s.data?.has_api_key).length;
  const activeProvider = stages.find(s => s.data?.has_api_key)?.data?.provider || '';
  const activeModel = stages.find(s => s.data?.has_api_key)?.data?.model || '';
  const providerLabel = PROVIDER_PRESETS[activeProvider]?.label || activeProvider;

  return (
    <div style={{ padding: 32, maxWidth: 800, margin: '0 auto' }}>
      <h2 style={{ color: '#002B4E', fontSize: 22, fontWeight: 600, marginBottom: 8 }}>
        系统设置
      </h2>
      <p style={{ color: '#8B9DAF', fontSize: 14, marginBottom: 20 }}>
        配置各阶段使用的LLM模型和API Key
      </p>

      {/* ── Config status overview bar ── */}
      {anyKey ? (
        <Alert
          message={
            <span>
              <CheckCircleFilled style={{ color: '#52c41a', marginRight: 6 }} />
              API 已配置 — {mode === 'universal' ? '通用模式' : '分阶段模式'}
              {mode === 'universal' && activeProvider && (
                <span style={{ color: '#595959' }}> · {providerLabel} · {activeModel}</span>
              )}
            </span>
          }
          description={
            mode === 'advanced' ? (
              <div style={{ marginTop: 4, fontSize: 12 }}>
                {stages.map(s => {
                  const ok = s.data?.has_api_key;
                  return (
                    <span key={s.key} style={{ marginRight: 12 }}>
                      <span style={{
                        display: 'inline-block', width: 8, height: 8, borderRadius: 4,
                        background: ok ? '#52c41a' : '#d9d9d9', marginRight: 4, verticalAlign: 'middle',
                      }} />
                      <span style={{ color: ok ? '#2D3436' : '#8B9DAF' }}>
                        {STAGE_INFO[s.key]?.label || s.key}
                      </span>
                    </span>
                  );
                })}
                {!allKeys && <span style={{ color: '#faad14', marginLeft: 8 }}>（{configuredCount}/{stages.length} 已配置）</span>}
              </div>
            ) : undefined
          }
          type="success"
          showIcon={false}
          style={{ marginBottom: 20, borderRadius: 2 }}
        />
      ) : (
        <Alert
          message={
            <span>
              <WarningFilled style={{ color: '#faad14', marginRight: 6 }} />
              API Key 未配置 — 请先填写 API Key 才能生成 PPT
            </span>
          }
          description={
            <div style={{ marginTop: 6 }}>
              <Text style={{ fontSize: 13, color: '#595959' }}>
                首次使用？推荐「通用配置」模式，三步完成：
              </Text>
              <ol style={{ margin: '6px 0 0 18px', fontSize: 13, color: '#595959', lineHeight: '1.8' }}>
                <li>选择模型厂商（如 DeepSeek）</li>
                <li>选择模型</li>
                <li>粘贴 API Key → 保存</li>
              </ol>
            </div>
          }
          type="warning"
          showIcon={false}
          style={{ marginBottom: 20, borderRadius: 2 }}
        />
      )}

      {/* ── 模式切换 ── */}
      <Radio.Group
        value={mode}
        onChange={e => setMode(e.target.value)}
        style={{ marginBottom: 24 }}
        optionType="button"
        buttonStyle="solid"
      >
        <Radio.Button value="universal">
          <ThunderboltOutlined style={{ marginRight: 6 }} />
          通用配置
        </Radio.Button>
        <Radio.Button value="advanced">
          <ExperimentOutlined style={{ marginRight: 6 }} />
          分阶段配置
        </Radio.Button>
      </Radio.Group>

      {mode === 'universal' && (
        <>
          <Alert
            message="通用模式：只需配置一个模型，所有阶段统一使用"
            description="适合大多数用户。如果你有多个模型厂商的 API Key，可以切换到「分阶段配置」按能力分工。"
            type="info"
            showIcon
            style={{ marginBottom: 20, borderRadius: 2 }}
          />
          <UniversalConfigCard
            stageData={config?.analyze}
            saving={saving}
            onSave={handleUniversalSave}
          />
        </>
      )}

      {mode === 'advanced' && (
        <>
          <Alert
            message="分阶段模式：每个阶段独立配置模型"
            description={
              <span>
                推荐组合：大纲/内容用 DeepSeek-R1（推理强），图表用通义千问（数据稳定）。
                <br />
                <Text style={{ fontSize: 12, color: '#8B9DAF' }}>适合进阶用户：不同阶段用不同模型以优化效果。</Text>
              </span>
            }
            type="info"
            showIcon
            style={{ marginBottom: 20, borderRadius: 2 }}
          />
          {stages.map(({ key, data }) => (
            <StageConfigCard
              key={key}
              stageKey={key}
              stageData={data}
              saving={saving}
              onSave={(values) => handleAdvancedSave(key, values)}
            />
          ))}
        </>
      )}
    </div>
  );
};

// ── Sub-component: Universal Config Card ──

interface UniversalConfigCardProps {
  stageData?: StageModelConfig;
  saving: boolean;
  onSave: (values: { provider: string; model: string; api_key: string; base_url: string }) => void;
}

const UniversalConfigCard: React.FC<UniversalConfigCardProps> = ({
  stageData, saving, onSave,
}) => {
  const [form] = Form.useForm();
  const [selectedProvider, setSelectedProvider] = useState(stageData?.provider || 'deepseek');
  const [customMode, setCustomMode] = useState(false);

  useEffect(() => {
    const provider = stageData?.provider || 'deepseek';
    const isCustom = provider === 'custom' || !PROVIDER_PRESETS[provider];
    setCustomMode(isCustom);
    setSelectedProvider(isCustom ? 'custom' : provider);
    form.setFieldsValue({
      provider: isCustom ? 'custom' : provider,
      model: stageData?.model || PROVIDER_PRESETS['deepseek'].models[0],
      api_key: '',
      base_url: stageData?.base_url || PROVIDER_PRESETS['deepseek'].base_url,
    });
  }, [stageData, form]);

  const preset = PROVIDER_PRESETS[selectedProvider];
  const modelOptions = preset?.models || [];

  const handleProviderChange = (v: string) => {
    setSelectedProvider(v);
    const isCustom = v === 'custom';
    setCustomMode(isCustom);
    const p = PROVIDER_PRESETS[v];
    form.setFieldsValue({
      model: p?.models?.[0] || '',
      base_url: p?.base_url || '',
    });
  };

  return (
    <Card
      title={
        <span style={{ color: '#002B4E', fontWeight: 600 }}>
          <KeyOutlined style={{ marginRight: 8, color: '#C9A84C' }} />
          通用模型配置
        </span>
      }
      style={{ marginBottom: 20, borderRadius: 2 }}
      styles={{ body: { padding: '20px 24px' } }}
    >
      <Form form={form} layout="vertical" onFinish={onSave}>
        {!customMode ? (
          <Space style={{ width: '100%' }} size={16} align="start">
            <Form.Item label="模型厂商" name="provider" style={{ width: 200, marginBottom: 16 }}>
              <Select onChange={handleProviderChange}>
                {Object.entries(PROVIDER_PRESETS)
                  .filter(([k]) => k !== 'custom')
                  .map(([k, v]) => (
                    <Select.Option key={k} value={k}>{v.label}</Select.Option>
                  ))}
              </Select>
            </Form.Item>
            <Form.Item label="模型" name="model" style={{ flex: 1, marginBottom: 16 }}>
              <AutoComplete
                options={modelOptions.map(m => ({ value: m }))}
                placeholder="选择或输入模型名称"
                filterOption={(input, option) =>
                  (option?.value as string)?.toLowerCase().includes(input.toLowerCase())
                }
                style={{ width: '100%' }}
              />
            </Form.Item>
          </Space>
        ) : (
          <>
            <Form.Item name="provider" hidden><Input /></Form.Item>
            <Space style={{ width: '100%' }} size={16} align="start">
              <Form.Item
                label="模型名称"
                name="model"
                style={{ flex: 1, marginBottom: 16 }}
                rules={[{ required: true, message: '请输入模型名称' }]}
              >
                <Input placeholder="例如: gpt-4o, claude-3-opus" style={{ borderRadius: 2 }} />
              </Form.Item>
            </Space>
            <Form.Item
              label={<span><ApiOutlined style={{ marginRight: 4 }} />API Base URL (OpenAI兼容)</span>}
              name="base_url"
              style={{ marginBottom: 16 }}
              rules={[{ required: true, message: '自定义模式需要填写Base URL' }]}
            >
              <Input placeholder="https://your-endpoint.com/v1" style={{ maxWidth: 500, borderRadius: 2 }} />
            </Form.Item>
          </>
        )}

        <Space style={{ width: '100%', marginBottom: 16 }} size={16} align="center">
          <Form.Item
            label="API Key"
            name="api_key"
            style={{ flex: 1, marginBottom: 0 }}
            extra={
              stageData?.has_api_key
                ? <span style={{ color: '#52c41a', fontSize: 12 }}>✓ 已配置，留空则保持不变</span>
                : <span style={{ color: '#ff4d4f', fontSize: 12 }}>⚠ 请填写 API Key</span>
            }
            validateStatus={stageData?.has_api_key ? undefined : 'warning'}
          >
            <Input.Password
              placeholder={stageData?.has_api_key ? '已配置 (留空不改)' : '请输入 API Key'}
              style={{ maxWidth: 500 }}
            />
          </Form.Item>
          <Space>
            <Text style={{ fontSize: 12, color: '#8B9DAF' }}>自定义模式</Text>
            <Switch
              size="small"
              checked={customMode}
              onChange={(checked) => {
                setCustomMode(checked);
                if (checked) {
                  setSelectedProvider('custom');
                  form.setFieldValue('provider', 'custom');
                }
              }}
            />
          </Space>
        </Space>

        <Button
          type="primary"
          htmlType="submit"
          loading={saving}
          icon={<SaveOutlined />}
          style={{ background: '#003D6E', borderColor: '#003D6E' }}
        >
          保存（应用到所有阶段）
        </Button>
      </Form>
    </Card>
  );
};

// ── Sub-component: Stage Config Card (advanced mode) ──

interface StageConfigCardProps {
  stageKey: string;
  stageData: StageModelConfig;
  saving: boolean;
  onSave: (values: { provider: string; model: string; api_key: string; base_url: string }) => void;
}

const StageConfigCard: React.FC<StageConfigCardProps> = ({
  stageKey, stageData, saving, onSave,
}) => {
  const [form] = Form.useForm();
  const [selectedProvider, setSelectedProvider] = useState(stageData.provider);
  const [customMode, setCustomMode] = useState(
    stageData.provider === 'custom' || !PROVIDER_PRESETS[stageData.provider]
  );

  const info = STAGE_INFO[stageKey] || { label: stageKey, desc: '' };

  useEffect(() => {
    const isCustom = stageData.provider === 'custom' || !PROVIDER_PRESETS[stageData.provider];
    setCustomMode(isCustom);
    setSelectedProvider(isCustom ? 'custom' : stageData.provider);
    form.setFieldsValue({
      provider: isCustom ? 'custom' : stageData.provider,
      model: stageData.model,
      api_key: '',
      base_url: stageData.base_url || '',
    });
  }, [stageData, form]);

  const preset = PROVIDER_PRESETS[selectedProvider];
  const modelOptions = preset?.models || [];

  const handleProviderChange = (v: string) => {
    setSelectedProvider(v);
    const isCustom = v === 'custom';
    setCustomMode(isCustom);
    const p = PROVIDER_PRESETS[v];
    form.setFieldsValue({
      model: p?.models?.[0] || '',
      base_url: p?.base_url || '',
    });
  };

  return (
    <Card
      title={
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <span style={{ color: '#002B4E', fontWeight: 600 }}>
            <KeyOutlined style={{ marginRight: 8, color: '#C9A84C' }} />
            {info.label}
          </span>
          <Space size={8}>
            <Text style={{ fontSize: 12, color: '#8B9DAF' }}>自定义模式</Text>
            <Switch
              size="small"
              checked={customMode}
              onChange={(checked) => {
                setCustomMode(checked);
                if (checked) {
                  setSelectedProvider('custom');
                  form.setFieldValue('provider', 'custom');
                }
              }}
            />
          </Space>
        </div>
      }
      style={{ marginBottom: 20, borderRadius: 2 }}
      styles={{ body: { padding: '20px 24px' } }}
    >
      <Text style={{ color: '#8B9DAF', fontSize: 13, display: 'block', marginBottom: 16 }}>
        {info.desc}
      </Text>

      <Form form={form} layout="vertical" onFinish={onSave}>
        {!customMode ? (
          <>
            <Space style={{ width: '100%' }} size={16} align="start">
              <Form.Item label="模型厂商" name="provider" style={{ width: 200, marginBottom: 16 }}>
                <Select onChange={handleProviderChange}>
                  {Object.entries(PROVIDER_PRESETS)
                    .filter(([k]) => k !== 'custom')
                    .map(([k, v]) => (
                      <Select.Option key={k} value={k}>{v.label}</Select.Option>
                    ))}
                </Select>
              </Form.Item>

              <Form.Item label="模型" name="model" style={{ flex: 1, marginBottom: 16 }}>
                <AutoComplete
                  options={modelOptions.map(m => ({ value: m }))}
                  placeholder="选择或输入模型名称"
                  filterOption={(input, option) =>
                    (option?.value as string)?.toLowerCase().includes(input.toLowerCase())
                  }
                  style={{ width: '100%' }}
                />
              </Form.Item>
            </Space>
          </>
        ) : (
          <>
            <Form.Item name="provider" hidden><Input /></Form.Item>
            <Space style={{ width: '100%' }} size={16} align="start">
              <Form.Item
                label="模型名称"
                name="model"
                style={{ flex: 1, marginBottom: 16 }}
                rules={[{ required: true, message: '请输入模型名称' }]}
              >
                <Input
                  placeholder="例如: gpt-4o, claude-3-opus, llama-3.1-70b"
                  style={{ borderRadius: 2 }}
                />
              </Form.Item>
            </Space>

            <Form.Item
              label={
                <span>
                  <ApiOutlined style={{ marginRight: 4 }} />
                  API Base URL (OpenAI兼容)
                </span>
              }
              name="base_url"
              style={{ marginBottom: 16 }}
              rules={[{ required: true, message: '自定义模式需要填写Base URL' }]}
            >
              <Input
                placeholder="https://your-endpoint.com/v1"
                style={{ maxWidth: 500, borderRadius: 2 }}
              />
            </Form.Item>
          </>
        )}

        <Form.Item
          label="API Key"
          name="api_key"
          style={{ marginBottom: 16 }}
          extra={
            stageData.has_api_key
              ? <span style={{ color: '#52c41a', fontSize: 12 }}>✓ 已配置，留空则保持不变</span>
              : <span style={{ color: '#ff4d4f', fontSize: 12 }}>⚠ 请填写 API Key</span>
          }
          validateStatus={stageData.has_api_key ? undefined : 'warning'}
        >
          <Input.Password
            placeholder={stageData.has_api_key ? '已配置 (留空不改)' : '请输入 API Key'}
            style={{ maxWidth: 500 }}
          />
        </Form.Item>

        <Button
          type="primary"
          htmlType="submit"
          loading={saving}
          icon={<SaveOutlined />}
          style={{ background: '#003D6E', borderColor: '#003D6E' }}
        >
          保存
        </Button>
      </Form>
    </Card>
  );
};

export default SettingsPage;
