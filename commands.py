#!/usr/bin/env python
"""
Script de comandos personalizados para el proyecto Django
Uso: python commands.py [comando]

Comandos disponibles:
    startapp    - Activa el venv y ejecuta el servidor Django
    migrate     - Ejecuta makemigrations y migrate
    superuser   - Crea un superusuario
"""

import sys
import os
import subprocess
import platform

def get_venv_python():
    """Obtiene la ruta del ejecutable de Python del venv"""
    if platform.system() == "Windows":
        return os.path.join(".venv", "Scripts", "python.exe")
    else:
        return os.path.join(".venv", "bin", "python")

def startapp():
    """Ejecuta el servidor Django"""
    python_path = get_venv_python()
    if not os.path.exists(python_path):
        print("❌ No se encontró el entorno virtual en .venv")
        return
    
    print("🚀 Iniciando servidor Django...")
    subprocess.run([python_path, "manage.py", "runserver"])

def migrate():
    """Ejecuta las migraciones"""
    python_path = get_venv_python()
    if not os.path.exists(python_path):
        print("❌ No se encontró el entorno virtual en .venv")
        return
    
    print("📦 Creando migraciones...")
    subprocess.run([python_path, "manage.py", "makemigrations"])
    print("🔄 Aplicando migraciones...")
    subprocess.run([python_path, "manage.py", "migrate"])

def migrations():
    """Ejecuta makemigrations y migrate de una vez"""
    python_path = get_venv_python()
    if not os.path.exists(python_path):
        print("❌ No se encontró el entorno virtual en .venv")
        return
    
    print("📦 Creando y aplicando migraciones...")
    subprocess.run([python_path, "manage.py", "makemigrations"])
    subprocess.run([python_path, "manage.py", "migrate"])

def superuser():
    """Crea un superusuario"""
    python_path = get_venv_python()
    if not os.path.exists(python_path):
        print("❌ No se encontró el entorno virtual en .venv")
        return
    
    print("👤 Creando superusuario...")
    subprocess.run([python_path, "manage.py", "createsuperuser"])

def show_help():
    """Muestra la ayuda"""
    print(__doc__)

if __name__ == "__main__":
    if len(sys.argv) < 2:
        show_help()
        sys.exit(1)
    
    command = sys.argv[1]
    
    commands = {
        'startapp': startapp,
        'migrate': migrate,
        'migrations': migrations,
        'superuser': superuser,
        'help': show_help,
    }
    
    if command in commands:
        commands[command]()
    else:
        print(f"❌ Comando '{command}' no reconocido")
        show_help()
