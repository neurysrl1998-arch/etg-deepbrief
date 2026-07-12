@echo off
chcp 65001 >nul
title ETG DeepBrief - Actualizador (version de codigo)
echo.
echo   ====== ACTUALIZANDO ETG DEEPBRIEF DESDE GITHUB ======
echo.
cd /d "%~dp0"
git pull origin main
if errorlevel 1 (
  echo.
  echo   No se pudo actualizar. Revisa tu conexion o que git este instalado.
  pause
  exit /b
)
echo.
echo   Actualizado. Instalando dependencias por si hay nuevas...
"%LOCALAPPDATA%\Programs\Python\Python313\python.exe" -m pip install --quiet flask feedparser requests tzdata beautifulsoup4 lxml pystray pillow
echo.
echo   Listo. Ya tienes la ultima version.
echo   Abre "ETG DeepBrief.bat" o recompila el .exe si lo prefieres.
echo.
pause
