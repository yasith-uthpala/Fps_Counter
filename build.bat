@echo off
echo ============================================================
echo   Building Standalone Native Windows FPS Overlay
echo ============================================================

set CSC="C:\Windows\Microsoft.NET\Framework64\v4.0.30319\csc.exe"

if not exist %CSC% (
    echo Error: C# compiler not found at %CSC%
    pause
    exit /b 1
)

echo Compiling FpsOverlay.cs into FpsOverlay.exe...
%CSC% /nologo /target:winexe /optimize+ /r:System.Windows.Forms.dll,System.Drawing.dll,System.dll /out:FpsOverlay.exe FpsOverlay.cs

if %ERRORLEVEL% EQU 0 (
    echo.
    echo [SUCCESS] FpsOverlay.exe compiled successfully!
    echo You can run FpsOverlay.exe anytime directly.
) else (
    echo.
    echo [ERROR] Build failed.
)

pause
