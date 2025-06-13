import google.generativeai as genai
import logging
from typing import Optional, Dict, Any, List
import sys
import json
import os
import subprocess
import tempfile
import pdfkit
import markdown
import time

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
    def __init__(self, api_key: Optional[str] = None):
        """
        Inicializa el manejador de Gemini con la clave API proporcionada o desde una variable de entorno.
        
        Args:
            api_key (Optional[str]): Clave API de Google Gemini. Si es None, se intentará cargar de GEMINI_API_KEY.
        """
        logger.info("Inicializando GeminiHandler...")
        if api_key is None:
            api_key = os.environ.get("GEMINI_API_KEY")
            if api_key is None:
                raise ValueError("La clave API de Gemini no se proporcionó y no se encontró en la variable de entorno 'GEMINI_API_KEY'.")
        self.api_key = api_key
        self._configure_gemini()
        self.max_chunk_size = 15000  # Tamaño máximo de cada chunk de texto
        self.max_chunks = 3  # Número máximo de chunks a procesar

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

    def _split_transcript(self, transcript: str, detail_level: str = 'intermedio') -> List[str]:
        """
        Divide el transcript en chunks manejables.
        
        Args:
            transcript (str): Transcripción completa del video
            detail_level (str): Nivel de detalle del análisis
            
        Returns:
            List[str]: Lista de chunks de texto
        """
        # Ajustar el tamaño máximo del chunk según el nivel de detalle
        chunk_sizes = {
            'basico': 8000,     # Chunks más pequeños para análisis básico
            'intermedio': 12000, # Tamaño estándar para análisis intermedio
            'avanzado': 20000    # Chunks más grandes para análisis avanzado
        }
        
        self.max_chunk_size = chunk_sizes.get(detail_level, 14000)
        
        words = transcript.split()
        chunks = []
        current_chunk = []
        current_size = 0
        
        for word in words:
            word_size = len(word) + 1  # +1 por el espacio
            if current_size + word_size > self.max_chunk_size:
                chunks.append(' '.join(current_chunk))
                current_chunk = [word]
                current_size = word_size
            else:
                current_chunk.append(word)
                current_size += word_size
        
        if current_chunk:
            chunks.append(' '.join(current_chunk))
        
        # Si hay más de max_chunks, combinar los chunks adicionales
        if len(chunks) > self.max_chunks:
            combined_chunks = []
            chunk_size = len(chunks) // self.max_chunks
            for i in range(0, len(chunks), chunk_size):
                combined_chunks.append(' '.join(chunks[i:i + chunk_size]))
            chunks = combined_chunks
        
        logger.info(f"Transcript dividido en {len(chunks)} chunks de tamaño máximo {self.max_chunk_size}")
        return chunks

    def generate_analysis(self, transcript: str, detail_level: str = 'intermedio') -> Dict[str, Any]:
        """Genera un análisis del transcript usando Gemini."""
        mermaid_diagram_example = """
        graph TD
            A[Proceso Inicial] --> B{¿Cumple condición?}
            B -- Sí --> C[Ejecutar Acción A]
            C --> D[Resultado Esperado]
            B -- No --> E[Ejecutar Acción B]
            E --> F[Alternativa]
            D --> G[Conclusión Final]
            F --> G
            G --> H[Fin]
        """

        # Definir el nivel de detalle en el prompt según el parámetro
        detail_instructions = {
            'basico': """Genera un análisis conciso y directo que incluya:
            1. Un resumen breve de los puntos principales
            2. Los temas más importantes
            3. Un diagrama Mermaid simple que muestre el flujo básico
            4. Conclusiones principales
            5. 2-3 temas relacionados""",
            
            'intermedio': """Genera un análisis detallado que incluya:
            1. Un resumen ejecutivo de los puntos principales
            2. Los temas clave discutidos con sus subtemas
            3. Un diagrama Mermaid que muestre el flujo de los conceptos principales
            4. Conclusiones y recomendaciones
            5. 3-5 temas relacionados""",
            
            'avanzado': """Genera un análisis exhaustivo y profundo que incluya:
            1. Un resumen ejecutivo detallado con contexto y objetivos
            2. Análisis temático profundo con subtemas y conexiones
            3. Un diagrama Mermaid complejo que muestre todas las relaciones
            4. Conclusiones detalladas, recomendaciones y casos de estudio
            5. 5-7 temas relacionados con explicaciones"""
        }

        prompt = f"""Analiza el siguiente transcript de un video de YouTube y genera un análisis en formato Markdown.
        {detail_instructions.get(detail_level, detail_instructions['intermedio'])}

        Usa el siguiente formato de ejemplo para el diagrama Mermaid o mejoralo según la información:
        ```mermaid
{mermaid_diagram_example}
        ```

        Transcript:
        {transcript}

        Genera el análisis en español y asegúrate de que el diagrama Mermaid sea relevante y útil para entender las relaciones entre los conceptos o procesos principales.
        """

        try:
            response = self.model.generate_content(prompt)
            analysis = response.text
            
            # Extraer el resumen estructurado
            summary_prompt = """Basado en el siguiente análisis, genera un resumen estructurado en formato JSON con los siguientes campos:
            - titulo: título del video
            - temas_principales: lista de los temas principales
            - puntos_clave: lista de los puntos clave
            - conclusiones: lista de las conclusiones principales
            - recomendaciones: lista de recomendaciones

            Análisis:
            {analysis}
            """.format(analysis=analysis)
            
            summary_response = self.model.generate_content(summary_prompt)
            
            try:
                summary = json.loads(summary_response.text)
            except json.JSONDecodeError as json_e:
                logger.error(f"Error al decodificar el resumen JSON: {json_e}")
                logger.error(f"Texto de respuesta que causó el error: {summary_response.text[:500]}...")
                summary = {"error": "Error al parsear el resumen JSON"}

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
        prompt = """Analiza la siguiente transcripción de un video de YouTube y proporciona un análisis extremadamente detallado, exhaustivo y profundo en español. 
        El análisis debe ser lo más completo posible, explicando cada concepto en profundidad y proporcionando ejemplos específicos.
        IMPORTANTE: No seas conciso, explica todo en detalle y profundidad.

# 1. Resumen Ejecutivo Detallado:
   ## Contexto General:
   - Explicación detallada del contexto histórico y actual
   - Antecedentes relevantes y su importancia
   - Situación actual del tema en la industria
   - Tendencias y desarrollos recientes

   ## Objetivos y Alcance:
   - Objetivos principales del video explicados en detalle
   - Alcance del contenido y sus limitaciones
   - Público objetivo y sus necesidades específicas
   - Nivel de dificultad y requisitos previos

   ## Puntos Principales:
   - Lista exhaustiva de puntos principales con explicaciones detalladas
   - Ideas fundamentales desarrolladas a profundidad
   - Conceptos clave explicados con ejemplos
   - Impacto y relevancia del contenido en el contexto actual

# 2. Análisis Temático Profundo:
   ## Temas Principales:
   ### Tema 1: [Nombre del Tema]
   - Explicación detallada del tema
   - Conceptos fundamentales y su desarrollo
   - Ejemplos específicos y casos de uso
   - Aplicaciones prácticas y limitaciones
   - Mejores prácticas y consideraciones

   ### Tema 2: [Nombre del Tema]
   - Explicación detallada del tema
   - Conceptos fundamentales y su desarrollo
   - Ejemplos específicos y casos de uso
   - Aplicaciones prácticas y limitaciones
   - Mejores prácticas y consideraciones

   [Repetir para cada tema principal]

   ## Subtemas y Conceptos Relacionados:
   ### Subtema 1: [Nombre del Subtema]
   - Explicación detallada
   - Relación con temas principales
   - Ejemplos específicos
   - Aplicaciones prácticas

   [Repetir para cada subtema importante]

   ## Conexiones y Relaciones:
   - Mapeo detallado de relaciones entre temas
   - Dependencias y correlaciones
   - Flujos de información y procesos
   - Impacto de cada tema en otros

# 3. Ejemplos y Casos de Estudio:
   ## Casos Prácticos:
   ### Caso 1: [Nombre del Caso]
   - Contexto y situación
   - Problema o desafío
   - Solución implementada
   - Resultados y lecciones aprendidas
   - Recomendaciones para casos similares

   [Repetir para cada caso importante]

   ## Aplicaciones en el Mundo Real:
   - Ejemplos de implementación exitosa
   - Casos de fracaso y lecciones aprendidas
   - Adaptaciones y variaciones
   - Consideraciones para diferentes contextos

# 4. Insights y Recomendaciones Detalladas:
   ## Lecciones Aprendidas:
   - Principales enseñanzas con ejemplos
   - Errores comunes y cómo evitarlos
   - Consejos prácticos y trucos
   - Experiencias compartidas y testimonios

   ## Mejores Prácticas:
   - Guías detalladas de implementación
   - Estrategias de optimización
   - Consideraciones de rendimiento
   - Aspectos de seguridad y mantenimiento

   ## Recomendaciones para Implementación:
   - Pasos detallados con ejemplos
   - Herramientas necesarias y alternativas
   - Recursos adicionales y referencias
   - Consideraciones de tiempo y recursos

# 5. Conclusiones y Reflexiones Profundas:
   ## Conclusiones Principales:
   - Resumen detallado de hallazgos clave
   - Implicaciones a largo plazo
   - Impacto en la industria
   - Tendencias futuras y predicciones

   ## Áreas de Oportunidad:
   - Mejoras potenciales explicadas
   - Investigación futura necesaria
   - Desarrollo de habilidades requeridas
   - Oportunidades de crecimiento

   ## Preguntas para Reflexión:
   - Cuestionamientos importantes con contexto
   - Áreas de debate y controversia
   - Consideraciones éticas y sociales
   - Implicaciones a largo plazo

# 6. Visualización Completa:
   Genera un diagrama Mermaid detallado que muestre las relaciones entre todos los temas principales y subtemas.
   Incluye:
   - Nodos para cada tema principal
   - Subnodos para subtemas
   - Flechas con etiquetas explicativas
   - Notas y comentarios importantes
   ```mermaid
   graph TD
   A[Tema Principal 1] --> B{{Relación con Tema 2?}}
   B -- Sí --> C[Tema Relacionado 2]
   B -- No --> D[Tema Relacionado 3]
   C --> E[Conclusión del Tema]
   D --> E
   ```

# 7. Temas Relacionados y Recursos:
   ## Videos Relacionados:
   - Lista detallada de videos complementarios
   - Canales recomendados con explicación
   - Playlists relevantes y su contenido
   - Series relacionadas y su contexto

   ## Artículos y Recursos:
   - Documentación técnica detallada
   - Blogs y tutoriales específicos
   - Libros recomendados con resumen
   - Documentos de investigación relevantes

   ## Herramientas y Tecnologías:
   - Software mencionado con detalles
   - Frameworks relevantes y sus usos
   - Bibliotecas útiles y ejemplos
   - Recursos de desarrollo y aprendizaje

   ## Comunidad y Soporte:
   - Foros de discusión activos
   - Grupos de usuarios y sus beneficios
   - Eventos relacionados y su importancia
   - Oportunidades de networking

# 8. Glosario de Términos:
   ## Conceptos Clave:
   - Definiciones detalladas
   - Ejemplos de uso
   - Contexto histórico
   - Evolución del concepto

   ## Términos Técnicos:
   - Explicaciones técnicas
   - Aplicaciones prácticas
   - Consideraciones importantes
   - Referencias cruzadas

   ## Acrónimos y Abreviaturas:
   - Significado completo
   - Uso común
   - Contexto de aplicación
   - Variaciones y alternativas

Transcripción:
{transcript}

Por favor, proporciona la respuesta en español y en formato Markdown compatible con Obsidian. 
IMPORTANTE: 
1. No seas conciso, explica todo en detalle y profundidad
2. Incluye ejemplos específicos para cada concepto
3. Proporciona contexto y antecedentes cuando sea necesario
4. Explica las relaciones entre conceptos
5. Incluye citas relevantes del video
6. Proporciona referencias cruzadas entre secciones
7. Mantén un tono profesional pero accesible
8. Asegúrate de que cada sección sea exhaustiva y completa""".format(transcript=transcript)
        logger.info("Prompt creado correctamente")
        return prompt

    def get_analysis(self, transcript: str, detail_level: str = 'intermedio') -> Optional[Dict[str, Any]]:
        """
        Obtiene el análisis de la transcripción usando Gemini.
        
        Args:
            transcript (str): Transcripción del video
            detail_level (str): Nivel de detalle del análisis ('basico', 'intermedio', 'avanzado')
            
        Returns:
            Optional[Dict[str, Any]]: Análisis generado o None si hay error
        """
        try:
            # Dividir el transcript en chunks
            chunks = self._split_transcript(transcript, detail_level)
            
            # Determinar cuántos chunks procesar según el nivel de detalle
            chunks_to_process = {
                'basico': 1,
                'intermedio': 2,
                'avanzado': 3
            }.get(detail_level, 2)  # Por defecto, procesar 2 chunks
            
            # Limitar el número de chunks a procesar
            chunks = chunks[:chunks_to_process]
            
            # Generar análisis para cada chunk
            analyses = []
            for chunk in chunks:
                analysis = self.generate_analysis(chunk, detail_level)
                if analysis:
                    analyses.append(analysis["analysis"])
            
            if not analyses:
                return None
            
            # Combinar los análisis
            combined_analysis = self._combine_analyses(analyses)
            
            # Formatear el análisis final
            formatted_analysis = self._format_markdown(combined_analysis)
            
            return {
                "raw_response": combined_analysis,
                "formatted_markdown": formatted_analysis
            }
            
        except Exception as e:
            logger.error(f"Error al obtener el análisis: {e}")
            return None

    def _combine_analyses(self, analyses: List[str]) -> str:
        """
        Combina múltiples análisis en uno coherente y detallado.
        
        Args:
            analyses (List[str]): Lista de análisis individuales
            
        Returns:
            str: Análisis combinado
        """
        if len(analyses) == 1:
            return analyses[0]
        
        # Crear un prompt para combinar los análisis
        combine_prompt = """Combina los siguientes análisis de un video de YouTube en un único análisis coherente, detallado y bien estructurado.
        Mantén la estructura de Markdown y asegúrate de que el análisis final sea exhaustivo y bien organizado.
        
        Análisis a combinar:
        {analyses}
        
        Genera un análisis final que incluya:

        # 1. Resumen Ejecutivo Detallado:
           - Síntesis de los puntos principales de todos los análisis
           - Ideas fundamentales y conceptos clave
           - Impacto general del contenido
           - Contexto histórico y actual
           - Objetivos principales del video
           - Público objetivo y nivel de dificultad

        # 2. Análisis Temático Profundo:
           ## Temas Principales:
           - Lista detallada de temas principales
           - Explicación de cada tema con ejemplos
           - Subtemas y conceptos relacionados
           - Conexiones entre temas
           - Jerarquía de conceptos

           ## Ejemplos y Casos:
           - Ejemplos prácticos mencionados
           - Casos de uso específicos
           - Aplicaciones en el mundo real
           - Escenarios de implementación

        # 3. Insights y Recomendaciones:
           - Lecciones aprendidas
           - Mejores prácticas
           - Recomendaciones para implementación
           - Consideraciones importantes

        # 4. Conclusiones y Reflexiones:
           - Conclusiones principales
           - Implicaciones a largo plazo
           - Áreas de oportunidad
           - Preguntas para reflexión

        # 5. Visualización:
           Genera un diagrama Mermaid detallado que muestre las relaciones entre todos los temas principales y subtemas.

        # 6. Temas Relacionados:
           - Videos de YouTube relacionados
           - Artículos y recursos adicionales
           - Conceptos complementarios
           - Herramientas y tecnologías mencionadas

        # 7. Glosario de Términos:
           - Definiciones de conceptos clave
           - Términos técnicos explicados
           - Acrónimos y abreviaturas

        Asegúrate de:
        1. Eliminar redundancias
        2. Mantener una estructura clara y coherente
        3. Incluir ejemplos específicos y citas relevantes
        4. Proporcionar referencias cruzadas entre secciones
        5. Mantener un tono profesional y objetivo
        6. Incluir detalles técnicos cuando sea relevante
        7. Proporcionar contexto adicional cuando sea necesario
        
        El análisis final debe ser exhaustivo y cubrir todos los aspectos importantes del contenido.""".format(analyses="\n\n---\n\n".join(analyses))
        
        try:
            response = self.model.generate_content(combine_prompt)
            return response.text
        except Exception as e:
            logger.error(f"Error al combinar análisis: {e}")
            # Si falla la combinación, devolver los análisis separados con un encabezado
            return """# Análisis Completo de la Transcripción del Video de YouTube

Este análisis integra múltiples secciones de la transcripción, proporcionando una visión completa del contenido. 
Se han eliminado las redundancias y se ha mantenido una estructura clara y concisa.

---

""" + "\n\n---\n\n".join(analyses)

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

    def _extract_mermaid_code(self, markdown_text: str) -> Optional[str]:
        """
        Extrae el bloque de código Mermaid de un texto Markdown.
        
        Args:
            markdown_text (str): Texto Markdown que contiene un diagrama Mermaid.
            
        Returns:
            Optional[str]: El código Mermaid extraído, o None si no se encuentra.
        """
        logger.info("Intentando extraer código Mermaid del texto Markdown...")
        start_tag = "```mermaid"
        end_tag = "```"
        
        start_index = markdown_text.find(start_tag)
        if start_index == -1:
            logger.debug("No se encontró la etiqueta de inicio '```mermaid'.")
            return None
            
        # Ajustar start_index para omitir la etiqueta de inicio
        start_index += len(start_tag)
        
        end_index = markdown_text.find(end_tag, start_index)
        if end_index == -1:
            logger.debug("No se encontró la etiqueta de fin '```'.")
            return None
            
        mermaid_code = markdown_text[start_index:end_index].strip()
        logger.info("Código Mermaid extraído correctamente.")
        return mermaid_code

    def save_analysis(self, analysis: Dict[str, Any], video_id: str) -> None:
        """
        Guarda el análisis en un archivo Markdown y PDF, y si se encuentra,
        también el diagrama Mermaid asociado en formato HTML y PNG.
        
        Args:
            analysis (Dict[str, Any]): Análisis a guardar
            video_id (str): ID del video
        """
        try:
            filename = f"analisis_{video_id}.md"
            pdf_filename = f"analisis_{video_id}.pdf"
            html_filename = f"diagrama_{video_id}.html"
            png_filename = f"diagrama_{video_id}.png"

            logger.info(f"Guardando análisis en {filename}...")
            formatted_markdown = analysis["formatted_markdown"]
            with open(filename, 'w', encoding='utf-8') as f:
                f.write(formatted_markdown)
            logger.info(f"Análisis guardado correctamente en {filename}")

            # Generar PDF
            try:
                logger.info(f"Generando PDF en {pdf_filename}...")
                # Convertir Markdown a HTML
                html_body = markdown.markdown(formatted_markdown)
                
                html_content = f"""
                <!DOCTYPE html>
                <html>
                <head>
                    <meta charset="UTF-8">
                    <style>
                        body {{ font-family: Arial, sans-serif; margin: 40px; }}
                        h1 {{ color: #2c3e50; }}
                        h2 {{ color: #34495e; }}
                        pre {{ background-color: #f8f9fa; padding: 15px; border-radius: 5px; }}
                        code {{ font-family: 'Courier New', monospace; }}
                    </style>
                </head>
                <body>
                    {html_body}
                </body>
                </html>
                """
                # Guardar HTML temporal
                temp_html = f"temp_{video_id}.html"
                with open(temp_html, 'w', encoding='utf-8') as f:
                    f.write(html_content)
                
                # Configurar la ruta de wkhtmltopdf
                config = pdfkit.configuration(wkhtmltopdf=r'C:\Program Files\wkhtmltopdf\bin\wkhtmltopdf.exe')
                
                # Convertir HTML a PDF
                pdfkit.from_file(temp_html, pdf_filename, configuration=config)
                os.remove(temp_html)  # Eliminar archivo temporal
                logger.info(f"PDF generado correctamente en {pdf_filename}")
            except Exception as pdf_error:
                logger.error(f"Error al generar PDF: {pdf_error}")

            # Extraer y guardar el diagrama Mermaid
            mermaid_code = self._extract_mermaid_code(formatted_markdown)
            if mermaid_code:
                logger.info("Diagrama Mermaid encontrado en el análisis. Generando HTML y PNG...")
                self.generate_mermaid_html(mermaid_code, html_filename)
                self.save_mermaid_as_image(mermaid_code, png_filename)
            else:
                logger.info("No se encontró ningún diagrama Mermaid en el análisis.")

        except Exception as e:
            logger.error(f"Error al guardar el análisis o los diagramas: {e}")
            logger.error(f"Tipo de error: {type(e).__name__}")
            logger.error(f"Detalles del error: {str(e)}")

    def generate_mermaid_html(self, mermaid_code: str, output_file: str) -> None:
        """
        Genera un archivo HTML a partir de un código Mermaid.
        
        Args:
            mermaid_code (str): Código Mermaid
            output_file (str): Ruta del archivo de salida
        """
        logger.debug(f"[generate_mermaid_html] Función llamada con output_file: {output_file}")
        try:
            logger.info("Generando archivo HTML a partir de código Mermaid...")
            html_template = f"""
<!DOCTYPE html>
<html>
<body>
    <script src="https://cdn.jsdelivr.net/npm/mermaid/dist/mermaid.min.js"></script>
    <div class="mermaid">
        {mermaid_code}
    </div>
</body>
</html>
"""
            logger.debug("[generate_mermaid_html] Intentando abrir el archivo para escritura...")
            with open(output_file, "w", encoding="utf-8") as f:
                f.write(html_template.format(mermaid_code=mermaid_code))
            logger.debug("[generate_mermaid_html] Escritura de archivo completada.")
            logger.info(f"Archivo HTML generado correctamente en {output_file}")
        except Exception as e:
            logger.error(f"[generate_mermaid_html] Error al generar archivo HTML: {e}")
            logger.error(f"Tipo de error: {type(e).__name__}")
            logger.error(f"Detalles del error: {str(e)}")

    def save_mermaid_as_image(self, mermaid_code: str, output_file: str) -> None:
        """
        Guarda una imagen a partir de un código Mermaid usando mermaid-cli.
        Requiere Node.js y @mermaid-js/mermaid-cli instalados globalmente.
        
        Args:
            mermaid_code (str): Código Mermaid
            output_file (str): Ruta del archivo de salida (ej. diagram.png)
        """
        try:
            logger.info("Guardando imagen a partir de código Mermaid...")
            temp_mmd_file = "temp_diagram.mmd"
            with open(temp_mmd_file, "w", encoding="utf-8") as f:
                f.write(mermaid_code)
            
            # Ejecutar mermaid-cli
            subprocess.run(["mmdc", "-i", temp_mmd_file, "-o", output_file], check=True)
            logger.info(f"Imagen guardada como {output_file}")
            
            # Eliminar archivo temporal
            os.remove(temp_mmd_file)
        except FileNotFoundError:
            logger.error("Error: 'mmdc' no encontrado. Asegúrate de tener Node.js y @mermaid-js/mermaid-cli instalados globalmente (npm install -g @mermaid-js/mermaid-cli).")
        except subprocess.CalledProcessError as e:
            logger.error(f"Error al ejecutar mermaid-cli: {e}")
            logger.error(f"Salida de error: {e.stderr.decode()}")
        except Exception as e:
            logger.error(f"Error al guardar imagen: {e}")
            logger.error(f"Tipo de error: {type(e).__name__}")
            logger.error(f"Detalles del error: {str(e)}")

