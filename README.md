# Transcripción y Análisis de Videos de YouTube

Esta aplicación web permite transcribir y analizar videos de YouTube utilizando la API de YouTube y Gemini.

## Características

- Transcripción automática de videos de YouTube
- Análisis del contenido utilizando Gemini
- Generación de archivos en formato Markdown y JSON
- Interfaz web amigable

## Requisitos

- Python 3.x
- Flask
- API Key de YouTube
- API Key de Gemini

## Instalación

1. Clona este repositorio
2. Instala las dependencias:
```bash
pip install -r requirements.txt
```

## Configuración

1. Configura tu API Key de YouTube en el archivo `app.py`:
```python
transcriber = YouTubeTranscriber("TU_API_KEY_AQUI")
```

## Uso

1. Inicia el servidor Flask:
```bash
python app.py
```

2. Abre tu navegador y ve a `http://localhost:5000`

3. Ingresa la URL del video de YouTube que deseas analizar

4. La aplicación generará:
   - Una transcripción del video
   - Un análisis del contenido
   - Archivos en formato Markdown y JSON

## Estructura del Proyecto

```
.
├── app.py              # Aplicación principal Flask
├── yutube_trascripcion.py  # Módulo de transcripción
├── templates/          # Plantillas HTML
│   └── index.html     # Página principal
└── static/            # Archivos estáticos
```

## Endpoints

### GET /
- Muestra la página principal de la aplicación

### POST /analizar
- Parámetros:
  - `video_url`: URL del video de YouTube
- Respuesta:
  - JSON con el análisis y rutas de los archivos generados

## Manejo de Errores

La aplicación maneja los siguientes casos de error:
- URL de YouTube inválida
- Video sin transcripción disponible
- Errores en el análisis
- Errores generales del servidor

## Archivos Generados

- `analisis_[video_id].md`: Análisis en formato Markdown
- `resumen_[video_id].json`: Resumen completo en formato JSON

## Contribuir

Las contribuciones son bienvenidas. Por favor, abre un issue para discutir los cambios propuestos.

## Licencia

Este proyecto está bajo la Licencia MIT. 