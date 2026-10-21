import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from browser_runtime import browser_config


class BrowserRuntimeTests(unittest.TestCase):
    def test_bundled_then_edge_then_chrome_and_missing(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            chromium = SimpleNamespace(executable_path=str(root / 'chromium.exe'))
            with patch.dict('os.environ', {'PROGRAMFILES(X86)': directory,
                                          'PROGRAMFILES': directory, 'LOCALAPPDATA': directory}):
                with self.assertRaises(RuntimeError):
                    browser_config(chromium)
                chrome = root / 'Google/Chrome/Application/chrome.exe'
                chrome.parent.mkdir(parents=True)
                chrome.touch()
                self.assertEqual(browser_config(chromium)[1], {'channel': 'chrome'})
                edge = root / 'Microsoft/Edge/Application/msedge.exe'
                edge.parent.mkdir(parents=True)
                edge.touch()
                self.assertEqual(browser_config(chromium)[1], {'channel': 'msedge'})
                Path(chromium.executable_path).touch()
                self.assertEqual(browser_config(chromium), ('Chromium', {}, 'browser'))


if __name__ == '__main__':
    unittest.main()
