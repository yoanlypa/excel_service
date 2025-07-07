# exceptions.py
class ParseError(Exception):
    """Error de parseo de Excel"""

class ApiError(Exception):
    """Error en la llamada a la API de Django"""
