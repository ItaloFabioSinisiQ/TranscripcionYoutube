import os
import json
import logging
import subprocess
from typing import Optional
import sys
import re
from gemini_handler import GeminiHandler

# Configurar logging con más detalle
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('transcripcion.log')
    ]
)
logger = logging.getLogger(__name__)

class YouTubeTranscriber:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.gemini_handler = GeminiHandler(api_key)

    def get_transcript(self, video_id: str) -> Optional[str]:
        """
        Obtener la transcripción auto-generada en español usando yt-dlp.
        """
        try:
            video_url = f'https://www.youtube.com/watch?v={video_id}'
            vtt_filename = f"{video_id}.es.vtt"

            # Ejecutar yt-dlp para descargar la transcripción auto-generada
            logger.info("Descargando transcripción auto-generada con yt-dlp...")
            cmd = [
                "yt-dlp",
                "--write-auto-subs",
                "--sub-lang", "es",
                "--skip-download",
                "-o", f"{video_id}.%(ext)s",
                video_url
            ]
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode != 0:
                logger.error(f"Error al ejecutar yt-dlp: {result.stderr}")
                return None
            if not os.path.exists(vtt_filename):
                logger.error(f"No se encontró el archivo de transcripción: {vtt_filename}")
                return None

            # Leer y procesar el archivo .vtt
            logger.info(f"Procesando archivo de transcripción: {vtt_filename}")
            with open(vtt_filename, 'r', encoding='utf-8') as f:
                vtt_text = f.read()

            # Eliminar líneas de tiempo y metadatos
            transcript_lines = []
            for line in vtt_text.splitlines():
                if re.match(r"^\d{2}:\d{2}:\d{2}\.\d{3} --> ", line):
                    continue  # Saltar líneas de tiempo
                if line.strip() == '' or line.startswith('WEBVTT') or line.startswith('Kind:') or line.startswith('Language:'):
                    continue  # Saltar líneas vacías y metadatos
                transcript_lines.append(line.strip())
            transcript = ' '.join(transcript_lines)

            # Opcional: eliminar el archivo .vtt después de procesar
            os.remove(vtt_filename)

            logger.info("Transcripción obtenida y procesada correctamente")
            return transcript
        except Exception as e:
            logger.error(f"Error al obtener la transcripción: {e}")
            logger.error(f"Tipo de error: {type(e).__name__}")
            logger.error(f"Detalles del error: {str(e)}")
            return None

    def save_summary(self, summary: dict, video_id: str):
        filename = f"resumen_{video_id}.json"
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(summary, f, ensure_ascii=False, indent=2)
        logger.info(f"Resumen guardado en {filename}")

def extract_video_id(url: str) -> Optional[str]:
    """
    Extrae el ID del video de una URL de YouTube.
    """
    try:
        # Patrones comunes de URLs de YouTube
        patterns = [
            r'(?:v=|\/)([0-9A-Za-z_-]{11}).*',  # Formato estándar
            r'youtu\.be\/([0-9A-Za-z_-]{11})',   # Formato corto
            r'youtube\.com\/embed\/([0-9A-Za-z_-]{11})'  # Formato embed
        ]
        
        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)
        
        logger.error("No se pudo extraer el ID del video de la URL proporcionada")
        return None
    except Exception as e:
        logger.error(f"Error al extraer el ID del video: {e}")
        return None

def main():
    try:
        api_key = "AIzaSyAsjXWIqf5ecv4ZDjnAWSjr-zn_1nMMm4k"
        transcriber = YouTubeTranscriber(api_key)
        
        # Solicitar URL del video
        print("\n=== Transcripción y Análisis de Videos de YouTube ===")
        print("Por favor, ingresa la URL del video de YouTube:")
        video_url = input().strip()
        
        # Extraer ID del video
        video_id = extract_video_id(video_url)
        if not video_id:
            print("Error: No se pudo extraer el ID del video. Asegúrate de que la URL sea válida.")
            return
            
        logger.info(f"Procesando video con ID: {video_id}")
        
        # Obtener transcripción
        transcript = transcriber.get_transcript(video_id)
        if not transcript:
            print("Error: No se pudo obtener la transcripción del video.")
            return
            
        # Obtener análisis de Gemini
        analysis = transcriber.gemini_handler.get_analysis(transcript)
        if not analysis:
            print("Error: No se pudo generar el análisis.")
            return
            
        # Guardar análisis en formato Markdown
        transcriber.gemini_handler.save_analysis(analysis, video_id)
        
        # Guardar resumen en JSON
        summary = {
            "video_id": video_id,
            "transcript": transcript,
            "analysis": analysis["raw_response"]
        }
        transcriber.save_summary(summary, video_id)
        
        # Mostrar análisis en la terminal
        print("\n=== Análisis del Video ===")
        print("\n" + analysis["formatted_markdown"] + "\n")
        print(f"El análisis completo se ha guardado en 'analisis_{video_id}.md'")
        print(f"El resumen se ha guardado en 'resumen_{video_id}.json'")
        
    except Exception as e:
        logger.error(f"Error en la función main: {e}")
        logger.error(f"Tipo de error: {type(e).__name__}")
        logger.error(f"Detalles del error: {str(e)}")
        print(f"\nError: {str(e)}")

if __name__ == "__main__":
    main()