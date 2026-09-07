"""Bể API key Gemini: ưu tiên vắt kiệt hạn mức Free Tier, chỉ rơi sang key trả
phí khi các key free đã chạm giới hạn.

VÌ SAO CẦN
    GUI chạy MỖI FILE trong một tiến trình con riêng, nên trạng thái "key này đã
    hết hạn mức" không thể giữ trong bộ nhớ - phải ghi ra đĩa, nếu không mỗi file
    lại đâm đầu vào đúng cái key vừa bị 429 và lãng phí một lượt gọi.

CẤU HÌNH TRONG .env
    GEMINI_API_KEY_FREE_1=...     # key thuộc project Free Tier
    GEMINI_API_KEY_FREE_2=...     # key Free Tier thứ hai
    GEMINI_API_KEY_PAID=...       # key thuộc project trả phí, dùng khi free hết
    GEMINI_API_KEY=...            # tương thích ngược: coi như key trả phí

    GEMINI_FREE_MIN_INTERVAL=4.5  # giây tối thiểu giữa 2 lượt gọi CÙNG một key
    GEMINI_PAID_MIN_INTERVAL=0.5
    GEMINI_COOLDOWN_MAC_DINH=60   # giây nghỉ của một key sau khi dính 429
    GEMINI_KHONG_DUNG_FREE=1      # cấm tuyệt đối định tuyến qua Free Tier

LƯU Ý BẢO MẬT
    Theo điều khoản Gemini API, nội dung gửi qua dịch vụ KHÔNG TRẢ PHÍ có thể
    được Google dùng để cải thiện sản phẩm và có người thật xem xét. Với hồ sơ
    mời thầu, hợp đồng hay tài liệu có ràng buộc bảo mật, hãy đặt
    GEMINI_KHONG_DUNG_FREE=1 (hoặc gọi với chi_dung_paid=True) để ép đi key trả phí.
"""

import json
import os
import re
import sys
import time

from google import genai

_HERE = os.path.dirname(os.path.abspath(__file__))
BASE_DIR = os.path.dirname(_HERE)

# Nơi ghi trạng thái dùng chung giữa các tiến trình con của GUI.
FILE_TRANG_THAI = os.path.join(BASE_DIR, 'data', '.gemini_pool_state.json')

MIN_INTERVAL_FREE = float(os.environ.get('GEMINI_FREE_MIN_INTERVAL') or 4.5)
MIN_INTERVAL_PAID = float(os.environ.get('GEMINI_PAID_MIN_INTERVAL') or 0.5)
COOLDOWN_MAC_DINH = float(os.environ.get('GEMINI_COOLDOWN_MAC_DINH') or 60)
# Mỗi trang PDF bị tính 258 token đầu vào bất kể độ phân giải (tài liệu Google).
# Dùng để ước lượng trước khi gọi, giúp cảnh báo sớm chứ không phải để tính tiền.
TOKEN_MOI_TRANG_PDF = 258


class LoiHetPool(RuntimeError):
    """Mọi key trong bể đều đã chạm hạn mức hoặc hỏng."""


def upload_an_toan(client, duong_dan):
    """Upload file lên Files API, né được lỗi tên file có dấu tiếng Việt.

    SDK google-genai đặt tên file vào HTTP header và mã hoá bằng ASCII, nên MỌI
    file có dấu trong tên đều chết ngay từ bước upload:
        'ascii' codec can't encode character '\\u1ebf' ... (chữ 'ế')
    Đây là lỗi âm thầm giết cả loạt tài liệu tiếng Việt - 'Quyết định...',
    'Đê điều...', 'Tiêu chuẩn...'. Cách chữa: copy sang file tạm tên thuần ASCII
    rồi mới upload; nội dung không đổi nên kết quả y hệt.
    """
    try:
        return client.files.upload(file=duong_dan)
    except UnicodeEncodeError:
        pass
    except Exception as loi:
        if 'ascii' not in str(loi).lower() or 'codec' not in str(loi).lower():
            raise

    import shutil
    import tempfile
    duoi = os.path.splitext(duong_dan)[1] or '.bin'
    fd, tam = tempfile.mkstemp(suffix=duoi, prefix='pdf2md_up_')
    os.close(fd)
    try:
        shutil.copy2(duong_dan, tam)
        return client.files.upload(file=tam)
    finally:
        try:
            os.remove(tam)
        except Exception:
            pass


