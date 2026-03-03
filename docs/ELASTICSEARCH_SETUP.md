# 🔍 Integración de Elasticsearch - Guía de Instalación

## 📋 Requisitos

- Python 3.8+
- Elasticsearch 8.x
- Django 5.1.4+

## 🚀 Instalación

### 1. Instalar dependencias
```bash
pip install -r requirements.txt
```

### 2. Instalar Elasticsearch

#### Opción A: Descarga Local (Windows - RECOMENDADO)

1. **Descargar Elasticsearch**
   - Ir a: https://www.elastic.co/downloads/elasticsearch
   - Descargar la versión 8.14.0 (Windows)
   - O descargar directamente: https://artifacts.elastic.co/downloads/elasticsearch/elasticsearch-8.14.0-windows-x86_64.zip

2. **Extraer el archivo**
   ```powershell
   # Descomprimirlo en una carpeta, ej: C:\elasticsearch-8.14.0
   ```

3. **Ejecutar Elasticsearch**
   ```powershell
   # Abrir PowerShell como Administrador
   cd C:\elasticsearch-8.14.0\bin
   .\elasticsearch.bat
   ```

4. **Verificar que está corriendo**
   ```bash
   curl http://localhost:9200
   ```
   
   Deberías ver algo como:
   ```json
   {
     "name" : "...",
     "cluster_name" : "elasticsearch",
     "version" : { "number" : "8.14.0", ... }
   }
   ```

#### Opción B: Usar Docker Desktop (Si lo instalas después)
```bash
docker run -d --name elasticsearch -e "discovery.type=single-node" -e "xpack.security.enabled=false" -p 9200:9200 docker.elastic.co/elasticsearch/elasticsearch:8.14.0
```

#### Opción C: Usar Elastic Cloud (Nube)
- Registrarse en: https://cloud.elastic.co
- Crear un cluster gratuito
- Reemplazar `localhost:9200` por tu URL en elasticsearch_docs.py

### 3. Indexar datos
```bash
python manage.py indexar_elasticsearch
```

Si todo está bien, deberías ver:
```
✅ X jugadores indexados
✅ Y equipos indexados
✅ Indexación completada
```

## 🔎 Funcionamiento

### Búsqueda
La búsqueda funciona desde el navbar de LigaMaster:

1. Escribe mínimo 3 caracteres
2. Los resultados se actualizan en tiempo real (300ms de debounce)
3. Se mostrarán máximo 5 resultados
4. Busca por:
   - ✅ Nombre completo del jugador
   - ✅ Nombre de jugador
   - ✅ Apellido del jugador
   - ✅ Nombre del equipo

### Endpoint API
```
GET /api/buscar/?q=QUERY
```

**Respuesta de ejemplo:**
```json
{
  "status": "success",
  "results": [
    {
      "type": "jugador",
      "id": 123,
      "nombre": "Cristiano Ronaldo",
      "posicion": "Delantero",
      "url": "/jugador/123/"
    },
    {
      "type": "equipo",
      "id": 5,
      "nombre": "Real Madrid",
      "url": "/equipo/real-madrid/"
    }
  ]
}
```

## 🛠️ Troubleshooting

### Error: "Elasticsearch connection refused"
- Verifica que Elasticsearch esté corriendo en `localhost:9200`
- Ejecuta: `curl http://localhost:9200`
- Si sale error, asegúrate de haber iniciado Elasticsearch

**En Windows:**
```powershell
cd C:\elasticsearch-8.14.0\bin
.\elasticsearch.bat
```

**Espera 20-30 segundos a que inicie completamente**

### Error: "Index not found"
- Ejecuta: `python manage.py indexar_elasticsearch`
- Esto creará los índices necesarios

### La búsqueda no devuelve resultados
- Verifica que hayas ejecutado `python manage.py indexar_elasticsearch`
- Revisa los logs de Django para errores
- Asegúrate de que los datos existan en la base de datos

### Error: "elasticsearch-dsl not installed"
- Ejecuta: `pip install -r requirements.txt`

### Error: ConnectionRefusedError
- Elasticsearch no está corriendo
- Necesitas tener abierta la ventana terminal donde corre Elasticsearch
- NO cierres esa ventana mientras desarrollas

## 📝 Notas
- La búsqueda usa fuzzy matching (tolera pequeños errores ortográficos)
- Los resultados se ordenan por relevancia automáticamente
- La búsqueda es completamente agnóstica a mayúsculas/minúsculas
- Soporta caracteres acentuados (ó, á, ú, etc.)
- Si Elasticsearch no está disponible, la búsqueda simplemente no funciona (pero el sitio sigue operativo)

## 🔄 Mantener índices actualizados
Cuando agregues nuevos jugadores o equipos, ejecuta:
```bash
python manage.py indexar_elasticsearch
```

O los signales de Django indexarán automáticamente al crear/actualizar objetos (requiere Elasticsearch disponible).

## 💡 Paso a Paso: Primera Ejecución

1. Descargar e instalar Elasticsearch en Windows
2. Ejecutar `elasticsearch.bat` en otra ventana PowerShell (mantenerla abierta)
3. Ejecutar servidor Django: `python manage.py runserver`
4. En otra ventana: `python manage.py indexar_elasticsearch`
5. Abrir http://localhost:8000 y probar la búsqueda en el navbar

¡Eso es todo!
