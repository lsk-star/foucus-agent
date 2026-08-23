import unittest

from pybase.modules.agent.router import router


class AgentModuleTests(unittest.TestCase):
    def test_router_metadata(self) -> None:
        self.assertEqual(router.prefix, "/agent")
        self.assertIn("agent", router.tags)
