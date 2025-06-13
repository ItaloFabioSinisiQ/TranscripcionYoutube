from flask import Flask, render_template, request, jsonify, send_file, url_for
from yutube_trascripcion import YouTubeTranscriber, extract_video_id
import os
import qrcode
import io
import base64
from datetime import datetime
import json
import time
import psutil

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

def get_system_metrics():
    """Obtiene métricas del sistema"""
    try:
        cpu_percent = psutil.cpu_percent()
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
        
        return {
            'cpu_usage': f"{cpu_percent}%",
            'memory_usage': f"{memory.percent}%",
            'storage_usage': f"{disk.percent}%"
        }
    except Exception as e:
        print(f"Error obteniendo métricas del sistema: {e}")
        return {
            'cpu_usage': '0%',
            'memory_usage': '0%',
            'storage_usage': '0%'
        }

def get_processing_metrics():
    try:
        # Contar archivos de resumen en ambas ubicaciones
        current_dir_summaries = len([f for f in os.listdir('.') if f.startswith('resumen_') and f.endswith('.json')])
        generated_files_summaries = len([f for f in os.listdir(UPLOAD_FOLDER) if f.startswith('resumen_') and f.endswith('.json')])
        total_summaries = current_dir_summaries + generated_files_summaries

        total_words = 0
        total_transcription_time = 0
        total_analysis_time = 0
        words_by_date = []
        valid_files_for_avg = 0

        # Procesar archivos de resumen en el directorio actual
        for filename in os.listdir('.'):
            if filename.startswith('resumen_') and filename.endswith('.json'):
                try:
                    with open(filename, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        process_summary_file(data)
                except Exception as e:
                    print(f"Error procesando {filename}: {str(e)}")
                    continue

        # Procesar archivos de resumen en generated_files
        for filename in os.listdir(UPLOAD_FOLDER):
            if filename.startswith('resumen_') and filename.endswith('.json'):
                try:
                    with open(os.path.join(UPLOAD_FOLDER, filename), 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        process_summary_file(data)
                except Exception as e:
                    print(f"Error procesando {filename}: {str(e)}")
                    continue

        def process_summary_file(data):
            nonlocal total_words, total_transcription_time, total_analysis_time, valid_files_for_avg
            # Contar palabras del transcript
            if 'transcript' in data:
                words = len(data['transcript'].split())
                total_words += words
                
                # Obtener fecha del timestamp
                if 'timestamp' in data:
                    date = data['timestamp'].split('T')[0]
                    words_by_date.append({
                        'date': date,
                        'words': words
                    })
            
            # Procesar tiempos
            if 'processing_times' in data:
                times = data['processing_times']
                if isinstance(times, dict):
                    total_transcription_time += float(times.get('transcription', 0))
                    total_analysis_time += float(times.get('analysis', 0))
                    valid_files_for_avg += 1

        # Calcular promedios
        avg_transcription = total_transcription_time / valid_files_for_avg if valid_files_for_avg > 0 else 0
        avg_analysis = total_analysis_time / valid_files_for_avg if valid_files_for_avg > 0 else 0

        avg_total_processing_time = avg_transcription + avg_analysis

        # Calcular porcentajes
        percent_transcription = round((avg_transcription / avg_total_processing_time) * 100, 2) if avg_total_processing_time > 0 else 0
        percent_analysis = round((avg_analysis / avg_total_processing_time) * 100, 2) if avg_total_processing_time > 0 else 0

        # Ordenar datos por fecha
        words_by_date.sort(key=lambda x: x['date'])

        return {
            'total_summaries': total_summaries,
            'total_words': total_words,
            'avg_time': round(avg_total_processing_time, 2),
            'avg_transcription_percent': percent_transcription,
            'avg_analysis_percent': percent_analysis,
            'words_by_date': words_by_date
        }
    except Exception as e:
        print(f"Error en get_processing_metrics: {str(e)}")
        return {
            'total_summaries': 0,
            'total_words': 0,
            'avg_time': 0,
            'avg_transcription_percent': 0,
            'avg_analysis_percent': 0,
            'words_by_date': []
        }

def update_url_history(video_url, video_id):
    """Actualiza el historial de URLs procesadas"""
    try:
        history_file = 'url_history.json'
        if os.path.exists(history_file):
            with open(history_file, 'r', encoding='utf-8') as f:
                history = json.load(f)
        else:
            history = {
                "urls": [],
                "total_processed": 0,
                "last_updated": ""
            }
        
        # Verificar si la URL ya existe
        url_exists = any(url['video_id'] == video_id for url in history['urls'])
        
        if not url_exists:
            history['urls'].append({
                'url': video_url,
                'video_id': video_id,
                'timestamp': datetime.now().isoformat()
            })
            history['total_processed'] = len(history['urls'])
            history['last_updated'] = datetime.now().isoformat()
            
            with open(history_file, 'w', encoding='utf-8') as f:
                json.dump(history, f, indent=4, ensure_ascii=False)
        
        return history['total_processed']
    except Exception as e:
        print(f"Error actualizando historial de URLs: {e}")
        return 0

@app.route('/')
def index():
    try:
        metrics = get_processing_metrics()
        print("Métricas generadas:", metrics)
        return render_template('index.html', metrics=metrics)
    except Exception as e:
        print(f"Error en index: {str(e)}")
        return render_template('index.html', metrics={
            'total_summaries': 0,
            'total_words': 0,
            'avg_time': 0,
            'avg_transcription_percent': 0,
            'avg_analysis_percent': 0,
            'words_by_date': []
        })

@app.route('/analizar', methods=['POST'])
def analizar():
    try:
        video_url = request.form.get('video_url')
        detail_level = request.form.get('detail_level', 'intermedio')
        
        if not video_url:
            return jsonify({'error': 'Por favor, proporciona una URL de YouTube'}), 400

        # Extraer ID del video
        video_id = extract_video_id(video_url)
        if not video_id:
            return jsonify({'error': 'URL de YouTube inválida'}), 400

        # Actualizar historial de URLs
        total_processed = update_url_history(video_url, video_id)

        # Generar ID único para el análisis
        analysis_id = f"{datetime.now().strftime('%Y%m%d%H%M%S')}_{video_id}"
        
        # Inicializar estado del análisis
        analysis_status[analysis_id] = {
            'status': 'iniciando',
            'progress': 0,
            'message': 'Iniciando análisis...',
            'total_processed': total_processed
        }

        # Actualizar estado
        analysis_status[analysis_id]['status'] = 'transcribiendo'
        analysis_status[analysis_id]['progress'] = 20
        analysis_status[analysis_id]['message'] = 'Obteniendo transcripción...'

        # Obtener transcripción
        start_transcription_time = time.time()
        transcript = transcriber.get_transcript(video_id)
        end_transcription_time = time.time()
        transcription_duration = end_transcription_time - start_transcription_time

        if not transcript:
            return jsonify({'error': 'No se pudo obtener la transcripción del video'}), 400

        # Actualizar estado
        analysis_status[analysis_id]['status'] = 'analizando'
        analysis_status[analysis_id]['progress'] = 50
        analysis_status[analysis_id]['message'] = 'Generando análisis...'

        # Obtener análisis
        start_analysis_time = time.time()
        analysis = transcriber.gemini_handler.get_analysis(transcript, detail_level=detail_level)
        end_analysis_time = time.time()
        analysis_duration = end_analysis_time - start_analysis_time

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
            "timestamp": datetime.now().isoformat(),
            "processing_times": {
                "transcription": transcription_duration,
                "analysis": analysis_duration,
                "summary": 0 # No se mide un tiempo de resumen por separado en este flujo
            }
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