from pathlib import Path
import unittest

import i18n

ROOT = Path(__file__).resolve().parents[1]
UI_FILE = ROOT / "windows_app.py"
SOURCE = "① Choose folder  →  ② Run audit  →  ③ Review flagged items  →  ④ Save report"
ENGLISH = "① Choose folder  →  ② Run audit  →  ③ Review flagged items  →  ④ Save report"
JAPANESE = "① フォルダを選択  →  ② 監査を実行  →  ③ 要確認項目を見る  →  ④ レポートを保存"


class I18nUiContractTests(unittest.TestCase):
    def tearDown(self):
        i18n.set_language("en")

    def test_guide_switches_both_languages(self):
        i18n.set_language("en")
        self.assertEqual(i18n.translate(SOURCE), ENGLISH)
        i18n.set_language("ja")
        self.assertEqual(i18n.translate(SOURCE), JAPANESE)

    def test_ui_installs_visible_language_switch(self):
        ui = UI_FILE.read_text(encoding="utf-8")
        helper = (ROOT / "i18n.py").read_text(encoding="utf-8")
        self.assertIn("install_bilingual_ui", ui)
        self.assertIn("Language / 言語", helper)


if __name__ == "__main__":
    unittest.main()
