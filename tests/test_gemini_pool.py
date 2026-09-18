import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
import gemini_pool as gp


class Clock:
    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now

    def sleep(self, seconds):
        self.now += seconds


class GeminiPoolTests(unittest.TestCase):
    def make_pool(self, extra=None):
        env = {
            'GEMINI_API_KEY_FREE_1': 'free-one-secret',
            'GEMINI_API_KEY_PAID': 'paid-secret',
            'GEMINI_MODEL': 'model-a',
            'GEMINI_FALLBACK_MODELS': 'model-b',
            'GEMINI_FREE_MIN_INTERVAL': '0',
            'GEMINI_PAID_MIN_INTERVAL': '0',
            'GEMINI_MAX_ATTEMPTS': '3',
            'GEMINI_BACKOFF_BASE': '1',
            'GEMINI_BACKOFF_MAX': '4',
        }
        env.update(extra or {})
        self.clock = Clock()
        return gp.GeminiPool(
            env=env, clock=self.clock, sleeper=self.clock.sleep,
            client_factory=lambda api_key: api_key)

    def test_models_come_only_from_configuration(self):
        self.assertEqual(
            gp._models_tu_env({'GEMINI_MODEL': 'one', 'GEMINI_FALLBACK_MODELS': 'two, one ,three'}),
            ['one', 'two', 'three'])
        with self.assertRaisesRegex(RuntimeError, 'GEMINI_MODEL'):
            gp._models_tu_env({})

    def test_503_on_free_never_falls_through_to_paid(self):
        pool = self.make_pool()
        calls = []

        def work(key, model):
            calls.append(key)
            if key == 'free-one-secret':
                raise RuntimeError('503 UNAVAILABLE: high demand')
            return 'unexpected'

        self.assertIsNone(pool.chay(work, 'test'))
        self.assertNotIn('paid-secret', calls)
        self.assertEqual(calls, ['free-one-secret'] * 3)
        self.assertEqual(self.clock.now, 3.0)

    def test_model_404_moves_to_configured_fallback(self):
        pool = self.make_pool()
        calls = []

        def work(key, model):
            calls.append((key, model))
            if model == 'model-a':
                raise RuntimeError('404 NOT_FOUND: model is unavailable')
            return 'OK'

        self.assertEqual(pool.chay(work, 'test'), 'OK')
        self.assertIn('model-a', pool.model_hong)
        self.assertEqual(calls[-1], ('free-one-secret', 'model-b'))

    def test_file_404_does_not_disable_model(self):
        pool = self.make_pool()
        self.assertEqual(
            pool.chay(
                lambda key, model: 'OK' if key == 'paid-secret'
                else (_ for _ in ()).throw(RuntimeError('404 file not found')),
                'test'),
            'OK')
        self.assertEqual(pool.model_hong, set())

    def test_redact_error_removes_secret(self):
        secret = 'do-not-log-me'
        message = gp.redact_error(f'https://example.test/?key={secret} {secret}', [secret])
        self.assertNotIn(secret, message)
        self.assertIn('[REDACTED]', message)


if __name__ == '__main__':
    unittest.main()
