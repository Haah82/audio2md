# -*- coding: utf-8 -*-
"""Pool API key Gemini: vat kiet Free Tier truoc, chi rot sang key tra phi khi het.

Quy uoc dat ten bien moi truong (xem .env):
  - Ten bien co chu FREE  -> Free Tier (mien phi, nhung Google CO THE doc noi dung).
  - Moi ten khac          -> tra phi (dung cho tai lieu mat).
"""

import os
import re
import time
import itertools

from google import genai

# Chi ten bien co chu FREE moi duoc coi la mien phi. Mac dinh la tra phi de
# khong bao gio vo tinh day tai lieu mat qua Free Tier chi vi go nham ten bien.
_MAU_TEN_KEY = re.compile(r'^GEMINI_API_KEY(_.*)?$')
_MAU_RETRY_DELAY = re.compile(r"retry[_ ]?delay['\"]?\s*[:=]\s*['\"]?(\d+(?:\.\d+)?)s", re.I)

# Loi bao het quota / qua nhieu request -> nghi key nay, chuyen key khac.
_DAU_HIEU_HET_QUOTA = ('429', 'resource_exhausted', 'quota', 'rate limit', 'too many requests')
# Loi bao model khong ton tai -> bo han model nay, khong phi thoi gian quay vong key.
_DAU_HIEU_MODEL_HONG = ('404', 'not found', 'not supported', 'is not found', 'unsupported')


def _so(ten, mac_dinh):
    try:
        return float(os.getenv(ten, '').strip() or mac_dinh)
    except ValueError:
        return mac_dinh


class _Key:
    def __init__(self, ten, gia_tri, mien_phi, gian_cach):
        self.ten = ten
        self.gia_tri = gia_tri
        self.mien_phi = mien_phi
        self.gian_cach = gian_cach      # giay toi thieu giua 2 luot goi cung key
        self.lan_goi_cuoi = 0.0
        self.nghi_den = 0.0             # timestamp het han cooldown sau khi dinh 429
        self.so_luot = 0
        self._client = None

    @property
    def client(self):
        # Tai su dung client: file da upload thuoc ve dung key da upload no.
        if self._client is None:
            self._client = genai.Client(api_key=self.gia_tri)
        return self._client

    @property
    def nhan(self):
        return f"{self.ten} [{'FREE' if self.mien_phi else 'PAID'}]"


