import streamlit as st
import PyPDF2
import re
import json
import io
import time

# ----------------------------------------------------------------------
# Funciones de extracción (adaptadas del script original)
# ----------------------------------------------------------------------

def limpiar_texto(texto):
    """Elimina espacios y saltos de línea redundantes."""
    return re.sub(r'\n\s*\n', '\n', texto.strip())

def extraer_paciente(texto):
    """Extrae datos básicos del paciente: documento, nombre, fecha nacimiento, edad."""
    paciente = {}
    # Documento (CC)
    doc = re.search(r'CC\s*(\d+)', texto)
    if doc:
        paciente['documento'] = doc.group(1)
    # Nombre (entre '--' y 'Fec. Nacimiento')
    nombre = re.search(r'--\s*([A-ZÁÉÍÓÚÑ\s]+?)\s+Fec\.\s*Nacimiento', texto)
    if nombre:
        paciente['nombre'] = nombre.group(1).strip()
    # Fecha de nacimiento
    fn = re.search(r'Fec\.\s*Nacimiento:\s*(\d{2}/\d{2}/\d{4})', texto)
    if fn:
        paciente['fecha_nacimiento'] = fn.group(1)
    # Edad
    edad = re.search(r'Edad\s*actual:\s*(\d+)\s*AÑOS', texto)
    if edad:
        paciente['edad'] = int(edad.group(1))
    return paciente

def extraer_servicios(texto):
    """Extrae registros de atención (servicios) con fecha, hora y tipo."""
    servicios = []
    # Patrón típico: SEDE DE ATENCION 0304 ... FOLIO ... FECHA ... TIPO DE ATENCION : ...
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
    """Extrae fórmulas médicas estándar."""
    medicamentos = []
    bloques = re.split(r'FORMULA MEDICA ESTANDAR', texto)
    for bloque in bloques[1:]:
        fin = re.search(r'\n[A-Z ]+\n', bloque)
        if fin:
            bloque = bloque[:fin.start()]
        lineas = bloque.split('\n')
        for i, linea in enumerate(lineas):
            # Busca líneas que empiecen con cantidad (ej. "1.00  NOMBRE")
            if re.match(r'\s*\d+\.\d+\s+[A-Za-z0-9]', linea):
                partes = linea.strip().split(maxsplit=1)
                if len(partes) >= 2:
                    cantidad = partes[0]
                    desc = partes[1]
                else:
                    continue
                # Intenta capturar dosis en la siguiente línea
                dosis = ''
                if i+1 < len(lineas):
                    prox = lineas[i+1].strip()
                    if re.match(r'\d+[.,]?\d*\s*(MG|ML|G|MCG)', prox, re.IGNORECASE):
                        dosis = prox
                        desc += ' ' + prox
                # Busca frecuencia en las siguientes líneas
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
    """Extrae procedimientos quirúrgicos y no quirúrgicos."""
    procedimientos = []
    # Quirúrgicos
    pattern_qx = r'PROCEDIMIENTOS QUIRURGICOS\s*\n\s*(\d+)\s+([^\n]+)'
    for match in re.finditer(pattern_qx, texto, re.IGNORECASE):
        procedimientos.append({
            'tipo': 'quirurgico',
            'cantidad': match.group(1),
            'descripcion': match.group(2).strip()
        })
    # No quirúrgicos
    pattern_noqx = r'ORDENES DE PROCEDIMIENTOS NO QX\s*\n\s*(\d+)\s+([^\n]+)'
    for match in re.finditer(pattern_noqx, texto, re.IGNORECASE):
        procedimientos.append({
            'tipo': 'no_quirurgico',
            'cantidad': match.group(1),
            'descripcion': match.group(2).strip()
        })
    return procedimientos

def extraer_laboratorios(texto):
    """Extrae órdenes de laboratorio."""
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
    """Extrae órdenes de imágenes diagnósticas."""
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

# ----------------------------------------------------------------------
# Función para extraer texto del PDF
# ----------------------------------------------------------------------
def extraer_texto_pdf(archivo_pdf):
    """Extrae todo el texto de un archivo PDF usando PyPDF2."""
    texto = ""
    try:
        lector = PyPDF2.PdfReader(archivo_pdf)
        num_paginas = len(lector.pages)
        for i, pagina in enumerate(lector.pages):
            texto_pagina = pagina.extract_text()
            if texto_pagina:
                texto += texto_pagina + "\n"
        return texto, num_paginas
    except Exception as e:
        st.error(f"Error al leer el PDF: {e}")
        return None, 0

# ----------------------------------------------------------------------
# Interfaz de Streamlit
# ----------------------------------------------------------------------
st.set_page_config(page_title="Lector de Historias Clínicas", page_icon="📄")
st.title("📄 Lector de Historias Clínicas")
st.markdown("Sube un archivo PDF de una historia clínica (máx. 200 MB) y obtén un reporte JSON con la información facturable.")

# Límite de 200 MB
MAX_MB = 200
archivo_subido = st.file_uploader("Selecciona un archivo PDF", type="pdf", accept_multiple_files=False)

if archivo_subido is not None:
    # Verificar tamaño
    tamaño_bytes = archivo_subido.size
    tamaño_mb = tamaño_bytes / (1024 * 1024)
    if tamaño_mb > MAX_MB:
        st.error(f"El archivo excede el tamaño máximo de {MAX_MB} MB ({tamaño_mb:.2f} MB).")
    else:
        st.success(f"Archivo cargado: {archivo_subido.name} ({tamaño_mb:.2f} MB)")
        
        # Botón para procesar
        if st.button("🔍 Procesar PDF"):
            with st.spinner("Extrayendo texto del PDF..."):
                texto, num_paginas = extraer_texto_pdf(archivo_subido)
                if texto is None:
                    st.stop()
                st.info(f"Se extrajeron {num_paginas} páginas.")
            
            with st.spinner("Analizando información..."):
                texto_limpio = limpiar_texto(texto)
                
                resultado = {
                    'paciente': extraer_paciente(texto_limpio),
                    'servicios': extraer_servicios(texto_limpio),
                    'medicamentos': extraer_medicamentos(texto_limpio),
                    'procedimientos': extraer_procedimientos(texto_limpio),
                    'laboratorios': extraer_laboratorios(texto_limpio),
                    'imagenes': extraer_imagenes(texto_limpio)
                }
                
                # Mostrar resumen
                st.success("✅ Extracción completada")
                st.write(f"**Paciente:** {resultado['paciente'].get('nombre', 'No encontrado')}")
                st.write(f"**Documento:** {resultado['paciente'].get('documento', 'No encontrado')}")
                st.write(f"**Servicios:** {len(resultado['servicios'])}")
                st.write(f"**Medicamentos:** {len(resultado['medicamentos'])}")
                st.write(f"**Procedimientos:** {len(resultado['procedimientos'])}")
                st.write(f"**Laboratorios:** {len(resultado['laboratorios'])}")
                st.write(f"**Imágenes:** {len(resultado['imagenes'])}")
                
                # Mostrar JSON y descarga
                with st.expander("Ver JSON completo"):
                    st.json(resultado)
                
                # Convertir a JSON y ofrecer descarga
                json_str = json.dumps(resultado, indent=2, ensure_ascii=False)
                st.download_button(
                    label="📥 Descargar JSON",
                    data=json_str,
                    file_name=f"{archivo_subido.name.replace('.pdf', '')}_reporte.json",
                    mime="application/json"
                )
