import unittest

from pybase.modules.skills.router import router


class SkillsModuleTests(unittest.TestCase):
    def test_router_metadata(self) -> None:
        self.assertEqual(router.prefix, "/skills")
        self.assertIn("skills", router.tags)
