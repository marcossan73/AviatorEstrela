"""Corrige bytes latin-1 corrompidos nas linhas novas do aviator_service2.py."""
data = open('aviator_service2.py', 'rb').read()

fixes = [
    (b'executa a an\xe1lise ML sem bloquear a captura de dados', b'executa a analise ML sem bloquear a captura de dados'),
    (b'evita execu\xe7\xf5es concorrentes', b'evita execucoes concorrentes'),
    (b'refer\xeancia mut\xe1vel', b'referencia mutavel'),
    (b'Erro na an\xe1lise background', b'Erro na analise background'),
    (b'an\xe1lise ML em background', b'analise ML em background'),
]

count = 0
for old, new in fixes:
    if old in data:
        data = data.replace(old, new)
        count += 1

open('aviator_service2.py', 'wb').write(data)
print(f'Pronto! {count} substituicoes realizadas.')
