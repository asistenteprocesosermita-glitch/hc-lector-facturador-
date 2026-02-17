#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Aplicación web para cargar historias clínicas en PDF y extraer información facturable.
Máximo tamaño de archivo: 200 MB.
"""

import os
import re
import json
import tempfile
from flask import Flask, request, render_template_string, jsonify, send_file
import PyPDF2
from werkzeug.utils import secure_filename

# Configuración de la aplicación
app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 200 * 1024 * 1024  # 200 MB
app.config['UPLOAD_FOLDER'] = tempfile.gettempdir()
app.config['SECRET_KEY'] = 'clave-secreta-para-sesiones'

# Extensiones permitidas
ALLOWED_EXTENSIONS = {'pdf'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# ----------------------------------------------------------------------
# Funciones de extracción (adaptadas de lector_pdf.py)
# ----------------------------------------------------------------------

def limpiar_texto(texto):
    return re.sub(r'\n\s*\n', '\n', texto.strip())

def extraer_paciente(texto):
    paciente = {}
    doc = re.search(r'CC\s*(\d+)', texto)
    if doc:
        paciente['documento'] = doc.group(1)
    nombre = re.search(r'--\s*([A-ZÁÉÍÓÚÑ\s]+?)\s+Fec\.\s*Nacimiento', texto)
    if nombre:
        paciente['nombre'] = nombre.group(1).strip()
    fn = re.search(r'Fec\.\s*Nacimiento:\s*(\d{2}/\d{2}/\d{4})', texto)
    if fn:
        paciente['fecha_nacimiento'] = fn.group(1)
    edad = re.search(r'Edad\s*actual:\s*(\d+)\s*AÑOS', texto)
    if edad:
        paciente['edad'] = int(edad.group(1))
    return paciente

def extraer_servicios(texto):
    servicios = []
    pattern = r'SEDE DE ATENCION\s+(\d+)\s+([^\n]+?)\s+FOLIO\s+\d+\s+FECHA\s+(\d{2}/\d{2}/\d{4})\s+(\d{2}:\d{2}:\d{2})\s+TIPO DE ATENCION\s*:\s*([^\n]+)'
    for match in re.finditer(pattern, texto, re.IGNORECASE):
        servicios.append({
            'sede_codigo': match.group(1),
            'sede_nombre': match.group(2).strip(),
            'fecha': match.group(3),
            'hora': match.group(4),
            'tipo_atencion': match.group(5).strip()
        })
    return servicios

def extraer_medicamentos(texto):
    medicamentos = []
    bloques = re.split(r'FORMULA MEDICA ESTANDAR', texto)
    for bloque in bloques[1:]:
        fin = re.search(r'\n[A-Z ]+\n', bloque)
        if fin:
            bloque = bloque[:fin.start()]
        lineas = bloque.split('\n')
        for i, linea in enumerate(lineas):
            if re.match(r'\s*\d+\.\d+\s+[A-Za-z0-9]', linea):
                partes = linea.strip().split(maxsplit=1)
                if len(partes) >= 2:
                    cantidad = partes[0]
                    desc = partes[1]
                else:
                    continue
                dosis = ''
                if i+1 < len(lineas):
                    prox = lineas[i+1].strip()
                    if re.match(r'\d+[.,]?\d*\s*(MG|ML|G|MCG)', prox, re.IGNORECASE):
                        dosis = prox
                        desc += ' ' + prox
                freq = ''
                for j in range(i, min(i+5, len(lineas))):
                    if 'Frecuencia' in lineas[j]:
                        freq = lineas[j].strip()
                        break
                medicamentos.append({
                    'cantidad': cantidad,
                    'descripcion': desc,
                    'dosis': dosis,
                    'frecuencia': freq
                })
    return medicamentos

def extraer_procedimientos(texto):
    procedimientos = []
    pattern_qx = r'PROCEDIMIENTOS QUIRURGICOS\s*\n\s*(\d+)\s+([^\n]+)'
    for match in re.finditer(pattern_qx, texto, re.IGNORECASE):
        procedimientos.append({
            'tipo': 'quirurgico',
            'cantidad': match.group(1),
            'descripcion': match.group(2).strip()
        })
    pattern_noqx = r'ORDENES DE PROCEDIMIENTOS NO QX\s*\n\s*(\d+)\s+([^\n]+)'
    for match in re.finditer(pattern_noqx, texto, re.IGNORECASE):
        procedimientos.append({
            'tipo': 'no_quirurgico',
            'cantidad': match.group(1),
            'descripcion': match.group(2).strip()
        })
    return procedimientos

def extraer_laboratorios(texto):
    laboratorios = []
    bloques = re.split(r'ORDENES DE LABORATORIO', texto)
    for bloque in bloques[1:]:
        fin = re.search(r'\n[A-Z ]+\n', bloque)
        if fin:
            bloque = bloque[:fin.start()]
        lineas = bloque.split('\n')
        for linea in lineas:
            if re.match(r'\s*\d+\s+[A-Za-z]', linea):
                partes = linea.strip().split(maxsplit=1)
                if len(partes) >= 2:
                    laboratorios.append({
                        'cantidad': partes[0],
                        'descripcion': partes[1]
                    })
    return laboratorios

def extraer_imagenes(texto):
    imagenes = []
    bloques = re.split(r'ORDENES DE IMAGENES DIAGNOSTICAS', texto)
    for bloque in bloques[1:]:
        fin = re.search(r'\n[A-Z ]+\n', bloque)
        if fin:
            bloque = bloque[:fin.start()]
        lineas = bloque.split('\n')
        for linea in lineas:
            if re.match(r'\s*\d+\s+[A-Za-z]', linea):
                partes = linea.strip().split(maxsplit=1)
                if len(partes) >= 2:
                    imagenes.append({
                        'cantidad': partes[0],
                        'descripcion': partes[1]
                    })
    return imagenes

def extraer_texto_pdf(ruta_pdf):
    texto = ""
    try:
        with open(ruta_pdf, 'rb') as archivo:
            lector = PyPDF2.PdfReader(archivo)
            num_paginas = len(lector.pages)
            for pagina in lector.pages:
                texto_pagina = pagina.extract_text()
                if texto_pagina:
                    texto += texto_pagina + "\n"
    except Exception as e:
        raise Exception(f"Error al leer el PDF: {e}")
    return texto

def procesar_pdf(ruta_pdf):
    contenido = extraer_texto_pdf(ruta_pdf)
    contenido = limpiar_texto(contenido)
    resultado = {
        'paciente': extraer_paciente(contenido),
        'servicios': extraer_servicios(contenido),
        'medicamentos': extraer_medicamentos(contenido),
        'procedimientos': extraer_procedimientos(contenido),
        'laboratorios': extraer_laboratorios(contenido),
        'imagenes': extraer_imagenes(contenido)
    }
    return resultado

# ----------------------------------------------------------------------
# Plantilla HTML (incrustada para simplicidad)
# ----------------------------------------------------------------------
HTML_TEMPLATE = """
<!doctype html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Lector de Historias Clínicas</title>
    <style>
        body { font-family: Arial, sans-serif; max-width: 800px; margin: 0 auto; padding: 20px; }
        h1 { color: #333; }
        .form-group { margin-bottom: 15px; }
        label { display: block; margin-bottom: 5px; font-weight: bold; }
        input[type="file"] { padding: 8px; border: 1px solid #ccc; border-radius: 4px; width: 100%; }
        button { background-color: #4CAF50; color: white; padding: 10px 20px; border: none; border-radius: 4px; cursor: pointer; }
        button:hover { background-color: #45a049; }
        .error { color: red; margin-top: 10px; }
        .success { color: green; margin-top: 10px; }
        .info { color: #555; margin-top: 10px; }
    </style>
</head>
<body>
    <h1>📄 Lector de Historias Clínicas</h1>
    <p>Carga un archivo PDF (máximo 200 MB) y extrae automáticamente la información facturable.</p>
    <form method="post" enctype="multipart/form-data" action="/">
        <div class="form-group">
            <label for="file">Seleccionar archivo PDF:</label>
            <input type="file" name="file" accept=".pdf" required>
        </div>
        <button type="submit">Procesar</button>
    </form>
    {% if error %}
    <div class="error">❌ {{ error }}</div>
    {% endif %}
    {% if success %}
    <div class="success">✅ {{ success }}</div>
    <div class="info">
        <strong>Resumen:</strong> {{ servicios }} servicios, {{ medicamentos }} medicamentos, 
        {{ procedimientos }} procedimientos, {{ laboratorios }} laboratorios, {{ imagenes }} imágenes.
    </div>
    <p><a href="/download/{{ filename }}" target="_blank">📥 Descargar reporte JSON</a></p>
    {% endif %}
</body>
</html>
"""

# ----------------------------------------------------------------------
# Rutas de la aplicación
# ----------------------------------------------------------------------
@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        # Verificar que se envió un archivo
        if 'file' not in request.files:
            return render_template_string(HTML_TEMPLATE, error="No se seleccionó ningún archivo.")
        file = request.files['file']
        if file.filename == '':
            return render_template_string(HTML_TEMPLATE, error="El archivo está vacío.")
        if not allowed_file(file.filename):
            return render_template_string(HTML_TEMPLATE, error="Tipo de archivo no permitido. Solo PDF.")

        # Guardar el archivo temporalmente
        filename = secure_filename(file.filename)
        ruta_temp = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(ruta_temp)

        try:
            # Procesar el PDF
            resultado = procesar_pdf(ruta_temp)

            # Guardar el resultado en un archivo JSON en la misma carpeta temporal
            json_filename = os.path.splitext(filename)[0] + '.json'
            json_path = os.path.join(app.config['UPLOAD_FOLDER'], json_filename)
            with open(json_path, 'w', encoding='utf-8') as f:
                json.dump(resultado, f, indent=2, ensure_ascii=False)

            # Preparar resumen para mostrar
            servicios = len(resultado.get('servicios', []))
            medicamentos = len(resultado.get('medicamentos', []))
            procedimientos = len(resultado.get('procedimientos', []))
            laboratorios = len(resultado.get('laboratorios', []))
            imagenes = len(resultado.get('imagenes', []))

            return render_template_string(
                HTML_TEMPLATE,
                success="Archivo procesado correctamente.",
                filename=json_filename,
                servicios=servicios,
                medicamentos=medicamentos,
                procedimientos=procedimientos,
                laboratorios=laboratorios,
                imagenes=imagenes
            )
        except Exception as e:
            return render_template_string(HTML_TEMPLATE, error=str(e))
        finally:
            # Limpiar archivo PDF temporal (opcional)
            if os.path.exists(ruta_temp):
                os.remove(ruta_temp)

    return render_template_string(HTML_TEMPLATE)

@app.route('/download/<filename>')
def download(filename):
    """Descarga el archivo JSON generado."""
    json_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    if os.path.exists(json_path):
        return send_file(json_path, as_attachment=True, download_name=filename)
    else:
        return "Archivo no encontrado", 404

# ----------------------------------------------------------------------
# Punto de entrada
# ----------------------------------------------------------------------
if __name__ == '__main__':
    # Ejecutar la aplicación en modo debug (solo para pruebas locales)
    app.run(debug=True, host='0.0.0.0', port=5000)
