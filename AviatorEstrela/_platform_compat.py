# _platform_compat.py
# Compatibilidade cross-platform: stub do winsound para Linux.
# O aviator_service2.py usa winsound.Beep() que so existe no Windows.
# Este modulo cria um stub silencioso no Linux.
# Uso: import _platform_compat  (antes de import winsound)

import sys

if sys.platform != "win32":
    import types
    _ws = types.ModuleType("winsound")
    _ws.Beep = lambda freq, dur: None
    _ws.MB_OK = 0
    _ws.SND_FILENAME = 0
    _ws.SND_ASYNC = 0
    _ws.PlaySound = lambda sound, flags: None
    sys.modules["winsound"] = _ws
