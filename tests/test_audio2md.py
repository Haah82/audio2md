import json
import os
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from types import SimpleNamespace as NS
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
import gemini_pool as gp
import media_io
import refine
import storage
from pipeline import Job, Pipeline


RAW = '> **Reference:** https://example.org/media\n\nChúng tôi thử cách X trên một mẫu nhỏ. Chưa có số đo hiệu quả.\n'
OLD = '''# Tiêu đề Việt giữ nguyên

## 1. Tóm tắt 3 câu
Tóm tắt gốc. Câu hai. Câu ba.

## 2. Bài học cốt lõi
- Bài học gốc không được mất.

## 3. Trích dẫn hay nhất
> Chưa có số đo hiệu quả.

---

# English title retained

## 1. 3-Sentence Summary
Original summary. Sentence two. Sentence three.

## 2. Core Lessons
- Original lesson must remain.

## 3. Best Quotes
> Chưa có số đo hiệu quả.

---
**Reference:** https://example.org/media
'''
PATCH = {'vi': {'results': 'Chưa có kết quả đo lường. [S0001]',
                'insight': 'Thiếu dữ liệu đo. [S0001]\nGóc nhìn chuyên sâu: Đề xuất đo trước/sau trên mẫu nhỏ.'},
         'en': {'results': 'No measured outcomes. [S0001]',
                'insight': 'Missing measurements. [S0001]\nIn-depth perspective: Expert proposal: a small before/after test.'}}


def generated():
    return {lang: {'title': 'Tiêu đề' if lang == 'vi' else 'Title',
                   'summary': 'Câu một. Câu hai. Câu ba.', 'lessons': data['results'],
                   'insight': data['insight'],
                   'quotes': [{'id': 'S0001', 'text': 'Chưa có số đo hiệu quả.'}]}
            for lang, data in PATCH.items()}


def response(text='OK', total=12, finish='STOP'):
    return NS(text=text, candidates=[NS(finish_reason=NS(name=finish))],
              usage_metadata=NS(prompt_token_count=5, candidates_token_count=7,
                                thoughts_token_count=0, total_token_count=total))


class APIError(Exception):
    def __init__(self, code, text=''):
        super().__init__(text)
        self.code = code


class Clock:
    def __init__(self):
        self.now = 0
    def __call__(self):
        return self.now
    def sleep(self, seconds):
        self.now += seconds


