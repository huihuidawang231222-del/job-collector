import io
import unittest

from pypdf import PdfWriter
from pypdf.generic import DictionaryObject, NameObject, DecodedStreamObject, ArrayObject, NumberObject, TextStringObject

from resume_pdf import parse_resume, MAX_BYTES


def synthetic_pdf(texts, encrypted=False):
    """In-memory fixtures with a standard Chinese Type0 font mapping."""
    writer = PdfWriter()
    font = DictionaryObject({
        NameObject('/Type'): NameObject('/Font'),
        NameObject('/Subtype'): NameObject('/Type0'),
        NameObject('/BaseFont'): NameObject('/STSong-Light'),
        NameObject('/Encoding'): NameObject('/UniGB-UCS2-H'),
        NameObject('/DescendantFonts'): ArrayObject([DictionaryObject({
            NameObject('/Type'): NameObject('/Font'),
            NameObject('/Subtype'): NameObject('/CIDFontType0'),
            NameObject('/BaseFont'): NameObject('/STSong-Light'),
            NameObject('/CIDSystemInfo'): DictionaryObject({
                NameObject('/Registry'): TextStringObject('Adobe'),
                NameObject('/Ordering'): TextStringObject('GB1'),
                NameObject('/Supplement'): NumberObject(4),
            }),
        })]),
    })
    for text in texts:
        page = writer.add_blank_page(width=595, height=842)
        if text:
            page[NameObject('/Resources')] = DictionaryObject({
                NameObject('/Font'): DictionaryObject({NameObject('/F1'): font})})
            stream = DecodedStreamObject()
            stream.set_data(('BT /F1 12 Tf 40 780 Td <' + text.encode('utf-16-be').hex() + '> Tj ET').encode())
            page[NameObject('/Contents')] = stream
    if encrypted:
        writer.encrypt('synthetic-test-password')
    output = io.BytesIO()
    writer.write(output)
    return output.getvalue()


class ResumeTests(unittest.TestCase):
    def test_chinese_text_and_page_provenance(self):
        source = '合成测试简历 本科 Python SQL 数据分析 项目经历仅用于测试'
        data = synthetic_pdf([source, '第二页 这是合成的工作经历，不代表真实用户信息'])
        parsed = parse_resume(data, 'synthetic.pdf')
        self.assertEqual(parsed['page_count'], 2)
        self.assertIn(source, parsed['text'])
        self.assertIn('[第2页]', parsed['text'])
        self.assertEqual(parsed['pages'][0]['page'], 1)
        self.assertEqual(parsed['warnings'], [])
        self.assertEqual(len(parsed['sha256']), 64)

    def test_no_text_and_partial_text_are_explicit(self):
        blank = parse_resume(synthetic_pdf(['']), 'blank.pdf')
        self.assertEqual(blank['text'], '')
        self.assertIn('OCR', blank['status'])
        partial = parse_resume(synthetic_pdf(['完整测试简历 本科 SQL 数据分析 项目经历全部为合成示例', '']), 'partial.pdf')
        self.assertTrue(partial['warnings'])
        self.assertIn('2', partial['warnings'][0])

    def test_invalid_encrypted_and_oversize_inputs(self):
        for data in [b'', b'not a PDF', b'%PDF-broken', b'%PDF-' + b'x' * MAX_BYTES,
                     synthetic_pdf(['test'], encrypted=True), synthetic_pdf([''] * 21)]:
            with self.subTest(size=len(data)):
                with self.assertRaises(ValueError):
                    parse_resume(data, 'invalid.pdf')


if __name__ == '__main__':
    unittest.main()
