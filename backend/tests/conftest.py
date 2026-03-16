import pytest
import sys
from pathlib import Path
from unittest.mock import MagicMock, AsyncMock, patch

sys.path.insert(0, str(Path(__file__).parent.parent.parent))


@pytest.fixture
def mock_settings():
    with patch('backend.config.settings') as mock:
        mock.KOKORO_URL = "http://localhost:8880"
        mock.REDIS_URL = "redis://localhost:6379"
        mock.GROQ_API_KEY = "test_key"
        mock.GEMINI_API_KEY = "test_key"
        mock.OLLAMA_URL = "http://localhost:11434"
        mock.DEFAULT_LLM_MODE = "groq"
        mock.DATABASE_PATH = ":memory:"
        mock.OUTPUT_DIR = "/tmp/fabot_test/output"
        mock.UPLOAD_DIR = "/tmp/fabot_test/uploads"
        mock.MAX_UPLOAD_MB = 50
        mock.LOG_LEVEL = "INFO"
        mock.LOG_FILE = "/tmp/fabot_test.log"
        yield mock


@pytest.fixture
def sample_text():
    return """Python é uma linguagem de programação de alto nível.
É amplamente usada em ciência de dados e machine learning.
Sua sintaxe simples facilita o aprendizado."""


@pytest.fixture
def sample_pdf_path(tmp_path):
    pdf_content = b"""%PDF-1.4
1 0 obj
<< /Type /Catalog /Pages 2 0 R >>
endobj
2 0 obj
<< /Type /Pages /Kids [3 0 R] /Count 1 >>
endobj
3 0 obj
<< /Type /Page /Parent 2 0 R /Resources << /Font << /F1 << /Type /Font /Subtype /Type1 /BaseFont /Helvetica >> >> >> /MediaBox [0 0 612 792] /Contents 4 0 R >>
endobj
4 0 obj
<< /Length 100 >>
stream
BT
/F1 12 Tf
100 700 Td
(Test PDF content for testing) Tj
ET
endstream
endobj
xref
0 5
0000000000 65535 f
0000000009 00000 n
0000000058 00000 n
0000000115 00000 n
0000000214 00000 n
trailer
<< /Size 5 /Root 1 0 R >>
startxref
310
%%EOF"""
    pdf_path = tmp_path / "test.pdf"
    pdf_path.write_bytes(pdf_content)
    return pdf_path


@pytest.fixture
def sample_docx_path(tmp_path):
    docx_content = b"PK\x03\x04\x14\x00\x00\x00\x08\x00"
    docx_path = tmp_path / "test.docx"
    docx_path.write_bytes(docx_content)
    return docx_path


@pytest.fixture
def sample_txt_path(tmp_path):
    txt_path = tmp_path / "test.txt"
    txt_path.write_text("Este é um arquivo de teste.\nCom várias linhas.\nPara testes do ingestor.", encoding='utf-8')
    return txt_path
