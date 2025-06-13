from flask import Flask, render_template, request, jsonify, send_file, url_for
from yutube_trascripcion import YouTubeTranscriber, extract_video_id
import os
import qrcode
import io
import base64
from datetime import datetime
import json

app = Flask(__name__)
app.config['SECRET_KEY'] = 'tu_clave_secreta_aqui'

# Configurar la carpeta de archivos generados
UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'generated_files')
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

# Inicializar el transcriber con la API key
transcriber = YouTubeTranscriber("AIzaSyAsjXWIqf5ecv4ZDjnAWSjr-zn_1nMMm4k")

# Diccionario para almacenar el estado de los análisis y sus resultados
analysis_status = {}
analysis_results = {}

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/analizar', methods=['POST'])
def analizar():
    try:
        video_url = request.form.get('video_url')
        detail_level = request.form.get('detail_level', 'intermedio')
        
        if not video_url:
            return jsonify({'error': 'Por favor, proporciona una URL de YouTube'}), 400

        # Generar ID único para el análisis
        analysis_id = f"{datetime.now().strftime('%Y%m%d%H%M%S')}_{extract_video_id(video_url)}"
        
        # Inicializar estado del análisis
        analysis_status[analysis_id] = {
            'status': 'iniciando',
            'progress': 0,
            'message': 'Iniciando análisis...'
        }

        # Extraer ID del video
        video_id = extract_video_id(video_url)
        if not video_id:
            return jsonify({'error': 'URL de YouTube inválida'}), 400

        # Actualizar estado
        analysis_status[analysis_id]['status'] = 'transcribiendo'
        analysis_status[analysis_id]['progress'] = 20
        analysis_status[analysis_id]['message'] = 'Obteniendo transcripción...'

        # Obtener transcripción
        transcript = transcriber.get_transcript(video_id)
        if not transcript:
            return jsonify({'error': 'No se pudo obtener la transcripción del video'}), 400

        # Actualizar estado
        analysis_status[analysis_id]['status'] = 'analizando'
        analysis_status[analysis_id]['progress'] = 50
        analysis_status[analysis_id]['message'] = 'Generando análisis...'

        # Obtener análisis
        analysis = transcriber.gemini_handler.get_analysis(transcript, detail_level=detail_level)
        if not analysis:
            return jsonify({'error': 'No se pudo generar el análisis'}), 400

        # Actualizar estado
        analysis_status[analysis_id]['status'] = 'guardando'
        analysis_status[analysis_id]['progress'] = 80
        analysis_status[analysis_id]['message'] = 'Guardando archivos...'

        # Guardar archivos
        transcriber.gemini_handler.save_analysis(analysis, video_id)
        summary = {
            "video_id": video_id,
            "transcript": transcript,
            "analysis": analysis["raw_response"],
            "detail_level": detail_level,
            "timestamp": datetime.now().isoformat()
        }
        transcriber.save_summary(summary, video_id)

        # Guardar resultados para compartir
        analysis_results[analysis_id] = {
            'video_id': video_id,
            'analysis': analysis["formatted_markdown"],
            'detail_level': detail_level,
            'timestamp': datetime.now().isoformat()
        }

        # Actualizar estado final
        analysis_status[analysis_id]['status'] = 'completado'
        analysis_status[analysis_id]['progress'] = 100
        analysis_status[analysis_id]['message'] = 'Análisis completado'

        # Generar URLs para compartir
        share_url = url_for('shared_analysis', analysis_id=analysis_id, _external=True)
        
        # Generar rutas de archivos
        markdown_file = f'analisis_{video_id}.md'
        json_file = f'resumen_{video_id}.json'
        pdf_file = f'analisis_{video_id}.pdf'
        
        return jsonify({
            'success': True,
            'analysis_id': analysis_id,
            'analysis': analysis["formatted_markdown"],
            'files': {
                'markdown': url_for('download_file', filename=markdown_file),
                'json': url_for('download_file', filename=json_file),
                'pdf': url_for('download_file', filename=pdf_file)
            },
            'share_url': share_url
        })

    except Exception as e:
        if 'analysis_id' in locals():
            analysis_status[analysis_id]['status'] = 'error'
            analysis_status[analysis_id]['message'] = str(e)
        return jsonify({'error': str(e)}), 500

@app.route('/status/<analysis_id>')
def get_analysis_status(analysis_id):
    return jsonify(analysis_status.get(analysis_id, {
        'status': 'no_encontrado',
        'progress': 0,
        'message': 'Análisis no encontrado'
    }))

@app.route('/shared/<analysis_id>')
def shared_analysis(analysis_id):
    if analysis_id not in analysis_status:
        return "Análisis no encontrado", 404
    
    status = analysis_status[analysis_id]
    if status['status'] != 'completado':
        return render_template('shared_analysis.html', status=status)
    
    # Obtener los resultados del análisis
    result = analysis_results.get(analysis_id)
    if not result:
        return "Análisis no encontrado", 404
    
    return render_template('shared_analysis.html', 
                         status=status,
                         analysis=result['analysis'],
                         video_id=result['video_id'],
                         detail_level=result['detail_level'],
                         timestamp=result['timestamp'])

@app.route('/qr/<analysis_id>')
def generate_qr(analysis_id):
    if analysis_id not in analysis_status:
        return jsonify({'error': 'Análisis no encontrado'}), 404
        
    share_url = url_for('shared_analysis', analysis_id=analysis_id, _external=True)
    
    # Generar código QR
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=4,
    )
    qr.add_data(share_url)
    qr.make(fit=True)
    
    # Crear imagen
    img = qr.make_image(fill_color="black", back_color="white")
    
    # Convertir a base64
    buffered = io.BytesIO()
    img.save(buffered, format="PNG")
    img_str = base64.b64encode(buffered.getvalue()).decode()
    
    return jsonify({
        'qr_code': f'data:image/png;base64,{img_str}',
        'share_url': share_url
    })

@app.route('/download/<filename>')
def download_file(filename):
    try:
        # Buscar el archivo en la carpeta raíz primero
        file_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), filename)
        if not os.path.exists(file_path):
            # Si no está en la carpeta raíz, buscar en generated_files
            file_path = os.path.join(UPLOAD_FOLDER, filename)
            if not os.path.exists(file_path):
                return jsonify({'error': f'Archivo no encontrado: {filename}'}), 404
        
        return send_file(file_path, as_attachment=True)
    except Exception as e:
        return jsonify({'error': f'Error al descargar el archivo: {str(e)}'}), 404

if __name__ == '__main__':
    app.run(debug=True) 