#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
hc_lector.py

Script para extraer información facturable de una historia clínica en texto plano.
Lee un archivo de texto (historia.txt) y genera un archivo JSON (facturacion.json)
con los datos estructurados.

Autor: [Tu nombre]
Fecha: [Fecha actual]
"""

import re
import json
import sys
import os
from datetime import datetime

# ----------------------------------------------------------------------
# Configuración
# ----------------------------------------------------------------------
ARCHIVO_ENTRADA = "historia.txt"   # Nombre del archivo de entrada
ARCHIVO_SALIDA = "facturacion.json" # Nombre del archivo de salida
CODIFICACION = "utf-8"               # Codificación del archivo

# ----------------------------------------------------------------------
# Funciones de utilidad
# ----------------------------------------------------------------------
def limpiar_texto(texto):
    """
    Elimina líneas vacías múltiples y espacios redundantes.
    """
    # Reemplaza saltos de línea múltiples por uno solo
    texto = re.sub(r'\n\s*\n', '\n', texto)
    # Elimina espacios al inicio y final de cada línea
    lineas = [linea.strip() for linea in texto.split('\n')]
    # Vuelve a unir
    return '\n'.join(lineas)

def validar_archivo(ruta):
    """
    Verifica que el archivo exista y sea legible.
    """
    if not os.path.exists(ruta):
        print(f"❌ Error: El archivo '{ruta}' no existe.")
        return False
    if not os.path.isfile(ruta):
        print(f"❌ Error: '{ruta}' no es un archivo válido.")
        return False
    return True

def guardar_json(datos, ruta):
    """
    Guarda los datos en un archivo JSON con formato legible.
    """
    try:
        with open(ruta, 'w', encoding=CODIFICACION) as f:
            json.dump(datos, f, indent=2, ensure_ascii=False)
        return True
    except Exception as e:
        print(f"❌ Error al guardar JSON: {e}")
        return False

# ----------------------------------------------------------------------
# Funciones de extracción (cada una se enfoca en una sección)
# ----------------------------------------------------------------------
def extraer_paciente(texto):
    """
    Extrae datos básicos del paciente: documento, nombre, fecha de nacimiento, edad.
    """
    paciente = {}

    # Documento (CC 123456789)
    patron_doc = r'CC\s*(\d+)'
    match = re.search(patron_doc, texto)
    if match:
        paciente['documento'] = match.group(1)
    else:
        paciente['documento'] = None

    # Nombre (entre '--' y 'Fec. Nacimiento')
    patron_nombre = r'--\s*([A-ZÁÉÍÓÚÑ\s]+?)\s+Fec\.\s*Nacimiento'
    match = re.search(patron_nombre, texto)
    if match:
        paciente['nombre'] = match.group(1).strip()
    else:
        paciente['nombre'] = None

    # Fecha de nacimiento (dd/mm/aaaa)
    patron_fn = r'Fec\.\s*Nacimiento:\s*(\d{2}/\d{2}/\d{4})'
    match = re.search(patron_fn, texto)
    if match:
        paciente['fecha_nacimiento'] = match.group(1)
    else:
        paciente['fecha_nacimiento'] = None

    # Edad actual (XX AÑOS)
    patron_edad = r'Edad\s*actual:\s*(\d+)\s*AÑOS'
    match = re.search(patron_edad, texto)
    if match:
        paciente['edad'] = int(match.group(1))
    else:
        paciente['edad'] = None

    return paciente

def extraer_servicios(texto):
    """
    Extrae todos los registros de atención (servicios) basados en las líneas
    'SEDE DE ATENCION ... FOLIO ... FECHA ... TIPO DE ATENCION'
    """
    servicios = []
    # Patrón mejorado para capturar también la sede y el tipo de atención
    patron = (
        r'SEDE DE ATENCION\s+(\d+)\s+([^\n]+?)\s+'
        r'FOLIO\s+\d+\s+'
        r'FECHA\s+(\d{2}/\d{2}/\d{4})\s+(\d{2}:\d{2}:\d{2})\s+'
        r'TIPO DE ATENCION\s*:\s*([^\n]+)'
    )
    for match in re.finditer(patron, texto, re.IGNORECASE):
        servicio = {
            'sede_codigo': match.group(1),
            'sede_nombre': match.group(2).strip(),
            'fecha': match.group(3),
            'hora': match.group(4),
            'tipo_atencion': match.group(5).strip()
        }
        servicios.append(servicio)

    return servicios

def extraer_medicamentos(texto):
    """
    Extrae todas las fórmulas médicas estándar.
    Busca bloques 'FORMULA MEDICA ESTANDAR' y dentro de ellos extrae:
    - Cantidad
    - Descripción (incluye dosis si está en línea siguiente)
    - Vía
    - Frecuencia
    - Estado (NUEVO, CONTINUAR, etc.)
    """
    medicamentos = []
    # Dividir el texto por el encabezado "FORMULA MEDICA ESTANDAR"
    bloques = re.split(r'FORMULA MEDICA ESTANDAR', texto)

    # El primer bloque (antes del primer encabezado) no sirve, lo ignoramos
    for bloque in bloques[1:]:
        # Limitar el bloque hasta el siguiente encabezado (todo en mayúsculas)
        fin = re.search(r'\n[A-Z ]{5,}\n', bloque)
        if fin:
            bloque = bloque[:fin.start()]

        lineas = bloque.split('\n')
        i = 0
        while i < len(lineas):
            linea = lineas[i].strip()
            if not linea:
                i += 1
                continue

            # Detectar línea que comienza con cantidad (ej. "1.00  ...")
            if re.match(r'^\s*\d+\.\d+\s+', linea):
                partes = linea.split(maxsplit=1)
                if len(partes) < 2:
                    i += 1
                    continue
                cantidad = partes[0].strip()
                descripcion = partes[1].strip()

                # Buscar dosis en la siguiente línea (si comienza con número y unidad)
                dosis = ""
                if i + 1 < len(lineas):
                    sig = lineas[i + 1].strip()
                    if re.match(r'^\d+[.,]?\d*\s*(MG|ML|G|MCG|UI)', sig, re.IGNORECASE):
                        dosis = sig
                        descripcion += " " + sig
                        i += 1  # saltar esa línea

                # Buscar vía (ej. "Via ORAL", "Via INTRAVENOSO")
                via = ""
                for j in range(i, min(i+5, len(lineas))):
                    if 'Via' in lineas[j]:
                        via = lineas[j].strip()
                        break

                # Buscar frecuencia (ej. "Frecuencia 24 Horas")
                frecuencia = ""
                for j in range(i, min(i+5, len(lineas))):
                    if 'Frecuencia' in lineas[j]:
                        frecuencia = lineas[j].strip()
                        break

                # Buscar estado (ej. "Estado: NUEVO")
                estado = ""
                for j in range(i, min(i+5, len(lineas))):
                    if 'Estado:' in lineas[j]:
                        estado = lineas[j].strip()
                        break

                medicamentos.append({
                    'cantidad': cantidad,
                    'descripcion': descripcion,
                    'dosis': dosis,
                    'via': via,
                    'frecuencia': frecuencia,
                    'estado': estado
                })
            i += 1

    return medicamentos

def extraer_procedimientos(texto):
    """
    Extrae procedimientos quirúrgicos y no quirúrgicos.
    - PROCEDIMIENTOS QUIRURGICOS
    - ORDENES DE PROCEDIMIENTOS NO QX
    """
    procedimientos = []

    # Procedimientos quirúrgicos
    patron_qx = r'PROCEDIMIENTOS QUIRURGICOS\s*\n\s*(\d+)\s+([^\n]+)'
    for match in re.finditer(patron_qx, texto, re.IGNORECASE):
        procedimientos.append({
            'tipo': 'quirurgico',
            'cantidad': match.group(1).strip(),
            'descripcion': match.group(2).strip()
        })

    # Procedimientos no quirúrgicos
    patron_noqx = r'ORDENES DE PROCEDIMIENTOS NO QX\s*\n\s*(\d+)\s+([^\n]+)'
    for match in re.finditer(patron_noqx, texto, re.IGNORECASE):
        procedimientos.append({
            'tipo': 'no_quirurgico',
            'cantidad': match.group(1).strip(),
            'descripcion': match.group(2).strip()
        })

    return procedimientos

def extraer_laboratorios(texto):
    """
    Extrae órdenes de laboratorio.
    Busca el encabezado 'ORDENES DE LABORATORIO' y dentro las líneas con cantidad y descripción.
    """
    laboratorios = []
    bloques = re.split(r'ORDENES DE LABORATORIO', texto)

    for bloque in bloques[1:]:
        fin = re.search(r'\n[A-Z ]{5,}\n', bloque)
        if fin:
            bloque = bloque[:fin.start()]

        lineas = bloque.split('\n')
        for linea in lineas:
            linea = linea.strip()
            if not linea:
                continue
            # Buscar líneas que empiecen con un número (cantidad) y luego texto
            if re.match(r'^\s*\d+\s+', linea):
                partes = linea.split(maxsplit=1)
                if len(partes) == 2:
                    laboratorios.append({
                        'cantidad': partes[0].strip(),
                        'descripcion': partes[1].strip()
                    })

    return laboratorios

def extraer_imagenes(texto):
    """
    Extrae órdenes de imágenes diagnósticas.
    Busca 'ORDENES DE IMAGENES DIAGNOSTICAS' y dentro las líneas con cantidad y descripción.
    """
    imagenes = []
    bloques = re.split(r'ORDENES DE IMAGENES DIAGNOSTICAS', texto)

    for bloque in bloques[1:]:
        fin = re.search(r'\n[A-Z ]{5,}\n', bloque)
        if fin:
            bloque = bloque[:fin.start()]

        lineas = bloque.split('\n')
        for linea in lineas:
            linea = linea.strip()
            if not linea:
                continue
            if re.match(r'^\s*\d+\s+', linea):
                partes = linea.split(maxsplit=1)
                if len(partes) == 2:
                    imagenes.append({
                        'cantidad': partes[0].strip(),
                        'descripcion': partes[1].strip()
                    })

    return imagenes

def extraer_otros(texto):
    """
    Extrae otras secciones como 'INTERCONSULTAS', 'EVOLUCION', etc., si se desea.
    Por ahora es un placeholder.
    """
    # Podríamos extraer interconsultas, transfusiones, etc.
    otros = {}
    return otros

# ----------------------------------------------------------------------
# Función principal
# ----------------------------------------------------------------------
def procesar_historia(ruta_archivo):
    """
    Orquesta todas las extracciones y retorna un diccionario con los resultados.
    """
    print(f"📖 Leyendo archivo: {ruta_archivo}")
    try:
        with open(ruta_archivo, 'r', encoding=CODIFICACION) as f:
            contenido = f.read()
    except Exception as e:
        print(f"❌ Error al leer archivo: {e}")
        return None

    contenido = limpiar_texto(contenido)
    print("✅ Texto limpiado.")

    resultado = {
        'paciente': extraer_paciente(contenido),
        'servicios': extraer_servicios(contenido),
        'medicamentos': extraer_medicamentos(contenido),
        'procedimientos': extraer_procedimientos(contenido),
        'laboratorios': extraer_laboratorios(contenido),
        'imagenes': extraer_imagenes(contenido),
        'otros': extraer_otros(contenido)
    }

    # Resumen de lo encontrado
    print("📊 Resumen de extracción:")
    print(f"   - Paciente: {resultado['paciente'].get('nombre', 'Desconocido')}")
    print(f"   - Servicios encontrados: {len(resultado['servicios'])}")
    print(f"   - Medicamentos encontrados: {len(resultado['medicamentos'])}")
    print(f"   - Procedimientos encontrados: {len(resultado['procedimientos'])}")
    print(f"   - Laboratorios encontrados: {len(resultado['laboratorios'])}")
    print(f"   - Imágenes encontradas: {len(resultado['imagenes'])}")

    return resultado

# ----------------------------------------------------------------------
# Punto de entrada
# ----------------------------------------------------------------------
if __name__ == "__main__":
    print("=" * 50)
    print("HC LECTOR FACTURADOR")
    print("=" * 50)

    # Validar archivo de entrada
    if not validar_archivo(ARCHIVO_ENTRADA):
        print("\n💡 Asegúrate de que el archivo '{}' esté en la misma carpeta que este script.".format(ARCHIVO_ENTRADA))
        sys.exit(1)

    # Procesar
    datos = procesar_historia(ARCHIVO_ENTRADA)

    if datos is None:
        print("❌ No se pudo procesar la historia.")
        sys.exit(1)

    # Guardar resultado
    if guardar_json(datos, ARCHIVO_SALIDA):
        print(f"\n✅ Resultado guardado en '{ARCHIVO_SALIDA}'")
    else:
        print("❌ Error al guardar el resultado.")

    print("\n✨ Proceso completado.")
