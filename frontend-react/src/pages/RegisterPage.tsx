/* ============================================================
   RegisterPage
   ============================================================ */

import React, { useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { Form, Input, Button, message, Divider } from 'antd';
import { UserOutlined, LockOutlined, FilePptOutlined } from '@ant-design/icons';
import { register } from '../api/client';
import { useAuth } from '../App';

const RegisterPage: React.FC = () => {
  const navigate = useNavigate();
  const { setAuth } = useAuth();
  const [loading, setLoading] = useState(false);

  const onFinish = async (values: { username: string; password: string }) => {
    setLoading(true);
    try {
      const res = await register(values.username, values.password);
      setAuth(res.token, res.user);
      message.success('注册成功');
      navigate('/');
    } catch (err: any) {
      const msg = err.response?.data?.detail || '注册失败';
      message.error(msg);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={styles.container}>
      <div style={styles.card}>
        <div style={styles.header}>
          <FilePptOutlined style={{ fontSize: 40, color: '#C9A84C' }} />
          <h1 style={{ color: '#E8E4D9', fontSize: 28, fontWeight: 700, margin: '8px 0 0', letterSpacing: '2px' }}>
            创建账号
          </h1>
          <p style={{ color: '#8B9DAF', fontSize: 14, margin: '4px 0 0' }}>注册以使用PPT Agent</p>
        </div>

        <Divider style={{ borderColor: 'rgba(201,168,76,0.2)', margin: '24px 0' }} />

        <Form onFinish={onFinish} size="large">
          <Form.Item name="username" rules={[
            { required: true, message: '请输入用户名' },
            { min: 3, message: '用户名至少3个字符' },
          ]}>
            <Input
              prefix={<UserOutlined style={{ color: '#8B9DAF' }} />}
              placeholder="用户名"
              style={styles.input}
            />
          </Form.Item>
          <Form.Item name="password" rules={[
            { required: true, message: '请输入密码' },
            { min: 6, message: '密码至少6个字符' },
          ]}>
            <Input.Password
              prefix={<LockOutlined style={{ color: '#8B9DAF' }} />}
              placeholder="密码"
              style={styles.input}
            />
          </Form.Item>
          <Form.Item name="confirm" dependencies={['password']} rules={[
            { required: true, message: '请确认密码' },
            ({ getFieldValue }) => ({
              validator(_, value) {
                if (!value || getFieldValue('password') === value) return Promise.resolve();
                return Promise.reject(new Error('两次输入的密码不一致'));
              },
            }),
          ]}>
            <Input.Password
              prefix={<LockOutlined style={{ color: '#8B9DAF' }} />}
              placeholder="确认密码"
              style={styles.input}
            />
          </Form.Item>
          <Form.Item style={{ marginBottom: 16 }}>
            <Button type="primary" htmlType="submit" loading={loading} block style={styles.submitBtn}>
              注册
            </Button>
          </Form.Item>
        </Form>

        <div style={{ textAlign: 'center', marginTop: 8 }}>
          <span style={{ color: '#8B9DAF' }}>已有账号？</span>
          <Link to="/login" style={{ color: '#C9A84C', marginLeft: 6 }}>立即登录</Link>
        </div>
      </div>
    </div>
  );
};

const styles: Record<string, React.CSSProperties> = {
  container: {
    minHeight: '100vh',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    background: 'linear-gradient(135deg, #001B33 0%, #003D6E 50%, #002B4E 100%)',
  },
  input: {
    background: 'rgba(0, 20, 40, 0.6)',
    borderColor: 'rgba(201, 168, 76, 0.3)',
    color: '#E8E4D9',
    borderRadius: 2,
  },
  submitBtn: {
    height: 44,
    background: '#C9A84C',
    borderColor: '#C9A84C',
    color: '#002B4E',
    fontWeight: 700,
    fontSize: 15,
    borderRadius: 2,
    letterSpacing: '1px',
  },
};

export default RegisterPage;
