# -*- coding: utf-8 -*-
"""数据契约校验: 10列 v1.1.0"""
import json, csv, os, sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCHEMA_PATH = os.path.join(BASE, "schemas", "recruit.tsv.json")

def load_schema():
    with open(SCHEMA_PATH, encoding="utf-8") as f:
        return json.load(f)

def validate_row(row, schema):
    """校验单行"""
    errors = []
    cols = schema["columns"]
    if len(row) != len(cols):
        errors.append("列数错误: 期望" + str(len(cols)) + "列, 实际" + str(len(row)) + "列")
        return errors
    for i, col in enumerate(cols):
        val = row[i] if i < len(row) else ""
        if col["required"] and not val:
            errors.append("第" + str(i+1) + "列" + col["name"] + ": 值为空")
            continue
        if col["type"] == "enum" and val and val not in col["values"]:
            errors.append("第" + str(i+1) + "列" + col["name"] + ": " + val + " 不在枚举中")
        if col["type"] == "int" and val:
            try:
                v = int(val)
                if "min" in col and v < col["min"]:
                    errors.append("第" + str(i+1) + "列" + col["name"] + ": " + str(v) + " < min")
                if "max" in col and v > col["max"]:
                    errors.append("第" + str(i+1) + "列" + col["name"] + ": " + str(v) + " > max")
            except ValueError:
                errors.append("第" + str(i+1) + "列" + col["name"] + ": " + val + " 不是整数")
    return errors

def test_schema_valid():
    """校验数据契约文件本身"""
    schema = load_schema()
    assert schema["version"] == "1.1.0"
    assert len(schema["columns"]) == 10
    assert schema["columns"][9]["name"] == "company_tier"
    print("[PASS] 契约版本 " + schema["version"] + ", " + str(len(schema["columns"])) + "列, 第10列=" + schema["columns"][9]["name"])

def test_data_file():
    """校验 recruit_clean.tsv"""
    schema = load_schema()
    data_file = os.path.join(BASE, "data", "clean", "recruit_clean.tsv")
    if not os.path.exists(data_file):
        print("[SKIP] " + data_file + " 不存在, 跳过数据校验")
        return
    errors_all = []
    with open(data_file, encoding="utf-8") as f:
        reader = csv.reader(f, delimiter="\t")
        for i, row in enumerate(reader):
            if i == 0:
                continue  # skip header
            errs = validate_row(row, schema)
            if errs:
                errors_all.append("行" + str(i+1) + ": " + "; ".join(errs))
    if errors_all:
        print("[FAIL] 发现 " + str(len(errors_all)) + " 行错误:")
        for e in errors_all[:5]:
            print("  " + e)
        assert False, "数据契约校验失败"
    print("[PASS] 数据契约校验通过")

if __name__ == "__main__":
    test_schema_valid()
    test_data_file()
