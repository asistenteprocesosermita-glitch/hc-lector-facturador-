import streamlit as st
import PyPDF2
import re
import json

# ----------------------------------------------------------------------
# Funciones de extracción (iguales)
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

def extraer_texto_pdf(archivo_pdf):
    texto = ""
    try:
        lector = PyPDF2.PdfReader(archivo_pdf)
        num_paginas = len(lector.pages)
        for pagina in lector.pages:
            texto_pagina = pagina.extract_text()
            if texto_pagina:
                texto += texto_pagina + "\n"
        return texto, num_paginas
    except Exception as e:
        st.error(f"Error al leer el PDF: {e}")
        return None, 0

# ----------------------------------------------------------------------
# Interfaz de Streamlit (sin expanders, todo visible)
# ----------------------------------------------------------------------
st.set_page_config(page_title="Lector de Historias Clínicas", page_icon="📄", layout="wide")
st.title("📄 Lector de Historias Clínicas")
st.markdown("Sube un archivo PDF de una historia clínica (máx. 200 MB) y obtén un reporte con los elementos facturables.")

MAX_MB = 200
archivo_subido = st.file_uploader("Selecciona un archivo PDF", type="pdf")

if archivo_subido is not None:
    tamaño_mb = archivo_subido.size / (1024 * 1024)
    if tamaño_mb > MAX_MB:
        st.error(f"El archivo excede el tamaño máximo de {MAX_MB} MB ({tamaño_mb:.2f} MB).")
    else:
        st.success(f"Archivo cargado: {archivo_subido.name} ({tamaño_mb:.2f} MB)")

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

                st.success("✅ Extracción completada")

                # Mostrar datos del paciente
                col1, col2 = st.columns(2)
                with col1:
                    st.write("**Paciente:**", resultado['paciente'].get('nombre', 'No encontrado'))
                with col2:
                    st.write("**Documento:**", resultado['paciente'].get('documento', 'No encontrado'))

                # ---------- MEDICAMENTOS ----------
                st.markdown("---")
                st.subheader(f"💊 Medicamentos encontrados ({len(resultado['medicamentos'])})")
                if resultado['medicamentos']:
                    for med in resultado['medicamentos']:
                        with st.container(border=True):
                            cols = st.columns([1, 3, 2, 2])
                            cols[0].write(f"**Cant:** {med['cantidad']}")
                            cols[1].write(f"**{med['descripcion']}**")
                            cols[2].write(f"Dosis: {med['dosis']}")
                            cols[3].write(f"Frec: {med['frecuencia']}")
                else:
                    st.write("No se encontraron medicamentos.")

                # ---------- PROCEDIMIENTOS ----------
                st.markdown("---")
                st.subheader(f"🩺 Procedimientos ({len(resultado['procedimientos'])})")
                if resultado['procedimientos']:
                    for proc in resultado['procedimientos']:
                        st.write(f"- **{proc['descripcion']}** ({proc['tipo']}) – Cantidad: {proc['cantidad']}")
                else:
                    st.write("No se encontraron procedimientos.")

                # ---------- LABORATORIOS ----------
                st.markdown("---")
                st.subheader(f"🔬 Laboratorios ({len(resultado['laboratorios'])})")
                if resultado['laboratorios']:
                    for lab in resultado['laboratorios']:
                        st.write(f"- **{lab['descripcion']}** (Cantidad: {lab['cantidad']})")
                else:
                    st.write("No se encontraron órdenes de laboratorio.")

                # ---------- IMÁGENES ----------
                st.markdown("---")
                st.subheader(f"📸 Imágenes diagnósticas ({len(resultado['imagenes'])})")
                if resultado['imagenes']:
                    for img in resultado['imagenes']:
                        st.write(f"- **{img['descripcion']}** (Cantidad: {img['cantidad']})")
                else:
                    st.write("No se encontraron imágenes.")

                # ---------- SERVICIOS (ESTANCIAS) ----------
                st.markdown("---")
                st.subheader(f"🏥 Servicios de atención ({len(resultado['servicios'])})")
                if resultado['servicios']:
                    for serv in resultado['servicios']:
                        st.write(f"- **{serv['tipo_atencion']}** en {serv['sede_nombre']} ({serv['fecha']} {serv['hora']})")
                else:
                    st.write("No se encontraron registros de servicios.")

                # ---------- JSON COMPLETO PARA DESCARGA ----------
                st.markdown("---")
                st.subheader("📦 JSON completo")
                st.json(resultado)

                # Botón de descarga
                json_str = json.dumps(resultado, indent=2, ensure_ascii=False)
                st.download_button(
                    label="📥 Descargar JSON",
                    data=json_str,
                    file_name=f"{archivo_subido.name.replace('.pdf', '')}_reporte.json",
                    mime="application/json"
                )
