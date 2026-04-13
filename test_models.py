"""
测试数据模型导入
"""
from models import SlideSpec, PresentationSpec, SlideType, NarrativeRole

def test_import():
    """测试能否正确导入核心模型"""
    print("✅ SlideSpec:", SlideSpec)
    print("✅ PresentationSpec:", PresentationSpec)
    print("✅ SlideType:", SlideType)
    print("✅ NarrativeRole:", NarrativeRole)

    # 创建一个简单的SlideSpec测试
    slide = SlideSpec(
        slide_type=SlideType.CONTENT,
        takeaway_message="这是一个测试页面",
        narrative_arc=NarrativeRole.EVIDENCE
    )
    print("✅ 创建SlideSpec成功:", slide.slide_id)
    print("\n所有数据模型导入正常！")

if __name__ == "__main__":
    test_import()
