"""
单元测试：数据模型
测试StageModelConfig、PipelineModelConfig
"""
import unittest

from models.model_config import StageModelConfig, PipelineModelConfig, STAGE_DEFAULTS


class TestStageModelConfig(unittest.TestCase):
    def test_valid_config(self):
        c = StageModelConfig(provider="zhipu", model="glm-4-plus", api_key="test-key")
        self.assertEqual(c.provider, "zhipu")
        self.assertEqual(c.model, "glm-4-plus")
        self.assertEqual(c.temperature, 0.7)
        self.assertEqual(c.max_tokens, 4096)

    def test_custom_params(self):
        c = StageModelConfig(
            provider="deepseek", model="deepseek-r1",
            temperature=0.3, max_tokens=8192,
            base_url="https://api.deepseek.com/v1"
        )
        self.assertEqual(c.temperature, 0.3)
        self.assertEqual(c.max_tokens, 8192)
        self.assertEqual(c.base_url, "https://api.deepseek.com/v1")

    def test_invalid_temperature(self):
        with self.assertRaises(Exception):
            StageModelConfig(provider="zhipu", model="glm-4-plus", temperature=3.0)

    def test_defaults(self):
        self.assertIn("analyze", STAGE_DEFAULTS)
        self.assertEqual(STAGE_DEFAULTS["analyze"].provider, "zhipu")
        self.assertIn("outline", STAGE_DEFAULTS)
        self.assertEqual(STAGE_DEFAULTS["outline"].provider, "deepseek")
        self.assertIn("content", STAGE_DEFAULTS)
        self.assertIn("design", STAGE_DEFAULTS)


class TestPipelineModelConfig(unittest.TestCase):
    def test_default_config(self):
        c = PipelineModelConfig()
        self.assertEqual(c.analyze.provider, "zhipu")
        self.assertEqual(c.outline.provider, "deepseek")
        self.assertEqual(c.content.provider, "deepseek")
        self.assertEqual(c.design.provider, "tongyi")

    def test_get_stage_config(self):
        c = PipelineModelConfig()
        sc = c.get_stage_config("analyze")
        self.assertEqual(sc.provider, "zhipu")
        sc2 = c.get_stage_config("outline")
        self.assertEqual(sc2.provider, "deepseek")

    def test_get_unknown_stage_raises(self):
        c = PipelineModelConfig()
        with self.assertRaises(ValueError):
            c.get_stage_config("nonexistent")

    def test_set_stage_config(self):
        c = PipelineModelConfig()
        new_config = StageModelConfig(provider="moonshot", model="moonshot-v1-8k", api_key="test")
        c.set_stage_config("analyze", new_config)
        self.assertEqual(c.analyze.provider, "moonshot")

    def test_mask_api_keys(self):
        c = PipelineModelConfig()
        c.analyze.api_key = "sk-1234567890abcdef"
        masked = c.mask_api_keys()
        self.assertIn("****", masked.analyze.api_key)
        self.assertNotEqual(masked.analyze.api_key, c.analyze.api_key)

    def test_serialization(self):
        c = PipelineModelConfig()
        json_str = c.model_dump_json()
        c2 = PipelineModelConfig.model_validate_json(json_str)
        self.assertEqual(c2.analyze.provider, c.analyze.provider)
        self.assertEqual(c2.design.provider, c.design.provider)


if __name__ == "__main__":
    unittest.main()
