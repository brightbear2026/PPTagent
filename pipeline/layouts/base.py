"""LayoutModule Protocol — contract for typed, system-assembled HTML layouts."""
from dataclasses import dataclass
from typing import Protocol, runtime_checkable


@dataclass
class Capacity:
    max_text_chars: int = 300
    max_bullet_count: int = 3


@runtime_checkable
class LayoutModule(Protocol):
    name: str
    content_schema: type
    capacity: Capacity

    def build_html(
        self,
        content,
        theme_colors: dict[str, str],
        page_number: int = 1,
        total_slides: int = 1,
    ) -> str: ...

    def from_slide_data(self, slide_data: dict) -> object: ...

    def prompt_fragment(self) -> str: ...
