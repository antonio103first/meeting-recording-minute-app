"""
회의녹음요약 v3 - 파일 저장 관리
v3 변경: 3폴더 분리 저장 (MP3 / STT .md / 회의록 .md)
v3.1: F-02 프린트 고도화 — Markdown → HTML 렌더링 후 인쇄
"""
import os
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from config import MP3_SAVE_DIR, STT_SAVE_DIR, SUMMARY_SAVE_DIR
# 하위 호환 alias
AUDIO_SAVE_DIR = MP3_SAVE_DIR


def get_default_base_name() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def save_stt_text(text: str, save_dir: str, file_name: str) -> tuple:
    """STT 변환본을 .txt 파일로 저장"""
    try:
        path = Path(save_dir)
        path.mkdir(parents=True, exist_ok=True)
        stem = file_name if not file_name.endswith((".txt", ".md")) else Path(file_name).stem
        out = path / (stem + ".txt")
        out.write_text(text, encoding="utf-8")
        return True, str(out)
    except Exception as e:
        return False, f"STT 파일 저장 실패: {e}"


def save_summary_text(text: str, save_dir: str, file_name: str) -> tuple:
    """회의록 요약을 .md 파일로 저장"""
    try:
        path = Path(save_dir)
        path.mkdir(parents=True, exist_ok=True)
        stem = file_name if not file_name.endswith((".txt", ".md")) else Path(file_name).stem
        out = path / (stem + ".md")
        out.write_text(text, encoding="utf-8")
        return True, str(out)
    except Exception as e:
        return False, f"요약 파일 저장 실패: {e}"


def copy_audio_to_save_dir(src_path: str, save_dir: str, file_name: str) -> tuple:
    try:
        path = Path(save_dir)
        path.mkdir(parents=True, exist_ok=True)
        ext = Path(src_path).suffix
        out = path / (file_name + ext)
        shutil.copy2(src_path, str(out))
        return True, str(out)
    except Exception as e:
        return False, f"오디오 파일 복사 실패: {e}"


def get_file_size_mb(file_path: str) -> float:
    try:
        return os.path.getsize(file_path) / 1024 / 1024
    except Exception:
        return 0.0


def list_audio_files() -> list:
    """MP3 저장 폴더에서 오디오 파일 목록 반환"""
    files = []
    for ext in [".mp3", ".wav", ".m4a", ".mp4", ".ogg", ".flac"]:
        for f in Path(MP3_SAVE_DIR).rglob(f"*{ext}"):
            files.append(str(f))
    return sorted(files, reverse=True)


def list_stt_files() -> list:
    """STT 변환본 .md 파일 목록 반환"""
    files = []
    for ext in [".md", ".txt"]:
        for f in Path(STT_SAVE_DIR).rglob(f"*{ext}"):
            files.append(str(f))
    return sorted(files, reverse=True)


def list_summary_files() -> list:
    """회의록 요약 .md 파일 목록 반환"""
    files = []
    for ext in [".md", ".txt"]:
        for f in Path(SUMMARY_SAVE_DIR).rglob(f"*{ext}"):
            files.append(str(f))
    return sorted(files, reverse=True)


def open_file_in_explorer(file_path: str):
    """파일 탐색기에서 파일 위치 열기 (선택 상태로)"""
    try:
        path = Path(file_path)
        if sys.platform == "win32":
            if path.is_file():
                subprocess.Popen(["explorer", "/select,", str(path)])
            else:
                subprocess.Popen(["explorer", str(path)])
        elif sys.platform == "darwin":
            subprocess.Popen(["open", "-R", str(path)])
        else:
            subprocess.Popen(["xdg-open", str(path.parent)])
    except Exception:
        pass


# ── F-02: Markdown → HTML 렌더링 ─────────────────────────

