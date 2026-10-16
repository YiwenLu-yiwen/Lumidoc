"""本地 PDF 提取无需下载版面模型，并能处理混合扫描页。"""
import importlib.util
import os
from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest


def load_module():
    path = Path(os.environ.get('LUMIDOC_ROOT', Path(__file__).resolve().parents[1])) / 'src/modules/fileproc/processors/local_pdf.py'
    spec = importlib.util.spec_from_file_location('local_pdf', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_mixed_pdf_preserves_native_text_and_scans_image_pages():
    module = load_module()
    native, scanned = MagicMock(), MagicMock()
    native.get_textpage.return_value.get_text_range.return_value = 'Original searchable text'
    scanned.get_textpage.return_value.get_text_range.return_value = ''
    document = MagicMock()
    document.__iter__.return_value = iter([native, scanned])
    document.__len__.return_value = 2
    import numpy as np
    scanned.render.return_value.to_pil.return_value.convert.return_value = np.zeros((2, 2, 3), dtype=np.uint8)
    engine = MagicMock(return_value=([[[0], 'Scanned inspection checklist', 0.99]], [0.1]))
    with patch.object(module.pdfium, 'PdfDocument', return_value=document), patch.object(module, 'RapidOCR', return_value=engine) as factory:
        result = module.extract_pdf_locally('test.pdf', '/models')
    assert result['page_count'] == 2
    assert 'Original searchable text' in result['content']
    assert 'Scanned inspection checklist' in result['content']
    native.render.assert_not_called()
    engine.assert_called_once()
    assert 'det_model_path' not in factory.call_args.kwargs  # bundled wheel models
    document.close.assert_called_once()


def test_blank_scanned_pdf_is_not_reported_as_success():
    module = load_module()
    page = MagicMock()
    page.get_textpage.return_value.get_text_range.return_value = ''
    document = MagicMock()
    document.__iter__.return_value = iter([page])
    document.__len__.return_value = 1
    import numpy as np
    page.render.return_value.to_pil.return_value.convert.return_value = np.zeros((2, 2, 3), dtype=np.uint8)
    with patch.object(module.pdfium, 'PdfDocument', return_value=document), patch.object(module, 'RapidOCR', return_value=MagicMock(return_value=(None, []))):
        with pytest.raises(ValueError, match='未识别到'):
            module.extract_pdf_locally('blank.pdf', '/models')
    document.close.assert_called_once()
