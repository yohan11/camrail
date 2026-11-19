@echo off
rem ==============================================================================
rem CAMRAIL RailMind Lite - Script de Deploiement Conteneurise Clé en Main (Docker)
rem ==============================================================================

setlocal enabledelayedexpansion

cd /d "%~dp0\.."

echo ==============================================================================
echo   CAMRAIL RailMind Lite - Demarrage de la Pile Docker Compose
echo ==============================================================================

rem 1. Verification de la disponibilite de Docker
where docker >nul 2>nul
if %errorlevel% neq 0 (
    echo [ERREUR CRITIQUE] Docker n'est pas installe ou n'est pas dans le PATH systeme.
    echo Veuillez installer Docker Desktop ^(Windows^) ou le moteur Docker ^(Linux/WSL2^).
    echo https://docs.docker.com/get-docker/
    pause
    exit /b 1
)

rem 2. Preparation automatique des fichiers d'environnement
if not exist "backend\.env" (
    echo [INFO] Creation automatique de backend\.env a partir du modele...
    copy "backend\.env.example" "backend\.env" >nul
)

if not exist "frontend\camrail-rda\.env.local" (
    if exist "frontend\camrail-rda\.env.local.example" (
        echo [INFO] Creation automatique de frontend\camrail-rda\.env.local...
        copy "frontend\camrail-rda\.env.local.example" "frontend\camrail-rda\.env.local" >nul
    )
)

rem 3. Verification des dossiers persistants
if not exist "backend\storage\documents" mkdir "backend\storage\documents"
if not exist "backend\models" mkdir "backend\models"

rem 4. Choix du profil de deploiement
set PROFILE_ARG=
if /i "%1"=="https" (
    echo [INFO] Profil active : HTTPS ^(Reverse-Proxy Nginx durci^)...
    set PROFILE_ARG=--profile https
) else if /i "%1"=="full" (
    echo [INFO] Profil active : Full ^(Nginx HTTPS + Service Ollama integre^)...
    set PROFILE_ARG=--profile ollama --profile https
) else if /i "%1"=="ollama" (
    echo [INFO] Profil active : Ollama conteneurise...
    set PROFILE_ARG=--profile ollama
) else (
    echo [INFO] Profil standard : Base de donnees pgvector + Backend FastAPI + Frontend Next.js
)

rem 5. Lancement de la composition Docker
echo [INFO] Construction et demarrage des conteneurs en arriere-plan...
docker compose %PROFILE_ARG% up -d --build

if %errorlevel% neq 0 (
    echo [ERREUR] Echec lors du lancement de Docker Compose. Verifiez que le daemon Docker est bien demarre.
    exit /b %errorlevel%
)

echo.
echo ==============================================================================
echo   Deploiement Conteneurise Reussi !
echo ==============================================================================
echo   - Interface Web (Frontend) : http://localhost:3000
echo   - API Swagger (Backend)    : http://localhost:8000/docs
echo   - Verification Sante       : http://localhost:8000/health
if /i "%1"=="https" echo   - Acces Securise HTTPS     : https://localhost
if /i "%1"=="full"  echo   - Acces Securise HTTPS     : https://localhost
echo.
echo   Comptes de demonstration préconfigurés :
echo     * Administrateur : admin@camrail.net    / adminpassword
echo     * Doc Admin      : docadmin@camrail.net / docadminpassword
echo.
echo   Commandes utiles :
echo     * Voir les logs      : docker compose logs -f
echo     * Arreter les services : docker compose down
echo ==============================================================================

