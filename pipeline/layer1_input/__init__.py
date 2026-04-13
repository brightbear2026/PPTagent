"""
Layer 1: 输入解析层
解析多种输入格式为统一的RawContent对象
"""

from .input_router import InputRouter

__all__ = ["InputRouter"]