def _bay_gio():
    return time.time()


# --- Phân loại lỗi ------------------------------------------------------------

def phan_loai_loi(loi):
    """Trả về một trong: 'het_han_muc', 'key_hong', 'het_tien', 'tam_thoi'."""
    s = str(loi)
    thap = s.lower()
    if '429' in s or 'resource_exhausted' in thap or 'rate limit' in thap \
            or 'quota' in thap:
        return 'het_han_muc'
    if '402' in s or 'payment required' in thap or 'billing' in thap \
            or 'insufficient' in thap:
        return 'het_tien'
    if any(x in thap for x in ('api key not valid', 'api_key_invalid',
                               'unauthenticated', '401', 'permission_denied',
                               '403')):
        return 'key_hong'
    return 'tam_thoi'


def _giay_cho_tu_loi(loi, mac_dinh=COOLDOWN_MAC_DINH):
    """Google hay kèm retryDelay trong thân lỗi 429 - dùng đúng con số đó."""
    m = re.search(r"retryDelay['\"]?\s*[:=]\s*['\"]?(\d+(?:\.\d+)?)s", str(loi))
    if m:
        try:
            return max(float(m.group(1)), 1.0)
        except ValueError:
            pass
    return mac_dinh


# --- Trạng thái dùng chung giữa các tiến trình --------------------------------

def _doc_trang_thai():
    try:
        with open(FILE_TRANG_THAI, encoding='utf-8') as fh:
            return json.load(fh)
    except Exception:
        return {}


def _ghi_trang_thai(tt):
    try:
        os.makedirs(os.path.dirname(FILE_TRANG_THAI), exist_ok=True)
        tam = FILE_TRANG_THAI + '.tmp'
        with open(tam, 'w', encoding='utf-8') as fh:
            json.dump(tt, fh, ensure_ascii=False, indent=1)
        os.replace(tam, FILE_TRANG_THAI)
    except Exception:
        pass


# --- Một key trong bể ---------------------------------------------------------

class Key:
    def __init__(self, ten, api_key, tra_phi):
        self.ten = ten
        self.api_key = api_key
        self.tra_phi = tra_phi
        self._client = None
        self.hong = False

    @property
    def client(self):
        if self._client is None:
            self._client = genai.Client(api_key=self.api_key)
        return self._client

    @property
    def min_interval(self):
        return MIN_INTERVAL_PAID if self.tra_phi else MIN_INTERVAL_FREE

    def __repr__(self):
        return f"<Key {self.ten} {'PAID' if self.tra_phi else 'FREE'}>"


def doc_cac_key():
    """Gom key từ .env theo thứ tự ưu tiên: các key Free trước, key trả phí sau.

    Nhận cả tên có đánh số (GEMINI_API_KEY_FREE_1..9, GEMINI_API_KEY_PAID_1..9)
    lẫn tên trần. GEMINI_API_KEY cũ được coi là key trả phí để không phá cấu hình
    hiện có của người dùng.
    """
    free, paid = [], []
    for bien, gia_tri in os.environ.items():
        gia_tri = (gia_tri or '').strip()
        if not gia_tri or not bien.startswith('GEMINI_API_KEY'):
            continue
        # Chỉ tên biến có chữ FREE mới được coi là Free Tier. Mọi tên khác - kể
        # cả GEMINI_API_KEY trần của cấu hình cũ - mặc định là trả phí, để không
        # bao giờ vô tình đẩy tài liệu mật qua Free Tier vì gõ nhầm tên biến.
        (free if 'FREE' in bien[len('GEMINI_API_KEY'):].upper() else paid).append(
            (bien, gia_tri))
    free.sort()
    paid.sort()

    da_thay = set()
    keys = []
    for danh_sach, tra_phi in ((free, False), (paid, True)):
        for ten, gt in danh_sach:
            if gt in da_thay:  # cùng một key khai hai lần thì chỉ giữ một
                continue
            da_thay.add(gt)
            keys.append(Key(ten, gt, tra_phi=tra_phi))
    return keys


# --- Bể key -------------------------------------------------------------------

