"""
test_extractor.py - Pruebas unitarias para el módulo extractor.
"""

import unittest
import sys
import os

# Agregar la carpeta src al path para poder importar extractor
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))

from extractor import (
    extraer_paciente,
    extraer_servicios,
    extraer_medicamentos,
    extraer_procedimientos,
    extraer_laboratorios,
    extraer_imagenes,
    procesar_historia
)

class TestExtractor(unittest.TestCase):
    
    def test_extraer_paciente(self):
        texto = """
        HISTORIA CLINICA No. CC 123456789 -- JUAN PEREZ GOMEZ
        Fac. Nacimiento: 15/05/1980 Edad actual:45 AÑOS Sexo: M
        """
        esperado = {
            'documento': '123456789',
            'nombre': 'JUAN PEREZ GOMEZ',
            'fecha_nacimiento': '15/05/1980',
            'edad': 45
        }
        resultado = extraer_paciente(texto)
        self.assertEqual(resultado, esperado)
    
    def test_extraer_paciente_sin_datos(self):
        texto = "Texto sin información de paciente"
        resultado = extraer_paciente(texto)
        self.assertEqual(resultado, {})
    
    def test_extraer_servicios(self):
        texto = """
        SEDE DE ATENCION 0304 CLINICA PIE DE LA POPA
        FOLIO 78 FECHA 30/10/2025 05:38:01 TIPO DE ATENCION : HOSPITALIZACION
        SEDE DE ATENCION 0304 CLINICA PIE DE LA POPA
        FOLIO 79 FECHA 30/10/2025 07:28:19 TIPO DE ATENCION : HOSPITALIZACION
        """
        resultado = extraer_servicios(texto)
        self.assertEqual(len(resultado), 2)
        self.assertEqual(resultado[0]['sede_codigo'], '0304')
        self.assertEqual(resultado[0]['sede_nombre'], 'CLINICA PIE DE LA POPA')
        self.assertEqual(resultado[0]['fecha'], '30/10/2025')
        self.assertEqual(resultado[0]['hora'], '05:38:01')
        self.assertEqual(resultado[0]['tipo_atencion'], 'HOSPITALIZACION')
    
    def test_extraer_medicamentos(self):
        texto = """
        FORMULA MEDICA ESTANDAR
        1.00 OMEPRAZOL 20 MG TABLETA 20 mg
        Dosis: 1,00 TABLETA Via ORAL Frecuencia 24 Horas Estado: NUEVO
        2.00 ACETAMINOFEN 500 MG TABLETA 500 mg
        Dosis: 1,00 TABLETA Via ORAL Frecuencia 8 Horas
        """
        resultado = extraer_medicamentos(texto)
        self.assertEqual(len(resultado), 2)
        self.assertEqual(resultado[0]['cantidad'], '1.00')
        self.assertIn('OMEPRAZOL', resultado[0]['descripcion'])
        self.assertEqual(resultado[1]['cantidad'], '2.00')
        self.assertIn('ACETAMINOFEN', resultado[1]['descripcion'])
    
    def test_extraer_procedimientos(self):
        texto = """
        PROCEDIMIENTOS QUIRURGICOS
        1 MASTECTOMIA IZQUIERDA
        ORDENES DE PROCEDIMIENTOS NO QX
        2 CURACION DE HERIDA
        """
        resultado = extraer_procedimientos(texto)
        self.assertEqual(len(resultado), 2)
        quirurgico = next(p for p in resultado if p['tipo'] == 'quirurgico')
        no_qx = next(p for p in resultado if p['tipo'] == 'no_quirurgico')
        self.assertEqual(quirurgico['cantidad'], '1')
        self.assertEqual(quirurgico['descripcion'], 'MASTECTOMIA IZQUIERDA')
        self.assertEqual(no_qx['cantidad'], '2')
        self.assertEqual(no_qx['descripcion'], 'CURACION DE HERIDA')
    
    def test_extraer_laboratorios(self):
        texto = """
        ORDENES DE LABORATORIO
        1 HEMOGRAMA IV
        2 IONOGRAMA [CLORO SODIO POTASIO]
        """
        resultado = extraer_laboratorios(texto)
        self.assertEqual(len(resultado), 2)
        self.assertEqual(resultado[0]['cantidad'], '1')
        self.assertEqual(resultado[0]['descripcion'], 'HEMOGRAMA IV')
        self.assertEqual(resultado[1]['cantidad'], '2')
        self.assertEqual(resultado[1]['descripcion'], 'IONOGRAMA [CLORO SODIO POTASIO]')
    
    def test_extraer_imagenes(self):
        texto = """
        ORDENES DE IMAGENES DIAGNOSTICAS
        1 RADIOGRAFIA DE TORAX
        2 TOMOGRAFIA COMPUTADA DE CRANEO
        """
        resultado = extraer_imagenes(texto)
        self.assertEqual(len(resultado), 2)
        self.assertEqual(resultado[0]['cantidad'], '1')
        self.assertEqual(resultado[0]['descripcion'], 'RADIOGRAFIA DE TORAX')
        self.assertEqual(resultado[1]['cantidad'], '2')
        self.assertEqual(resultado[1]['descripcion'], 'TOMOGRAFIA COMPUTADA DE CRANEO')
    
    def test_procesar_historia_completa(self):
        # Simula un fragmento de la historia clínica real
        texto = """
        HISTORIA CLINICA No. CC 73129351 -- JAVIER ENRIQUE MARRUGO RODRIGUEZ
        Fac. Nacimiento: 03/08/1967 Edad actual:59 AÑOS Sexo: M
        SEDE DE ATENCION 0304 CLINICA PIE DE LA POPA
        FOLIO 78 FECHA 30/10/2025 05:38:01 TIPO DE ATENCION : HOSPITALIZACION
        FORMULA MEDICA ESTANDAR
        1.00 OMEPRAZOL 20 MG CADA 24 HRS
        Dosis: 1,00 TABLETA Via ORAL Frecuencia 24 Horas
        PROCEDIMIENTOS QUIRURGICOS
        1 MASTECTOMIA IZQUIERDA
        ORDENES DE LABORATORIO
        1 HEMOGRAMA IV
        ORDENES DE IMAGENES DIAGNOSTICAS
        1 RADIOGRAFIA DE TORAX
        """
        resultado = procesar_historia(texto)
        self.assertIn('paciente', resultado)
        self.assertEqual(resultado['paciente']['documento'], '73129351')
        self.assertEqual(len(resultado['servicios']), 1)
        self.assertEqual(len(resultado['medicamentos']), 1)
        self.assertEqual(len(resultado['procedimientos']), 1)
        self.assertEqual(len(resultado['laboratorios']), 1)
        self.assertEqual(len(resultado['imagenes']), 1)

if __name__ == '__main__':
    unittest.main()