# Código de prueba
if __name__ == "__main__":
    api_key = None
    try:
        # Intenta cargar la API Key de las variables de entorno
        api_key = os.environ.get("GEMINI_API_KEY")
        
        if api_key is None:
            logger.error("La clave API de Gemini no se encontró en la variable de entorno 'GEMINI_API_KEY'.")
            logger.info("Por favor, configura la variable de entorno GEMINI_API_KEY antes de ejecutar el script.")
            sys.exit(1) # Salir si la API Key no está configurada

        handler = GeminiHandler(api_key)
        
        # Prueba simple
        test_transcript = "Este es un transcript de prueba sobre la monetización para desarrolladores. Hablamos de freelancing, SaaS y cursos online."
        logger.info("Realizando prueba simple de análisis con Gemini...")
        analysis_result = handler.get_analysis(test_transcript)
        
        if analysis_result:
            video_id = "test_video_123" # ID de video de ejemplo
            handler.save_analysis(analysis_result, video_id)
            logger.info(f"Análisis y diagramas guardados para el video ID: {video_id}")
        else:
            logger.error("No se pudo obtener el análisis de Gemini.")

        # Los ejemplos de generate_mermaid_html y save_mermaid_as_image
        # ahora se llaman automáticamente dentro de save_analysis si se encuentra un diagrama.
        
    except ValueError as ve:
        logger.error(f"Error de configuración: {ve}")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Error en la ejecución principal: {e}")
        logger.error(f"Tipo de error: {type(e).__name__}")
        logger.error(f"Detalles del error: {str(e)}") 