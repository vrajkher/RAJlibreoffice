import importlib.util
from pathlib import Path
import tempfile
import unittest

from raj_libreoffice.config import Config


@unittest.skipUnless(importlib.util.find_spec("openai_mcp_extensions"), "requires OpenAI optional dependencies")
class OpenAIExtensionTests(unittest.IsolatedAsyncioTestCase):
    async def test_real_extension_registration_and_resources(self):
        from raj_libreoffice.server import create_server
        with tempfile.TemporaryDirectory() as directory:
            server, bridge = create_server(Config(Path(directory)), openai=True)
            try:
                tools = await server.list_tools()
                names = {t.name for t in tools}
                self.assertIn("settings.read", names)
                self.assertIn("settings.update", names)
                self.assertIn("document_save_preferred", names)
                self.assertIn("document_create", names)
                self.assertNotIn("python_run", names)
                self.assertGreaterEqual(len(await server.list_resources()), 3)
            finally:
                bridge.close()


if __name__ == "__main__":
    unittest.main()

