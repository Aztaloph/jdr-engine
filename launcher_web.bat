@echo off
chcp 65001 >nul
cd /d "%~dp0"

REM --- Verifications (goto : labels, plus fiable que les blocs if (...)) ---
if not exist "venv\Scripts\python.exe" goto venv_missing
venv\Scripts\python.exe -V >nul 2>&1
if errorlevel 1 goto venv_broken
goto venv_ok

:venv_missing
echo.
echo [ERREUR] Environnement virtuel introuvable.
echo Executez installer.bat puis relancez.
echo.
pause
exit /b 1

:venv_broken
echo.
echo [ERREUR] Environnement virtuel casse (Python reinstalle ?).
echo Relancez : installer.bat
echo.
pause
exit /b 1

:venv_ok
where npm >nul 2>&1
if errorlevel 1 goto npm_missing
goto npm_ok

:npm_missing
echo.
echo [ERREUR] npm introuvable - installez Node.js 18+.
echo.
pause
exit /b 1

:npm_ok
if not exist "web\node_modules\" goto npm_install
goto npm_ready

:npm_install
echo Installation des dependances web...
pushd web
call npm install
if errorlevel 1 (
    popd
    pause
    exit /b 1
)
popd
echo.

:npm_ready
echo.
echo ========================================
echo   CLIENT WEB JDR - API + Svelte
echo ========================================
echo.
echo Demarrage de deux fenetres :
echo   - API FastAPI  : http://127.0.0.1:8000
echo   - Client Svelte: http://localhost:5173/#/lobby
echo.
echo Fermez les fenetres cmd pour arreter les serveurs.
echo.

set "ROOT=%~dp0"
set "ROOT=%ROOT:~0,-1%"

start "JDR API :8000" cmd /k cd /d "%ROOT%" ^&^& venv\Scripts\python.exe -m uvicorn --factory interfaces.api.app:create_app
timeout /t 2 /nobreak >nul
start "JDR Web :5173" cmd /k cd /d "%ROOT%\web" ^&^& npm run dev

pause
