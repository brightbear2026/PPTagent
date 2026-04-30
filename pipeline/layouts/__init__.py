"""LayoutTemplate Registry — typed, system-assembled HTML layouts.

Each registered layout bypasses LLM HTML generation entirely: ContentAgent fills
a pydantic schema, and the layout module assembles HTML deterministically.

To add a new layout:
  1. Create pipeline/layouts/<name>.py implementing LayoutModule protocol
  2. Import and register it below
  3. Add the layout_hint value to ContentAgent._TEMPLATE_CONTENT_GUIDE
"""
from pipeline.layouts.base import Capacity, LayoutModule
from pipeline.layouts.call_to_action import CallToActionLayout, CTAContent


class LayoutRegistry:
    _modules: dict[str, LayoutModule] = {}

    @classmethod
    def register(cls, module: LayoutModule) -> None:
        cls._modules[module.name] = module

    @classmethod
    def get(cls, name: str) -> LayoutModule:
        return cls._modules[name]

    @classmethod
    def names(cls) -> set[str]:
        return set(cls._modules.keys())


LayoutRegistry.register(CallToActionLayout())
