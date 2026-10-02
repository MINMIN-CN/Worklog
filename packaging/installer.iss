; 工作小记 Inno Setup 安装脚本
; 构建：packaging\build.bat（或 ISCC.exe /DUseChinese=1 packaging\installer.iss）

#define MyAppName "工作小记"
#define MyAppVersion "0.5.2"
#define MyAppExeName "WorkLog.exe"
#define MyAppId "{{B7E4A2F1-3C6D-4E8B-9A5F-1D2C3B4A5E6F}"
#define MyAppIdPlain "{B7E4A2F1-3C6D-4E8B-9A5F-1D2C3B4A5E6F}"

[Setup]
AppId={#MyAppId}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} {#MyAppVersion}
AppPublisher=WorkLog
AppComments=本地优先的 AI 工作记录与日报助手
DefaultDirName={localappdata}\Programs\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
OutputDir=..\dist\installer
OutputBaseFilename=WorkLog-Setup-{#MyAppVersion}
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
SetupIconFile=worklog.ico
UninstallDisplayIcon={app}\{#MyAppExeName}
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
ShowLanguageDialog=auto
; ---- 升级安装 ----
DisableDirPage=auto
UsePreviousAppDir=yes
CloseApplications=no
RestartApplications=no
SetupMutex=WorkLogSetupMutex,Global\WorkLogSetupMutex

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"
#ifdef UseChinese
Name: "chinesesimplified"; MessagesFile: "ChineseSimplified.isl"
#endif

[CustomMessages]
english.DesktopIcon=Create a desktop shortcut
chinesesimplified.DesktopIcon=创建桌面快捷方式
english.Autostart=Start automatically on sign-in (recommended for continuous logging)
chinesesimplified.Autostart=开机自动启动（推荐，持续记录工作轨迹）
english.AdditionalTasks=Additional tasks:
chinesesimplified.AdditionalTasks=附加任务：
english.RunApp=Launch {#MyAppName}
chinesesimplified.RunApp=立即启动 {#MyAppName}
english.UpgradeWelcome=The installer detected version %1 of 工作小记 (WorkLog) and will upgrade it to v%2. All work data, reports and settings will be kept — no need to uninstall first. Click Next to continue.
chinesesimplified.UpgradeWelcome=安装程序检测到已安装的 工作小记 v%1，将自动升级到 v%2。原有的工作数据、报告和设置会完整保留，无需先卸载旧版本。点击「下一步」继续。
english.DeleteDataQuestion=Delete work data?
chinesesimplified.DeleteDataQuestion=是否删除工作数据？
english.DeleteDataText=Work data includes records, reports, to-dos and AI settings. Choosing "Keep data" moves it to:
chinesesimplified.DeleteDataText=工作数据包含：工作记录、报告、待办和 AI 配置。选择「保留数据」会把数据移动到：
english.DeleteDataHint=Reinstalling later will migrate it back automatically.
chinesesimplified.DeleteDataHint=以后重新安装会自动迁移回来。
english.DeleteData=Delete data
chinesesimplified.DeleteData=删除数据
english.KeepData=Keep data
chinesesimplified.KeepData=保留数据
english.MoveFailed=Could not move the data; it is still kept in the program folder: %1
chinesesimplified.MoveFailed=数据移动失败，数据仍保留在程序目录：%1

[Tasks]
Name: "desktopicon"; Description: "{cm:DesktopIcon}"; GroupDescription: "{cm:AdditionalTasks}"; Flags: checkedonce
Name: "autostart"; Description: "{cm:Autostart}"; GroupDescription: "{cm:AdditionalTasks}"

[Files]
Source: "..\dist\WorkLog\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{userprograms}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{userdesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon
Name: "{userstartup}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: autostart

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:RunApp}"; Flags: nowait postinstall skipifsilent; Check: ShouldShowRunEntry

[Code]
var
  PreviousVersion: String;
  WasRunning: Boolean;

(* 通过进程名判断旧版本应用是否在运行（兼容还没有互斥体的旧版本） *)
function IsAppRunning(): Boolean;
var
  ResultCode: Integer;
  OutputFile: String;
  Content: AnsiString;
begin
  Result := False;
  OutputFile := ExpandConstant('{localappdata}') + '\WorkLog_setup_check.txt';
  DeleteFile(OutputFile);
  if Exec(ExpandConstant('{cmd}'),
          '/c tasklist /FI "IMAGENAME eq WorkLog.exe" /FO CSV > "' + OutputFile + '"',
          '', SW_HIDE, ewWaitUntilTerminated, ResultCode) then
  begin
    if FileExists(OutputFile) then
    begin
      if LoadStringFromFile(OutputFile, Content) then
        Result := Pos('WorkLog.exe', Content) > 0;
      DeleteFile(OutputFile);
    end;
  end;
end;

(* 检测已安装版本：升级安装时给出明确提示 *)
function InitializeSetup(): Boolean;
var
  Key: String;
begin
  Key := 'Software\Microsoft\Windows\CurrentVersion\Uninstall\{#MyAppIdPlain}_is1';
  PreviousVersion := '';
  if not RegQueryStringValue(HKCU, Key, 'DisplayVersion', PreviousVersion) then
    RegQueryStringValue(HKLM, Key, 'DisplayVersion', PreviousVersion);
  WasRunning := CheckForMutexes('WorkLogAppMutex') or IsAppRunning();
  Result := True;
end;

procedure InitializeWizard();
begin
  if PreviousVersion <> '' then
    WizardForm.WelcomeLabel2.Caption :=
      FmtMessage(ExpandConstant('{cm:UpgradeWelcome}'), [PreviousVersion, '{#MyAppVersion}']);
end;

(* 升级前让正在运行的应用自行退出，避免文件被占用。
   通过数据目录下的 .installer_close 标记通知应用（应用每 2 秒检查一次）；
   旧版本不认识该标记时，等待几秒后强制结束进程。 *)
function PrepareToInstall(var NeedsRestart: Boolean): String;
var
  ResultCode: Integer;
  Marker: String;
  Tries: Integer;
begin
  Result := '';
  if not WasRunning then
    exit;
  Marker := ExpandConstant('{app}\data\.installer_close');
  ForceDirectories(ExpandConstant('{app}\data'));
  SaveStringToFile(Marker, GetDateTimeString('yyyy-mm-dd hh:nn:ss', '-', ':'), False);
  for Tries := 1 to 12 do
  begin
    if not IsAppRunning() then
      break;
    Sleep(500);
  end;
  if IsAppRunning() then
    Exec('taskkill', '/F /IM WorkLog.exe', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
  DeleteFile(Marker);
end;

(* 升级安装完成后，把升级前正在运行的应用重新拉起来（静默升级同样生效）。
   --wait-instance 让新实例等待旧进程退出后再接管，避免单实例保护误判。 *)
procedure CurStepChanged(CurStep: TSetupStep);
var
  ErrorCode2: Integer;
begin
  if CurStep = ssDone then
  begin
    DeleteFile(ExpandConstant('{app}\data\.installer_close'));
    if WasRunning and (PreviousVersion <> '') then
      ShellExec('open', ExpandConstant('{app}\{#MyAppExeName}'), '--wait-instance', '',
                SW_SHOWNORMAL, ewNoWait, ErrorCode2);
  end;
end;

(* 升级安装时不再重复显示「立即启动」，避免和自动重启冲突 *)
function ShouldShowRunEntry(): Boolean;
begin
  Result := PreviousVersion = '';
end;

(* 递归移动目录：用于卸载时保留数据，把安装目录下的 data 移到用户目录 *)
function MoveDirRecursive(const SourceDir, DestDir: String): Boolean;
var
  FindRec: TFindRec;
  SourceFile, DestFile: String;
begin
  Result := False;
  if not DirExists(SourceDir) then
  begin
    Result := True;
    exit;
  end;
  if not ForceDirectories(DestDir) then
    exit;
  if FindFirst(SourceDir + '\*', FindRec) then
  begin
    try
      repeat
        if (FindRec.Name <> '.') and (FindRec.Name <> '..') then
        begin
          SourceFile := SourceDir + '\' + FindRec.Name;
          DestFile := DestDir + '\' + FindRec.Name;
          if (FindRec.Attributes and FILE_ATTRIBUTE_DIRECTORY) <> 0 then
          begin
            if not MoveDirRecursive(SourceFile, DestFile) then
              exit;
          end
          else
          begin
            if not CopyFile(SourceFile, DestFile, False) then
              exit;
            DeleteFile(SourceFile);
          end;
        end;
      until not FindNext(FindRec);
    finally
      FindClose(FindRec);
    end;
  end;
  RemoveDir(SourceDir);
  Result := True;
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  DataDir, KeepDir: String;
begin
  if CurUninstallStep = usUninstall then
  begin
    DataDir := ExpandConstant('{app}\data');
    if DirExists(DataDir) then
    begin
      KeepDir := ExpandConstant('{localappdata}\WorkLog\data');
      if UninstallSilent then
      begin
        { 静默卸载不弹窗，默认保留数据（移动到用户目录） }
        MoveDirRecursive(DataDir, KeepDir);
      end
      else
      begin
        case TaskDialogMsgBox(
          ExpandConstant('{cm:DeleteDataQuestion}'),
          ExpandConstant('{cm:DeleteDataText}') + #13#10 + KeepDir + #13#10 +
          ExpandConstant('{cm:DeleteDataHint}'),
          mbConfirmation, MB_YESNO, [ExpandConstant('{cm:DeleteData}'), ExpandConstant('{cm:KeepData}')], 1) of
          IDYES:
            DelTree(DataDir, True, True, True);
          IDNO:
            if not MoveDirRecursive(DataDir, KeepDir) then
              MsgBox(FmtMessage(ExpandConstant('{cm:MoveFailed}'), [DataDir]),
                     mbInformation, MB_OK);
        end;
      end;
    end;
  end;
end;
