# ?? Aviator ML Intelligence - Instalação Simplificada

## ? Instalação Rápida (1 Comando)

```sh
# No servidor Ubuntu/Debian
cd ~
git clone https://github.com/marcossan73/AviatorEstrela.git
cd AviatorEstrela/AviatorEstrela
chmod +x setup_aviator.sh
./setup_aviator.sh
```

**Pronto!** O script cuida de tudo automaticamente.

---

## ?? O Que o Script Instala

### Componentes do Sistema
- ? **Python 3.10+** (via PPA se necessário)
- ? **Google Chrome** (via APT, não Snap)
- ? **ChromeDriver** (versão compatível)
- ? **Xvfb** (display virtual para headless)
- ? **Screen** (sessões persistentes)
- ? **Dependências** (build-essential, libffi-dev, etc.)

### Dependências Python
- ? **Flask 3.0.3** (dashboard web)
- ? **Selenium 4.21.0** (automação browser)
- ? **Pandas 2.2.2** (análise de dados)
- ? **Scikit-learn 1.5.0** (machine learning)
- ? **pytz 2024.1** (timezone Brasília)
- ? **Webdriver Manager 4.0.1** (gerencia ChromeDriver)

### Scripts de Controle
- ? `iniciar.sh` - Inicia em primeiro plano
- ? `iniciar_background.sh` - Inicia em background (nohup)
- ? `parar.sh` - Para o serviço
- ? `status.sh` - Mostra status e recursos
- ? `diagnostico.sh` - Ferramentas ML

### Configurações
- ? **Timezone**: Horário de Brasília (GMT-3)
- ? **Compatibilidade**: Linux (stub winsound)
- ? **Ambiente Virtual**: Isolado em `venv/`
- ? **Chrome**: Detecção automática de binário

---

## ?? Comandos Principais

### Iniciar Serviço

```sh
# Primeiro plano (ver logs em tempo real)
./iniciar.sh

# Background (pode desconectar SSH)
./iniciar_background.sh
```

### Controlar Serviço

```sh
# Ver status
./status.sh

# Parar
./parar.sh

# Ver logs
tail -f aviator_service.log
```

### Machine Learning

```sh
# Diagnóstico completo
./diagnostico.sh

# Retreinar todos os modelos
./diagnostico.sh --retrain

# Retreinar apenas >50x
./diagnostico.sh --retrain >50

# Limpar modelos antigos
./diagnostico.sh --clean

# Ver histórico de assertividade
./diagnostico.sh --history
```

---

## ?? Acessar Dashboard

Após iniciar o serviço:

```
http://SEU_IP:5005
```

Exemplo: `http://213.136.66.116:5005`

---

## ?? Configuração Inicial

### 1. Editar Credenciais

```sh
nano aviator_service2.py
```

Alterar linhas:
```python
EMAIL = "seu_email@gmail.com"
SENHA = "sua_senha"
```

### 2. Iniciar Serviço

```sh
./iniciar_background.sh
```

### 3. Verificar Status

```sh
./status.sh
```

---

## ?? Estrutura de Arquivos

```
~/AviatorEstrela/AviatorEstrela/
??? aviator_service2.py          # Serviço principal
??? ml_diagnostico.py             # Diagnóstico ML
??? setup_aviator.sh              # ? SCRIPT DE INSTALAÇÃO
?
??? Scripts de Controle
?   ??? iniciar.sh                # Inicia primeiro plano
?   ??? iniciar_background.sh     # Inicia background
?   ??? parar.sh                  # Para serviço
?   ??? status.sh                 # Mostra status
?   ??? diagnostico.sh            # Ferramentas ML
?
??? Ambiente Virtual
?   ??? venv/                     # Isolamento Python
?
??? Dados e Logs
?   ??? aviator_service.log       # Log do serviço
?   ??? resultados_aviator.txt    # Dados capturados
?   ??? ml_models/                # Modelos treinados
?   ??? ml_history.json           # Histórico ML
?   ??? predictions.txt           # Predições
?
??? Compatibilidade
    ??? _platform_compat.py       # Stub winsound (Linux)
```

---

## ?? Troubleshooting

### Problema: Chrome não encontrado

```sh
# Verificar instalação
google-chrome-stable --version

# Se não estiver instalado, reinstalar
sudo apt-get update
sudo apt-get install -y google-chrome-stable
```

### Problema: Serviço não inicia

```sh
# Ver log de erros
tail -f aviator_service.log

# Testar Python
source venv/bin/activate
python aviator_service2.py
```

### Problema: Porta 5005 ocupada

```sh
# Ver processo usando porta
sudo netstat -tlnp | grep :5005

# Matar processo
sudo kill $(sudo lsof -t -i:5005)
```

### Problema: Timezone incorreto

```sh
# Verificar timezone
python3 -c "from aviator_service2 import agora_brasilia; print(agora_brasilia())"

# Deve mostrar horário de Brasília com -03
```

---

## ?? Reinstalação Completa

Se algo der errado, reinstale do zero:

```sh
# 1. Parar serviço
./parar.sh

# 2. Backup dos dados (opcional)
tar -czf ~/backup_aviator_$(date +%Y%m%d).tar.gz \
    resultados_aviator.txt \
    ml_models/ \
    ml_history.json 2>/dev/null || true

# 3. Limpar instalação
cd ~
rm -rf AviatorEstrela

# 4. Reinstalar
git clone https://github.com/marcossan73/AviatorEstrela.git
cd AviatorEstrela/AviatorEstrela
chmod +x setup_aviator.sh
./setup_aviator.sh

# 5. Restaurar backup (opcional)
tar -xzf ~/backup_aviator_*.tar.gz
```

---

## ?? Documentação Adicional

- **TIMEZONE_BRASILIA.md** - Detalhes sobre timezone
- **CORRECAO_ORDENACAO.md** - Correção de ordenação
- **SOLUCAO_SNAP_APT.md** - Chrome Snap vs APT
- **EXECUTAR_BACKGROUND.md** - Métodos de execução em background

---

## ? Verificação Pós-Instalação

```sh
# 1. Verificar Python
python3 --version

# 2. Verificar Chrome
google-chrome-stable --version

# 3. Verificar ChromeDriver
chromedriver --version

# 4. Verificar venv
source venv/bin/activate
python -c "import pytz, selenium, flask; print('OK')"

# 5. Ver status do serviço
./status.sh

# 6. Acessar dashboard
curl http://localhost:5005
```

**Todos devem retornar OK!**

---

## ?? Comandos Úteis

```sh
# Ver logs em tempo real
tail -f aviator_service.log

# Monitorar recursos
watch -n 1 './status.sh'

# Backup rápido
tar -czf backup_$(date +%Y%m%d_%H%M).tar.gz *.txt *.json ml_models/

# Retreinar modelos após coletar dados
./diagnostico.sh --clean
./diagnostico.sh --retrain

# Reiniciar serviço
./parar.sh && ./iniciar_background.sh
```

---

## ?? Suporte

- **Repositório**: https://github.com/marcossan73/AviatorEstrela
- **Issues**: Reportar bugs via GitHub Issues
- **Documentação**: Ver arquivos `.md` na pasta do projeto

---

**Criado**: Dezembro 2024  
**Versão**: 3.0 - Instalação Unificada  
**Compatível**: Ubuntu 20.04+, Debian 11+
