import tempfile
import unittest
from pathlib import Path

try:
    from fastapi.testclient import TestClient
    from exam_extractor.api import create_app
except (ImportError, RuntimeError):
    TestClient = None
    create_app = None


@unittest.skipIf(TestClient is None, "install the web extra to run API tests")
class Phase5Tests(unittest.TestCase):
    def test_health_and_provider_endpoints(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            with TestClient(create_app(Path(directory))) as client:
                self.assertEqual(client.get("/health/live").json()["status"], "ok")
                providers = client.get("/api/providers").json()
                self.assertIn("openai_compatible", providers["llm"])
                self.assertIn("faster_whisper", providers["speech"])

    def test_request_validation_and_job_creation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            with TestClient(create_app(Path(directory))) as client:
                self.assertEqual(client.post("/api/jobs", json={"source": "missing.mp4"}).status_code, 202)
                self.assertEqual(client.post("/api/jobs", json={"source": ""}).status_code, 422)


if __name__ == "__main__":
    unittest.main()
