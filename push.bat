@echo off
echo ===================================
echo Quick Git Push Script
echo ===================================

:: Ask the user for a commit message
set /p message="Enter a commit message (or press enter for 'Auto update'): "

:: If no message is provided, use a default one
if "%message%"=="" set message=Auto update

echo.
echo Staging all changes...
git add .

echo.
echo Committing with message: "%message%"
git commit -m "%message%"

echo.
echo Pushing to GitHub...
git push

echo.
echo ===================================
echo Push Complete!
echo ===================================
pause
