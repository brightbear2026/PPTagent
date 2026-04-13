"""
测试 FastAPI 后端
"""

import sys
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

import requests
import time
import json

API_BASE = "http://localhost:8000"


def test_api():
    """测试API端点"""

    print("\n" + "=" * 60)
    print("  FastAPI 后端测试")
    print("=" * 60)

    # 测试1: 健康检查
    print("\n📋 测试1: 健康检查")
    try:
        response = requests.get(f"{API_BASE}/api/health", timeout=2)
        if response.status_code == 200:
            print("✅ 后端服务正常")
            print(f"   {json.dumps(response.json(), indent=2, ensure_ascii=False)}")
        else:
            print(f"❌ 健康检查失败: {response.status_code}")
            return
    except Exception as e:
        print(f"❌ 无法连接后端: {str(e)}")
        print("   请先启动后端: python3 api/main.py")
        return

    # 测试2: 创建生成任务
    print("\n📋 测试2: 创建PPT生成任务")
    test_content = """
    2023年业务分析报告

    一、业绩回顾
    公司实现营收15.2亿元，同比增长5%。但低于行业平均12%。

    二、核心挑战
    1. 获客成本同比上升45%
    2. 客户流失率达到18%
    3. 系统老旧，交付周期3个月

    三、解决方案
    1. 启动数字化转型
    2. 构建客户数据平台
    3. 实施营销自动化
    """

    try:
        response = requests.post(
            f"{API_BASE}/api/generate",
            json={
                "title": "业务分析报告",
                "content": test_content,
                "target_audience": "管理层",
                "language": "zh"
            },
            timeout=10
        )

        if response.status_code == 200:
            data = response.json()
            task_id = data["task_id"]
            print(f"✅ 任务创建成功")
            print(f"   Task ID: {task_id}")

            # 轮询状态
            print("\n📋 测试3: 轮询任务状态")
            max_wait = 120  # 最长等待2分钟
            start_time = time.time()

            while time.time() - start_time < max_wait:
                response = requests.get(
                    f"{API_BASE}/api/status/{task_id}/json",
                    timeout=5
                )

                if response.status_code == 200:
                    status = response.json()
                    progress = status["progress"]
                    current_step = status["current_step"]
                    status_type = status["status"]

                    print(f"   [{progress}%] {current_step} - {status_type}")

                    if status_type == "completed":
                        print(f"\n✅ PPT生成完成!")
                        print(f"   输出文件: {status['output_file']}")

                        # 测试下载
                        print("\n📋 测试4: 下载PPT文件")
                        download_url = f"{API_BASE}/api/download/{task_id}"
                        print(f"   下载地址: {download_url}")
                        print(f"   可在浏览器中打开下载")

                        break

                    elif status_type == "failed":
                        print(f"\n❌ 生成失败: {status.get('error', '未知错误')}")
                        break

                    time.sleep(2)
                else:
                    print(f"❌ 状态查询失败: {response.status_code}")
                    break
            else:
                print("⏰ 超时：生成时间过长")

        else:
            print(f"❌ 创建任务失败: {response.status_code}")
            print(f"   {response.text}")

    except Exception as e:
        print(f"❌ 测试失败: {str(e)}")

    # 测试5: 历史记录
    print("\n📋 测试5: 历史记录")
    try:
        response = requests.get(f"{API_BASE}/api/history", timeout=5)
        if response.status_code == 200:
            history = response.json()
            print(f"✅ 历史记录查询成功")
            print(f"   总数: {history['total']}")

            if history["items"]:
                print("   最近一条:")
                item = history["items"][0]
                print(f"   - {item['title']} ({item['status']})")
        else:
            print(f"❌ 历史记录查询失败: {response.status_code}")
    except Exception as e:
        print(f"❌ 历史记录测试失败: {str(e)}")

    print("\n" + "=" * 60)
    print("  测试完成")
    print("=" * 60)


if __name__ == "__main__":
    test_api()
