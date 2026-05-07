"""Converte todos os scripts .sh de CRLF para LF (compatibilidade Linux)."""
import glob

files = glob.glob('*.sh')
count = 0
for f in files:
    data = open(f, 'rb').read()
    fixed = data.replace(b'\r\n', b'\n').replace(b'\r', b'\n')
    if fixed != data:
        open(f, 'wb').write(fixed)
        count += 1
        print(f'Corrigido: {f}')
    else:
        print(f'OK (ja LF): {f}')

print(f'\nTotal: {count} arquivo(s) convertido(s) para LF.')
