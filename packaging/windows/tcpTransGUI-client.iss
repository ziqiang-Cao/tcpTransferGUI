#define MyAppName "TCPTransGUI Client"
#ifndef MyAppVersion
  #define MyAppVersion "1.1.0"
#endif
#define MyAppPublisher "TCPTransGUI"
#define MyAppURL "https://localhost/tcptransgui"

[Setup]
AppId={{0AF63A6B-6A2B-48D1-A4C0-88A9E3A08B61}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
DefaultDirName={autopf}\TCPTransGUI Client
DefaultGroupName=TCPTransGUI Client
DisableProgramGroupPage=yes
Compression=lzma
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir=..\release\windows\installer
OutputBaseFilename=tcpTransGUI-client-setup-{#MyAppVersion}
PrivilegesRequired=admin
SetupIconFile=..\assets\branding\app_icon.ico
UninstallDisplayIcon={app}\tcpTransClient.exe
WizardImageFile=..\assets\branding\installer_banner.bmp
WizardSmallImageFile=..\assets\branding\installer_header.bmp

[Languages]
Name: "chinesesimp"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "创建桌面快捷方式"; GroupDescription: "附加任务:"

[Files]
Source: "..\release\windows\client\tcpTransClient.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\release\windows\client\README.md"; DestDir: "{app}"; DestName: "README.md"; Flags: ignoreversion

[Icons]
Name: "{autoprograms}\TCPTransGUI Client\TCP 文件传输客户端"; Filename: "{app}\tcpTransClient.exe"
Name: "{autodesktop}\TCP 文件传输客户端"; Filename: "{app}\tcpTransClient.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\tcpTransClient.exe"; Description: "安装完成后启动客户端"; Flags: nowait postinstall skipifsilent unchecked
