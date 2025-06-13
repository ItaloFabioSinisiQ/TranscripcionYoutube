from flask import Flask, render_template, request, jsonify, send_file
from yutube_trascripcion import YouTubeTranscriber, extract_video_id
import os

app = Flask(__name__)
app.config['SECRET_KEY'] = 'tu_clave_secreta_aqui'

# Configurar la carpeta de archivos generados
UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'generated_files')
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

# Inicializar el transcriber con la API key
transcriber = YouTubeTranscriber("AIzaSyAsjXWIqf5ecv4ZDjnAWSjr-zn_1nMMm4k")

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/analizar', methods=['POST'])
def analizar():
    try:
        video_url = request.form.get('video_url')
        if not video_url:
            return jsonify({'error': 'Por favor, proporciona una URL de YouTube'}), 400

        # Extraer ID del video
        video_id = extract_video_id(video_url)
        if not video_id:
            return jsonify({'error': 'URL de YouTube inválida'}), 400

        # Obtener transcripción
        transcript = transcriber.get_transcript(video_id)
        if not transcript:
            return jsonify({'error': 'No se pudo obtener la transcripción del video'}), 400

        # Obtener análisis
        analysis = transcriber.gemini_handler.get_analysis(transcript)
        if not analysis:
            return jsonify({'error': 'No se pudo generar el análisis'}), 400

        # Guardar archivos
        transcriber.gemini_handler.save_analysis(analysis, video_id)
        summary = {
            "video_id": video_id,
            "transcript": transcript,
            "analysis": analysis["raw_response"]
        }
        transcriber.save_summary(summary, video_id)

        return jsonify({
            'success': True,
            'analysis': analysis["formatted_markdown"],
            'files': {
                'markdown': f'/download/analisis_{video_id}.md',
                'json': f'/download/resumen_{video_id}.json',
                'pdf': f'/download/analisis_{video_id}.pdf'
            }
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/download/<filename>')
def download_file(filename):
    try:
        return send_file(filename, as_attachment=True)
    except Exception as e:
        return jsonify({'error': f'Error al descargar el archivo: {str(e)}'}), 404

if __name__ == '__main__':
    app.run(debug=True) 