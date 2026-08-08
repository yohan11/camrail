@echo off
echo ===================================================
echo Installation de pgvector dans PostgreSQL 18
echo ===================================================
xcopy "%TEMP%\pgvector_install\*" "C:\Program Files\PostgreSQL\18\" /E /Y /I
echo.
echo Termine ! Vous pouvez fermer cette fenetre.
pause
