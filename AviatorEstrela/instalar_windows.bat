@echo off
@echo off
chcp 65001 >nul 2>&1
setlocal EnableDelayedExpansion

title Aviator ML Intelligence - Instalador Windows
echo.
echo  ===================================================
echo   Aviator ML Intelligence - Instalador Windows
echo  ===================================================
echo.

:: -------------------------------------------------
:: 1. Verificar Python
:: -------------------------------------------------
echo [1/5] Verificando Python...
where python >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo    Python NAO encontrado no PATH.
    goto :install_python
)
for /f "tokens=2 delims= " %%v in ('python --version 2^>^&1') do set PYVER=%%v
for /f "tokens=1,2 delims=." %%a in ("%PYVER%") do (
    set PYMAJOR=%%a
    set PYMINOR=%%b
)
if %PYMAJOR% LSS 3 goto :install_python
if %PYMAJOR% EQU 3 if %PYMINOR% LSS 10 goto :install_python
echo    OK: Python %PYVER%
goto :python_ok

:install_python
echo    Python 3.10+ nao encontrado. Baixando instalador...
if "%PROCESSOR_ARCHITECTURE%"=="AMD64" (
    set PYURL=https://www.python.org/ftp/python/3.10.11/python-3.10.11-amd64.exe
    set PYINST=python-3.10.11-amd64.exe
) else (
    set PYURL=https://www.python.org/ftp/python/3.10.11/python-3.10.11.exe
    set PYINST=python-3.10.11.exe
)
powershell -Command "Invoke-WebRequest -Uri '%PYURL%' -OutFile '%TEMP%\%PYINST%'" 2>nul
if not exist "%TEMP%\%PYINST%" (
    echo    ERRO: Falha no download.
    echo    Instale manualmente: https://www.python.org/downloads/
    echo    IMPORTANTE: Marque "Add Python to PATH"!
    pause
    exit /b 1
)
echo    Instalando Python silenciosamente...
"%TEMP%\%PYINST%" /quiet InstallAllUsers=1 PrependPath=1 Include_test=0
set "PATH=C:\Program Files\Python310;C:\Program Files\Python310\Scripts;%PATH%"
set "PATH=%LOCALAPPDATA%\Programs\Python\Python310;%LOCALAPPDATA%\Programs\Python\Python310\Scripts;%PATH%"
where python >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo    ERRO: Python instalado mas nao no PATH.
    echo    Feche este terminal, abra um NOVO e execute instalar_windows.bat novamente.
    pause
    exit /b 1
)
for /f "tokens=2 delims= " %%v in ('python --version 2^>^&1') do set PYVER=%%v
echo    OK: Python %PYVER% instalado.
del "%TEMP%\%PYINST%" >nul 2>&1
:python_ok

:: -------------------------------------------------
:: 2. Verificar Google Chrome
:: -------------------------------------------------
echo.
echo [2/5] Verificando Google Chrome...
set CF=0
if exist "C:\Program Files\Google\Chrome\Application\chrome.exe" set CF=1
if exist "C:\Program Files (x86)\Google\Chrome\Application\chrome.exe" set CF=1
if exist "%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe" set CF=1
if %CF% EQU 1 (
    echo    OK: Chrome encontrado.
) else (
    echo    AVISO: Chrome nao encontrado. O Selenium precisa dele.
    echo    Instale em: https://www.google.com/chrome/
    choice /c SN /m "   Abrir pagina de download agora? (S/N)"
    if !ERRORLEVEL! EQU 1 start https://www.google.com/chrome/
)

:: -------------------------------------------------
:: 3. Criar ambiente virtual
:: -------------------------------------------------
echo.
echo [3/5] Criando ambiente virtual...
set VENV=%~dp0venv
if exist "%VENV%\Scripts\activate.bat" (
    echo    OK: venv ja existe.
) else (
    python -m venv "%VENV%"
    if %ERRORLEVEL% NEQ 0 (
        echo    ERRO: Falha ao criar venv.
        pause
        exit /b 1
    )
    echo    OK: venv criado.
)
call "%VENV%\Scripts\activate.bat"

:: -------------------------------------------------
:: 4. Instalar dependencias
:: -------------------------------------------------
echo.
echo [4/5] Instalando dependencias...
python -m pip install --upgrade pip >nul 2>&1

:: Procura requirements.txt na pasta do bat ou na subpasta AviatorEstrela
set RQ=%~dp0requirements.txt
if not exist "%RQ%" (
    set RQ=%~dp0AviatorEstrela\requirements.txt
)
if exist "%RQ%" (
    pip install -r "%RQ%"
    if %ERRORLEVEL% NEQ 0 (
        echo    ERRO: Falha ao instalar dependencias.
        pause
        exit /b 1
    )
) else (
    echo    requirements.txt nao encontrado. Instalando manualmente...
    pip install Flask==3.0.3 joblib==1.4.2 "numpy<2.0" pandas==2.2.2 scikit-learn==1.5.0 selenium==4.21.0
)
echo    OK: Dependencias instaladas.

:: -------------------------------------------------
:: 5. Criar atalhos de execucao
:: -------------------------------------------------
echo.
echo [5/5] Criando atalhos de execucao...

:: Detecta onde esta o aviator_service2.py
set SD=%~dp0
if exist "%~dp0AviatorEstrela\aviator_service2.py" (
    set SD=%~dp0AviatorEstrela
)

> "%~dp0iniciar.bat" (
echo @echo off
echo chcp 65001 ^>nul 2^>^&1
echo title Aviator ML Intelligence
echo cd /d "%SD%"
echo call "%VENV%\Scripts\activate.bat"
echo echo.
echo echo  Aviator ML Intelligence
echo echo  Dashboard: http://localhost:5005
echo echo  Ctrl+C para encerrar.
echo echo.
echo python aviator_service2.py
echo pause
)

> "%~dp0diagnostico.bat" (
echo @echo off
echo chcp 65001 ^>nul 2^>^&1
echo cd /d "%SD%"
echo call "%VENV%\Scripts\activate.bat"
echo python ml_diagnostico.py %%*
echo pause
)

echo    OK: iniciar.bat e diagnostico.bat criados.
echo.
echo  ===================================================
echo   INSTALACAO CONCLUIDA COM SUCESSO!
echo  ===================================================
echo.
echo  Para iniciar o servico:  iniciar.bat
echo  Para diagnostico ML:    diagnostico.bat
echo  Dashboard:              http://localhost:5005
echo.
pause
