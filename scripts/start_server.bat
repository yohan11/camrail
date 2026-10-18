@echo off
rem ==============================================================================
rem CAMRAIL RailMind Lite - Script de Demarrage Multi-Workers en Production
rem ==============================================================================
rem
rem NOTE IMPORTANTE SUR LA GESTION DE LA MEMOIRE RAM :
rem Chaque processus worker Uvicorn charge son propre modele d'embedding SentenceTransformer
rem en memoire vive (environ 400 Mo de RAM par worker) et maintient son propre pool
rem de connexions SQLAlchemy vers PostgreSQL.
rem
rem Dimensionnement recommande selon la RAM du serveur :
rem   - 2 workers (defaut) : ~800 Mo a 1.2 Go de RAM totale allouee au backend.
rem   - 4 workers          : ~1.6 Go a 2.4 Go de RAM totale.
rem
rem Pour modifier le nombre de workers, definissez la variable UVICORN_WORKERS
rem avant l'execution (ex: set UVICORN_WORKERS=4).
rem ==============================================================================

setlocal enabledelayedexpansion

rem Se positionner dans le dossier backend
cd /d "%~dp0\..\backend"

rem Activation de l'environnement virtuel Python si present
if exist "venv\Scripts\activate.bat" (
    call venv\Scripts\activate.bat
)

if "%UVICORN_WORKERS%"=="" set UVICORN_WORKERS=2
if "%HOST%"=="" set HOST=0.0.0.0
if "%PORT%"=="" set PORT=8000

echo ==============================================================================
echo   Demarrage de CAMRAIL RailMind Lite Backend avec %UVICORN_WORKERS% workers
echo   Ecoute sur http://%HOST%:%PORT%
echo ==============================================================================

if "%TRUSTED_PROXIES%"=="" set TRUSTED_PROXIES=*

rem Demarrage du serveur ASGI multi-workers avec support reverse-proxy / HTTPS
uvicorn app.main:app --host %HOST% --port %PORT% --workers %UVICORN_WORKERS% --proxy-headers --forwarded-allow-ips "%TRUSTED_PROXIES%"
