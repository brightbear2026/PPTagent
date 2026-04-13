"""
Streamlit 前端应用
PPT Agent 用户界面 — 5阶段 / 2检查点 Pipeline
"""

import sys
import os
import time
import json
import requests
from pathlib import Path
from typing import Optional

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import streamlit as st

# ============================================================
# 禁用代理（localhost不走代理，避免socks5导致的延迟/超时）
# ============================================================
os.environ["no_proxy"] = "localhost,127.0.0.1"
os.environ["NO_PROXY"] = "localhost,127.0.0.1"
os.environ.pop("all_proxy", None)
os.environ.pop("ALL_PROXY", None)

# ============================================================
# 配置
# ============================================================

st.set_page_config(
    page_title="PPT Agent",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

try:
    API_BASE = st.secrets["API_BASE"]
except (KeyError, Exception):
    API_BASE = os.environ.get("API_BASE", "http://localhost:8000")

# ============================================================
# 样式
# ============================================================

st.markdown("""
<style>
    .stage-bar { display: flex; gap: 2px; margin: 8px 0; flex-wrap: wrap; }
    .stage-chip {
        padding: 6px 14px; border-radius: 16px; font-size: 0.85rem;
        font-weight: 500; white-space: nowrap;
    }
    .stage-pending { background: #e9ecef; color: #6c757d; }
    .stage-running { background: #cce5ff; color: #004085; animation: pulse 1.5s infinite; }
    .stage-completed { background: #d4edda; color: #155724; }
    .stage-checkpoint { background: #fff3cd; color: #856404; border: 2px solid #ffc107; }
    .stage-failed { background: #f8d7da; color: #721c24; }
    @keyframes pulse { 0%,100% { opacity: 1; } 50% { opacity: 0.6; } }
    .download-btn {
        display: inline-block; background: #003D6E; color: white !important;
        padding: 12px 32px; border-radius: 8px; text-decoration: none;
        font-size: 1.1rem; font-weight: 600; margin: 10px 0;
    }
    .download-btn:hover { background: #005a9e; }
    .checkpoint-banner {
        background: linear-gradient(90deg, #fff3cd, #ffeeba);
        border-left: 5px solid #ffc107; padding: 16px; margin: 12px 0;
        border-radius: 4px;
    }
</style>
""", unsafe_allow_html=True)

# Pipeline阶段定义（5阶段 / 2检查点）
STAGES = [
    ("parse",   "输入解析", False),
    ("analyze", "数据分析", False),
    ("outline", "大纲生成", True),    # 检查点1
    ("content", "内容填充", True),    # 检查点2
    ("build",   "PPT构建", False),
]

CHECKPOINT_NAMES = {
    "outline": "大纲确认",
    "content": "内容确认",
}

# ============================================================
# 辅助函数
# ============================================================

_NO_PROXY = {"http": "", "https": "", "all": ""}


def check_backend_health() -> bool:
    try:
        r = requests.get(f"{API_BASE}/api/health", timeout=10, proxies=_NO_PROXY)
        return r.status_code == 200
    except Exception:
        return False


def poll_task_status(task_id: str) -> Optional[dict]:
    try:
        r = requests.get(f"{API_BASE}/api/status/{task_id}/json", timeout=10, proxies=_NO_PROXY)
        if r.status_code == 200:
            return r.json()
    except Exception:
        pass
    return None


def get_stages(task_id: str) -> Optional[list]:
    try:
        r = requests.get(f"{API_BASE}/api/task/{task_id}/stages", timeout=10, proxies=_NO_PROXY)
        if r.status_code == 200:
            return r.json()
    except Exception:
        pass
    return None


def api_get(url: str) -> Optional[dict]:
    try:
        r = requests.get(f"{API_BASE}{url}", timeout=10, proxies=_NO_PROXY)
        if r.status_code == 200:
            return r.json()
    except Exception:
        pass
    return None


def api_post(url: str, json_data=None, data=None, files=None, timeout=60) -> Optional[dict]:
    try:
        r = requests.post(f"{API_BASE}{url}", json=json_data, data=data, files=files,
                          timeout=timeout, proxies=_NO_PROXY)
        if r.status_code == 200:
            return r.json()
        else:
            try:
                err = r.json()
                return {"error": err.get("detail", r.text), "_status": r.status_code}
            except Exception:
                return {"error": r.text, "_status": r.status_code}
    except Exception as e:
        return {"error": str(e)}


def api_put(url: str, json_data=None) -> Optional[dict]:
    try:
        r = requests.put(f"{API_BASE}{url}", json=json_data, timeout=10, proxies=_NO_PROXY)
        if r.status_code == 200:
            return r.json()
        else:
            try:
                return {"error": r.json().get("detail", r.text)}
            except Exception:
                return {"error": r.text}
    except Exception as e:
        return {"error": str(e)}


def render_stage_bar(stages_data: list):
    """渲染Pipeline阶段进度条"""
    html = '<div class="stage-bar">'
    for stage_key, stage_name, is_checkpoint in STAGES:
        stage = next((s for s in stages_data if s["stage"] == stage_key), None)
        status = stage["status"] if stage else "pending"
        css_class = f"stage-{status}"
        icon = {"completed": "✓", "running": "●", "checkpoint": "⏸", "failed": "✗"}.get(status, "○")
        label = f"{icon} {stage_name}"
        if is_checkpoint and status != "pending":
            label += " 🔍"
        html += f'<span class="stage-chip {css_class}">{label}</span>'
    html += '</div>'
    st.markdown(html, unsafe_allow_html=True)


def show_stage_detail(stage_key: str, stage_data: dict):
    """展示单个阶段的详细结果"""
    result = stage_data.get("result")
    if not result:
        st.info("该阶段暂无结果数据")
        return

    if stage_key == "parse":
        st.write(f"**源类型**: {result.get('source_type')} | "
                 f"**语言**: {result.get('detected_language')} | "
                 f"**文本长度**: {result.get('text_length', 0)}字")
        if result.get("table_count", 0) > 0:
            st.write(f"**表格**: {result['table_count']}个")
            for t in result.get("tables", []):
                st.write(f"  - {t['sheet']}: {', '.join(t['headers'][:5])} ({t['row_count']}行)")
        with st.expander("查看原始文本预览"):
            st.text(result.get("raw_text_preview", "")[:500])

    elif stage_key == "analyze":
        metrics = result.get("derived_metrics", [])
        findings = result.get("key_findings", [])
        gaps = result.get("data_gaps", [])
        warnings = result.get("validation_warnings", [])

        col1, col2, col3, col4 = st.columns(4)
        col1.metric("派生指标", len(metrics))
        col2.metric("关键发现", len(findings))
        col3.metric("数据缺失", len(gaps))
        col4.metric("校验警告", len(warnings))

        if metrics:
            with st.expander(f"📊 派生指标 ({len(metrics)})"):
                # 按类型分组
                groups = {}
                for m in metrics:
                    t = m.get("metric_type", "other")
                    groups.setdefault(t, []).append(m)
                for t, items in groups.items():
                    st.write(f"**{t}** ({len(items)}个)")
                    for m in items[:5]:
                        line = f"- {m['name']}: {m['formatted_value']}"
                        if m.get("context"):
                            line += f" ({m['context']})"
                        st.write(line)
                    if len(items) > 5:
                        st.caption(f"...共{len(items)}个")

        if findings:
            with st.expander(f"💡 关键发现 ({len(findings)})"):
                for f in findings:
                    st.write(f"- {f}")

        if gaps:
            with st.expander(f"⚠️ 数据缺失建议 ({len(gaps)})"):
                for g in gaps:
                    importance = g.get("importance", "medium")
                    icon = {"high": "🔴", "medium": "🟡", "low": "🟢"}.get(importance, "⚪")
                    st.write(f"- {icon} {g.get('gap_description', '')} — {g.get('reason', '')}")

        if warnings:
            with st.expander(f"⚠️ 数据一致性警告 ({len(warnings)})"):
                for w in warnings:
                    st.warning(w.get("message", ""))

    elif stage_key == "outline":
        items = result.get("items", [])
        logic = result.get("narrative_logic", "")
        gap_suggestions = result.get("data_gap_suggestions", [])

        st.write(f"**叙事逻辑**: {logic}")
        st.write(f"共 **{len(items)}** 页")

        for item in items:
            type_icon = {"title": "🏷️", "agenda": "📋", "content": "📝", "data": "📊",
                        "diagram": "🔀", "comparison": "⚖️", "summary": "📌"}.get(
                item.get("slide_type", ""), "📄")
            with st.expander(
                f"{type_icon} 第{item.get('page_number', '?')}页 "
                f"[{item.get('slide_type', '')}] "
                f"{item.get('takeaway_message', '')[:50]}"
            ):
                st.write(f"**核心论点**: {item.get('takeaway_message', '')}")
                if item.get("supporting_hint"):
                    st.write(f"**支撑提示**: {item['supporting_hint']}")
                if item.get("data_source"):
                    st.write(f"**数据来源**: {item['data_source']}")

        if gap_suggestions:
            with st.expander("💡 数据补充建议"):
                for s in gap_suggestions:
                    st.write(f"- {s}")

    elif stage_key == "content":
        slides = result.get("slides", [])
        total = result.get("total_pages", 0)
        failed = result.get("failed_pages", [])

        st.write(f"共 **{total}** 页内容，失败 **{len(failed)}** 页")

        for slide in slides:
            is_failed = slide.get("is_failed", False)
            icon = "❌" if is_failed else "📝"
            title = slide.get("takeaway_message", "")[:50]

            with st.expander(f"{icon} 第{slide.get('page_number', '?')}页 — {title}"):
                if is_failed:
                    st.error(f"生成失败: {slide.get('error_message', '未知错误')}")
                    continue

                # 文本块
                for tb in slide.get("text_blocks", []):
                    indent = "  " * tb.get("level", 0)
                    bold = "**" if tb.get("is_bold") else ""
                    st.write(f"{indent}- {bold}{tb.get('content', '')}{bold}")

                # 图表建议
                cs = slide.get("chart_suggestion")
                if cs:
                    st.write(f"\n📊 **图表**: {cs.get('title', '')} ({cs.get('chart_type', '')})")
                    if cs.get("so_what"):
                        st.write(f"   结论: {cs['so_what']}")

                # 图表规格
                ds = slide.get("diagram_spec")
                if ds:
                    st.write(f"\n🔀 **图示**: {ds.get('title', '')} ({ds.get('diagram_type', '')})")

                if slide.get("source_note"):
                    st.caption(f"来源: {slide['source_note']}")

                if slide.get("warnings"):
                    for w in slide["warnings"]:
                        st.warning(w)

    elif stage_key == "build":
        st.write(f"**输出文件**: {result.get('file_name')}")
        st.write(f"**页面数**: {result.get('slide_count')}")

    else:
        st.json(result)


def show_stage_editor(stage_key: str, stage_data: dict, task_id: str):
    """展示阶段编辑器"""
    result = stage_data.get("result")
    if not result:
        st.info("该阶段暂无结果可编辑")
        return

    if stage_key == "outline":
        st.subheader("编辑大纲")
        items = result.get("items", [])

        for i, item in enumerate(items):
            with st.expander(
                f"第{item.get('page_number', i+1)}页 [{item.get('slide_type', '')}]"
            ):
                item["takeaway_message"] = st.text_input(
                    "核心论点",
                    value=item.get("takeaway_message", ""),
                    key=f"tw_{i}"
                )
                item["supporting_hint"] = st.text_input(
                    "支撑提示",
                    value=item.get("supporting_hint", ""),
                    key=f"hint_{i}"
                )

        if st.button("保存修改", type="primary", key="save_outline"):
            new_result = dict(result)
            new_result["items"] = items
            resp = api_put(f"/api/task/{task_id}/stage/outline", new_result)
            if resp and not resp.get("error"):
                st.success("已保存，后续阶段已重置")
                st.rerun()
            else:
                st.error(f"保存失败: {resp.get('error', '未知错误') if resp else '请求失败'}")

    elif stage_key == "content":
        st.subheader("编辑内容")
        slides = result.get("slides", [])

        for slide in slides:
            if slide.get("is_failed"):
                continue
            pn = slide.get("page_number", "?")
            with st.expander(f"第{pn}页"):
                slide["takeaway_message"] = st.text_input(
                    "核心论点",
                    value=slide.get("takeaway_message", ""),
                    key=f"ct_tw_{pn}"
                )
                # 编辑文本块
                for j, tb in enumerate(slide.get("text_blocks", [])):
                    tb["content"] = st.text_input(
                        f"L{tb.get('level', 0)} 文本",
                        value=tb.get("content", ""),
                        key=f"ct_tb_{pn}_{j}"
                    )

        if st.button("保存修改", type="primary", key="save_content"):
            new_result = dict(result)
            resp = api_put(f"/api/task/{task_id}/stage/content", new_result)
            if resp and not resp.get("error"):
                st.success("已保存，后续阶段已重置")
                st.rerun()
            else:
                st.error(f"保存失败: {resp.get('error', '未知错误') if resp else '请求失败'}")

    else:
        st.info("该阶段暂不支持编辑")


def _show_model_config_ui():
    """侧边栏：多阶段模型配置UI"""
    model_config = api_get("/api/config/models")
    if not model_config:
        st.warning("无法获取模型配置")
        return

    config = model_config.get("config", {})
    available_providers = model_config.get("available_providers", [])

    # 新阶段名
    stage_labels = {
        "analyze": ("数据分析", "zhipu"),
        "outline": ("大纲生成", "deepseek"),
        "content": ("内容填充", "deepseek"),
        "build":   ("PPT构建", "tongyi"),
    }

    provider_models = {
        "zhipu": ["glm-4-plus", "glm-4-flash", "glm-4"],
        "deepseek": ["deepseek-r1", "deepseek-chat"],
        "tongyi": ["qwen-max", "qwen-plus"],
        "qwen": ["qwen-max", "qwen-plus"],
        "moonshot": ["moonshot-v1-8k"],
        "openai": ["gpt-4", "gpt-4o"],
    }

    has_any_key = False
    updates = {}

    for stage_key, (label, default_provider) in stage_labels.items():
        stage_cfg = config.get(stage_key, {})
        current_provider = stage_cfg.get("provider", default_provider)
        current_model = stage_cfg.get("model", "")
        has_key = stage_cfg.get("has_api_key", False) or bool(stage_cfg.get("api_key", ""))
        if has_key:
            has_any_key = True

        status_icon = "🟢" if has_key else "⚪"
        with st.expander(f"{status_icon} {label} ({current_provider})"):
            new_provider = st.selectbox(
                "提供商", available_providers,
                index=available_providers.index(current_provider)
                    if current_provider in available_providers else 0,
                key=f"cfg_prov_{stage_key}",
            )
            models = provider_models.get(new_provider, ["(自定义)"])
            new_model = st.selectbox(
                "模型", models,
                index=models.index(current_model) if current_model in models else 0,
                key=f"cfg_model_{stage_key}",
            )
            new_key = st.text_input(
                "API Key (留空保留现有)", type="password",
                key=f"cfg_key_{stage_key}",
            )
            if new_provider != current_provider or new_model != current_model or new_key:
                update = {"provider": new_provider, "model": new_model}
                if new_key:
                    update["api_key"] = new_key
                updates[stage_key] = update

    if has_any_key:
        st.success("API 已配置")
    else:
        st.warning("请至少为一个阶段配置 API Key")

    if updates and st.button("保存模型配置", type="primary"):
        resp = api_put("/api/config/models", updates)
        if resp and not resp.get("error"):
            st.success("模型配置已保存")
            st.rerun()
        else:
            st.error(f"保存失败: {resp.get('error', '未知错误') if resp else '请求失败'}")


def show_task_view(task_id: str):
    """
    统一的任务视图：展示进度/结果/操作按钮
    """
    status = poll_task_status(task_id)
    if not status:
        st.warning("无法获取任务状态")
        return

    task_status = status["status"]

    # 状态提示
    if task_status == "completed":
        st.balloons()
        st.success("PPT 生成完成!")
    elif task_status == "checkpoint":
        current_stage = status.get("current_stage", "")
        checkpoint_name = CHECKPOINT_NAMES.get(current_stage, "")
        st.markdown(
            f'<div class="checkpoint-banner">'
            f'<strong>检查点暂停</strong> — {checkpoint_name}<br/>'
            f'<span style="font-size:0.9rem;color:#6c757d">请审查下方结果后确认继续</span>'
            f'</div>',
            unsafe_allow_html=True,
        )
    elif task_status == "processing":
        pct = status["progress"]
        step = status.get("current_step", "")
        st.progress(pct / 100, text=f"{pct}% - {step}")
        st.info(status.get("message", "处理中..."))
    elif task_status == "failed":
        st.error(f"生成失败: {status.get('error', '未知错误')}")

    # 阶段条
    stages_resp = get_stages(task_id)
    if stages_resp:
        render_stage_bar(stages_resp.get("stages", []))

    # 阶段详情
    if stages_resp:
        for stage_key, stage_name, is_checkpoint in STAGES:
            stage = next(
                (s for s in stages_resp["stages"] if s["stage"] == stage_key),
                {"stage": stage_key, "status": "pending", "result": None}
            )
            icon = {
                "completed": "✅", "running": "🔄",
                "checkpoint": "⏸", "failed": "❌"
            }.get(stage["status"], "⏳")

            # 检查点阶段暂停时展开最后一个检查点的结果
            is_expanded = stage["status"] == "completed" or (
                task_status == "checkpoint" and is_checkpoint
                and stage["status"] == "completed"
            )

            with st.expander(f"{icon} {stage_name}", expanded=is_expanded):
                if stage["status"] == "completed" and stage.get("result"):
                    show_stage_detail(stage_key, stage)
                    st.divider()
                    show_stage_editor(stage_key, stage, task_id)
                elif stage["status"] == "failed":
                    st.error(stage.get("error", "未知错误"))
                else:
                    st.info("等待执行")

    # 操作按钮区
    st.divider()

    if task_status == "checkpoint":
        current_stage = status.get("current_stage", "")
        checkpoint_name = CHECKPOINT_NAMES.get(current_stage, "")
        col1, col2 = st.columns([2, 3])
        with col1:
            if st.button(f"确认 {checkpoint_name}，继续生成", type="primary",
                         use_container_width=True):
                resp = api_post(f"/api/task/{task_id}/confirm")
                if resp:
                    st.rerun()
        with col2:
            st.caption("确认后将执行到下一个检查点或完成PPT构建。")

    if task_status == "processing":
        time.sleep(2)
        st.rerun()

    # 下载按钮
    output_file = status.get("output_file")
    if output_file:
        try:
            dl_resp = requests.get(
                f"{API_BASE}/api/download/{task_id}", timeout=10, proxies=_NO_PROXY
            )
            if dl_resp.status_code == 200:
                filename = output_file.split("/")[-1]
                st.download_button(
                    label="下载PPT文件",
                    data=dl_resp.content,
                    file_name=filename,
                    mime="application/vnd.openxmlformats.officedocument.presentationml.presentation",
                    type="primary",
                )
        except Exception as e:
            st.error(f"下载出错: {e}")

    # 重跑
    col1, col2 = st.columns(2)
    with col1:
        from_stage = st.selectbox(
            "从指定阶段重跑",
            options=[s[0] for s in STAGES],
            format_func=lambda x: next(n for k, n, _ in STAGES if k == x),
            index=0,
        )
    with col2:
        if st.button("重新执行"):
            resp = api_post(f"/api/task/{task_id}/resume?from_stage={from_stage}")
            if resp:
                st.success("已开始重跑")
                st.rerun()

    # 新建任务
    if task_status in ("completed", "failed"):
        if st.button("创建新任务"):
            st.session_state.pop("active_task_id", None)
            st.rerun()


# ============================================================
# 主页面
# ============================================================

def main():
    st.markdown(
        '<p style="font-size:2.5rem;font-weight:700;color:#003D6E;margin-bottom:0.5rem">'
        'PPT Agent</p>',
        unsafe_allow_html=True
    )
    st.markdown(
        '<p style="font-size:1.2rem;color:#636E72;margin-bottom:2rem">'
        '专业PPT自动生成系统</p>',
        unsafe_allow_html=True
    )

    if not check_backend_health():
        st.error("**后端服务未启动**\n\n```\npython3 -m uvicorn api.main:app --reload\n```")
        st.stop()

    # ── 侧边栏 ──
    with st.sidebar:
        st.header("模型配置")
        _show_model_config_ui()

        st.divider()

        st.header("设置")
        language = st.selectbox("语言", ["中文", "英文"], index=0)
        audience = st.selectbox("目标受众", ["管理层", "技术团队", "客户", "投资者"], index=0)

        st.divider()
        st.header("使用步骤")
        st.markdown("1. 配置 API Key\n2. 输入内容或上传文件\n3. 点击生成\n4. 确认2个检查点\n5. 下载PPT")

    # ── 主内容 ──
    tab1, tab2, tab3 = st.tabs(["创建PPT", "生成历史", "帮助"])

    active_task = st.session_state.get("active_task_id")
    if active_task:
        task_status = poll_task_status(active_task)
        if task_status and task_status["status"] in (
            "processing", "checkpoint", "completed", "failed"
        ):
            with tab1:
                try:
                    show_task_view(active_task)
                except Exception as e:
                    st.error(f"渲染错误: {e}")
                    st.code(str(e))

            with st.sidebar:
                st.divider()
                if st.button("新建任务"):
                    st.session_state.pop("active_task_id", None)
                    st.rerun()
            return
        else:
            st.session_state.pop("active_task_id", None)

    # ── Tab 1: 创建PPT ──
    with tab1:
        input_mode = st.radio("输入方式", ["文本输入", "文件上传"], horizontal=True)
        title = st.text_input("演示文稿标题", value="数字化转型战略方案",
                              placeholder="输入PPT标题...")

        if input_mode == "文本输入":
            content = st.text_area("原始内容", height=200,
                                   placeholder="粘贴内容...\n\n建议包含标题、数据、分析和结论。")

            if st.button("生成PPT", type="primary", use_container_width=True, key="btn_text"):
                if not content.strip():
                    st.warning("请输入内容")
                elif not title.strip():
                    st.warning("请输入标题")
                else:
                    lang_code = "zh" if language == "中文" else "en"
                    result = api_post("/api/generate", {
                        "title": title, "content": content,
                        "target_audience": audience, "language": lang_code,
                    })
                    if result:
                        if result.get("error"):
                            st.error(f"请求失败: {result['error']}")
                        else:
                            st.session_state["active_task_id"] = result["task_id"]
                            st.rerun()
        else:
            uploaded_file = st.file_uploader(
                "上传文件", type=["docx", "xlsx", "csv", "pptx", "txt", "md"],
                help="支持 .docx, .xlsx, .csv, .pptx, .txt, .md，最大 50MB",
            )
            if uploaded_file:
                st.info(f"已选择: **{uploaded_file.name}** ({uploaded_file.size / 1024:.1f} KB)")

            if st.button("生成PPT", type="primary", use_container_width=True, key="btn_file"):
                if not uploaded_file:
                    st.warning("请选择文件")
                elif not title.strip():
                    st.warning("请输入标题")
                else:
                    lang_code = "zh" if language == "中文" else "en"
                    with st.spinner("上传文件中..."):
                        result = api_post(
                            "/api/generate/file",
                            files={"file": (uploaded_file.name, uploaded_file.getvalue(),
                                            uploaded_file.type)},
                            data={
                                "title": title, "target_audience": audience,
                                "language": lang_code,
                            },
                            timeout=120,
                        )
                    if result:
                        if result.get("error"):
                            st.error(f"上传失败: {result['error']}")
                        else:
                            st.session_state["active_task_id"] = result["task_id"]
                            st.rerun()

    # ── Tab 2: 生成历史 ──
    with tab2:
        st.header("生成历史")
        try:
            history = api_get("/api/history")
            if history:
                if history["total"] == 0:
                    st.info("暂无生成历史")
                else:
                    st.caption(f"共 {history['total']} 条记录")
                    for item in history["items"]:
                        with st.container():
                            cols = st.columns([4, 3, 2])
                            with cols[0]:
                                st.write(f"**{item['title']}**")
                            with cols[1]:
                                created = item.get("created_at", "")
                                st.write(f"{created[:19] if created else '-'}")
                            with cols[2]:
                                if item.get("output_file"):
                                    tid = item["task_id"]
                                    fname = item["output_file"].split("/")[-1]
                                    if st.button("下载", key=f"hdl_{tid}"):
                                        dl_r = requests.get(
                                            f"{API_BASE}/api/download/{tid}",
                                            timeout=10, proxies=_NO_PROXY
                                        )
                                        if dl_r.status_code == 200:
                                            st.download_button(
                                                "确认下载", dl_r.content, fname,
                                                mime="application/vnd.openxmlformats"
                                                     ".officedocument.presentationml"
                                                     ".presentation",
                                                key=f"hdlb_{tid}"
                                            )
                        st.divider()
        except Exception:
            st.warning("无法加载历史记录")

    # ── Tab 3: 帮助 ──
    with tab3:
        st.header("使用帮助")
        st.markdown("""
        ### 工作流程

        系统通过 **2个检查点** 确保PPT质量：

        | # | 检查点 | 审查内容 | 可编辑 |
        |---|--------|----------|--------|
        | 1 | 大纲确认 | 叙事逻辑、每页核心论点和数据来源 | 编辑论点、调整页面 |
        | 2 | 内容确认 | 每页文字内容、图表建议、图示规格 | 编辑文字、修改图表 |

        解析和分析阶段静默执行。内容确认通过后，PPT构建连续完成。

        ### Pipeline阶段

        | 阶段 | 功能 | 方式 |
        |------|------|------|
        | 输入解析 | 解析文件/文本 | 规则引擎 |
        | 数据分析 | 计算派生指标（YoY/CAGR/趋势等） | 代码计算 + LLM辅助 |
        | 大纲生成 | 金字塔原理生成页面级大纲 | LLM |
        | 内容填充 | 逐页生成文字、图表、图示 | LLM批量调用 |
        | PPT构建 | 视觉设计 + 图表 + 布局 + 输出 | 规则引擎 |

        ### 重跑机制

        编辑某个阶段后，该阶段之后的所有阶段会自动重置。
        点击"从该阶段重新执行"即可从任意阶段重跑。
        """)


if __name__ == "__main__":
    main()
