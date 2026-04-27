"""
Tech Stack Matrix Diagram Skill

技术选型矩阵：表格布局，选中项高亮。
python-pptx 用表格形状渲染。
"""

from pptx.util import Pt, Emu, Inches
from pptx.enum.text import PP_ALIGN
from pptx.dml.color import RGBColor

from models import DiagramSpec, Rect, VisualTheme
from pipeline.skills.base import RenderingSkill, SkillDescriptor
from pipeline.skills._utils import theme_color


class TechStackMatrixSkill(RenderingSkill):

    def descriptor(self) -> SkillDescriptor:
        return SkillDescriptor(
            skill_id="diagram_tech_stack_matrix",
            skill_type="diagram",
            handles_types=["tech_stack_matrix"],
        )

    def prompt_fragment(self) -> str:
        return """**tech_stack_matrix**（技术选型矩阵图）:
  约束: 3-6个类别（categories），每类2-4个options，每个option必须标明 selected: true/false
  反模式: 不要用于单一技术栈展示（用tech_architecture）；不要用于对比分析（用framework的matrix_2x2）"""

    def design_tokens(self) -> dict:
        return {
            "header_font_size": 10,
            "cell_font_size": 9,
            "selected_marker": "■",
            "unselected_marker": "□",
        }

    def render(self, slide, data: DiagramSpec, rect, theme: VisualTheme) -> bool:
        nodes = data.nodes
        if not nodes:
            return False

        tokens = self.design_tokens()
        primary = theme_color(theme, "primary", "#003D6E")
        accent = theme_color(theme, "accent", "#FF6B35")
        white = RGBColor(255, 255, 255)
        muted = RGBColor(0x99, 0x99, 0x99)
        font = theme.fonts.get("body", "Calibri")

        # 用 nodes 构建 categories × options 矩阵
        # 每个 node = 一行（category），node.label = category名，node.sublabel = options (逗号分隔)
        # 第一个 node 的 items 也用于确定列数
        n_categories = min(len(nodes), 6)

        # 尝试从 items 提取选项
        all_options = []
        categories = []
        for node in nodes[:n_categories]:
            cat_name = node.label
            items_text = node.sublabel or ""
            # items 可以是 "React ■, Vue □" 格式，或纯文本
            options = [o.strip() for o in items_text.split(",") if o.strip()]
            if not options:
                options = [cat_name]
            categories.append({"name": cat_name, "options": options})
            if len(options) > len(all_options):
                all_options = options

        n_cols = len(all_options) + 1  # +1 for category name column
        n_rows = n_categories + 1  # +1 for header

        # 创建表格
        table_shape = slide.shapes.add_table(
            n_rows, n_cols,
            Emu(rect.left), Emu(rect.top),
            Emu(rect.width), Emu(rect.height),
        )
        table = table_shape.table

        # 设置列宽
        cat_col_w = int(rect.width * 0.25)
        opt_col_w = (rect.width - cat_col_w) // max(n_cols - 1, 1)
        table.columns[0].width = Emu(cat_col_w)
        for ci in range(1, n_cols):
            table.columns[ci].width = Emu(opt_col_w)

        # 表头行
        header_cell = table.cell(0, 0)
        header_cell.text = "类别"
        self._style_cell(header_cell, font, tokens["header_font_size"],
                         primary, white, bold=True)
        for ci, opt_name in enumerate(all_options):
            cell = table.cell(0, ci + 1)
            cell.text = opt_name
            self._style_cell(cell, font, tokens["header_font_size"],
                             primary, white, bold=True)

        # 数据行
        for ri, cat in enumerate(categories):
            # 类别名
            cat_cell = table.cell(ri + 1, 0)
            cat_cell.text = cat["name"]
            self._style_cell(cat_cell, font, tokens["cell_font_size"],
                             RGBColor(0xF0, 0xF0, 0xF0), primary, bold=True)

            # 选项列
            for ci, opt in enumerate(all_options):
                cell = table.cell(ri + 1, ci + 1)
                # 判断该选项是否属于该 category
                is_selected = any(
                    opt.lower() in co.lower() or co.lower() in opt.lower()
                    for co in cat["options"]
                )
                if is_selected:
                    cell.text = f'{tokens["selected_marker"]} {opt}'
                    self._style_cell(cell, font, tokens["cell_font_size"],
                                     primary, white, bold=True)
                else:
                    cell.text = f'{tokens["unselected_marker"]}'
                    self._style_cell(cell, font, tokens["cell_font_size"],
                                     white, muted)

        return True

    @staticmethod
    def _style_cell(cell, font_name, font_size, bg_color, text_color, bold=False):
        cell.fill.solid()
        cell.fill.fore_color.rgb = bg_color
        for paragraph in cell.text_frame.paragraphs:
            paragraph.font.size = Pt(font_size)
            paragraph.font.color.rgb = text_color
            paragraph.font.bold = bold
            paragraph.font.name = font_name
            paragraph.alignment = PP_ALIGN.CENTER