class Pool:
    def __init__(self, keys=None, im_lang=False):
        self.keys = keys if keys is not None else doc_cac_key()
        self.im_lang = im_lang
        self.tt = _doc_trang_thai()
        self._vong = 0
        if os.environ.get('GEMINI_KHONG_DUNG_FREE') == '1':
            self.keys = [k for k in self.keys if k.tra_phi]

    # -- tiện ích trạng thái
    def _muc(self, key):
        return self.tt.setdefault(key.ten, {})

    def _dang_nghi(self, key):
        return self._muc(key).get('nghi_den', 0) > _bay_gio()

    def _cho_nghi(self, key, giay, ly_do):
        muc = self._muc(key)
        muc['nghi_den'] = _bay_gio() + giay
        muc['ly_do'] = ly_do
        _ghi_trang_thai(self.tt)

    def _ghi_nhan_goi(self, key, res=None):
        muc = self._muc(key)
        muc['goi_cuoi'] = _bay_gio()
        muc['so_luot'] = muc.get('so_luot', 0) + 1
        meta = getattr(res, 'usage_metadata', None) if res is not None else None
        if meta is not None:
            for ten_field, ten_luu in (('prompt_token_count', 'token_vao'),
                                       ('candidates_token_count', 'token_ra'),
                                       ('total_token_count', 'token_tong')):
                gt = getattr(meta, ten_field, None)
                if isinstance(gt, int):
                    muc[ten_luu] = muc.get(ten_luu, 0) + gt
        _ghi_trang_thai(self.tt)

    def _cho_du_nhip(self, key):
        """Giữ khoảng cách tối thiểu giữa hai lượt gọi cùng một key (né RPM)."""
        con = self._muc(key).get('goi_cuoi', 0) + key.min_interval - _bay_gio()
        if con > 0:
            time.sleep(min(con, 30))

    def _in(self, *a):
        if not self.im_lang:
            print(*a)

    # -- chọn key
    def thu_tu_key(self, chi_dung_paid=False):
        """Free trước (xoay vòng để chia đều tải), rồi mới tới paid."""
        dung = [k for k in self.keys if not k.hong]
        if chi_dung_paid:
            return [k for k in dung if k.tra_phi]
        free = [k for k in dung if not k.tra_phi]
        paid = [k for k in dung if k.tra_phi]
        if free:
            self._vong = (self._vong + 1) % len(free)
            free = free[self._vong:] + free[:self._vong]
        san_sang = [k for k in free + paid if not self._dang_nghi(k)]
        # Không còn key nào rảnh thì vẫn trả về danh sách đầy đủ để tầng trên
        # quyết định có chờ hết cooldown hay không.
        return san_sang or (free + paid)

    def mo_ta(self):
        dong = []
        for k in self.keys:
            muc = self._muc(k)
            trang = 'HỎNG' if k.hong else (
                f"nghỉ {int(muc['nghi_den'] - _bay_gio())}s" if self._dang_nghi(k)
                else 'sẵn sàng')
            dong.append(f"   {k.ten}: {'PAID' if k.tra_phi else 'FREE'} | {trang}"
                        f" | {muc.get('so_luot', 0)} lượt"
                        f" | {muc.get('token_tong', 0):,} token")
        return '\n'.join(dong)

    # -- gọi model
    def goi(self, ham, chi_dung_paid=False, nhan='', so_vong=2):
        """Chạy `ham(client, ten_key)` trên key đầu tiên còn hạn mức.

        `ham` phải TỰ TRỌN GÓI mọi việc cần cùng một client (upload file, gọi
        model, xoá file) vì file đã upload chỉ tồn tại trong project của key đó.
        Trả về đúng giá trị `ham` trả về.
        """
        loi_cuoi = None
        for vong in range(so_vong):
            danh_sach = self.thu_tu_key(chi_dung_paid)
            if not danh_sach:
                raise LoiHetPool("Không có API key nào khả dụng. Kiểm tra .env.")
            for key in danh_sach:
                if self._dang_nghi(key):
                    continue
                self._cho_du_nhip(key)
                try:
                    ket_qua = ham(key.client, key.ten)
                except Exception as loi:  # noqa: BLE001
                    loai = phan_loai_loi(loi)
                    loi_cuoi = loi
                    if loai == 'het_han_muc':
                        giay = _giay_cho_tu_loi(loi)
                        self._cho_nghi(key, giay, '429 hết hạn mức')
                        self._in(f"⏳ {key.ten} chạm hạn mức{nhan}, nghỉ {int(giay)}s "
                                 f"-> chuyển key khác.")
                        continue
                    if loai == 'het_tien':
                        self._cho_nghi(key, 3600, '402 hết số dư')
                        self._in(f"💳 {key.ten} hết số dư{nhan} -> chuyển key khác.")
                        continue
                    if loai == 'key_hong':
                        key.hong = True
                        self._in(f"🔑 {key.ten} không dùng được (key sai/không có "
                                 f"quyền) -> loại khỏi bể.")
                        continue
                    # Lỗi tạm thời: thử key kế tiếp, vòng sau quay lại key này.
                    self._in(f"⚠️ {key.ten} lỗi tạm thời{nhan}: {loi}")
                    self._cho_nghi(key, 5, 'lỗi tạm thời')
                    continue
                # Ghi sổ NGAY TẠI ĐÂY, một lần duy nhất. Người gọi KHÔNG cần
                # gọi thêm ghi_nhan_res, làm vậy sẽ đếm token gấp đôi.
                self._ghi_nhan_goi(key, ket_qua if hasattr(ket_qua, 'usage_metadata')
                                   else None)
                return ket_qua, key

            # Hết lượt trong vòng này: chờ key nào sắp hết cooldown sớm nhất.
            if vong < so_vong - 1:
                cho = min((self._muc(k).get('nghi_den', 0) - _bay_gio()
                           for k in self.keys if not k.hong), default=0)
                if cho > 0:
                    self._in(f"⏸️  Mọi key đang nghỉ, chờ {int(cho)}s rồi thử lại...")
                    time.sleep(min(cho + 1, 120))

        raise LoiHetPool(
            f"Toàn bộ API pool đã cạn hạn mức{nhan}. Lỗi cuối: {loi_cuoi}")

    def ghi_nhan_res(self, key, res):
        """Cộng token của một response vào sổ của key.

        CHỈ dùng khi response KHÔNG phải giá trị trả về của `ham` trong `goi`
        (ví dụ `ham` trả về tuple). Nếu `ham` trả thẳng response thì `goi` đã ghi
        sổ rồi - gọi thêm hàm này sẽ đếm token gấp đôi.
        """
        self._ghi_nhan_goi(key, res)

    def tong_ket(self):
        tong_vao = sum(m.get('token_vao', 0) for m in self.tt.values())
        tong_ra = sum(m.get('token_ra', 0) for m in self.tt.values())
        return (f"📊 Cộng dồn: {tong_vao:,} token vào | {tong_ra:,} token ra\n"
                + self.mo_ta())


