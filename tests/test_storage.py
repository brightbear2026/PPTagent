"""
单元测试：存储层
测试TaskStore、settings、api_keys、encryption
"""
import os
import unittest
import tempfile

os.environ.setdefault("MASTER_ENCRYPTION_KEY", "dGVzdC1rZXktZm9yLXZlcmlmaWNhdGlvbi1vbmx5")


class TestEncryption(unittest.TestCase):
    def test_encrypt_decrypt_roundtrip(self):
        from storage.encryption import encrypt_api_key, decrypt_api_key
        plain = "sk-test-12345"
        encrypted = encrypt_api_key(plain)
        decrypted = decrypt_api_key(encrypted)
        self.assertEqual(decrypted, plain)

    def test_different_users_isolated(self):
        from storage.encryption import encrypt_api_key, decrypt_api_key
        plain = "sk-test-key"
        enc_a = encrypt_api_key(plain, user_id="user_a")
        enc_b = encrypt_api_key(plain, user_id="user_b")
        # Same plaintext produces different ciphertext for different users
        self.assertNotEqual(enc_a, enc_b)
        # But both decrypt correctly
        self.assertEqual(decrypt_api_key(enc_a, "user_a"), plain)
        self.assertEqual(decrypt_api_key(enc_b, "user_b"), plain)

    def test_wrong_key_fails(self):
        from storage.encryption import encrypt_api_key
        encrypted = encrypt_api_key("sk-test")
        # Change master key
        os.environ["MASTER_ENCRYPTION_KEY"] = "YW5vdGhlci1rZXktdGhhdC1pcy1kaWZmZXJlbnQ="
        try:
            from storage.encryption import decrypt_api_key
            with self.assertRaises(ValueError):
                decrypt_api_key(encrypted)
        finally:
            os.environ["MASTER_ENCRYPTION_KEY"] = "dGVzdC1rZXktZm9yLXZlcmlmaWNhdGlvbi1vbmx5"


class TestTaskStore(unittest.TestCase):
    def setUp(self):
        self.tmpfile = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.tmpfile.close()
        from storage import TaskStore
        self.store = TaskStore(self.tmpfile.name)

    def tearDown(self):
        os.unlink(self.tmpfile.name)

    def test_create_and_get_task(self):
        task = self.store.create_task("test-1", title="Test", content="Hello")
        self.assertIsNotNone(task)
        self.assertEqual(task["title"], "Test")

    def test_update_task(self):
        self.store.create_task("test-2", title="Old")
        self.store.update_task("test-2", title="New")
        task = self.store.get_task("test-2")
        self.assertEqual(task["title"], "New")

    def test_delete_task(self):
        self.store.create_task("test-3")
        self.assertTrue(self.store.delete_task("test-3"))
        self.assertIsNone(self.store.get_task("test-3"))

    # Settings
    def test_settings_crud(self):
        self.store.save_setting("default", "key1", "value1")
        val = self.store.get_setting("default", "key1")
        self.assertEqual(val, "value1")

        all_settings = self.store.get_all_settings("default")
        self.assertIn("key1", all_settings)

    def test_settings_overwrite(self):
        self.store.save_setting("default", "key1", "v1")
        self.store.save_setting("default", "key1", "v2")
        self.assertEqual(self.store.get_setting("default", "key1"), "v2")

    # API Keys
    def test_api_keys_crud(self):
        self.store.save_api_key("default", "zhipu", "encrypted_key_123")
        key = self.store.get_api_key("default", "zhipu")
        self.assertEqual(key, "encrypted_key_123")

        keys = self.store.get_all_api_keys("default")
        self.assertEqual(len(keys), 1)

        self.store.delete_api_key("default", "zhipu")
        self.assertIsNone(self.store.get_api_key("default", "zhipu"))

    # Pipeline stages
    def test_stages_lifecycle(self):
        self.store.create_task("test-4")
        stages = self.store.get_stages("test-4")
        self.assertEqual(len(stages), 7)
        self.assertEqual(stages[0]["status"], "pending")

        self.store.save_stage_result("test-4", "layer1", {"text_length": 100})
        stage = self.store.get_stage("test-4", "layer1")
        self.assertEqual(stage["status"], "completed")
        self.assertEqual(stage["result"]["text_length"], 100)

    def test_reset_stages_from(self):
        self.store.create_task("test-5")
        self.store.save_stage_result("test-5", "layer1", {})
        self.store.save_stage_result("test-5", "layer2_extract", {})

        self.store.reset_stages_from("test-5", "layer2_extract")
        s1 = self.store.get_stage("test-5", "layer1")
        s2 = self.store.get_stage("test-5", "layer2_extract")
        self.assertEqual(s1["status"], "completed")
        self.assertEqual(s2["status"], "pending")


if __name__ == "__main__":
    unittest.main()
