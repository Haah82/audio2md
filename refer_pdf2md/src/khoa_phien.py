# -*- coding: utf-8 -*-
"""Khóa một phiên ứng dụng bằng thư viện chuẩn trên Windows.

Theo plan mục 5: giữ handle suốt phiên để hai bản PDF2MD không cùng thay đổi
lịch sử và output. Khóa do hệ điều hành giữ nên được giải phóng cả khi tiến
trình chết đột ngột, không cần dọn file khóa cũ.

Trên nền không có msvcrt thì coi như không khóa; dự án chỉ chạy Windows.
"""
from pathlib import Path

try:
    import msvcrt
except ImportError:  # không phải Windows
    msvcrt = None


class KhoaPhien:
    """Khóa theo kiểu giành được thì chạy, không giành được thì báo và dừng."""

    def __init__(self, duong_dan):
        self.duong_dan = Path(duong_dan)
        self._tep = None

    @property
    def dang_giu(self):
        return self._tep is not None

    def thu_khoa(self):
        """Giành khóa. Trả về True nếu giành được, False nếu phiên khác đang giữ."""
        if msvcrt is None:
            return True
        try:
            self.duong_dan.parent.mkdir(parents=True, exist_ok=True)
            self._tep = open(self.duong_dan, 'a+b')
            self._tep.seek(0)
            # LK_NBLCK khóa một byte và trả lỗi ngay thay vì chờ, nên giao diện
            # không bị treo khi có phiên khác đang giữ.
            msvcrt.locking(self._tep.fileno(), msvcrt.LK_NBLCK, 1)
        except OSError:
            self._dong()
            return False
        return True

    def nha_khoa(self):
        """Nhả khóa và đóng handle. Gọi nhiều lần vẫn an toàn."""
        if msvcrt is not None and self._tep is not None:
            try:
                self._tep.seek(0)
                msvcrt.locking(self._tep.fileno(), msvcrt.LK_UNLCK, 1)
            except OSError:
                pass
        self._dong()

    def _dong(self):
        if self._tep is not None:
            try:
                self._tep.close()
            except OSError:
                pass
            self._tep = None

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.nha_khoa()
        return False
