# -*- coding: utf-8 -*-
"""Ghi lich su theo thang vao ROOT/history/yyyy-mm.log.

Moi ban ghi la mot dong JSON; ban ghi moi nhat nam tren cung. Ten file lay theo
thang cua thoi diem ghi, khong phai thang bat dau luot chay. Chi mot noi ghi log
de tranh hai writer cung sua mot file.
"""
import json
import os
from datetime import datetime
from pathlib import Path


def duong_dan_thang(thu_muc_history, thoi_diem):
    """Tra ve duong dan file log ung voi thang cua thoi_diem."""
    return Path(thu_muc_history) / f"{thoi_diem.strftime('%Y-%m')}.log"


def ghi(thu_muc_history, ban_ghi):
    """Them mot ban ghi len dau file log thang hien tai, tra ve duong dan log.

    Ghi vao file tam cung thu muc roi os.replace de tranh hong log neu dung giua
    chung. Chi nap phan log cu de noi xuong duoi; log du an nho nen chi phi chap
    nhan duoc cho MVP.
    """
    thu_muc_history = Path(thu_muc_history)
    thu_muc_history.mkdir(parents=True, exist_ok=True)
    thoi_diem = datetime.now().astimezone()

    ban_ghi = dict(ban_ghi)
    ban_ghi.setdefault('thoi_gian', thoi_diem.isoformat(timespec='seconds'))
    dong_moi = json.dumps(ban_ghi, ensure_ascii=False)

    duong_dan = duong_dan_thang(thu_muc_history, thoi_diem)
    noi_dung_cu = ''
    if duong_dan.exists():
        noi_dung_cu = duong_dan.read_text(encoding='utf-8')

    tam = duong_dan.with_name(duong_dan.name + '.tmp')
    with open(tam, 'w', encoding='utf-8', newline='\n') as f:
        f.write(dong_moi + '\n')
        if noi_dung_cu:
            f.write(noi_dung_cu)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tam, duong_dan)
    return duong_dan
