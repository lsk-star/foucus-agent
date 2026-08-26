import unittest

from pybase.modules.sql_processing.router import router


class SchemaProviderModuleTests(unittest.TestCase):
    def test_router_metadata(self) -> None:
        self.assertEqual(router.prefix, "/sql_processing")
        self.assertIn("sql_processing", router.tags)
