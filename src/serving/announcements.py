"""Announcement storage for the single-process local demo server."""
import json
import os
from pathlib import Path
import re
import tempfile
import threading
import time
import uuid


class AnnouncementError(Exception):
    def __init__(self, status, message):
        super().__init__(message)
        self.status = status


def pagination(value, maximum):
    if not isinstance(value, str) or not re.fullmatch(r"[0-9]+", value) or len(value) > 10:
        raise AnnouncementError(400, "分页参数不正确")
    number = int(value)
    if not 1 <= number <= maximum:
        raise AnnouncementError(400, "分页参数不正确")
    return number


def content(data):
    if not isinstance(data, dict):
        raise AnnouncementError(400, "标题和正文不能为空")
    result = {}
    for key, label, maximum in (("title", "标题", 100), ("body", "正文", 10000)):
        value = data.get(key)
        if not isinstance(value, str):
            raise AnnouncementError(400, label + "必须为文本")
        value = value.strip()
        if not 1 <= len(value) <= maximum:
            raise AnnouncementError(400, f"{label}须为 1–{maximum} 字")
        # Reject invalid Unicode before reaching the filesystem encoder.
        try:
            value.encode("utf-8")
        except UnicodeError as error:
            raise AnnouncementError(400, "文本编码不正确") from error
        result[key] = value
    return result


class AnnouncementStore:
    def __init__(self, path, now=None):
        self.path = Path(path)
        self.lock = threading.RLock()
        self.now = now or (lambda: int(time.time() * 1000))

    def _read(self):
        try:
            with self.path.open(encoding="utf-8") as source:
                rows = json.load(source)
            if not isinstance(rows, list):
                raise ValueError()
            ids = set()
            for row in rows:
                if not isinstance(row, dict) or not all(isinstance(row.get(key), str) for key in
                        ("id", "title", "body", "author", "publishedAt", "updatedAt")):
                    raise ValueError()
                if not row["id"] or row["id"] in ids:
                    raise ValueError()
                content(row)
                int(row["publishedAt"]); int(row["updatedAt"])
                ids.add(row["id"])
            return rows
        except FileNotFoundError:
            return []
        except (OSError, ValueError, UnicodeError, AnnouncementError) as error:
            raise AnnouncementError(503, "公告存储不可用，请稍后重试") from error

    def _write(self, rows):
        temporary = None
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=self.path.parent,
                                             prefix=".announcements-", suffix=".tmp", delete=False) as target:
                temporary = target.name
                json.dump(rows, target, ensure_ascii=False, indent=2)
                target.flush()
                os.fsync(target.fileno())
            os.replace(temporary, self.path)
        except (OSError, ValueError, UnicodeError) as error:
            raise AnnouncementError(503, "公告保存失败，请稍后重试") from error
        finally:
            if temporary and os.path.exists(temporary):
                try:
                    os.unlink(temporary)
                except OSError:
                    pass

    @staticmethod
    def _public(row, with_body=True):
        item = {key: row[key] for key in ("id", "title", "publishedAt", "updatedAt")}
        item["author"] = "管理员"
        if with_body:
            item["body"] = row["body"]
        return item

    @staticmethod
    def _find(rows, identifier):
        for row in rows:
            if row["id"] == identifier:
                return row
        raise AnnouncementError(404, "公告不存在或已删除")

    def list(self, page="1", size="10"):
        page, size = pagination(page, 2147483647), pagination(size, 50)
        with self.lock:
            rows = sorted(self._read(), key=lambda row: (int(row["publishedAt"]), row["id"]), reverse=True)
            start = (page - 1) * size
            return {"code": 0, "items": [self._public(row, False) for row in rows[start:start + size]],
                    "total": len(rows), "page": page, "size": size}

    def detail(self, identifier):
        with self.lock:
            return self._public(self._find(self._read(), identifier))

    def create(self, data, author):
        row = content(data)
        with self.lock:
            rows = self._read()
            now = str(self.now())
            row.update(id=str(uuid.uuid4()), author=author, publishedAt=now, updatedAt=now)
            self._write(rows + [row])
            return self._public(row)

    def update(self, identifier, data):
        values = content(data)
        with self.lock:
            rows = self._read()
            row = self._find(rows, identifier)
            row.update(values, updatedAt=str(self.now()))
            self._write(rows)
            return self._public(row)

    def delete(self, identifier):
        with self.lock:
            rows = self._read()
            self._find(rows, identifier)
            self._write([row for row in rows if row["id"] != identifier])
