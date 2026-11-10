"""Configuración de pytest: añade la raíz del proyecto al sys.path."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
