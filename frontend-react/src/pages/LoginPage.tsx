/* ============================================================
   LoginPage — Dark navy consulting login
   ============================================================ */

import React, { useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { Form, Input, Button, message, Divider } from 'antd';
import { UserOutlined, LockOutlined, FilePptOutlined } from '@ant-design/icons';
import { login } from '../api/client';
import { useAuth } from '../App';

const LoginPage: React.FC = () => {
  const navigate = useNavigate();
  const { setAuth } = useAuth();
  const [loading, setLoading] = useState(false);

  const onFinish = async (values: { username: string; password: string }) => {
    setLoading(true);
    try {
      const res = await login(values.username, values.password);
      setAuth(res.token, res.user);
      message.success('登录成功');
      navigate('/');
    } catch (err: any) {
      const msg = err.response?.data?.detail || '登录失败，请检查用户名和密码';
      message.error(msg);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={styles.container}>
      <div style={styles.card}>
        {/* Header */}
        <div style={styles.header}>
          <FilePptOutlined style={styles.logo} />
          <h1 style={styles.title}>PPT Agent</h1>
          <p style={styles.subtitle}>专业咨询级PPT生成平台</p>
        </div>

        <Divider style={{ borderColor: 'rgba(201,168,76,0.2)', margin: '24px 0' }} />

        <Form onFinish={onFinish} size="large" style={{ marginTop: 8 }}>
          <Form.Item name="username" rules={[{ required: true, message: '请输入用户名' }]}>
            <Input
              prefix={<UserOutlined style={{ color: '#8B9DAF' }} />}
              placeholder="用户名"
              style={styles.input}
            />
          </Form.Item>
          <Form.Item name="password" rules={[{ required: true, message: '请输入密码' }]}>
            <Input.Password
              prefix={<LockOutlined style={{ color: '#8B9DAF' }} />}
              placeholder="密码"
              style={styles.input}
            />
          </Form.Item>
          <Form.Item style={{ marginBottom: 16 }}>
            <Button
              type="primary"
              htmlType="submit"
              loading={loading}
              block
              style={styles.submitBtn}
            >
              登录
            </Button>
          </Form.Item>
        </Form>

        <div style={styles.footer}>
          <span style={{ color: '#8B9DAF' }}>还没有账号？</span>
          <Link to="/register" style={{ color: '#C9A84C', marginLeft: 6 }}>
            立即注册
          </Link>
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
  card: {
    width: 420,
    padding: '40px 36px',
    background: 'rgba(0, 43, 78, 0.85)',
    backdropFilter: 'blur(20px)',
    borderRadius: 2,
    border: '1px solid rgba(201, 168, 76, 0.2)',
    boxShadow: '0 20px 60px rgba(0, 0, 0, 0.4)',
  },
  header: {
    textAlign: 'center' as const,
  },
  logo: {
    fontSize: 40,
    color: '#C9A84C',
  },
  title: {
    color: '#E8E4D9',
    fontSize: 28,
    fontWeight: 700,
    margin: '8px 0 0',
    letterSpacing: '2px',
  },
  subtitle: {
    color: '#8B9DAF',
    fontSize: 14,
    margin: '4px 0 0',
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
  footer: {
    textAlign: 'center' as const,
    marginTop: 8,
  },
};

export default LoginPage;