_PRINT_HTML_CSS = """
<style>
  body {
    font-family: 'Malgun Gothic', '맑은 고딕', 'NanumGothic', sans-serif;
    font-size: 11pt;
    line-height: 1.7;
    max-width: 800px;
    margin: 0 auto;
    padding: 20px 30px;
    color: #222;
  }
  h1 { font-size: 18pt; border-bottom: 2px solid #333; padding-bottom: 6px; }
  h2 { font-size: 14pt; border-bottom: 1px solid #aaa; padding-bottom: 4px; margin-top: 20px; }
  h3 { font-size: 12pt; margin-top: 14px; }
  table { border-collapse: collapse; width: 100%; margin: 12px 0; }
  th, td { border: 1px solid #ccc; padding: 6px 10px; text-align: left; }
  th { background: #f0f0f0; font-weight: bold; }
  code { background: #f5f5f5; padding: 2px 5px; font-family: monospace; font-size: 10pt; }
  pre  { background: #f5f5f5; padding: 10px; overflow-x: auto; }
  blockquote { border-left: 3px solid #aaa; margin-left: 10px; padding-left: 12px; color: #555; }
  hr { border: none; border-top: 1px solid #ddd; margin: 16px 0; }
  @media print {
    body { margin: 0; padding: 15px 20px; }
    h1 { page-break-after: avoid; }
    h2 { page-break-after: avoid; }
  }
</style>
"""


def convert_md_to_html(md_text: str, title: str = "회의록") -> str:
    """
    Markdown 텍스트를 인쇄용 HTML 문자열로 변환.
    markdown 패키지 사용 (없으면 기본 텍스트 폴백).
    """
    try:
        import markdown as md_lib
        body = md_lib.markdown(
            md_text,
            extensions=["tables", "fenced_code", "nl2br"],
        )
    except ImportError:
        # markdown 패키지 미설치 시 — 줄바꿈만 변환
        import html as html_lib
        escaped = html_lib.escape(md_text)
        body = "<pre style='white-space:pre-wrap;font-family:inherit'>" + escaped + "</pre>"

    return (
        "<!DOCTYPE html><html><head>"
        f"<meta charset='utf-8'><title>{title}</title>"
        f"{_PRINT_HTML_CSS}"
        "</head><body>"
        f"{body}"
        "</body></html>"
    )


def save_as_html(md_text: str, out_path: str, title: str = "회의록") -> tuple:
    """Markdown 파일을 HTML 파일로 변환 저장"""
    try:
        html = convert_md_to_html(md_text, title)
        Path(out_path).write_text(html, encoding="utf-8")
        return True, out_path
    except Exception as e:
        return False, f"HTML 변환 실패: {e}"


def print_file(file_path: str) -> tuple:
    """
    파일 인쇄 (F-02 고도화):
      - .md / .txt  → HTML 변환 후 기본 브라우저 인쇄 다이얼로그
      - .html       → 기본 브라우저 인쇄 다이얼로그
      - 기타(.pdf 등) → OS 기본 앱 인쇄 동사
    """
    try:
        fpath = Path(file_path)
        if not fpath.exists():
            return False, f"파일을 찾을 수 없습니다: {file_path}"

        suffix = fpath.suffix.lower()

        # ── .md / .txt → HTML 렌더링 후 인쇄 ──────────────
        if suffix in (".md", ".txt"):
            md_text = fpath.read_text(encoding="utf-8")
            html_str = convert_md_to_html(md_text, title=fpath.stem)

            # 임시 HTML 파일 생성 (앱 데이터 폴더)
            from config import APP_DATA_DIR
            tmp_dir = Path(APP_DATA_DIR)
            tmp_dir.mkdir(parents=True, exist_ok=True)
            tmp_html = tmp_dir / f"_print_{fpath.stem}.html"
            tmp_html.write_text(html_str, encoding="utf-8")
            file_to_print = str(tmp_html)
        else:
            file_to_print = file_path

        # ── OS별 인쇄 ────────────────────────────────────
        if sys.platform == "win32":
            # Windows: ShellExecute 'print' 동사 → 기본 앱 인쇄 다이얼로그
            import ctypes
            ret = ctypes.windll.shell32.ShellExecuteW(
                None, "print", file_to_print, None, None, 1)
            if ret <= 32:
                # ShellExecute 실패 시 폴백: 기본 앱으로 열기
                os.startfile(file_to_print)
            return True, "인쇄 다이얼로그를 열었습니다."
        elif sys.platform == "darwin":
            subprocess.Popen(["lpr", file_to_print])
            return True, "인쇄 요청 완료"
        else:
            subprocess.Popen(["lpr", file_to_print])
            return True, "인쇄 요청 완료"

    except Exception as e:
        return False, f"인쇄 실패: {e}"


