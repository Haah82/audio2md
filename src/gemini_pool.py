# -*- coding: utf-8 -*-
"""Pool Gemini API key, ưu tiên FREE và không làm lộ credential trong log."""

import os
import re
import time

from google import genai

_MAU_TEN_KEY = re.compile(r'^GEMINI_API_KEY(_.*)?$')
_MAU_MODEL = re.compile(r'^[A-Za-z0-9._/-]+$')
_MAU_RETRY_DELAY = re.compile(r"retry[_ ]?delay['\"]?\s*[:=]\s*['\"]?(\d+(?:\.\d+)?)s", re.I)
_DAU_HIEU_HET_QUOTA = ('429', 'resource_exhausted', 'quota', 'rate limit', 'too many requests')
_DAU_HIEU_TAM_THOI = ('503', 'unavailable', 'high demand', 'overloaded', 'service unavailable')


def _so(ten, mac_dinh, env=os.environ):
    try:
        return float((env.get(ten, '') or '').strip() or mac_dinh)
    except ValueError:
        return mac_dinh


def _models_tu_env(env=os.environ):
    """Đọc model theo thứ tự cấu hình; không có fallback ngầm."""
    values = [env.get('GEMINI_MODEL', '')]
    values.extend((env.get('GEMINI_FALLBACK_MODELS', '') or '').split(','))
    models = []
    for value in values:
        model = (value or '').strip()
        if not model:
            continue
        if not _MAU_MODEL.fullmatch(model):
            raise RuntimeError(f"Ten model khong hop le: {model!r}")
        if model not in models:
            models.append(model)
    if not models:
        raise RuntimeError('Chua cau hinh GEMINI_MODEL.')
    return models


def redact_error(error, secrets=()):
    """Trả về lỗi gọn để log không vô tình lộ API key hay URL có key."""
    text = ' '.join(str(error).split())
    for secret in secrets:
        if secret:
            text = text.replace(secret, '[REDACTED]')
    text = re.sub(r'([?&](?:key|api[_-]?key)=)[^&\s]+', r'\1[REDACTED]', text, flags=re.I)
    return text[:500]


class _Key:
    def __init__(self, ten, gia_tri, mien_phi, gian_cach, client_factory=genai.Client):
        self.ten = ten
        self.gia_tri = gia_tri
        self.mien_phi = mien_phi
        self.gian_cach = gian_cach
        self.lan_goi_cuoi = 0.0
        self.nghi_den = 0.0
        self.so_luot = 0
        self._client = None
        self._client_factory = client_factory

    @property
    def client(self):
        if self._client is None:
            self._client = self._client_factory(api_key=self.gia_tri)
        return self._client

    @property
    def nhan(self):
        return f"{self.ten} [{'FREE' if self.mien_phi else 'PAID'}]"


def configured_keys(env=os.environ, client_factory=genai.Client):
    """Lấy key hợp lệ, chỉ để nhãn key đi ra các lớp gọi bên ngoài."""
    free_interval = _so('GEMINI_FREE_MIN_INTERVAL', 4.5, env)
    paid_interval = _so('GEMINI_PAID_MIN_INTERVAL', 0.5, env)
    seen, free, paid = set(), [], []
    for name, value in env.items():
        if not _MAU_TEN_KEY.match(name):
            continue
        value = (value or '').strip()
        if not value or value.upper().startswith('YOUR_') or value in seen:
            continue
        seen.add(value)
        is_free = 'FREE' in name.upper()
        key = _Key(name, value, is_free, free_interval if is_free else paid_interval, client_factory)
        (free if is_free else paid).append(key)
    free.sort(key=lambda key: key.ten)
    paid.sort(key=lambda key: key.ten)
    if (env.get('GEMINI_KHONG_DUNG_FREE', '0') or '').strip() == '1':
        free = []
    return free, paid


