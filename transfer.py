"""Read native or Chinese exports without coercing textual job fields."""
import csv
import io
import json
import re

from classify import EXPORT_COLUMNS


def csv_cell(value):
    if isinstance(value, str) and re.match(r"^'*\s*[=+\-@]", value):
        return "'" + value
    return value


def read_import(data, filename):
    text = data.decode('utf-8-sig')
    is_csv = filename.lower().endswith('.csv')
    if is_csv:
        records = list(csv.DictReader(io.StringIO(text)))
    else:
        records = json.loads(text)
    if not isinstance(records, list) or any(not isinstance(r, dict) for r in records):
        raise ValueError('JSON 必须是对象数组')
    aliases = {label: key for key, label in EXPORT_COLUMNS.items()}
    output = []
    for record in records:
        if 'title' not in record and '岗位名称' not in record:
            raise ValueError('缺少 title 或 岗位名称 列')
        row = {}
        for key, value in record.items():
            if key is None or isinstance(value, (dict, list)):
                raise ValueError('字段必须是单个值，CSV 每行列数应与表头一致')
            if is_csv and key in aliases and isinstance(value, str) and re.match(r"^'+\s*[=+\-@]", value):
                value = value[1:]
            target = aliases.get(key, key)
            if target in row and row[target] != value:
                raise ValueError(f'中英文列冲突：{target}')
            row[target] = value
        output.append(row)
    return output