class PoolTests(unittest.TestCase):
    def make_pool(self, extra=None, **kw):
        self.clock = Clock()
        env = {'GEMINI_API_KEY_FREE_1': 'fake-free', 'GEMINI_API_KEY_PAID': 'fake-paid',
               'GEMINI_MODEL': 'model-a', 'GEMINI_FREE_MIN_INTERVAL': '0',
               'GEMINI_PAID_MIN_INTERVAL': '0'}
        env.update(extra or {})
        return gp.GeminiPool(env=env, clock=self.clock, sleeper=self.clock.sleep,
                             client_factory=lambda k: k.name, emit=lambda _: None,
                             allow_paid=True, paid_token_limit=100000, **kw)

    def test_wait_then_free_not_paid(self):
        pool = self.make_pool()
        calls = []
        def work(key, model):
            calls.append((key, self.clock.now))
            if len(calls) == 1:
                raise APIError(429, "retryDelay: '60s'")
            return response()
        self.assertEqual(pool.run(work, 'test'), 'OK')
        self.assertEqual(calls, [('GEMINI_API_KEY_FREE_1', 0), ('GEMINI_API_KEY_FREE_1', 60)])

    def test_paid_only_after_total_90(self):
        pool = self.make_pool()
        calls = []
        def work(key, model):
            calls.append((key, self.clock.now))
            if 'FREE' in key:
                raise APIError(429, 'retryDelay: 120s')
            return response()
        pool.run(work, 'test')
        self.assertEqual(calls[-1], ('GEMINI_API_KEY_PAID', 90))

    def test_free_b_ready(self):
        pool = self.make_pool({'GEMINI_API_KEY_FREE_2': 'fake-b',
            'GEMINI_PROJECT_GEMINI_API_KEY_FREE_1': 'project-a',
            'GEMINI_PROJECT_GEMINI_API_KEY_FREE_2': 'project-b'})
        pool.cooldowns[('project-a', 'model-a')] = 60
        calls = []
        pool.run(lambda k, m: (calls.append(k), response())[1], 'test')
        self.assertEqual(calls, ['GEMINI_API_KEY_FREE_2'])
        self.assertEqual(self.clock.now, 0)

    def test_same_project_not_extra_quota(self):
        pool = self.make_pool({'GEMINI_API_KEY_FREE_2': 'fake-b'})
        calls = []
        def work(k, m):
            calls.append((k, self.clock.now))
            if 'FREE' in k:
                raise APIError(429, 'retryDelay: 120s')
            return response()
        pool.run(work, 'test')
        self.assertEqual(len(calls), 2)

    def test_free_model_fallback_precedes_paid(self):
        pool = self.make_pool({'GEMINI_FALLBACK_MODELS': 'model-b'})
        calls = []
        def work(k, m):
            calls.append((k, m))
            if m == 'model-a':
                raise APIError(404, 'model not found')
            return response()
        pool.run(work, 'test')
        self.assertEqual(calls[-1], ('GEMINI_API_KEY_FREE_1', 'model-b'))

    def test_budget_shared_across_requests(self):
        pool = self.make_pool()
        budget = gp.StepBudget(waited=70)
        def work(k, m):
            if 'FREE' in k:
                raise APIError(429, 'retryDelay: 60s')
            return response()
        pool.run(work, 'chunk', budget)
        self.assertEqual(self.clock.now, 20)
        self.assertEqual(budget.waited, 90)

    def test_paid_disabled(self):
        pool = self.make_pool()
        pool.allow_paid = False
        with self.assertRaises(gp.PoolError):
            pool.run(lambda k, m: (_ for _ in ()).throw(APIError(429, 'retryDelay: 120s')), 'test')
        self.assertEqual(pool.paid_used, 0)

    def test_paid_limit_no_request(self):
        pool = self.make_pool({'GEMINI_KHONG_DUNG_FREE': '1'})
        pool.paid_limit = 5
        work = Mock()
        with self.assertRaises(gp.PoolError):
            pool.run(work, 'test', reserve_tokens=100)
        work.assert_not_called()

    def test_bad_input_does_not_rotate_paid(self):
        pool = self.make_pool()
        work = Mock(side_effect=APIError(400, 'bad input'))
        with self.assertRaises(gp.PoolError):
            pool.run(work, 'test')
        self.assertEqual(work.call_count, 1)

    def test_file_404_does_not_disable_model(self):
        pool = self.make_pool()
        with self.assertRaises(gp.PoolError):
            pool.run(Mock(side_effect=APIError(404, 'file not found')), 'test')
        self.assertFalse(pool.unavailable)

    def test_cancel_wait(self):
        pool = self.make_pool()
        pool.cancel.set()
        with self.assertRaises(gp.Cancelled):
            pool.wait(90, gp.StepBudget())

    def test_partial_response_rejected(self):
        pool = self.make_pool()
        with self.assertRaises(gp.PartialResponse):
            pool.run(lambda k, m: response('cut', finish='MAX_TOKENS'), 'test')
        self.assertEqual(pool.usage[0]['total'], 12)

    def test_unknown_usage_reserved_not_zero(self):
        pool = self.make_pool({'GEMINI_KHONG_DUNG_FREE': '1'})
        pool.run(lambda k, m: NS(text='OK', candidates=[], usage_metadata=None), 'test', reserve_tokens=50)
        self.assertEqual(pool.paid_used, 50)
        self.assertIsNone(pool.usage[0]['total'])


