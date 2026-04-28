#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script para corrigir encoding de todos os arquivos Python e Shell
Remove acentos e caracteres especiais, garantindo ASCII puro
"""

import os
import sys

def remove_accents(text):
    """Remove acentos e caracteres especiais."""
    replacements = {
        'a': 'aaaaaa',  # todos os 'a' com acento
        'e': 'eeee',    # todos os 'e' com acento  
        'i': 'iiii',    # todos os 'i' com acento
        'o': 'ooooo',   # todos os 'o' com acento
        'u': 'uuuu',    # todos os 'u' com acento
        'c': 'c',       # c cedilha
        'n': 'n',       # n til
    }

    result = text

    # Substituir caracteres especiais conhecidos
    special_chars = [
        (b'\xc3\xa1', 'a'), (b'\xc3\xa0', 'a'), (b'\xc3\xa3', 'a'), (b'\xc3\xa2', 'a'),
        (b'\xc3\xa9', 'e'), (b'\xc3\xaa', 'e'),
        (b'\xc3\xad', 'i'),
        (b'\xc3\xb3', 'o'), (b'\xc3\xb5', 'o'), (b'\xc3\xb4', 'o'),
        (b'\xc3\xba', 'u'),
        (b'\xc3\xa7', 'c'),
        (b'\xe2\x80\x94', '--'),  # em dash
        (b'\xe2\x80\x93', '-'),   # en dash
    ]

    if isinstance(result, str):
        result = result.encode('latin-1', errors='ignore')

    for special, replacement in special_chars:
        result = result.replace(special, replacement.encode('ascii'))

    return result.decode('ascii', errors='ignore')

def fix_file(filepath):
    """Corrige um arquivo."""
    try:
        # Ler arquivo
        with open(filepath, 'rb') as f:
            content_bytes = f.read()

        # Tentar decodificar
        content = None
        for encoding in ['utf-8', 'latin-1', 'cp1252']:
            try:
                content = content_bytes.decode(encoding)
                break
            except:
                continue

        if content is None:
            content = content_bytes.decode('latin-1', errors='replace')

        # Remover acentos
        fixed = remove_accents(content)

        # Garantir encoding declaration para Python
        if filepath.endswith('.py') and not fixed.startswith('# -*- coding: utf-8 -*-'):
            if fixed.startswith('#!'):
                lines = fixed.split('\n')
                lines.insert(1, '# -*- coding: utf-8 -*-')
                fixed = '\n'.join(lines)
            else:
                fixed = '# -*- coding: utf-8 -*-\n' + fixed

        # Escrever
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(fixed)

        return True
    except Exception as e:
        print(f"ERRO {filepath}: {e}")
        return False

def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))

    files = []
    for fname in os.listdir(script_dir):
        if fname.endswith(('.py', '.sh')) and fname != 'fix_encoding.py':
            fpath = os.path.join(script_dir, fname)
            if os.path.isfile(fpath):
                files.append(fpath)

    print("=" * 70)
    print("CORRIGINDO ENCODING")
    print("=" * 70)
    print()

    ok = 0
    fail = 0

    for fpath in sorted(files):
        fname = os.path.basename(fpath)
        print(f"{fname}...", end=' ')
        if fix_file(fpath):
            print("OK")
            ok += 1
        else:
            print("FALHOU")
            fail += 1

    print()
    print(f"Corrigidos: {ok}, Falharam: {fail}")
    print()

if __name__ == '__main__':
    main()