def export_pdf(md_text: str, out_path: str, title: str = "회의록") -> tuple:
    """
    Markdown → PDF 변환.
    방법 1: fpdf2 + 맑은 고딕 (한글 지원, PyInstaller 호환)
    방법 2: weasyprint (설치된 경우)
    방법 3: 폴백 — HTML 파일 저장
    """
    # ── 방법 1: fpdf2 ─────────────────────────────────────
    try:
        from fpdf import FPDF  # type: ignore

        # 한글 폰트 경로 탐색 (Windows 시스템 폰트)
        _font_candidates = [
            r"C:\Windows\Fonts\malgun.ttf",       # 맑은 고딕
            r"C:\Windows\Fonts\malgunbd.ttf",     # 맑은 고딕 Bold
            r"C:\Windows\Fonts\NanumGothic.ttf",  # 나눔고딕 (설치된 경우)
        ]
        _font_path = next((p for p in _font_candidates if os.path.exists(p)), None)

        pdf = FPDF()
        pdf.set_auto_page_break(auto=True, margin=15)
        pdf.add_page()
        pdf.set_margins(20, 20, 20)

        if _font_path:
            pdf.add_font("KR", style="",  fname=_font_path)
            pdf.add_font("KR", style="B", fname=_font_path)
            _fam = "KR"
        else:
            _fam = "Helvetica"

        # 제목
        pdf.set_font(_fam, style="B", size=16)
        pdf.cell(0, 12, title, ln=True, align="C")
        pdf.ln(4)

        # Markdown → 줄별 렌더링
        import re as _re
        for raw in md_text.split("\n"):
            line = raw.rstrip()

            # 헤더 처리 (# ~ ###)
            h = _re.match(r'^(#{1,3})\s+(.*)', line)
            if h:
                level = len(h.group(1))
                text  = h.group(2).strip()
                size  = 14 - (level - 1) * 2  # 14 / 12 / 10
                pdf.ln(2)
                pdf.set_font(_fam, style="B", size=size)
                pdf.multi_cell(0, 7, text)
                pdf.ln(1)
                continue

            # 굵게 **text** → 볼드 처리 (간략화: 마커 제거 후 볼드)
            if _re.search(r'\*\*', line):
                line = _re.sub(r'\*\*(.*?)\*\*', r'\1', line)
                pdf.set_font(_fam, style="B", size=10)
            else:
                pdf.set_font(_fam, style="", size=10)

            # 이탤릭 제거
            line = _re.sub(r'\*(.*?)\*', r'\1', line)

            # 불릿 리스트
            if _re.match(r'^\s*[-*]\s+', line):
                line = _re.sub(r'^\s*[-*]\s+', '• ', line)

            if line.strip():
                pdf.multi_cell(0, 6, line)
            else:
                pdf.ln(3)

        out_path = str(Path(out_path).with_suffix(".pdf"))
        pdf.output(out_path)
        return True, out_path

    except ImportError:
        pass  # fpdf2 미설치 → 다음 방법 시도
    except Exception as e:
        pass  # fpdf2 오류 → 다음 방법 시도

    # ── 방법 2: weasyprint ────────────────────────────────
    try:
        import weasyprint  # type: ignore
        html = convert_md_to_html(md_text, title)
        weasyprint.HTML(string=html).write_pdf(out_path)
        return True, out_path
    except ImportError:
        pass
    except Exception:
        pass

    # ── 방법 3: HTML 폴백 ─────────────────────────────────
    html_path = str(Path(out_path).with_suffix(".html"))
    ok, msg = save_as_html(md_text, html_path, title)
    if ok:
        return True, html_path
    return False, "PDF 변환 실패 (fpdf2·weasyprint 미설치, HTML로 대체 저장도 실패)"


