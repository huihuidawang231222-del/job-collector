import csv
import io
import json
import tempfile
import unittest
from pathlib import Path

import core
from classify import export_rows
from transfer import csv_cell, read_import


class TransferTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.previous = core.DB
        core.DB = Path(self.temp.name) / 'jobs.sqlite3'
        self.row = dict(title='分析师', company='NA', salary='8-12K',
                        location='广州·天河区', source='测试',
                        url='https://example.com/jobs/001',
                        jd='本科，SQL，完整 JD\n第二行', industry_raw='机械制造',
                        benefits='五险一金', raw='双休', search_keyword='分析')

    def tearDown(self):
        core.DB = self.previous
        self.temp.cleanup()

    def test_partial_update_preserves_details_and_refreshes_salary(self):
        core.save([self.row])
        first = core.load()[0]['first_seen']
        core.save([dict(title='高级分析师', url=self.row['url'],
                        salary='10-15K', jd='', industry_raw=None)])
        updated = core.load()[0]
        for key in ['jd', 'industry_raw', 'benefits', 'company', 'raw']:
            self.assertEqual(updated[key], self.row[key])
        self.assertEqual(updated['title'], '高级分析师')
        self.assertEqual(updated['salary_min'], 10000)
        self.assertEqual(updated['first_seen'], first)
        core.save([dict(title='高级分析师', url=self.row['url'], jd='新JD')])
        self.assertEqual(core.load()[0]['jd'], '新JD')

    def test_chinese_csv_and_json_roundtrip(self):
        core.save([self.row])
        original = core.load()[0]
        exported = export_rows([original])
        stream = io.StringIO(newline='')
        writer = csv.DictWriter(stream, fieldnames=exported[0])
        writer.writeheader()
        writer.writerows({k: csv_cell(v) for k, v in r.items()} for r in exported)
        files = [(stream.getvalue().encode('utf-8-sig'), 'JOBS.CSV'),
                 (json.dumps(exported, ensure_ascii=False).encode(), 'jobs.json')]
        for data, filename in files:
            with self.subTest(filename=filename):
                self.assertEqual(core.save(read_import(data, filename)), (0, 1, 0))
                self.assertEqual(len(core.load()), 1)
                for key in self.row:
                    self.assertEqual(core.load()[0][key], original[key])
                self.assertEqual(core.load()[0]['first_seen'], original['first_seen'])
        core.DB = Path(self.temp.name) / 'restored.sqlite3'
        core.save(read_import(files[0][0], 'jobs.csv'))
        self.assertEqual(core.load()[0]['first_seen'], original['first_seen'])

    def test_formula_escaping_is_reversible(self):
        for value in ['=1+1', ' +cmd', '@SUM(A1)', "'=literal", "''-literal", '普通文字']:
            with self.subTest(value=value):
                stream = io.StringIO(newline='')
                writer = csv.writer(stream)
                writer.writerow(['岗位名称', '公司'])
                writer.writerow(['分析师', csv_cell(value)])
                restored = read_import(stream.getvalue().encode(), 'jobs.csv')
                self.assertEqual(restored[0]['company'], value)

    def test_english_import_keeps_text_and_rejects_bad_shapes(self):
        rows = read_import(b'title,company,location\nAnalyst,NA,001\n', 'jobs.csv')
        self.assertEqual(rows[0]['company'], 'NA')
        self.assertEqual(rows[0]['location'], '001')
        for data, name in [(b'{}', 'jobs.json'), (b'[{"company":"x"}]', 'jobs.json'),
                           (b'title\na,b\n', 'jobs.csv')]:
            with self.assertRaises(ValueError):
                read_import(data, name)


if __name__ == '__main__':
    unittest.main()
