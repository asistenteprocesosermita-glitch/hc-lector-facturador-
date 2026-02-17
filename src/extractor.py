#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Extractor de información facturable de historias clínicas en texto plano.
Extrae: datos del paciente, servicios/días de estancia, medicamentos,
procedimientos, laboratorios e imágenes diagnósticas.
"""

import re
import json
import sys
from pathlib import Path

# ----------------------------------------------------------------------
# Utilidades
# ----------------------------------------------------------------------
def limpiar_texto(texto):
    """Elimina espacios redundantes y saltos de línea excesivos."""
    # Reemplaza múltiples saltos de línea con uno solo
    texto = re.sub(r'\n\s*\n', '\n', texto)
    # Elimina espacios al inicio y final de cada línea
    lineas = [linea.strip() for linea in texto.split('\n')]
    return '\n'.join(lineas)

def guardar_json(datos, archivo_salida):
    """Guarda los datos en un archivo JSON con formato legible."""
    with open(archivo_salida, 'w', encoding='utf-8') as f:
        json.dump(datos, f, indent=2, ensure_ascii=False, default=str)

# ----------------------------------------------------------------------
# Extracción de datos del paciente
# ----------------------------------------------------------------------
def extraer_paciente(texto):
    """Extrae nombre, documento, fecha nacimiento y edad."""
    paciente = {}
    # Número de documento (CC)
    doc = re.search(r'CC\s*(\d+)', texto)
    if doc:
        paciente['documento'] = doc.group(1)
    # Nombre (entre '--' y 'Fec. Nacimiento')
    nombre = re.search(r'--\s*([A-ZÁÉÍÓÚÑ\s]+?)\s+Fec\.?\s*Nacimiento', texto)
    if nombre:
        paciente['nombre'] = nombre.group(1).strip()
    # Fecha de nacimiento
    fn = re.search(r'Fec\.?\s*Nacimiento:\s*(\d{2}/\d{2}/\d{4})', texto)
    if fn:
        paciente['fecha_nacimiento'] = fn.group(1)
    # Edad
    edad = re.search(r'Edad\s*actual:\s*(\d+)\s*AÑOS', texto)
    if edad:
        paciente['edad'] = int(edad.group(1))
    return paciente

# ----------------------------------------------------------------------
# Extracción de servicios (días de estancia)
# ----------------------------------------------------------------------
def extraer_servicios(texto):
    """
    Busca líneas con SEDE DE ATENCION y FECHA para registrar cada ingreso.
    Devuelve una lista de diccionarios con sede, fecha, hora y tipo de atención.
    """
    servicios = []
    # Patrón: SEDE DE ATENCION codigo nombre ... FOLIO num FECHA fecha hora TIPO DE ATENCION : tipo
    patron = (
        r'SEDE DE ATENCION\s+(\d+)\s+([^\n]+?)\s+FOLIO\s+\d+\s+'
        r'FECHA\s+(\d{2}/\d{2}/\d{4})\s+(\d{2}:\d{2}:\d{2})\s+'
        r'TIPO DE ATENCION\s*:\s*([^\n]+)'
    )
    for match in re.finditer(patron, texto, re.IGNORECASE):
        servicios.append({
            'sede_codigo': match.group(1),
            'sede_nombre': match.group(2).strip(),
            'fecha': match.group(3),
            'hora': match.group(4),
            'tipo_atencion': match.group(5).strip()
        })
    return servicios

# ----------------------------------------------------------------------
# Extracción de medicamentos
# ----------------------------------------------------------------------
def extraer_medicamentos(texto):
    """
    Extrae fórmulas médicas estándar.
    Busca bloques "FORMULA MEDICA ESTANDAR" y extrae cantidad, descripción, dosis y frecuencia.
    """
    medicamentos = []
    bloques = re.split(r'FORMULA MEDICA ESTANDAR', texto)
    for bloque in bloques[1:]:
        # Tomar hasta el próximo encabezado (todo en mayúsculas) o fin
        fin = re.search(r'\n[A-Z ]{5,}\n', bloque)
        if fin:
            bloque = bloque[:fin.start()]
        lineas = bloque.split('\n')
        i = 0
        while i < len(lineas):
            linea = lineas[i].strip()
            # Busca líneas que comienzan con cantidad (ej: "1.00  NOMBRE")
            if re.match(r'^\d+\.?\d*\s+[A-Za-z0-9]', linea):
                partes = linea.split(maxsplit=1)
                cantidad = partes[0]
                desc = partes[1] if len(partes) > 1 else ''
                dosis = ''
                # Ver si la siguiente línea contiene dosis (números con mg/ml/g/mcg)
                if i+1 < len(lineas) and re.search(r'\d+[.,]?\d*\s*(MG|ML|G|MCG)', lineas[i+1], re.IGNORECASE):
                    dosis_line = lineas[i+1].strip()
                    dosis = dosis_line
                    desc += ' ' + dosis_line
                    i += 1
                # Buscar frecuencia en líneas siguientes (hasta 5 líneas)
                frecuencia = ''
                for j in range(i+1, min(i+6, len(lineas))):
                    if 'Frecuencia' in lineas[j]:
                        frecuencia = lineas[j].strip()
                        break
                medicamentos.append({
                    'cantidad': cantidad,
                    'descripcion': desc,
                    'dosis': dosis,
                    'frecuencia': frecuencia
                })
            i += 1
    return medicamentos

# ----------------------------------------------------------------------
# Extracción de procedimientos (quirúrgicos y no quirúrgicos)
# ----------------------------------------------------------------------
def extraer_procedimientos(texto):
    procedimientos = []
    # PROCEDIMIENTOS QUIRURGICOS
    patron_qx = r'PROCEDIMIENTOS QUIRURGICOS\s*\n\s*(\d+)\s+([^\n]+)'
    for match in re.finditer(patron_qx, texto, re.IGNORECASE):
        procedimientos.append({
            'tipo': 'quirurgico',
            'cantidad': match.group(1),
            'descripcion': match.group(2).strip()
        })
    # ORDENES DE PROCEDIMIENTOS NO QX
    patron_noqx = r'ORDENES DE PROCEDIMIENTOS NO QX\s*\n\s*(\d+)\s+([^\n]+)'
    for match in re.finditer(patron_noqx, texto, re.IGNORECASE):
        procedimientos.append({
            'tipo': 'no_quirurgico',
            'cantidad': match.group(1),
            'descripcion': match.group(2).strip()
        })
    return procedimientos

# ----------------------------------------------------------------------
# Extracción de laboratorios
# ----------------------------------------------------------------------
def extraer_laboratorios(texto):
    laboratorios = []
    bloques = re.split(r'ORDENES DE LABORATORIO', texto)
    for bloque in bloques[1:]:
        fin = re.search(r'\n[A-Z ]{5,}\n', bloque)
        if fin:
            bloque = bloque[:fin.start()]
        lineas = bloque.split('\n')
        for linea in lineas:
            linea = linea.strip()
            if re.match(r'^\d+\s+[A-Za-z]', linea):
                partes = linea.split(maxsplit=1)
                if len(partes) == 2:
                    laboratorios.append({
                        'cantidad': partes[0],
                        'descripcion': partes[1]
                    })
    return laboratorios

# ----------------------------------------------------------------------
# Extracción de imágenes diagnósticas
# ----------------------------------------------------------------------
def extraer_imagenes(texto):
    imagenes = []
    bloques = re.split(r'ORDENES DE IMAGENES DIAGNOSTICAS', texto)
    for bloque in bloques[1:]:
        fin = re.search(r'\n[A-Z ]{5,}\n', bloque)
        if fin:
            bloque = bloque[:fin.start()]
        lineas = bloque.split('\n')
        for linea in lineas:
            linea = linea.strip()
            if re.match(r'^\d+\s+[A-Za-z]', linea):
                partes = linea.split(maxsplit=1)
                if len(partes) == 2:
                    imagenes.append({
                        'cantidad': partes[0],
                        'descripcion': partes[1]
                    })
    return imagenes

# ----------------------------------------------------------------------
# Función principal de procesamiento
# ----------------------------------------------------------------------
def procesar_historia(archivo_entrada):
    """
    Lee un archivo de texto con la historia clínica y extrae la información facturable.
    Retorna un diccionario con los datos.
    """
    with open(archivo_entrada, 'r', encoding='utf-8') as f:
        contenido = f.read()
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
# Punto de entrada para línea de comandos
# ----------------------------------------------------------------------
if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Uso: python extractor.py <archivo_historia.txt> [archivo_salida.json]")
        sys.exit(1)

    archivo_entrada = sys.argv[1]
    if len(sys.argv) >= 3:
        archivo_salida = sys.argv[2]
    else:
        # Si no se especifica, guarda en la misma carpeta con nombre por defecto
        archivo_salida = 'facturacion.json'

    try:
        datos = procesar_historia(archivo_entrada)
        guardar_json(datos, archivo_salida)
        print(f"✅ Extracción completada. Resultados guardados en: {archivo_salida}")
        # También imprimimos un resumen en consola
        print(f"   Paciente: {datos['paciente'].get('nombre', 'N/A')} (Doc: {datos['paciente'].get('documento', 'N/A')})")
        print(f"   Servicios encontrados: {len(datos['servicios'])}")
        print(f"   Medicamentos: {len(datos['medicamentos'])}")
        print(f"   Procedimientos: {len(datos['procedimientos'])}")
        print(f"   Laboratorios: {len(datos['laboratorios'])}")
        print(f"   Imágenes: {len(datos['imagenes'])}")
    except Exception as e:
        print(f"❌ Error al procesar el archivo: {e}")
        sys.exit(1)
