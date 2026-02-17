"""
utilidades.py - Funciones auxiliares para el procesamiento de historias clínicas.
"""

import re
import json
from datetime import datetime

def cargar_archivo(ruta_archivo):
    """
    Lee un archivo de texto y retorna su contenido.
    """
    try:
        with open(ruta_archivo, 'r', encoding='utf-8') as f:
            return f.read()
    except FileNotFoundError:
        print(f"Error: No se encontró el archivo {ruta_archivo}")
        return None
    except Exception as e:
        print(f"Error al leer el archivo: {e}")
        return None

def limpiar_texto(texto):
    """
    Elimina espacios redundantes y saltos de línea excesivos.
    """
    if not texto:
        return ""
    # Reemplaza múltiples saltos de línea por uno solo
    texto = re.sub(r'\n\s*\n', '\n', texto)
    # Elimina espacios al inicio y final de cada línea
    lineas = [linea.strip() for linea in texto.split('\n')]
    return '\n'.join(lineas)

def guardar_json(datos, ruta_salida):
    """
    Guarda un diccionario en un archivo JSON con formato legible.
    """
    try:
        with open(ruta_salida, 'w', encoding='utf-8') as f:
            json.dump(datos, f, indent=2, ensure_ascii=False)
        print(f"Archivo guardado: {ruta_salida}")
    except Exception as e:
        print(f"Error al guardar JSON: {e}")

def extraer_fechas(texto):
    """
    Busca todas las fechas en formato DD/MM/AAAA dentro del texto.
    Retorna una lista de fechas encontradas.
    """
    patron = r'\b(\d{2}/\d{2}/\d{4})\b'
    return re.findall(patron, texto)

def formatear_resultado(datos):
    """
    Imprime en consola un resumen formateado de los datos extraídos.
    """
    print("\n" + "="*60)
    print("RESUMEN DE EXTRACCIÓN")
    print("="*60)
    
    if datos.get('paciente'):
        p = datos['paciente']
        print(f"Paciente: {p.get('nombre', 'N/A')} | Documento: {p.get('documento', 'N/A')}")
        print(f"Edad: {p.get('edad', 'N/A')} años | Fec. Nac: {p.get('fecha_nacimiento', 'N/A')}")
    
    print(f"\nServicios encontrados: {len(datos.get('servicios', []))}")
    for s in datos.get('servicios', [])[:3]:  # muestra solo 3
        print(f"  - {s.get('tipo_atencion')} en {s.get('sede_nombre')} el {s.get('fecha')}")
    
    print(f"\nMedicamentos: {len(datos.get('medicamentos', []))}")
    print(f"Procedimientos: {len(datos.get('procedimientos', []))}")
    print(f"Laboratorios: {len(datos.get('laboratorios', []))}")
    print(f"Imágenes: {len(datos.get('imagenes', []))}")
    print("="*60)

def es_fecha_valida(fecha_str):
    """
    Verifica si una cadena en formato DD/MM/AAAA es una fecha válida.
    """
    try:
        datetime.strptime(fecha_str, "%d/%m/%Y")
        return True
    except ValueError:
        return False
