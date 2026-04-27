# ?? SOLUÇÃO DEFINITIVA - Chrome via APT (não Snap)

## ? Problema Identificado

Seu servidor tem Chrome instalado via **Snap**, que causa o erro:
```
no chrome binary at /usr/bin/google-chrome-stable
```

O Snap cria **links simbólicos** que o Selenium não consegue executar corretamente.

## ? Solução: Instalar Chrome via APT

### **NO SERVIDOR LINUX - Execute estes comandos:**

#### 1. Atualizar código do GitHub

```sh
cd ~/AviatorEstrela/AviatorEstrela
git pull origin master
```

#### 2. Dar permissões aos novos scripts

```sh
chmod +x detectar_chrome_real.sh
chmod +x instalar_chrome_apt.sh
chmod +x testar_chrome_selenium.sh
```

#### 3. Remover Snap e instalar Chrome via APT

```sh
./instalar_chrome_apt.sh
```

**O que este script faz:**
1. Remove Chrome/Chromium via Snap
2. Remove pacotes antigos
3. Adiciona repositório oficial do Google
4. Instala `google-chrome-stable` via APT (método correto)
5. Verifica instalação
6. Testa Chrome headless

#### 4. Testar Selenium

```sh
./testar_chrome_selenium.sh
```

**Saída esperada:**
```
=== TESTE BEM-SUCEDIDO! ===

O Chrome e Selenium estao funcionando corretamente.
Chrome path: /opt/google/chrome/chrome
```

#### 5. Iniciar serviço

```sh
./iniciar.sh
```

---

## ?? Diferença: Snap vs APT

### Chrome via Snap (PROBLEMÁTICO) ?

```sh
$ readlink -f /usr/bin/google-chrome-stable
/snap/bin/chromium  # Link para snap, não executável real
```

### Chrome via APT (CORRETO) ?

```sh
$ readlink -f /usr/bin/google-chrome-stable
/opt/google/chrome/chrome  # Binário ELF real executável
```

---

## ?? Checklist Final

- [ ] `git pull` executado
- [ ] `./instalar_chrome_apt.sh` executado com sucesso
- [ ] `./testar_chrome_selenium.sh` passou sem erros
- [ ] Mensagem "TESTE BEM-SUCEDIDO!" apareceu
- [ ] Chrome instalado em `/opt/google/chrome/chrome`
- [ ] `./iniciar.sh` iniciou sem erros
- [ ] Dashboard acessível em `http://213.136.66.116:5005`

---

**Execute `./instalar_chrome_apt.sh` no servidor e o problema será resolvido!** ??
