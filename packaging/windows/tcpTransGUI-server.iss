#define MyAppName "TCPTransGUI Server"
#ifndef MyAppVersion
  #define MyAppVersion "1.1.0"
#endif
#define MyAppPublisher "TCPTransGUI"
#define MyAppURL "https://localhost/tcptransgui"

[Setup]
AppId={{D9F5B1FC-0E57-4E39-99F1-DCA4316A65E1}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
DefaultDirName={autopf}\TCPTransGUI Server
DefaultGroupName=TCPTransGUI Server
DisableProgramGroupPage=yes
Compression=lzma
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir=..\release\windows\installer
OutputBaseFilename=tcpTransGUI-server-setup-{#MyAppVersion}
PrivilegesRequired=admin
SetupIconFile=..\assets\branding\app_icon.ico
UninstallDisplayIcon={app}\tcpTransServer.exe
WizardImageFile=..\assets\branding\installer_banner.bmp
WizardSmallImageFile=..\assets\branding\installer_header.bmp

[Languages]
Name: "chinesesimp"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "创建桌面快捷方式"; GroupDescription: "附加任务:"
Name: "autostartserver"; Description: "安装服务端开机自启任务（后台无界面运行）"; GroupDescription: "服务端部署:"

[Files]
Source: "..\release\windows\server\tcpTransServer.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\release\windows\server\README.md"; DestDir: "{app}"; DestName: "README.md"; Flags: ignoreversion
Source: "..\release\windows\server\install_server_autostart.bat"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\release\windows\server\remove_server_autostart.bat"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{autoprograms}\TCPTransGUI Server\TCP 文件传输服务端"; Filename: "{app}\tcpTransServer.exe"
Name: "{autodesktop}\TCP 文件传输服务端"; Filename: "{app}\tcpTransServer.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\tcpTransServer.exe"; Description: "安装完成后启动服务端"; Flags: nowait postinstall skipifsilent unchecked

[Code]
const
  ServerTaskName = 'TCPTransGUI Server';

procedure RegisterServerAutostartTask();
var
  ResultCode: Integer;
  ServerCommand: string;
  CreateTaskCommand: string;
begin
  ForceDirectories(ExpandConstant('{localappdata}\TCPTransGUI\server_data'));
  ServerCommand :=
    '"' + ExpandConstant('{app}\tcpTransServer.exe') + '"' +
    ' --headless --host 0.0.0.0 --port 9999 --data-dir "' +
    ExpandConstant('{localappdata}\TCPTransGUI\server_data') + '"';
  CreateTaskCommand :=
    '/C schtasks /Create /F /TN "' + ServerTaskName + '" /SC ONLOGON /RL HIGHEST /RU "' + ExpandConstant('{username}') + '" /TR "' +
    StringChangeEx(ServerCommand, '"', '\"', True) + '"';
  Exec(ExpandConstant('{cmd}'), CreateTaskCommand, '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
end;

procedure RemoveServerAutostartTask();
var
  ResultCode: Integer;
begin
  Exec(
    ExpandConstant('{cmd}'),
    '/C schtasks /Delete /F /TN "' + ServerTaskName + '"',
    '',
    SW_HIDE,
    ewWaitUntilTerminated,
    ResultCode
  );
end;

procedure CurStepChanged(CurStep: TSetupStep);
begin
  if (CurStep = ssPostInstall) and WizardIsTaskSelected('autostartserver') then
  begin
    RegisterServerAutostartTask();
  end;
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
begin
  if CurUninstallStep = usUninstall then
  begin
    RemoveServerAutostartTask();
  end;
end;