class GeminiPool:
    def __init__(self):
        cam_free = os.getenv('GEMINI_KHONG_DUNG_FREE', '0').strip() == '1'
        gian_cach_free = _so('GEMINI_FREE_MIN_INTERVAL', 4.5)
        gian_cach_paid = _so('GEMINI_PAID_MIN_INTERVAL', 0.5)
        self.cooldown_mac_dinh = _so('GEMINI_COOLDOWN_MAC_DINH', 60.0)
        # Key FREE dang cooldown MA con cho duoi nguong nay thi van uu tien cho
        # het cooldown de dung tiep, thay vi tra tien cho key PAID. Google
        # thuong tra retryDelay 20-60s nen phan lon truong hop van mien phi.
        self.cho_free_toi_da = _so('GEMINI_CHO_FREE_TOI_DA', 90.0)

        da_thay = set()
        free, paid = [], []
        for ten, gia_tri in os.environ.items():
            if not _MAU_TEN_KEY.match(ten):
                continue
            gia_tri = (gia_tri or '').strip()
            if not gia_tri or gia_tri.upper().startswith('YOUR_') or gia_tri in da_thay:
                continue
            da_thay.add(gia_tri)
            mien_phi = 'FREE' in ten.upper()
            (free if mien_phi else paid).append(
                _Key(ten, gia_tri, mien_phi, gian_cach_free if mien_phi else gian_cach_paid))

        free.sort(key=lambda k: k.ten)
        paid.sort(key=lambda k: k.ten)

        if cam_free and free:
            print(f"[BAO MAT] GEMINI_KHONG_DUNG_FREE=1 -> bo qua {len(free)} key Free Tier.")
            free = []

        # Vat kiet Free Tier truoc, het moi rot sang key tra phi.
        self.keys = free + paid
        if not self.keys:
            raise RuntimeError(
                "Khong tim thay API key nao trong .env "
                "(can it nhat mot bien dang GEMINI_API_KEY_FREE_1 hoac GEMINI_API_KEY_PAID).")

        chinh = (os.getenv('GEMINI_MODEL', '') or '').strip()
        du_phong = [m for m in ('gemini-3.6-flash', 'gemini-2.5-flash') if m != chinh]
        self.models = ([chinh] if chinh else []) + du_phong
        self.model_hong = set()

        print(f"[POOL] {len(free)} key FREE + {len(paid)} key PAID | model: {', '.join(self.models)}"
              f" | cho FREE toi da {self.cho_free_toi_da:.0f}s")

    # ------------------------------------------------------------------ noi bo
    def _con_phai_cho(self, key):
        return max(0.0, key.nghi_den - time.time())

    def _uu_tien(self, key):
        """Khoa sap xep: cho cooldown ngan de giu mien phi, cooldown dai thi nhuong.

        Key phai cho lau hon nguong bi day xuong sau key tra phi; con lai giu
        nguyen thu tu goc (FREE truoc, PAID sau).
        """
        qua_lau = self._con_phai_cho(key) > self.cho_free_toi_da
        return (qua_lau, self.keys.index(key))

    def _cho_den_luot(self, key):
        """Ne rate-limit theo phut: gian cach toi thieu giua 2 luot cung mot key."""
        cho_quota = self._con_phai_cho(key)
        cho = max(cho_quota, key.lan_goi_cuoi + key.gian_cach - time.time())
        if cho > 0:
            ly_do = " (cho de khoi ton tien key PAID)" if cho_quota > 0 and key.mien_phi else ""
            print(f"[POOL] Cho {cho:.1f}s truoc khi dung {key.nhan}{ly_do}...")
            time.sleep(cho)

    def _cho_cooldown(self, key, loi):
        khop = _MAU_RETRY_DELAY.search(str(loi))
        giay = float(khop.group(1)) if khop else self.cooldown_mac_dinh
        key.nghi_den = time.time() + giay
        print(f"[POOL] {key.nhan} het quota -> nghi {giay:.0f}s, chuyen key khac.")

    # ------------------------------------------------------------------- cong khai
    def chay(self, cong_viec, mo_ta="goi API"):
        """Chay cong_viec(client, model) tren key re nhat con dung duoc.

        cong_viec phai TU CHUA (vd: upload file roi generate) vi file da upload
        chi thuoc ve dung key da upload no - doi key la phai upload lai.
        """
        loi_cuoi = None
        for model in self.models:
            if model in self.model_hong:
                continue
            # Uu tien key con san sang ngay; key dang cooldown de xuong cuoi.
            thu_tu = sorted(self.keys, key=self._uu_tien)
            for key in thu_tu:
                self._cho_den_luot(key)
                try:
                    print(f"[POOL] {mo_ta} | {key.nhan} | {model}")
                    ket_qua = cong_viec(key.client, model)
                    key.lan_goi_cuoi = time.time()
                    key.so_luot += 1
                    if ket_qua:
                        return ket_qua
                    loi_cuoi = RuntimeError("API tra ve rong")
                except Exception as e:
                    key.lan_goi_cuoi = time.time()
                    loi_cuoi = e
                    thong_bao = str(e).lower()
                    if any(d in thong_bao for d in _DAU_HIEU_HET_QUOTA):
                        self._cho_cooldown(key, e)
                        continue
                    if any(d in thong_bao for d in _DAU_HIEU_MODEL_HONG):
                        print(f"[POOL] Model {model} khong dung duoc -> bo qua han.")
                        self.model_hong.add(model)
                        break
                    print(f"[WARN] {key.nhan} loi: {e}")
        print(f"[ERROR] Het key/model kha dung cho '{mo_ta}'. Loi cuoi: {loi_cuoi}")
        return None

    def tong_ket(self):
        free = sum(k.so_luot for k in self.keys if k.mien_phi)
        paid = sum(k.so_luot for k in self.keys if not k.mien_phi)
        print(f"\n[CHI PHI] Luot goi mien phi: {free} | Luot goi tra phi: {paid}")