class RefineTests(unittest.TestCase):
    def test_patch_preserves_existing_content(self):
        updated = refine.Report.parse(OLD).patch(PATCH)
        for text in ['Tiêu đề Việt giữ nguyên', 'Tóm tắt gốc. Câu hai. Câu ba.',
                     '- Bài học gốc không được mất.', '> Chưa có số đo hiệu quả.',
                     'English title retained', 'Original summary. Sentence two. Sentence three.',
                     '- Original lesson must remain.', '**Reference:** https://example.org/media']:
            self.assertIn(text, updated)
        self.assertTrue(refine.Report.parse(updated).upgraded)
        self.assertEqual(updated.count('## 4.'), 2)
        self.assertEqual(updated.count('## 5.'), 2)

    def test_patch_repeat_no_duplicates(self):
        once = refine.Report.parse(OLD).patch(PATCH)
        twice = refine.Report.parse(once).patch(PATCH)
        self.assertEqual(once, twice)

    def test_unknown_schema_rejected(self):
        with self.assertRaises(ValueError):
            refine.Report.parse('# Chỉ tiếng Việt\n## 2. Tóm tắt\nText')

    def test_render_five_sections(self):
        text = refine.render(generated(), refine.evidence(RAW), 'source')
        self.assertTrue(refine.Report.parse(text).upgraded)
        self.assertIn('Góc nhìn chuyên sâu', text)

    def test_fabricated_quote_rejected(self):
        data = generated()
        data['vi']['quotes'][0]['text'] = 'tăng 300%'
        with self.assertRaises(ValueError):
            refine.render(data, refine.evidence(RAW), 'source')

    def test_invalid_evidence_rejected(self):
        with self.assertRaises(ValueError):
            refine.validate_ids('Claim [S9999]', refine.evidence(RAW))

    def test_evidence_keeps_long_tail(self):
        raw = 'a' * 14000 + 'END-TAIL'
        result = refine.evidence(raw)
        self.assertEqual(''.join(result.values()), raw)

    def test_new_report_has_patch_markers(self):
        old = refine.render(generated(), refine.evidence(RAW), 'source')
        updated = refine.Report.parse(old).patch(PATCH)
        self.assertTrue(refine.Report.parse(updated).upgraded)

    def test_vietnamese_numbered_legacy_gets_english(self):
        old = '# 1. Tiêu đề chính\nTiêu đề thật\n\n## 2. Tóm tắt 3 câu\nGiữ tóm tắt.\n\n## 3. Bài học cốt lõi\nGiữ bài học.\n\n## 4. Trích dẫn hay nhất\n> Chưa có số đo hiệu quả.\n\n**Reference:** source\n'
        data = {'vi': PATCH['vi'], 'en': generated()['en']}
        with patch('refine._call_json', return_value=data):
            result, _ = refine.generate(None, RAW, 'source', old)
        self.assertIn('Tiêu đề thật', result)
        self.assertIn('Giữ bài học.', result)
        self.assertIn('Giữ tóm tắt.', result)
        self.assertTrue(refine.Report.parse(result).upgraded)
        self.assertEqual(result.count('**Reference:**'), 1)

    def test_duplicate_outer_title_retained_as_text(self):
        old = '# Tên ngoài\n# 1. Tiêu đề chính\nTên trong\n## 2. Tóm tắt\nNội dung\n## 3. Bài học\nBài học\n## 4. Trích dẫn\nQuote\n'
        report = refine.Report.parse(old)
        self.assertEqual(report.languages, ['vi'])
        updated = report.patch({'vi': PATCH['vi']})
        self.assertIn('Tên ngoài', updated)
        self.assertIn('Tên trong', updated)

    def test_compact_evidence_missing_chunk_fails(self):
        data = {f'S{i:04}': 'a' * 6000 for i in range(1, 10)}
        with patch('refine._call_json', return_value={}):
            with self.assertRaises(ValueError):
                refine.compact_evidence(None, data, gp.StepBudget())


