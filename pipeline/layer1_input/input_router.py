"""
Layer 1 主入口：输入路由器
根据输入类型自动路由到对应的解析器
"""

from pathlib import Path
from models import RawContent


# 支持的文件格式映射
EXTENSION_MAP = {
    ".txt": "text",
    ".md": "markdown",
    ".docx": "doc",
    ".xlsx": "excel",
    ".csv": "excel",
    ".pptx": "ppt",
}


class InputRouter:
    """
    Layer 1 主类：输入路由器

    根据输入格式自动选择解析器，输出统一的RawContent对象
    """

    def __init__(self):
        self._parsers = {}

    def parse(self,
              text: str = None,
              file_path: str = None,
              source_type: str = None) -> RawContent:
        """
        解析输入并返回RawContent

        两种模式：
        1. 纯文本模式：传入text参数
        2. 文件模式：传入file_path，自动检测格式

        Args:
            text: 纯文本内容
            file_path: 文件路径
            source_type: 覆盖自动检测的类型

        Returns:
            RawContent对象

        Raises:
            ValueError: 未提供输入或格式不支持
            FileNotFoundError: 文件不存在
        """
        if file_path:
            return self.parse_file(file_path, source_type)
        elif text is not None:
            return self.parse_text(text)
        else:
            raise ValueError("请提供文本内容或上传文件")

    def parse_text(self, text: str) -> RawContent:
        """解析纯文本"""
        from .text_parser import TextParser
        parser = self._get_parser("text", TextParser)
        return parser.parse(text)

    def parse_file(self, file_path: str, source_type: str = None) -> RawContent:
        """
        解析文件

        Args:
            file_path: 文件路径
            source_type: 覆盖自动检测的类型
        """
        path = Path(file_path)

        # 确定source_type（先检查格式，再检查文件存在）
        if not source_type:
            source_type = self._detect_source_type(path)

        if not path.exists():
            raise FileNotFoundError(f"文件不存在: {file_path}")

        # 路由到对应的解析器
        if source_type == "text":
            with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
                text = f.read()
            return self.parse_text(text)

        elif source_type == "doc":
            from .docx_parser import DocxParser
            parser = self._get_parser("doc", DocxParser)
            return parser.parse(str(path))

        elif source_type == "excel":
            from .excel_parser import ExcelParser
            parser = self._get_parser("excel", ExcelParser)
            return parser.parse(str(path))

        elif source_type == "ppt":
            from .pptx_parser import PptxParser
            parser = self._get_parser("ppt", PptxParser)
            return parser.parse(str(path))

        elif source_type == "markdown":
            from .markdown_parser import MarkdownParser
            parser = self._get_parser("markdown", MarkdownParser)
            return parser.parse(str(path))

        else:
            raise ValueError(
                f"不支持的文件格式。"
                f"支持: .docx, .xlsx, .csv, .pptx, .txt, .md"
            )

    def _detect_source_type(self, path: Path) -> str:
        """根据文件扩展名检测类型"""
        ext = path.suffix.lower()
        source_type = EXTENSION_MAP.get(ext)
        if not source_type:
            supported = ", ".join(EXTENSION_MAP.keys())
            raise ValueError(
                f"不支持的文件格式 '{ext}'。支持的格式: {supported}"
            )
        return source_type

    def _get_parser(self, name: str, parser_class):
        """获取或创建解析器实例（懒加载+缓存）"""
        if name not in self._parsers:
            self._parsers[name] = parser_class()
        return self._parsers[name]
