# Solução Aplicada - Chrome no Linux

## ? O Que Foi Feito

### 1. **Modificação em `aviator_service2.py`**

A função `iniciar_driver()` foi atualizada com:

- **Detecção automática do Chrome** em múltiplos caminhos:
  - `/usr/bin/google-chrome-stable`
  - `/usr/bin/google-chrome`
  - `/usr/bin/chromium-browser`
  - `/usr/bin/chromium`
  - `/snap/bin/chromium`
  - Caminhos do Windows (para compatibilidade)

- **Argumentos adicionais para headless Linux**:
  - `--no-sandbox` (necessário para root)
  - `--disable-dev-shm-usage` (evita problemas de memória compartilhada)
  - `--disable-gpu` (desnecessário em headless)
  - `--disable-blink-features=AutomationControlled` (anti-detecção)

### 2. **Script `solucao_chrome.sh` Criado**

Script standalone que:
- Instala Google Chrome automaticamente
- Instala ChromeDriver compatível com a versão do Chrome
- Testa Chrome headless
- Detecta versão do Chrome e baixa driver correspondente

### 3. **`instalar_linux.sh` Atualizado**

Agora inclui instalação automática do ChromeDriver:
- **Etapa 3/7**: Verifica e instala ChromeDriver
- Suporte para Chrome 115+ (Chrome for Testing)
- Fallback para versões antigas
- Adiciona `unzip` e `curl` às dependências

---

## ?? Como Usar no Seu Servidor

### **Opção 1: Reinstalar com Script Atualizado** (Recomendado)

```sh
# No servidor Ubuntu
cd ~/AviatorEstrela/AviatorEstrela

# Baixar versão atualizada do repositório
git pull origin master

# Executar instalador atualizado
chmod +x instalar_linux.sh
./instalar_linux.sh

# Iniciar serviço
./iniciar.sh
```

### **Opção 2: Usar Script de Solução Rápida**

```sh
# No servidor
cd ~/AviatorEstrela/AviatorEstrela

# Baixar solucao_chrome.sh do repositório
git pull origin master

# Executar script de solução
chmod +x solucao_chrome.sh
./solucao_chrome.sh

# Iniciar serviço
./iniciar.sh
```

### **Opção 3: Instalação Manual do Chrome/ChromeDriver**

```sh
# 1. Instalar Chrome
cd /tmp
wget https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb
sudo dpkg -i google-chrome-stable_current_amd64.deb
sudo apt-get install -f -y

# 2. Verificar versão
google-chrome --version

# 3. Instalar ChromeDriver (para Chrome 120+)
wget https://storage.googleapis.com/chrome-for-testing-public/120.0.6099.109/linux64/chromedriver-linux64.zip
unzip chromedriver-linux64.zip
sudo mv chromedriver-linux64/chromedriver /usr/local/bin/
sudo chmod +x /usr/local/bin/chromedriver

# 4. Verificar
chromedriver --version

# 5. Atualizar código do aviator_service2.py
cd ~/AviatorEstrela/AviatorEstrela
git pull origin master

# 6. Iniciar
./iniciar.sh
```

---

## ?? Verificação

Antes de iniciar o serviço, verifique:

```sh
# 1. Chrome instalado?
google-chrome --version
# Esperado: Google Chrome 120.x.x.x ou superior

# 2. ChromeDriver instalado?
chromedriver --version
# Esperado: ChromeDriver 120.x.x.x

# 3. Chrome acessível?
which google-chrome
# Esperado: /usr/bin/google-chrome-stable ou /usr/bin/google-chrome

# 4. Testar headless
google-chrome --headless --disable-gpu --dump-dom https://www.google.com 2>/dev/null | grep Google
# Esperado: Ver HTML do Google
```

---

## ?? Saída Esperada ao Iniciar

```
  Aviator ML Intelligence
  Dashboard: http://localhost:5005
  Ctrl+C para encerrar.

 * Running on http://127.0.0.1:5005
 * Running on http://213.136.66.116:5005

[24/04/2026 21:15:30] Iniciando Serviço Principal...
[24/04/2026 21:15:30] Iniciando driver Chrome (modo headless)...
[24/04/2026 21:15:30] Chrome encontrado em: /usr/bin/google-chrome-stable
[24/04/2026 21:15:32] Iniciando Login...
[24/04/2026 21:15:35] Login bem-sucedido!
[24/04/2026 21:15:36] Captura iniciada...
```

---

## ?? Troubleshooting

### **Erro: "Chrome binary not found"**

```sh
# Verificar se Chrome está instalado
google-chrome --version

# Se não estiver:
./solucao_chrome.sh
```

### **Erro: "ChromeDriver version mismatch"**

```sh
# Reinstalar ChromeDriver compatível
./solucao_chrome.sh
```

### **Erro: "DevToolsActivePort file doesn't exist"**

Adicione ao `iniciar.sh`:

```sh
#!/bin/bash
cd "$SVC_DIR"
source "$VENV_DIR/bin/activate"

# Adicionar estas linhas:
export DISPLAY=:99
Xvfb :99 -screen 0 1920x1080x24 > /dev/null 2>&1 &
sleep 2

python aviator_service2.py
```

E instale Xvfb:
```sh
sudo apt-get install xvfb -y
```

### **Erro: Permission denied (executando como root)**

O argumento `--no-sandbox` já foi adicionado, mas se persistir:

```sh
# Criar usuário não-root
sudo useradd -m aviator
sudo chown -R aviator:aviator ~/AviatorEstrela

# Executar como esse usuário
sudo -u aviator ./iniciar.sh
```

---

## ?? Resumo das Mudanças

| Arquivo | Mudança | Benefício |
|---------|---------|-----------|
| `aviator_service2.py` | Detecção automática de Chrome | Funciona em Windows e Linux |
| `aviator_service2.py` | Argumentos `--no-sandbox`, `--disable-dev-shm-usage` | Compatível com servidores headless |
| `instalar_linux.sh` | Instala ChromeDriver automaticamente | Instalação completa em 1 comando |
| `solucao_chrome.sh` | Script dedicado Chrome+Driver | Solução rápida para problemas |

---

## ? Checklist Pós-Aplicação

- [ ] `git pull` executado para obter código atualizado
- [ ] Chrome instalado: `google-chrome --version`
- [ ] ChromeDriver instalado: `chromedriver --version`
- [ ] Serviço iniciado sem erros: `./iniciar.sh`
- [ ] Dashboard acessível: `http://IP_SERVIDOR:5005`
- [ ] Log mostra "Chrome encontrado em: ..."

---

## ?? Próximos Passos

Após resolver o erro do Chrome:

```sh
# 1. Retreinar modelos com as melhorias
./diagnostico.sh --clean
./diagnostico.sh --retrain

# 2. Verificar diagnóstico
./diagnostico.sh

# 3. Monitorar dashboard
# Abrir http://IP_SERVIDOR:5005
```

---

**Criado em**: Dezembro 2024  
**Versão**: 2.1 - Chrome Auto-Detection
