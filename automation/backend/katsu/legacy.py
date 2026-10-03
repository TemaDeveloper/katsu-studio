"""Load the existing, unchanged production tools by their explicit paths."""
import importlib.util
from functools import lru_cache
from .config import WORKSPACE


@lru_cache
def load(name):
    spec = importlib.util.spec_from_file_location(name, WORKSPACE / (name + '.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module
