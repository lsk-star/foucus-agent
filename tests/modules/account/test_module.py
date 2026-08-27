import unittest

from pybase.modules.account.router import router


class AccountModuleTests(unittest.TestCase):
    def test_router_metadata(self) -> None:
        self.assertEqual(router.prefix, "/account")
        self.assertIn("account", router.tags)
