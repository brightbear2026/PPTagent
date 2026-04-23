"""
单元测试：存储层
测试TaskStore、settings、api_keys、encryption

TaskStore tests require a live PostgreSQL instance (DATABASE_URL env var)
and the alembic package. They are skipped automatically when neither is
available so the suite can still pass in a plain dev environment.
"""
import os
import unittest

os.environ.setdefault("MASTER_ENCRYPTION_KEY", "dGVzdC1rZXktZm9yLXZlcmlmaWNhdGlvbi1vbmx5")

# ---------------------------------------------------------------------------
# Availability check — skip the DB tests when deps / server are missing
# ---------------------------------------------------------------------------

def _db_available() -> bool:
    try:
        import alembic  # noqa: F401
        import psycopg2
        url = os.environ.get(
            "DATABASE_URL",
            "postgresql://pptagent:pptagent_local@localhost:5432/pptagent",
        )
        conn = psycopg2.connect(url, connect_timeout=2)
        conn.close()
        return True
    except Exception:
        return False


DB_AVAILABLE = _db_available()


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
        self.assertNotEqual(enc_a, enc_b)
        self.assertEqual(decrypt_api_key(enc_a, "user_a"), plain)
        self.assertEqual(decrypt_api_key(enc_b, "user_b"), plain)

    def test_wrong_key_fails(self):
        from storage.encryption import encrypt_api_key
        encrypted = encrypt_api_key("sk-test")
        os.environ["MASTER_ENCRYPTION_KEY"] = "YW5vdGhlci1rZXktdGhhdC1pcy1kaWZmZXJlbnQ="
        try:
            from storage.encryption import decrypt_api_key
            with self.assertRaises(ValueError):
                decrypt_api_key(encrypted)
        finally:
            os.environ["MASTER_ENCRYPTION_KEY"] = "dGVzdC1rZXktZm9yLXZlcmlmaWNhdGlvbi1vbmx5"


@unittest.skipUnless(DB_AVAILABLE, "requires PostgreSQL + alembic (run in Docker)")
class TestTaskStore(unittest.TestCase):
    def setUp(self):
        from storage import TaskStore
        self.store = TaskStore()

    def test_create_and_get_task(self):
        tid = "pytest-task-1"
        task = self.store.create_task(tid, title="Test", content="Hello")
        self.assertIsNotNone(task)
        self.assertEqual(task["title"], "Test")
        self.store.delete_task(tid)

    def test_update_task(self):
        tid = "pytest-task-2"
        self.store.create_task(tid, title="Old")
        self.store.update_task(tid, title="New")
        task = self.store.get_task(tid)
        self.assertEqual(task["title"], "New")
        self.store.delete_task(tid)

    def test_delete_task(self):
        tid = "pytest-task-3"
        self.store.create_task(tid)
        self.assertTrue(self.store.delete_task(tid))
        self.assertIsNone(self.store.get_task(tid))

    def test_settings_crud(self):
        self.store.save_setting("default", "test_key1", "value1")
        val = self.store.get_setting("default", "test_key1")
        self.assertEqual(val, "value1")
        all_settings = self.store.get_all_settings("default")
        self.assertIn("test_key1", all_settings)

    def test_settings_overwrite(self):
        self.store.save_setting("default", "test_key2", "v1")
        self.store.save_setting("default", "test_key2", "v2")
        self.assertEqual(self.store.get_setting("default", "test_key2"), "v2")

    def test_api_keys_crud(self):
        self.store.save_api_key("default", "test_provider", "encrypted_key_123")
        key = self.store.get_api_key("default", "test_provider")
        self.assertEqual(key, "encrypted_key_123")
        keys = self.store.get_all_api_keys("default")
        self.assertGreaterEqual(len(keys), 1)
        self.store.delete_api_key("default", "test_provider")
        self.assertIsNone(self.store.get_api_key("default", "test_provider"))

    def test_stages_lifecycle(self):
        from storage.task_store import PIPELINE_STAGES
        tid = "pytest-task-4"
        self.store.create_task(tid)
        stages = self.store.get_stages(tid)
        self.assertEqual(len(stages), len(PIPELINE_STAGES))
        self.assertEqual(stages[0]["status"], "pending")

        first_stage = PIPELINE_STAGES[0]
        self.store.save_stage_result(tid, first_stage, {"text_length": 100})
        stage = self.store.get_stage(tid, first_stage)
        self.assertEqual(stage["status"], "completed")
        self.assertEqual(stage["result"]["text_length"], 100)
        self.store.delete_task(tid)

    def test_reset_stages_from(self):
        from storage.task_store import PIPELINE_STAGES
        tid = "pytest-task-5"
        self.store.create_task(tid)
        s0, s1 = PIPELINE_STAGES[0], PIPELINE_STAGES[1]
        self.store.save_stage_result(tid, s0, {})
        self.store.save_stage_result(tid, s1, {})
        self.store.reset_stages_from(tid, s1)
        self.assertEqual(self.store.get_stage(tid, s0)["status"], "completed")
        self.assertEqual(self.store.get_stage(tid, s1)["status"], "pending")
        self.store.delete_task(tid)


if __name__ == "__main__":
    unittest.main()
