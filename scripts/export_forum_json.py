# -*- coding: utf-8 -*-
"""把 src/serving/forum_data.py 的论坛内容导出为 JSON。

背景（两分支合并）：
    origin/main 分支的求职论坛（forum.html / article.html）原本由 Python 服务
    serve_website.py 提供 /api/forum/* 接口，而 codex/admin-account-security
    分支的网站主服务是 Spring Boot。合并后统一由 Spring Boot 提供接口，
    因此把 Python 侧的论坛数据固化成 JSON，供 ForumController 读取。

用法：
    python scripts/export_forum_json.py

输出：
    day08-backend/src/main/resources/forum-data.json
"""
import importlib.util
import json
import os
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
SOURCE = ROOT / "src" / "serving" / "forum_data.py"
TARGET = ROOT / "day08-backend" / "src" / "main" / "resources" / "forum-data.json"


def load_forum_data():
    """直接按文件路径加载，避免依赖 src/serving 的包结构。"""
    if not SOURCE.exists():
        print(f"[ERROR] 找不到论坛数据源：{SOURCE}")
        sys.exit(1)
    spec = importlib.util.spec_from_file_location("forum_data", SOURCE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main():
    fd = load_forum_data()
    articles = fd.FORUM_ARTICLES
    payload = {
        "categories": fd.FORUM_CATEGORIES,
        "articles": articles,
        "comments": fd.FORUM_COMMENTS,
    }
    TARGET.parent.mkdir(parents=True, exist_ok=True)
    with open(TARGET, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=1)
        handle.write("\n")

    comment_total = sum(len(v) for v in fd.FORUM_COMMENTS.values())
    print(f"[OK] 导出 {len(articles)} 篇文章 / {len(fd.FORUM_CATEGORIES)} 个分类 / "
          f"{comment_total} 条评论")
    print(f"[OK] 写入 {TARGET}")
    # 逐个校验，避免静默写坏
    with open(TARGET, "r", encoding="utf-8") as handle:
        check = json.load(handle)
    assert len(check["articles"]) == len(articles), "文章数量不一致"
    assert check["categories"] == fd.FORUM_CATEGORIES, "分类不一致"
    print("[OK] 回读校验通过")


if __name__ == "__main__":
    main()
