# Zajistí, že kořen repa je na sys.path - testy tak vidí `config` i balíček `src`.
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
