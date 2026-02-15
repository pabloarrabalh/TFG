#!/usr/bin/env python
import requests
import re
from bs4 import BeautifulSoup
from datetime import datetime

# Primera petición GET para obtener el CSRF token
session = requests.Session()
response = session.get('http://localhost:8000/login/')
print(f"GET /login/ Status: {response.status_code}")

# Extraer el CSRF token del HTML
soup = BeautifulSoup(response.text, 'html.parser')
csrf_input = soup.find('input', {'name': 'csrfmiddlewaretoken'})
if csrf_input:
    csrf_token = csrf_input.get('value')
    print(f"CSRF Token obtenido: {csrf_token[:20]}...")
else:
    print("ERROR: No se encontró CSRF token")
    exit(1)

# Datos de registro con email único basado en timestamp
timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
unique_email = f"test{timestamp}@example.com"

# Datos de registro
data = {
    'first_name': 'Test',
    'last_name': 'User',
    'nickname': f'testuser{timestamp}',
    'email': unique_email,
    'password1': 'SecurePassword123',
    'password2': 'SecurePassword123',
    'csrfmiddlewaretoken': csrf_token
}

# Hacer POST al registro
response = session.post('http://localhost:8000/register/submit/', data=data, allow_redirects=False)
print(f"\nPOST /register/submit/ Status: {response.status_code}")
print(f"Content-Type: {response.headers.get('Content-Type')}")

if response.status_code == 302:
    print(f"REDIRECT: {response.headers.get('Location')}")
    print("✅ REGISTRO EXITOSO - Se redirecciona a los favoritos")
elif response.status_code == 200:
    print("ERROR: Status 200 en lugar de redirección")
    print("Buscando mensaje de error en el HTML...")
    # Buscar si hay mensaje de error
    if 'register_error' in response.text or 'text-red-400' in response.text:
        soup = BeautifulSoup(response.text, 'html.parser')
        # Buscar de múltiples formas
        error_divs = soup.find_all(class_='text-red-400')
        if error_divs:
            for error_div in error_divs:
                print(f"✓ Error encontrado: {error_div.text}")
        else:
            # Buscar por patrón
            import re
            errors = re.findall(r'<p[^>]*class="[^"]*text-red[^"]*"[^>]*>([^<]+)</p>', response.text)
            if errors:
                for error in errors:
                    print(f"✓ Error encontrado: {error}")
            else:
                print("No se encontró mensaje de error visible")
                print("Primeros 1000 caracteres del HTML:")
                print(response.text[:1000])
    else:
        print("No hay 'register_error' ni 'text-red-400' en el HTML")
        # Print first 1000 chars
        print(f"Primeros 1000 caracteres: {response.text[:1000]}")
else:
    print(f"ERROR: Status {response.status_code}")
    print(f"Response: {response.text[:500]}")

