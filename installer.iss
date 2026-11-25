; Roundtable 설치 파일 (Inno Setup 6)
; 빌드: ISCC /DAppVersion=4.1.5 installer.iss   (보통 release.py 가 호출)
#ifndef AppVersion
  #define AppVersion "0.0.0"
#endif

[Setup]
AppId={{7C1E5A52-3B6D-4F0A-9B8E-52A0C6D4E1B7}
AppName=Roundtable
AppVersion={#AppVersion}
AppPublisher=K-Run Ventures
; 사용자 단위 설치 → 관리자 권한 불필요 → 자동 업데이트가 UAC 없이 조용히 동작
PrivilegesRequired=lowest
DefaultDirName={localappdata}\Programs\Roundtable
DisableProgramGroupPage=yes
DisableDirPage=auto
OutputDir=installer_out
OutputBaseFilename=Roundtable_Setup_{#AppVersion}
SetupIconFile=app_icon.ico
UninstallDisplayIcon={app}\Roundtable.exe
Compression=lzma2/normal
SolidCompression=yes
WizardStyle=modern
ShowLanguageDialog=no
CloseApplications=yes
RestartApplications=no
ArchitecturesInstallIn64BitMode=x64compatible

[Languages]
Name: "korean"; MessagesFile: "compiler:Languages\Korean.isl"

[Tasks]
Name: "desktopicon"; Description: "바탕화면에 바로가기 만들기"; Flags: checkedonce

[Files]
Source: "dist_배포\Roundtable\*"; DestDir: "{app}"; Flags: recursesubdirs ignoreversion
; seed: API keys / OAuth client. Never overwrite an existing user's settings.
#ifexist "seed\config.json"
Source: "seed\config.json"; DestDir: "{%USERPROFILE}\회의녹음요약_데이터"; Flags: onlyifdoesntexist uninsneveruninstall
Source: "seed\google_credentials.json"; DestDir: "{%USERPROFILE}\회의녹음요약_데이터"; Flags: onlyifdoesntexist uninsneveruninstall
#endif

[Icons]
Name: "{autoprograms}\Roundtable"; Filename: "{app}\Roundtable.exe"
Name: "{userdesktop}\Roundtable"; Filename: "{app}\Roundtable.exe"; Tasks: desktopicon

; skipifsilent 없음 → 자동 업데이트(무음) 후에도 앱이 다시 실행된다
[Run]
Filename: "{app}\Roundtable.exe"; Description: "Roundtable 실행"; Flags: nowait postinstall
