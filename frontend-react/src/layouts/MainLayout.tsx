/* ============================================================
   MainLayout — Dark navy sidebar + content area
   ============================================================ */

import React, { useState } from 'react';
import { Outlet, useNavigate, useLocation } from 'react-router-dom';
import { Layout, Menu, Avatar, Dropdown } from 'antd';
import {
  PlusCircleOutlined,
  HistoryOutlined,
  SettingOutlined,
  LogoutOutlined,
  UserOutlined,
  FilePptOutlined,
} from '@ant-design/icons';
import type { MenuProps } from 'antd';
import { useAuth } from '../App';

const { Sider, Content } = Layout;

const SIDEBAR_WIDTH = 220;

const ActiveDot = () => (
  <span style={{
    display: 'inline-block', width: 7, height: 7, borderRadius: '50%',
    background: '#C9A84C', marginLeft: 6, verticalAlign: 'middle',
  }} />
);

const MainLayout: React.FC = () => {
  const navigate = useNavigate();
  const location = useLocation();
  const [collapsed, setCollapsed] = useState(false);
  const { user, logout } = useAuth();

  // Show active task indicator on sidebar
  const hasActiveTask = !!localStorage.getItem('ppt_active_task');

  const navItems: MenuProps['items'] = [
    {
      key: '/',
      icon: <PlusCircleOutlined />,
      label: <span>创建PPT{hasActiveTask ? <ActiveDot /> : null}</span>,
    },
    {
      key: '/history',
      icon: <HistoryOutlined />,
      label: '历史记录',
    },
    {
      key: '/settings',
      icon: <SettingOutlined />,
      label: '系统设置',
    },
  ];

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  const username = user?.username || 'User';

  const dropdownItems: MenuProps['items'] = [
    {
      key: 'logout',
      icon: <LogoutOutlined />,
      label: '退出登录',
      onClick: handleLogout,
    },
  ];

  return (
    <Layout style={{ minHeight: '100vh' }}>
      <Sider
        width={SIDEBAR_WIDTH}
        collapsible
        collapsed={collapsed}
        onCollapse={setCollapsed}
        style={{
          background: 'linear-gradient(180deg, #002B4E 0%, #003D6E 40%, #004A7C 100%)',
          borderRight: '1px solid rgba(201, 168, 76, 0.15)',
          position: 'fixed',
          left: 0,
          top: 0,
          bottom: 0,
          zIndex: 100,
          overflow: 'auto',
        }}
        trigger={null}
      >
        {/* Logo */}
        <div
          style={{
            height: 64,
            display: 'flex',
            alignItems: 'center',
            justifyContent: collapsed ? 'center' : 'flex-start',
            padding: collapsed ? '0' : '0 20px',
            borderBottom: '1px solid rgba(201, 168, 76, 0.2)',
            cursor: 'pointer',
          }}
          onClick={() => setCollapsed(!collapsed)}
        >
          <FilePptOutlined
            style={{
              fontSize: 28,
              color: '#C9A84C',
              flexShrink: 0,
            }}
          />
          {!collapsed && (
            <span
              style={{
                color: '#C9A84C',
                fontSize: 18,
                fontWeight: 700,
                marginLeft: 12,
                letterSpacing: '1px',
                whiteSpace: 'nowrap',
              }}
            >
              PPT Agent
            </span>
          )}
        </div>

        {/* Nav Menu */}
        <Menu
          mode="inline"
          selectedKeys={[location.pathname]}
          items={navItems}
          onClick={({ key }) => navigate(key)}
          style={{
            background: 'transparent',
            borderRight: 'none',
            marginTop: 8,
          }}
          theme="dark"
        />

        {/* Bottom: user + collapse toggle */}
        <div
          style={{
            position: 'absolute',
            bottom: 0,
            left: 0,
            right: 0,
            borderTop: '1px solid rgba(201, 168, 76, 0.2)',
            padding: '12px 16px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: collapsed ? 'center' : 'space-between',
          }}
        >
          {!collapsed && (
            <Dropdown menu={{ items: dropdownItems }} placement="topLeft">
              <div style={{ display: 'flex', alignItems: 'center', cursor: 'pointer' }}>
                <Avatar
                  size={32}
                  icon={<UserOutlined />}
                  style={{ backgroundColor: '#C9A84C', flexShrink: 0 }}
                />
                <span
                  style={{
                    color: '#E8E4D9',
                    marginLeft: 10,
                    fontSize: 13,
                    overflow: 'hidden',
                    textOverflow: 'ellipsis',
                    whiteSpace: 'nowrap',
                  }}
                >
                  {username}
                </span>
              </div>
            </Dropdown>
          )}
          {collapsed && (
            <Dropdown menu={{ items: dropdownItems }} placement="topLeft">
              <Avatar
                size={32}
                icon={<UserOutlined />}
                style={{ backgroundColor: '#C9A84C', cursor: 'pointer' }}
              />
            </Dropdown>
          )}
        </div>
      </Sider>

      {/* Main content */}
      <Layout
        style={{
          marginLeft: collapsed ? 80 : SIDEBAR_WIDTH,
          transition: 'margin-left 0.2s',
          background: '#F7F8FA',
        }}
      >
        <Content
          style={{
            minHeight: '100vh',
            padding: 0,
          }}
        >
          <Outlet />
        </Content>
      </Layout>
    </Layout>
  );
};

export default MainLayout;
