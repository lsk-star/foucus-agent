import unittest

from pybase.modules.schema_provider.router import router


class SchemaProviderModuleTests(unittest.TestCase):
    def test_router_metadata(self) -> None:
        self.assertEqual(router.prefix, "/schema_provider")
        self.assertIn("schema_provider", router.tags)