def print_to_network(file_path: str, printer_ip: str,
                     printer_name: str = "printer") -> tuple:
    """
    F-02: 네트워크(IP) 프린터로 직접 출력.
    .md/.txt 는 HTML 임시 파일로 변환 후 전송.

    Windows: lpr 명령어 (Windows Print Services 기능 필요)
             또는 win32print (pywin32 설치 시)
    Linux/Mac: lpr -H <ip> -P <name>
    """
    try:
        fpath = Path(file_path)
        if not fpath.exists():
            return False, f"파일 없음: {file_path}"

        suffix = fpath.suffix.lower()

        # .md/.txt → HTML 임시 파일 변환
        if suffix in (".md", ".txt"):
            from config import APP_DATA_DIR
            tmp_dir = Path(APP_DATA_DIR)
            tmp_dir.mkdir(parents=True, exist_ok=True)
            md_text  = fpath.read_text(encoding="utf-8")
            html_str = convert_md_to_html(md_text, title=fpath.stem)
            tmp_html = tmp_dir / f"_netprint_{fpath.stem}.html"
            tmp_html.write_text(html_str, encoding="utf-8")
            file_to_print = str(tmp_html)
        else:
            file_to_print = file_path

        if sys.platform == "win32":
            # 방법 1: win32print (pywin32 설치 시)
            try:
                import win32print  # type: ignore
                printer_unc = f"\\\\{printer_ip}\\{printer_name}"
                hPrinter = win32print.OpenPrinter(printer_unc)
                try:
                    win32print.StartDocPrinter(hPrinter, 1,
                        (f"회의록_{fpath.stem}", None, "RAW"))
                    win32print.StartPagePrinter(hPrinter)
                    with open(file_to_print, "rb") as fp:
                        win32print.WritePrinter(hPrinter, fp.read())
                    win32print.EndPagePrinter(hPrinter)
                    win32print.EndDocPrinter(hPrinter)
                finally:
                    win32print.ClosePrinter(hPrinter)
                return True, f"✅ 네트워크 프린터 전송 완료 ({printer_ip})"
            except ImportError:
                pass  # pywin32 없으면 lpr로 폴백

            # 방법 2: Windows lpr 명령어
            result = subprocess.run(
                ["lpr", "-S", printer_ip, "-P", printer_name, file_to_print],
                capture_output=True, text=True, timeout=15)
            if result.returncode == 0:
                return True, f"✅ 네트워크 프린터 전송 완료 ({printer_ip})"
            else:
                err = result.stderr.strip() or "lpr 명령 실패"
                return False, (f"네트워크 인쇄 실패: {err}\n\n"
                               "Windows 기능 → 인쇄 및 문서 서비스 → LPR 포트 모니터가\n"
                               "활성화되어 있는지 확인해주세요.")
        else:
            # Linux / macOS
            result = subprocess.run(
                ["lpr", "-H", printer_ip, "-P", printer_name, file_to_print],
                capture_output=True, text=True, timeout=15)
            if result.returncode == 0:
                return True, f"✅ 네트워크 프린터 전송 완료 ({printer_ip})"
            return False, f"네트워크 인쇄 실패: {result.stderr.strip()}"

    except Exception as e:
        return False, f"네트워크 인쇄 오류: {e}"
