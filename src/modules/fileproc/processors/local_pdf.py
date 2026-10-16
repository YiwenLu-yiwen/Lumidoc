"""使用内置 PDF 文本层和本地 OCR 模型提取内容，无需联网下载版面模型。"""
from pathlib import Path

import numpy as np
import pypdfium2 as pdfium
from rapidocr_onnxruntime import RapidOCR


def extract_pdf_locally(file_path: str, models_path: str) -> dict:
    document = pdfium.PdfDocument(file_path)
    pages = []
    engine = None
    try:
        page_count = len(document)
        for page in document:
            try:
                text_page = page.get_textpage()
                try:
                    text = text_page.get_text_range().strip()
                finally:
                    text_page.close()
                if not text:
                    if engine is None:
                        root = Path(models_path)
                        # The wheel includes OCR models, so clean clones need no
                        # ignored local assets. Explicit complete overrides remain supported.
                        model_paths = {
                            'det_model_path': root / 'PP-OCRv4/ch_PP-OCRv4_det_infer.onnx',
                            'rec_model_path': root / 'PP-OCRv4/ch_PP-OCRv4_rec_server_infer.onnx',
                            'cls_model_path': root / 'PP-OCRv3/ch_ppocr_mobile_v2.0_cls_train.onnx',
                        }
                        overrides = (
                            {key: str(path) for key, path in model_paths.items()}
                            if all(path.is_file() for path in model_paths.values()) else {}
                        )
                        engine = RapidOCR(
                            **overrides,
                            intra_op_num_threads=2,
                            inter_op_num_threads=1,
                            print_verbose=False,
                        )
                    bitmap = page.render(scale=2)
                    try:
                        pixels = np.asarray(bitmap.to_pil().convert('RGB'))[:, :, ::-1].copy()
                        result, _ = engine(pixels)
                        text = '\n'.join(line[1] for line in (result or []))
                    finally:
                        bitmap.close()
                if text:
                    pages.append(text)
            finally:
                page.close()
        if not pages:
            raise ValueError('PDF 中未识别到可用文本')
        return {
            'success': True,
            'content': '\n\n--- PAGE BREAK ---\n\n'.join(pages),
            'page_count': page_count,
            'metadata': {'ocr_enabled': engine is not None, 'processor': 'local_pdf'},
        }
    finally:
        document.close()