class StorageTests(unittest.TestCase):
    def test_atomic_conflict_and_backup(self):
        with tempfile.TemporaryDirectory() as temp:
            p = Path(temp) / 'x.md'
            storage.atomic_write(p, 'original')
            original_hash = storage.file_hash(p)
            storage.atomic_write(p, 'new', original_hash, backup=True)
            self.assertEqual(next(Path(temp).glob('*.bak')).read_text(), 'original')
            with self.assertRaises(ValueError):
                storage.atomic_write(p, 'bad', original_hash)
            self.assertEqual(p.read_text(), 'new')

    def test_link_error_never_deletes(self):
        with tempfile.TemporaryDirectory() as temp:
            p = Path(temp) / 'links.md'
            storage.update_link(p, 'https://example.org/watch?v=1&x=2')
            self.assertEqual(len(storage.link_rows(p)), 1)
            self.assertNotIn('[[', storage.read(p))
            storage.update_link(p, 'https://example.org/watch?v=1&x=2', 'A|B')
            self.assertEqual(len(storage.link_rows(p)), 1)
            self.assertIn('A&#124;B', storage.read(p))

    def test_windows_names(self):
        self.assertEqual(storage.safe_name('CON'), '_CON')
        self.assertNotIn('|', storage.safe_name('A|B'))
        self.assertTrue(storage.safe_name('...'))

    def test_session_lock(self):
        with tempfile.TemporaryDirectory() as temp:
            one = storage.SessionLock(Path(temp) / 'lock')
            two = storage.SessionLock(Path(temp) / 'lock')
            self.assertTrue(one.acquire())
            self.assertFalse(two.acquire())
            one.close()
            self.assertTrue(two.acquire())
            two.close()


class MediaTests(unittest.TestCase):
    def test_subtitle_overlap_not_later_repetition(self):
        text = 'WEBVTT\n\n00:00.000 --> 00:03.000\nHello\n\n00:02.000 --> 00:04.000\nHello\nWorld\n\n00:05.000 --> 00:06.000\nHello\n'
        cues = media_io.subtitle_cues(text)
        self.assertEqual([c['text'] for c in cues], ['Hello', 'World', 'Hello'])

    def test_subtitle_first_no_audio_download(self):
        with tempfile.TemporaryDirectory() as folder:
            options = []
            class Downloader:
                def __init__(self, opts):
                    options.append(opts)
                    self.opts = opts
                def __enter__(self): return self
                def __exit__(self, *args): pass
                def extract_info(self, source, download):
                    if download:
                        self_test.assertTrue(self.opts['skip_download'])
                        Path(folder, 'id.vi.vtt').write_text('WEBVTT\n\n00:00.000 --> 00:01.000\nXin chào\n', encoding='utf-8')
                    return {'title': 'demo', 'language': 'vi', 'subtitles': {'vi': []}}
            self_test = self
            with patch('yt_dlp.YoutubeDL', Downloader), patch('media_io.executable', side_effect=AssertionError('No FFmpeg needed')):
                result = media_io.fetch('https://example.org/x', folder, threading.Event(), lambda _: None)
            self.assertIn('Xin chào', result['raw'])
            self.assertEqual(len(options), 2)

    def test_upload_cleanup_on_poll_error(self):
        client = NS(files=NS(upload=Mock(return_value=NS(name='file-1', state=NS(name='PROCESSING'))),
                             get=Mock(side_effect=ValueError('poll failed')), delete=Mock()))
        pool = NS(cancel=threading.Event(), emit=lambda _: None, check_cancel=lambda: None)
        pool.cancel.wait = Mock()
        pool.run = lambda work, *args: work(client, 'model')
        with self.assertRaises(ValueError):
            media_io.transcribe_one(pool, 'x', gp.StepBudget(), 'test')
        client.files.delete.assert_called_once_with(name='file-1')

    def test_empty_subtitle_falls_back_audio(self):
        with tempfile.TemporaryDirectory() as folder:
            opts_seen = []
            class Downloader:
                def __init__(self, opts):
                    self.opts = opts
                    opts_seen.append(opts)
                def __enter__(self): return self
                def __exit__(self, *args): pass
                def extract_info(self, source, download):
                    if download and self.opts.get('skip_download'):
                        Path(folder, 'id.vi.vtt').write_text('WEBVTT\n', encoding='utf-8')
                    elif download:
                        Path(folder, 'id.mp3').write_bytes(b'fake audio')
                    return {'title': 'demo', 'language': 'vi', 'subtitles': {'vi': []}}
            with patch('yt_dlp.YoutubeDL', Downloader), patch('media_io.executable', return_value='ffmpeg'):
                result = media_io.fetch('https://example.org/x', folder, threading.Event(), lambda _: None)
            self.assertTrue(result['audio'].is_file())
            self.assertEqual(len(opts_seen), 3)

    def test_chunk_checkpoint_skips_successful_audio(self):
        with tempfile.TemporaryDirectory() as folder:
            checkpoint = Path(folder) / 'chunks.json'
            pool = NS(cancel=threading.Event(), check_cancel=lambda: None)
            with patch('media_io.duration', return_value=350), patch('media_io.clip', return_value=Path(folder) / 'chunk.mp3'), patch('media_io.transcribe_one', return_value='lời nói') as api:
                first, _ = media_io.transcribe(pool, 'media', folder, checkpoint, 'fingerprint')
                second, _ = media_io.transcribe(pool, 'media', folder, checkpoint, 'fingerprint')
                self.assertEqual(first, second)
                self.assertEqual(api.call_count, 2)


class PipelineTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.out = self.root / 'data/output'
        self.out.mkdir(parents=True)
        self.raw = self.out / 'old_raw.md'
        self.refined = self.out / 'old_refine.md'
        self.raw.write_text(RAW, encoding='utf-8')
        self.refined.write_text(OLD, encoding='utf-8')
        self.fake_pool = NS(usage=[], close=lambda: None, tong_ket=lambda: None)
        self.pipeline = Pipeline(self.root, pool_factory=lambda **kw: self.fake_pool, emit=lambda _: None)

    def tearDown(self):
        self.temp.cleanup()

    def test_update_refine_no_media_no_raw_write_and_idempotent(self):
        old_hash = storage.file_hash(self.raw)
        with patch('refine._call_json', return_value=PATCH) as api, patch('media_io.fetch', side_effect=AssertionError('No media')):
            result = self.pipeline.process(Job(str(self.raw), update=True))
            self.assertEqual(result.status, 'success', result.message)
            self.assertEqual(storage.file_hash(self.raw), old_hash)
            self.assertEqual(api.call_count, 1)
            result = self.pipeline.process(Job(str(self.raw), update=True))
            self.assertEqual(result.status, 'no_change', result.message)
            self.assertEqual(api.call_count, 1)
        self.assertEqual(next(self.out.glob('*refine.md.*.bak')).read_text(encoding='utf-8'), OLD)

    def test_empty_checkboxes_no_api(self):
        with patch('refine._call_json', side_effect=AssertionError('No API')):
            result = self.pipeline.process(Job(str(self.raw), True, False, False))
        self.assertEqual(result.status, 'failed')

    def test_pair_exists_skip(self):
        result = self.pipeline.process(Job(str(self.raw)))
        self.assertEqual(result.status, 'skipped')
        self.assertIsNone(self.pipeline._pool)

    def test_raw_without_repair_no_full_transcribe(self):
        with patch('media_io.transcribe', side_effect=AssertionError('No ASR')):
            result = self.pipeline.process(Job(str(self.raw), True, True, False))
        self.assertEqual(result.status, 'failed')
        self.assertIsNone(self.pipeline._pool)

    def test_external_raw_edit_stops_publish(self):
        original = storage.file_hash(self.refined)
        def api(*args, **kwargs):
            self.raw.write_text(RAW + '\nUser edit', encoding='utf-8')
            return PATCH
        with patch('refine._call_json', side_effect=api):
            result = self.pipeline.process(Job(str(self.raw), True))
        self.assertEqual(result.status, 'failed')
        self.assertEqual(storage.file_hash(self.refined), original)

    def test_new_subtitle_raw_survives_missing_key(self):
        pipeline = Pipeline(self.root, pool_factory=Mock(side_effect=gp.PoolError('Missing key')),
                            emit=lambda _: None)
        with patch('media_io.fetch', return_value={'title': 'new', 'raw': 'Transcript text', 'cues': []}):
            result = pipeline.process(Job('https://example.org/new'))
        self.assertEqual(result.status, 'raw_only', result.message)
        self.assertTrue(Path(result.raw).exists())
        self.assertFalse(Path(result.refine).exists())

    def test_new_pair(self):
        with patch('media_io.fetch', return_value={'title': 'new', 'raw': storage.raw_body(RAW), 'cues': []}), patch('refine._call_json', return_value=generated()):
            result = self.pipeline.process(Job('https://example.org/new'))
        self.assertEqual(result.status, 'success', result.message)
        self.assertTrue(Path(result.raw).is_file())
        self.assertTrue(refine.Report.parse(storage.read(result.refine)).upgraded)

    def test_manifest_shared_between_url_and_raw_path(self):
        with patch('media_io.fetch', return_value={'title': 'new', 'raw': storage.raw_body(RAW), 'cues': []}), patch('refine._call_json', return_value=generated()):
            result = self.pipeline.process(Job('https://example.org/new'))
        _, _, key_url = self.pipeline.paths('https://example.org/new')
        _, _, key_raw = self.pipeline.paths(result.raw)
        self.assertEqual(key_url, key_raw)

    def test_bad_patch_keeps_old_report(self):
        original = storage.file_hash(self.refined)
        with patch('refine._call_json', return_value={'vi': {'results': 'bad'}, 'en': {}}):
            result = self.pipeline.process(Job(str(self.raw), True))
        self.assertEqual(result.status, 'failed')
        self.assertEqual(storage.file_hash(self.refined), original)

    def test_raw_repair_keeps_refine_and_untouched_lines(self):
        old_hash = storage.file_hash(self.refined)
        repair = {'start': 0, 'end': 10, 'first_line': 3, 'last_line': 3}
        with patch('media_io.fetch', return_value={'raw': 'Đoạn đã vá'}):
            result = self.pipeline.process(Job(str(self.raw), True, True, False, repair=repair))
        self.assertEqual(result.status, 'stale', result.message)
        self.assertEqual(storage.file_hash(self.refined), old_hash)
        self.assertIn('**Reference:** https://example.org/media', storage.read(self.raw))
        self.assertIn('Đoạn đã vá', storage.read(self.raw))

    def test_raw_repair_repeat_is_noop(self):
        repair = {'start': 0, 'end': 10, 'first_line': 3, 'last_line': 3}
        with patch('media_io.fetch', return_value={'raw': 'Đoạn đã vá'}) as api:
            self.pipeline.process(Job(str(self.raw), True, True, False, repair=repair))
            result = self.pipeline.process(Job(str(self.raw), True, True, False, repair=repair))
        self.assertEqual(api.call_count, 1)
        self.assertEqual(result.status, 'no_change')

    def test_refine_file_edited_during_generation_kept(self):
        def api(*args, **kw):
            self.refined.write_text(OLD + '\nUser added note', encoding='utf-8')
            return PATCH
        with patch('refine._call_json', side_effect=api):
            result = self.pipeline.process(Job(str(self.raw), True))
        self.assertEqual(result.status, 'failed')
        self.assertTrue(storage.read(self.refined).endswith('User added note'))

    def test_history_failure_does_not_lose_result(self):
        with patch('pipeline.history', side_effect=OSError('disk unavailable')):
            result = self.pipeline.process(Job(str(self.raw)))
        self.assertEqual(result.status, 'skipped')


if __name__ == '__main__':
    unittest.main()
