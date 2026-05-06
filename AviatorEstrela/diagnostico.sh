
#!/bin/bash

cd "/root/AviatorEstrela/AviatorEstrela"

source "/root/AviatorEstrela/AviatorEstrela/venv/bin/activate"

python ml_diagnostico.py "$@"

