"""
单元测试：LLM客户端层
测试LLMClient基类、LLMResponse、LLMError、GLMClient、OpenAICompatClient
"""
import unittest
from unittest.mock import patch, MagicMock

from llm_client.base import LLMClient, LLMResponse, LLMError


class TestLLMResponse(unittest.TestCase):
    def test_success_response(self):
        r = LLMResponse(content="hello", usage={"total_tokens": 10}, model="test")
        self.assertTrue(r.success)
        self.assertEqual(r.content, "hello")
        self.assertEqual(r.total_tokens, 10)
        self.assertIsNone(r.error)

    def test_error_response(self):
        r = LLMResponse(content="", usage={}, model="test", success=False, error="timeout")
        self.assertFalse(r.success)
        self.assertEqual(r.error, "timeout")
        self.assertEqual(r.total_tokens, 0)


class TestLLMError(unittest.TestCase):
    def test_error_properties(self):
        e = LLMError("test error", provider="zhipu", model="glm-4-plus", retryable=True)
        self.assertEqual(str(e), "test error")
        self.assertEqual(e.provider, "zhipu")
        self.assertTrue(e.retryable)


class TestGLMClient(unittest.TestCase):
    def test_init_with_api_key(self):
        from llm_client import GLMClient
        client = GLMClient(api_key="test-key", model="glm-4-plus")
        self.assertEqual(client.api_key, "test-key")
        self.assertEqual(client.model, "glm-4-plus")
        self.assertEqual(client.max_retries, 5)

    def test_init_no_key_raises(self):
        from llm_client import GLMClient
        with self.assertRaises(ValueError):
            GLMClient(api_key=None, model="glm-4-plus")

    def test_is_llm_client_subclass(self):
        from llm_client import GLMClient
        self.assertTrue(issubclass(GLMClient, LLMClient))

    def test_estimate_tokens(self):
        text = "这是一段测试文本"
        tokens = LLMClient.estimate_tokens(text)
        self.assertGreater(tokens, 0)


class TestOpenAICompatClient(unittest.TestCase):
    def test_init_deepseek(self):
        from llm_client import OpenAICompatClient
        client = OpenAICompatClient(api_key="test-key", provider="deepseek")
        self.assertEqual(client.model, "deepseek-r1")
        self.assertIn("deepseek", client.base_url)

    def test_init_tongyi(self):
        from llm_client import OpenAICompatClient
        client = OpenAICompatClient(api_key="test-key", provider="tongyi")
        self.assertEqual(client.model, "qwen-max")
        self.assertIn("dashscope", client.base_url)

    def test_init_custom_model(self):
        from llm_client import OpenAICompatClient
        client = OpenAICompatClient(api_key="test-key", model="custom-model", base_url="http://localhost:8080/v1")
        self.assertEqual(client.model, "custom-model")
        self.assertEqual(client.base_url, "http://localhost:8080/v1")


class TestFactory(unittest.TestCase):
    def test_get_client_zhipu(self):
        from llm_client.factory import get_client
        from llm_client.zhipu import ZhipuClient
        c = get_client("zhipu", api_key="test")
        self.assertIsInstance(c, ZhipuClient)

    def test_get_client_deepseek(self):
        from llm_client.factory import get_client
        from llm_client.openai_compat import OpenAICompatClient
        c = get_client("deepseek", api_key="test")
        self.assertIsInstance(c, OpenAICompatClient)

    def test_get_client_unknown_raises(self):
        from llm_client.factory import get_client
        with self.assertRaises(ValueError):
            get_client("nonexistent_provider", api_key="test")

    def test_get_client_for_stage(self):
        from llm_client.factory import get_client_for_stage
        c = get_client_for_stage("layer2_extract", api_key="test")
        self.assertIsNotNone(c)


if __name__ == "__main__":
    unittest.main()
