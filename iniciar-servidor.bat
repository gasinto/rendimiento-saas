@echo off
chcp 65001 >nul
title Rendimiento SaaS — Servidor
cd /d "%~dp0"

:: ───────────────────────────────────────────────
::  Verificar que PostgreSQL esté corriendo
:: ───────────────────────────────────────────────
echo ┌──────────────────────────────────────────────┐
echo │  Rendimiento SaaS — Inicio del servidor      │
echo └──────────────────────────────────────────────┘
echo.

docker ps --filter "name=rendimiento-pg" --format "{{.Status}}" 2>nul | findstr /i "Up" >nul
if %errorlevel% neq 0 (
    echo [..] PostgreSQL no está corriendo. Iniciando contenedor Docker...
    docker start rendimiento-pg 2>nul
    if %errorlevel% neq 0 (
        echo [!] Contenedor no encontrado. Creándolo desde docker-compose...
        docker compose up -d
    )
    timeout /t 3 /nobreak >nul
    echo [OK] PostgreSQL iniciado.
) else (
    echo [OK] PostgreSQL ya está corriendo.
)
echo.

:: ───────────────────────────────────────────────
::  Aplicar migraciones pendientes
:: ───────────────────────────────────────────────
echo [..] Verificando migraciones de base de datos...
call alembic upgrade head 2>&1
if %errorlevel% neq 0 (
    echo [!] Error al aplicar migraciones. Revisá alembic/versions/.
    pause
    exit /b 1
)
echo [OK] Base de datos actualizada.
echo.

:: ───────────────────────────────────────────────
::  Iniciar servidor
:: ───────────────────────────────────────────────
echo [OK] Servidor iniciado en:
echo        http://localhost:8501
echo        http://localhost:8501/docs       (Swagger)
echo        http://localhost:8501/redoc      (ReDoc)
echo.
echo  Para detenerlo: cerrá esta ventana o presioná Ctrl+C
echo ─────────────────────────────────────────────
echo.

set PYTHONIOENCODING=utf-8
set PYTHONUTF8=1
uvicorn app.main:app --reload --host 0.0.0.0 --port 8501

pause