class GeminiPool:
    def __init__(self, env=os.environ, sleeper=time.sleep, clock=time.time, client_factory=genai.Client):
        self.env = env
        self.sleep = sleeper
        self.clock = clock
        self.cooldown_mac_dinh = _so('GEMINI_COOLDOWN_MAC_DINH', 60.0, env)
        self.max_attempts = max(1, int(_so('GEMINI_MAX_ATTEMPTS', 3, env)))
        self.backoff_base = max(0.0, _so('GEMINI_BACKOFF_BASE', 3.0, env))
        self.backoff_max = max(self.backoff_base, _so('GEMINI_BACKOFF_MAX', 30.0, env))
        free, paid = configured_keys(env, client_factory)
        self.keys = free + paid
        self.models = _models_tu_env(env)
        self.model_hong = set()
        if not self.keys:
            raise RuntimeError('Khong tim thay API key Gemini hop le trong .env.')
        print(f"[POOL] {len(free)} key FREE + {len(paid)} key PAID | model: {', '.join(self.models)}")

    def _con_phai_cho(self, key):
        return max(0.0, key.nghi_den - self.clock())

    def _cho_den_luot(self, key):
        wait = max(self._con_phai_cho(key), key.lan_goi_cuoi + key.gian_cach - self.clock())
        if wait > 0:
            print(f"[POOL] Cho {wait:.1f}s truoc khi dung {key.nhan}...")
            self.sleep(wait)

    def _cho_cooldown(self, key, error):
        match = _MAU_RETRY_DELAY.search(str(error))
        seconds = float(match.group(1)) if match else self.cooldown_mac_dinh
        key.nghi_den = self.clock() + seconds
        print(f"[POOL] {key.nhan} het quota -> nghi {seconds:.0f}s.")

    @staticmethod
    def _la_model_khong_dung(error):
        message = str(error).lower()
        return ('404' in message or 'not found' in message or 'not supported' in message) and 'model' in message

    @staticmethod
    def _la_tam_thoi(error):
        message = str(error).lower()
        return any(token in message for token in _DAU_HIEU_TAM_THOI)

    def _goi(self, key, model, cong_viec, mo_ta):
        self._cho_den_luot(key)
        print(f"[POOL] {mo_ta} | {key.nhan} | {model}")
        result = cong_viec(key.client, model)
        key.lan_goi_cuoi = self.clock()
        key.so_luot += 1
        return result

    def chay(self, cong_viec, mo_ta='goi API'):
        """Chạy công việc trên model/key được cấu hình.

        503 ở FREE được retry theo backoff và dừng tại FREE; không đẩy sang PAID
        chỉ vì service đang quá tải.
        """
        last_error = None
        free = [key for key in self.keys if key.mien_phi]
        paid = [key for key in self.keys if not key.mien_phi]
        secrets = [key.gia_tri for key in self.keys]

        for model in self.models:
            if model in self.model_hong:
                continue
            free_temporary = False
            for attempt in range(self.max_attempts):
                free_temporary = False
                for key in free:
                    try:
                        result = self._goi(key, model, cong_viec, mo_ta)
                        if result:
                            return result
                        last_error = RuntimeError('API tra ve rong')
                    except Exception as error:
                        key.lan_goi_cuoi = self.clock()
                        last_error = error
                        if self._la_model_khong_dung(error):
                            print(f"[POOL] Model {model} khong dung duoc -> bo qua han.")
                            self.model_hong.add(model)
                            break
                        if self._la_tam_thoi(error):
                            free_temporary = True
                            print(f"[WARN] {key.nhan} tam thoi khong san sang (503).")
                            continue
                        if any(token in str(error).lower() for token in _DAU_HIEU_HET_QUOTA):
                            self._cho_cooldown(key, error)
                            continue
                        print(f"[WARN] {key.nhan} loi: {redact_error(error, secrets)}")
                if model in self.model_hong:
                    break
                if free_temporary and attempt + 1 < self.max_attempts:
                    wait = min(self.backoff_max, self.backoff_base * (2 ** attempt))
                    print(f"[POOL] FREE gap 503 -> thu lai sau {wait:.0f}s ({attempt + 1}/{self.max_attempts}).")
                    self.sleep(wait)
                    continue
                break
            if model in self.model_hong:
                continue
            if free_temporary:
                print(f"[ERROR] FREE van gap 503 sau {self.max_attempts} lan; khong dung key PAID.")
                return None

            for key in paid:
                try:
                    result = self._goi(key, model, cong_viec, mo_ta)
                    if result:
                        return result
                    last_error = RuntimeError('API tra ve rong')
                except Exception as error:
                    key.lan_goi_cuoi = self.clock()
                    last_error = error
                    if self._la_model_khong_dung(error):
                        print(f"[POOL] Model {model} khong dung duoc -> bo qua han.")
                        self.model_hong.add(model)
                        break
                    print(f"[WARN] {key.nhan} loi: {redact_error(error, secrets)}")

        print(f"[ERROR] Het key/model kha dung cho '{mo_ta}'. Loi cuoi: {redact_error(last_error, secrets)}")
        return None

    def tong_ket(self):
        free = sum(key.so_luot for key in self.keys if key.mien_phi)
        paid = sum(key.so_luot for key in self.keys if not key.mien_phi)
        print(f"\n[CHI PHI] Luot goi mien phi: {free} | Luot goi tra phi: {paid}")
