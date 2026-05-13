import sys
import os

# Agregar directorio actual al path
sys.path.insert(0, os.path.dirname(__file__))

from webhook import handler

# Vercel busca una función 'handler' en el módulo
__all__ = ['handler']
