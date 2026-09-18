import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
import check_api


class FakeClient:
    def __init__(self, api_key):
        self.api_key = api_key
        self.models = self

    def list(self):
        return [
            SimpleNamespace(name='models/gemini-ok', supported_actions=['generateContent']),
            SimpleNamespace(name='models/not-for-generation', supported_actions=['embedContent']),
        ]


class CheckApiTests(unittest.TestCase):
    def test_list_only_is_safe_and_filters_generate_content(self):
        output = []
        secret = 'never-print-this'
        code = check_api.check(
            env={'GEMINI_API_KEY_FREE_1': secret},
            emit=output.append,
            client_factory=FakeClient)
        text = '\n'.join(output)
        self.assertEqual(code, 0)
        self.assertIn('gemini-ok', text)
        self.assertNotIn('not-for-generation', text)
        self.assertNotIn(secret, text)


if __name__ == '__main__':
    unittest.main()