_pool_dung_chung = None


def pool(im_lang=False):
    """Bể dùng chung cho cả tiến trình."""
    global _pool_dung_chung
    if _pool_dung_chung is None:
        _pool_dung_chung = Pool(im_lang=im_lang)
    return _pool_dung_chung


def main():
    """`python src/gemini_pool.py` -> in tình trạng bể key hiện tại.
    Thêm `--go-nghi` để xoá trạng thái nghỉ (dùng khi đã sang ngày mới, hạn mức
    đã reset mà file trạng thái vẫn còn ghi cooldown cũ)."""
    from dotenv import load_dotenv
    load_dotenv(os.path.join(BASE_DIR, '.env'))
    if '--go-nghi' in sys.argv:
        try:
            os.remove(FILE_TRANG_THAI)
            print("✅ Đã xoá trạng thái nghỉ. Mọi key được coi là sẵn sàng trở lại.")
        except FileNotFoundError:
            print("ℹ️  Chưa có file trạng thái nào để xoá.")
        except Exception as e:  # noqa: BLE001
            print(f"❌ Không xoá được {FILE_TRANG_THAI}: {e}")
            return 1
    p = Pool()
    if not p.keys:
        print("❌ Chưa khai báo API key nào trong .env.")
        print(__doc__)
        return 1
    print(f"🔑 Bể có {len(p.keys)} key "
          f"({sum(1 for k in p.keys if not k.tra_phi)} free / "
          f"{sum(1 for k in p.keys if k.tra_phi)} trả phí):")
    print(p.tong_ket())
    return 0


if __name__ == '__main__':
    sys.exit(main() or 0)
