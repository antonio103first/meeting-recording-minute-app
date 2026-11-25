"""Roundtable 릴리스: 빌드 → 설치파일 → Drive 업로드 → latest.json 갱신.

사용:  python release.py [--notes "변경 요약"] [--skip-build] [--no-upload]
선행:  APP_VERSION(app_dist/main.py)을 먼저 올릴 것. Inno Setup 6 설치 필요.
Drive 인증: 앱 설정 탭에서 한 번 인증해 둔 ~/회의녹음요약_데이터 토큰을 그대로 사용.
"""
import argparse, hashlib, io, json, os, re, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "app_dist"))
CHANNEL = ROOT / "app_dist" / "update_channel.py"
ISCC = Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "Inno Setup 6" / "ISCC.exe"
FOLDER = "Roundtable_Releases"


def die(msg):
    print(f"[실패] {msg}", file=sys.stderr)
    sys.exit(1)


def app_version():
    m = re.search(r'^APP_VERSION\s*=\s*"([^"]+)"', (ROOT / "app_dist/main.py").read_text("utf-8"), re.M)
    if not m:
        die("APP_VERSION 을 찾지 못했습니다.")
    return m.group(1)


def drive():
    import google_drive as gd
    try:
        return gd._get_service()
    except Exception as e:
        die(f"Drive 인증 실패: {e}")


def make_public(svc, fid):
    try:
        svc.permissions().create(fileId=fid, body={"type": "anyone", "role": "reader"}).execute()
    except Exception as e:
        die("링크 공유(anyone) 설정 실패 — 조직 정책이 막았을 수 있습니다. "
            f"직원이 로그인 없이 받을 수 없어 자동 업데이트가 동작하지 않습니다: {e}")


def ensure_channel(svc):
    """latest.json 고정 파일 ID 확보 → update_channel.py 기록(첫 설치 파일에 박혀야 함)."""
    from googleapiclient.http import MediaIoBaseUpload
    cur = ""
    if CHANNEL.exists():
        m = re.search(r'LATEST_JSON_ID\s*=\s*"([^"]*)"', CHANNEL.read_text("utf-8"))
        cur = m.group(1) if m else ""
    if cur:
        return cur
    import google_drive as gd
    ok, folder_id, msg = gd.ensure_folder(FOLDER)
    if not ok:
        die(msg)
    media = MediaIoBaseUpload(io.BytesIO(b"{}"), mimetype="application/json")
    f = svc.files().create(body={"name": "latest.json", "parents": [folder_id]},
                           media_body=media, fields="id").execute()
    make_public(svc, f["id"])
    CHANNEL.write_text(f'LATEST_JSON_ID = "{f["id"]}"\n', "utf-8")
    print(f"업데이트 채널 생성: latest.json = {f['id']}")
    return f["id"]


HIDDEN = ["fitz", "pptx", "yaml", "win32com.client", "pythoncom", "sounddevice", "soundfile",
          "google.genai", "google.genai.types", "google.oauth2.credentials",
          "google_auth_oauthlib.flow", "google.auth.transport.requests",
          "googleapiclient.discovery", "googleapiclient.http", "googleapiclient.errors",
          "anthropic", "openai", "markdown", "requests", "tkinter", "tkinter.ttk",
          "sqlite3", "webbrowser", "updater", "update_channel"]


def build():
    """build_dist.bat 은 cmd 인코딩 문제로 파싱이 깨지고도 종료코드 0 을 돌려주므로 쓰지 않는다."""
    import time
    print("== PyInstaller 빌드 (3~6분) ==")
    started = time.time()
    cmd = [sys.executable, "-m", "PyInstaller", "--noconfirm", "--onedir", "--windowed",
           "--name", "Roundtable", "--icon", "app_icon.ico",
           "--add-data", "app_icon.ico;.",
           "--distpath", str(ROOT / "dist_배포"), "--workpath", str(ROOT / "build_dist_temp"),
           "--specpath", str(ROOT), "--paths", str(ROOT / "app_dist")]
    ff = ROOT / "ffmpeg_bundle" / "ffmpeg.exe"
    if ff.exists():
        cmd += ["--add-binary", f"{ff};."]
    else:
        die("ffmpeg_bundle/ffmpeg.exe 가 없습니다 (MP3 변환 불가 빌드가 됩니다).")
    for h in HIDDEN:
        cmd += ["--hidden-import", h]
    cmd.append(str(ROOT / "app_dist" / "main.py"))
    r = subprocess.run(cmd, cwd=ROOT, stdin=subprocess.DEVNULL)
    exe = ROOT / "dist_배포" / "Roundtable" / "Roundtable.exe"
    if r.returncode != 0:
        die(f"PyInstaller 실패 (코드 {r.returncode})")
    if not exe.exists() or exe.stat().st_mtime < started:
        die("PyInstaller 가 새 exe 를 만들지 못했습니다 (옛 빌드 그대로).")


def make_installer(ver):
    if not ISCC.exists():
        die("Inno Setup 6 가 없습니다: winget install JRSoftware.InnoSetup")
    exe = ROOT / "dist_배포" / "Roundtable" / "Roundtable.exe"
    if not exe.exists():
        die("dist_배포/Roundtable/Roundtable.exe 가 없습니다. 먼저 빌드하세요.")
    print("== 설치 파일 생성 ==")
    r = subprocess.run([str(ISCC), f"/DAppVersion={ver}", str(ROOT / "installer.iss")], cwd=ROOT)
    if r.returncode != 0:
        die("ISCC 실패")
    out = ROOT / "installer_out" / f"Roundtable_Setup_{ver}.exe"
    if not out.exists():
        die(f"설치 파일이 생성되지 않았습니다: {out}")
    return out


def sha256(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for c in iter(lambda: f.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()


def upload(svc, setup, ver, notes, channel_id):
    from googleapiclient.http import MediaFileUpload, MediaIoBaseUpload
    import google_drive as gd
    ok, folder_id, msg = gd.ensure_folder(FOLDER)
    if not ok:
        die(msg)
    print("== Drive 업로드 (수백 MB, 수 분 소요) ==")
    media = MediaFileUpload(str(setup), mimetype="application/octet-stream",
                            resumable=True, chunksize=32 * 1024 * 1024)
    req = svc.files().create(body={"name": setup.name, "parents": [folder_id]},
                             media_body=media, fields="id")
    resp = None
    while resp is None:
        st, resp = req.next_chunk()
        if st:
            print(f"  {int(st.progress() * 100)}%")
    make_public(svc, resp["id"])
    info = {"version": ver, "installer_id": resp["id"], "sha256": sha256(setup),
            "size": setup.stat().st_size, "notes": notes}
    body = MediaIoBaseUpload(io.BytesIO(json.dumps(info, ensure_ascii=False, indent=2).encode("utf-8")),
                             mimetype="application/json")
    svc.files().update(fileId=channel_id, media_body=body).execute()   # 같은 ID 유지
    print(f"latest.json 갱신 완료: v{ver}")
    return info


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--notes", default="")
    ap.add_argument("--skip-build", action="store_true")
    ap.add_argument("--no-upload", action="store_true", help="설치 파일만 만들고 업로드는 안 함")
    a = ap.parse_args()
    ver = app_version()
    svc = None if a.no_upload else drive()
    channel = ensure_channel(svc) if svc else None   # 빌드 전에 확보
    if not a.skip_build:
        build()
    setup = make_installer(ver)
    print(f"설치 파일: {setup} ({setup.stat().st_size/1e6:.0f} MB)")
    if svc:
        upload(svc, setup, ver, a.notes, channel)
