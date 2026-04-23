"""
布局骨架注册表
从templates/layouts.json加载布局定义，提供比例坐标到EMU坐标的转换
"""

import json
from pathlib import Path
from typing import Optional, Dict, List
from dataclasses import dataclass, field

from models import Rect


@dataclass
class LayoutSlot:
    """布局槽位定义（比例坐标）"""
    name: str
    x: float  # 0.0 ~ 1.0，相对于内容区域
    y: float
    w: float
    h: float
    max_chars: int = 0          # 该槽位最大字符数（0=不限）
    overflow: str = "shrink"    # 溢出策略: "shrink" | "truncate" | "split"

    def to_rect(self, content_left: int, content_top: int,
                content_width: int, content_height: int) -> Rect:
        """转换为EMU绝对坐标"""
        return Rect(
            left=int(content_left + self.x * content_width),
            top=int(content_top + self.y * content_height),
            width=int(self.w * content_width),
            height=int(self.h * content_height),
        )


@dataclass
class LayoutConstraints:
    """布局级约束"""
    max_title_chars: int = 60       # 标题最大字符数
    max_body_chars: int = 400       # 正文最大字符数（每个body slot）
    max_fill_ratio: float = 0.65    # 最大填充率
    min_fill_ratio: float = 0.10    # 最小填充率
    overflow_strategy: str = "shrink"  # 全局溢出策略


@dataclass
class LayoutSkeleton:
    """一个完整的布局骨架"""
    skeleton_id: str
    name: str
    category: str  # "core" or "extended"
    content_pattern: str
    slots: Dict[str, LayoutSlot] = field(default_factory=dict)
    constraints: LayoutConstraints = field(default_factory=LayoutConstraints)


class LayoutSkeletonRegistry:
    """
    布局骨架注册表

    从JSON文件加载布局定义，提供按ID查询和坐标转换
    """

    # 标准画布尺寸（16:9）
    CANVAS_WIDTH = 12192000   # EMU
    CANVAS_HEIGHT = 6858000   # EMU
    DEFAULT_MARGIN = 457200   # 0.5 inch

    def __init__(self, layouts_path: str = None):
        if layouts_path is None:
            layouts_path = str(Path(__file__).parent / "layouts.json")
        self._skeletons: Dict[str, LayoutSkeleton] = {}
        self._load(layouts_path)

    def _load(self, path: str):
        """从JSON文件加载布局定义"""
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        canvas = data.get("canvas", {})
        self.canvas_width = canvas.get("width_emu", self.CANVAS_WIDTH)
        self.canvas_height = canvas.get("height_emu", self.CANVAS_HEIGHT)
        self.margin = canvas.get("margin_emu", self.DEFAULT_MARGIN)

        for skeleton_id, layout_def in data.get("layouts", {}).items():
            slots = {}
            for slot_name, slot_def in layout_def.get("slots", {}).items():
                slots[slot_name] = LayoutSlot(
                    name=slot_name,
                    x=slot_def["x"],
                    y=slot_def["y"],
                    w=slot_def["w"],
                    h=slot_def["h"],
                    max_chars=slot_def.get("max_chars", 0),
                    overflow=slot_def.get("overflow", "shrink"),
                )

            # 解析约束
            constraints_data = layout_def.get("constraints", {})
            constraints = LayoutConstraints(
                max_title_chars=constraints_data.get("max_title_chars", 60),
                max_body_chars=constraints_data.get("max_body_chars", 400),
                max_fill_ratio=constraints_data.get("max_fill_ratio", 0.65),
                min_fill_ratio=constraints_data.get("min_fill_ratio", 0.10),
                overflow_strategy=constraints_data.get("overflow_strategy", "shrink"),
            )

            self._skeletons[skeleton_id] = LayoutSkeleton(
                skeleton_id=skeleton_id,
                name=layout_def.get("name", skeleton_id),
                category=layout_def.get("category", "core"),
                content_pattern=layout_def.get("content_pattern", ""),
                slots=slots,
                constraints=constraints,
            )

    def get(self, skeleton_id: str) -> Optional[LayoutSkeleton]:
        """获取布局骨架"""
        return self._skeletons.get(skeleton_id)

    def list_skeletons(self, category: str = None) -> List[LayoutSkeleton]:
        """列出所有布局骨架"""
        skeletons = list(self._skeletons.values())
        if category:
            skeletons = [s for s in skeletons if s.category == category]
        return skeletons

    def get_by_pattern(self, content_pattern: str) -> List[LayoutSkeleton]:
        """按ContentPattern查找布局骨架"""
        return [s for s in self._skeletons.values()
                if s.content_pattern == content_pattern]

    def get_content_area(self) -> tuple:
        """获取内容区域（去掉margin后的区域）"""
        m = self.margin
        return (
            m,  # left
            m,  # top
            self.canvas_width - 2 * m,  # width
            self.canvas_height - 2 * m,  # height
        )

    def resolve_slots_to_rects(
        self, skeleton_id: str
    ) -> Optional[Dict[str, Rect]]:
        """
        将布局骨架的所有槽位转换为EMU绝对坐标

        Returns:
            Dict[slot_name, Rect] 或 None
        """
        skeleton = self.get(skeleton_id)
        if not skeleton:
            return None

        cl, ct, cw, ch = self.get_content_area()
        return {
            slot_name: slot.to_rect(cl, ct, cw, ch)
            for slot_name, slot in skeleton.slots.items()
        }
