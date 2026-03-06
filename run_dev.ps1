# Script para correr el desarrollo sin problemas de venv
Set-Location "c:\Users\pablo\Desktop\TFG"
$env:Path = "c:\Users\pablo\Desktop\TFG\.venv311\Scripts;" + $env:Path

# Backend (Django)
Write-Host "🚀 Iniciando backend..." -ForegroundColor Green
Start-Process powershell -ArgumentList {
  Set-Location "c:\Users\pablo\Desktop\TFG"
  & "c:\Users\pablo\Desktop\TFG\.venv311\Scripts\python.exe" manage.py runserver 0.0.0.0:8000
}

# Esperar un poco y luego frontend
Start-Sleep -Seconds 3
Write-Host "🎨 Iniciando frontend..." -ForegroundColor Green
Start-Process powershell -ArgumentList {
  Set-Location "c:\Users\pablo\Desktop\TFG\frontend-web"
  npm start
}

Write-Host "`n✅ Backend en http://localhost:8000" -ForegroundColor Green
Write-Host "✅ Frontend en http://localhost:5173" -ForegroundColor Green
