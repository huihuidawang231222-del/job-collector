"""Local PDF text extraction; no model calls, OCR, or file persistence."""
import hashlib
import io

from pypdf import PdfReader

MAX_BYTES = 10 * 1024 * 1024
MAX_PAGES = 20
MAX_TEXT = 12000


def parse_resume(data, filename):
    if not data or len(data) > MAX_BYTES:
        raise ValueError('PDF 不能为空，且不能超过10MB')
    if not data.startswith(b'%PDF-'):
        raise ValueError('文件不是有效的 PDF，请勿仅修改文件扩展名')
    try:
        reader = PdfReader(io.BytesIO(data))
        if reader.is_encrypted:
            raise ValueError('暂不支持加密PDF，请使用原软件导出未加密副本')
        count = len(reader.pages)
        if not 1 <= count <= MAX_PAGES:
            raise ValueError('简历PDF需包含1至20页')
        pages = [{'page': index + 1,
                  'text': (page.extract_text(extraction_mode='layout') or '').strip()}
                 for index, page in enumerate(reader.pages)]
    except ValueError:
        raise
    except Exception:
        raise ValueError('PDF损坏或不受支持，请重新导出后上传') from None
    text = '\n\n'.join(f"[第{p['page']}页]\n{p['text']}" for p in pages if p['text'])
    if len(text) > MAX_TEXT:
        raise ValueError('提取文字超过12000字符，请上传精简版简历；未截断或发送内容')
    empty_pages = [p['page'] for p in pages if not p['text']]
    warnings = []
    if empty_pages:
        warnings.append('以下页面未提取到文字，可能为扫描图片或字体编码不受支持，需要OCR或人工补录：' + '、'.join(map(str, empty_pages)))
    if text and len(''.join(p['text'] for p in pages).strip()) < 30:
        warnings.append('提取文字过少，可能仅识别了页码或页眉；请核对是否缺少简历主体。')
    return dict(filename=filename, sha256=hashlib.sha256(data).hexdigest(),
                page_count=count, pages=pages, text=text, warnings=warnings,
                parser='pypdf', status='已提取文字，待人工核对' if text else '未提取到文字，需要OCR或人工补录')
