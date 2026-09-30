"""Compatibility entry to the shared current PERT engine.

Full certification and export use pert_cli with the documented intake state.
"""
from pathlib import Path
import sys

_scripts = Path(__file__).resolve().parents[1] / 'scripts'
sys.path.insert(0, str(_scripts))
from motor_pert import verificar

if __name__ == '__main__':
    from pert_cli import main
    sys.exit(main())
