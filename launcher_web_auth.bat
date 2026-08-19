@echo off
chcp 65001 >nul
cd /d "%~dp0"

REM --- Verifications ---
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
echo [ERREUR] Environnement virtuel casse.
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
echo   CLIENT WEB JDR - TEST AUTH (lot B1)
echo ========================================
echo.

set "ROOT=%~dp0"
set "ROOT=%ROOT:~0,-1%"

REM --- Port 8000 deja utilise ? ---
venv\Scripts\python.exe tools\wait_api_auth.py --port-only >nul 2>&1
if errorlevel 1 goto start_api

echo Port 8000 deja occupe - verification auth...
venv\Scripts\python.exe tools\wait_api_auth.py >nul 2>&1
set PROBE=%ERRORLEVEL%
if %PROBE%==0 goto api_already_running
if %PROBE%==2 goto auth_off
echo Attente reponse API sur le port 8000...
set WAIT=0
:wait_existing_api
timeout /t 1 /nobreak >nul
set /a WAIT+=1
venv\Scripts\python.exe tools\wait_api_auth.py >nul 2>&1
set PROBE=%ERRORLEVEL%
if %PROBE%==0 goto api_already_running
if %PROBE%==2 goto auth_off
if %WAIT% LSS 10 goto wait_existing_api
echo.
echo [ERREUR] Port 8000 occupe mais API injoignable.
echo Fermez les processus python.exe puis relancez.
echo.
pause
exit /b 1

:start_api
echo Demarrage de l'API avec JDR_API_AUTH=1...
start "JDR API :8000 auth ON" cmd /k cd /d "%ROOT%" ^&^& set JDR_API_AUTH=1 ^&^& set JDR_AUTH_DEV=1 ^&^& venv\Scripts\python.exe -m uvicorn --factory interfaces.api.app:create_app
echo Attente API auth ON (401 sur /v1/auth/me)...
set WAIT=0
:wait_api
timeout /t 1 /nobreak >nul
set /a WAIT+=1
venv\Scripts\python.exe tools\wait_api_auth.py >nul 2>&1
set PROBE=%ERRORLEVEL%
if %PROBE%==0 goto api_ready
if %PROBE%==2 goto auth_off
if %WAIT% LSS 25 goto wait_api
echo.
echo [AVERTISSEMENT] API non prete apres 25 s.
echo Verifiez la fenetre "JDR API :8000 auth ON".
goto start_web

:api_already_running
echo API auth deja active (401 OK) - reutilisation du port 8000.
goto start_web

:api_ready
echo API auth detectee (401 OK).

:start_web
echo.
echo Demarrage du client Svelte : http://localhost:5173/#/login
echo Utilisez localhost:5173 (PAS 127.0.0.1:8000).
echo Fermez les fenetres cmd pour arreter les serveurs.
echo.
start "JDR Web :5173" cmd /k cd /d "%ROOT%\web" ^&^& npm run dev
timeout /t 2 /nobreak >nul
start "" "http://localhost:5173/#/login"
echo Navigateur ouvert sur #/login
pause
exit /b 0

:auth_off
echo.
echo [ERREUR] Le port 8000 repond SANS auth (JDR_API_AUTH=0).
echo C'est en general launcher_web.bat ou une vieille fenetre API.
echo.
echo 1. Fermez TOUTES les fenetres cmd (JDR API, uvicorn, launcher).
echo 2. Gestionnaire des taches : arretez python.exe restants si besoin.
echo 3. Relancez launcher_web_auth.bat
echo.
pause
exit /b 1
