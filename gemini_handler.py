import google.generativeai as genai
import logging
from typing import Optional, Dict, Any
import sys
import json
import os

# Configurar logging para mostrar en consola
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('gemini_debug.log')
    ]
)
logger = logging.getLogger(__name__)

class GeminiHandler:
    def __init__(self, api_key: str):
        """
        Inicializa el manejador de Gemini con la clave API proporcionada.
        
        Args:
            api_key (str): Clave API de Google Gemini
        """
        logger.info("Inicializando GeminiHandler...")
        self.api_key = api_key
        self._configure_gemini()

    def _configure_gemini(self) -> None:
        """
        Configura la API de Gemini con la clave proporcionada.
        """
        try:
            logger.info("Configurando API de Gemini...")
            genai.configure(api_key=self.api_key)
            
            # Verificar modelos disponibles
            logger.info("Obteniendo lista de modelos disponibles...")
            models = genai.list_models()
            available_models = [model.name for model in models]
            logger.info(f"Modelos disponibles: {available_models}")
            
            # Intentar inicializar el modelo
            logger.info("Intentando inicializar el modelo gemini-1.5-flash...")
            self.model = genai.GenerativeModel('gemini-1.5-flash')
            logger.info("Modelo gemini-1.5-flash inicializado correctamente")
            
        except Exception as e:
            logger.error(f"Error al configurar la API de Gemini: {e}")
            logger.error(f"Tipo de error: {type(e).__name__}")
            logger.error(f"Detalles del error: {str(e)}")
            raise

    def generate_analysis(self, transcript: str) -> Dict[str, Any]:
        """Genera un análisis del transcript usando Gemini."""
        prompt = f"""Analiza el siguiente transcript de un video de YouTube y genera un análisis detallado en formato Markdown. 
        El análisis debe incluir:

        1. Un resumen ejecutivo de los puntos principales
        2. Los temas clave discutidos
        3. Un diagrama Mermaid que muestre el flujo de los conceptos o procesos principales discutidos. Utiliza `graph LR` para la dirección. 
           Aplica diferentes formas a los nodos (por ejemplo, rectángulos para procesos, diamantes para decisiones) y etiqueta las flechas para indicar el flujo condicional (como 'Sí'/'No').
        4. Conclusiones y recomendaciones

        Usa el siguiente formato para el diagrama Mermaid:
        ```mermaid
        graph LR
            A[Inicio] --> B{{Condición?}}
            B -- Sí --> C[Proceso Sí]
            B -- No --> D[Proceso No]
            C --> E[Fin]
            D --> E
        ```

        Transcript:
        {transcript}

        Genera el análisis en español y asegúrate de que el diagrama Mermaid sea relevante y útil para entender las relaciones entre los conceptos o procesos principales.
        """

        try:
            response = self.model.generate_content(prompt)
            analysis = response.text
            
            # Extraer el resumen estructurado
            summary_prompt = f"""Basado en el siguiente análisis, genera un resumen estructurado en formato JSON con los siguientes campos:
            - titulo: título del video
            - temas_principales: lista de los temas principales
            - puntos_clave: lista de los puntos clave
            - conclusiones: lista de las conclusiones principales
            - recomendaciones: lista de recomendaciones

            Análisis:
            {analysis}
            """
            
            summary_response = self.model.generate_content(summary_prompt)
            summary = json.loads(summary_response.text)
            
            return {
                "analysis": analysis,
                "summary": summary
            }
            
        except Exception as e:
            logger.error(f"Error al generar el análisis: {str(e)}")
            return {
                "analysis": "Error al generar el análisis",
                "summary": {
                    "error": str(e)
                }
            }

    def create_analysis_prompt(self, transcript: str) -> str:
        """
        Crea un prompt estructurado para el análisis de la transcripción.
        
        Args:
            transcript (str): Transcripción del video
            
        Returns:
            str: Prompt formateado para Gemini
        """
        logger.info("Creando prompt de análisis...")
        prompt = f"""Analiza la siguiente transcripción de un video de YouTube y proporciona un análisis detallado en español:

1. Resumen Ejecutivo:
   - Puntos principales
   - Ideas clave
   - Conclusiones fundamentales

2. Análisis Temático:
   - Temas principales identificados
   - Subtemas relevantes
   - Conexiones entre temas

3. Insights y Recomendaciones:
   - Aplicaciones prácticas
   - Sugerencias de implementación
   - Áreas de mejora identificadas

4. Visualización:
   Genera un grafo en formato Mermaid que muestre las relaciones entre los temas principales.
   Usa el formato:
   ```mermaid
   graph LR
   [conexiones entre temas]
   ```

Transcripción:
{transcript}

Por favor, proporciona la respuesta en español y en formato Markdown compatible con Obsidian."""
        logger.info("Prompt creado correctamente")
        return prompt

    def get_analysis(self, transcript: str) -> Optional[Dict[str, Any]]:
        """
        Obtiene el análisis de la transcripción usando Gemini.
        
        Args:
            transcript (str): Transcripción del video
            
        Returns:
            Optional[Dict[str, Any]]: Análisis estructurado o None si hay error
        """
        try:
            logger.info("Iniciando análisis con Gemini...")
            
            if not self.model:
                logger.error("El modelo no está inicializado")
                return None
                
            prompt = self.create_analysis_prompt(transcript)
            logger.info("Prompt enviado a Gemini")
            
            # Configurar parámetros de generación
            generation_config = {
                "temperature": 0.7,
                "top_p": 0.8,
                "top_k": 40,
                "max_output_tokens": 2048,
            }
            
            logger.info("Generando respuesta con Gemini...")
            response = self.model.generate_content(
                prompt,
                generation_config=generation_config
            )
            
            if not response.text:
                logger.error("La respuesta de Gemini está vacía")
                return None
                
            logger.info("Respuesta recibida de Gemini")
            return {
                "raw_response": response.text,
                "formatted_markdown": self._format_markdown(response.text)
            }
            
        except Exception as e:
            logger.error(f"Error al obtener análisis de Gemini: {e}")
            logger.error(f"Tipo de error: {type(e).__name__}")
            logger.error(f"Detalles del error: {str(e)}")
            return None

    def _format_markdown(self, text: str) -> str:
        """
        Formatea el texto para asegurar compatibilidad con Obsidian.
        
        Args:
            text (str): Texto a formatear
            
        Returns:
            str: Texto formateado en Markdown
        """
        logger.info("Formateando texto para Markdown...")
        text = text.replace("```mermaid", "\n```mermaid\n")
        text = text.replace("```", "\n```\n")
        
        text = text.replace("#", "\n#")
        
        logger.info("Texto formateado correctamente")
        return text.strip()

    def save_analysis(self, analysis: Dict[str, Any], video_id: str) -> None:
        """
        Guarda el análisis en un archivo Markdown.
        
        Args:
            analysis (Dict[str, Any]): Análisis a guardar
            video_id (str): ID del video
        """
        try:
            filename = f"analisis_{video_id}.md"
            logger.info(f"Guardando análisis en {filename}...")
            with open(filename, 'w', encoding='utf-8') as f:
                f.write(analysis["formatted_markdown"])
            logger.info(f"Análisis guardado correctamente en {filename}")
        except Exception as e:
            logger.error(f"Error al guardar el análisis: {e}")
            logger.error(f"Tipo de error: {type(e).__name__}")
            logger.error(f"Detalles del error: {str(e)}")

# Código de prueba
if __name__ == "__main__":
    try:
        api_key = "AIzaSyDXaohhZiiD4xHv6E8JW5OhTlAHmAh8hi8"
        handler = GeminiHandler(api_key)
        
        # Prueba simple
        test_prompt = "Hola, ¿cómo estás?"
        logger.info("Realizando prueba simple con Gemini...")
        response = handler.model.generate_content(test_prompt)
        logger.info(f"Respuesta de prueba: {response.text}")
        
    except Exception as e:
        logger.error(f"Error en prueba: {e}")
        logger.error(f"Tipo de error: {type(e).__name__}")
        logger.error(f"Detalles del error: {str(e)}") 