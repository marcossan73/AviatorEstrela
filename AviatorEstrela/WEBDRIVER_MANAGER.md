# Webdriver Manager - Solução Alternativa

## ?? O Que É

**webdriver-manager** é uma biblioteca Python que baixa e gerencia automaticamente o ChromeDriver compatível com sua versão do Chrome, eliminando problemas de incompatibilidade.

## ? Vantagens

- ? **Automático**: Detecta versão do Chrome e baixa driver compatível
- ? **Sem configuração manual**: Não precisa baixar ChromeDriver manualmente
- ? **Sempre atualizado**: Baixa versão correta automaticamente
- ? **Cache inteligente**: Reutiliza drivers já baixados
- ? **Multiplataforma**: Funciona em Windows, Linux e Mac

## ?? Instalação e Uso

### No Servidor Linux

```sh
cd ~/AviatorEstrela/AviatorEstrela

# Atualizar código do GitHub
git pull origin master

# Dar permissão ao script
chmod +x usar_webdriver_manager.sh

# Executar instalação
./usar_webdriver_manager.sh
```

**O script faz:**
1. Instala `webdriver-manager` no venv
2. Testa funcionamento
3. Código já suporta automaticamente!

### Instalação Manual

```sh
# Ativar ambiente virtual
source venv/bin/activate

# Instalar webdriver-manager
pip install webdriver-manager

# Testar
python3 << 'EOF'
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager

options = Options()
options.add_argument("--headless")
options.add_argument("--no-sandbox")

service = Service(ChromeDriverManager().install())
driver = webdriver.Chrome(service=service, options=options)
driver.get("https://www.google.com")
print("Teste OK:", driver.title)
driver.quit()
EOF
```

## ?? Como Funciona

O código foi atualizado para usar webdriver-manager automaticamente quando disponível:

```python
# aviator_service2.py já tem esta lógica:

try:
    from selenium.webdriver.chrome.service import Service
    from webdriver_manager.chrome import ChromeDriverManager
    USE_WEBDRIVER_MANAGER = True
except ImportError:
    USE_WEBDRIVER_MANAGER = False

def iniciar_driver():
    # ...configuração de opções...

    if USE_WEBDRIVER_MANAGER:
        # Usa webdriver-manager (automático)
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=options)
    else:
        # Fallback: método padrão
        driver = webdriver.Chrome(options=options)
```

**Comportamento**:
- Se `webdriver-manager` estiver instalado ? usa ele (automático)
- Se não estiver ? usa Selenium padrão (precisa ChromeDriver instalado)

## ?? Verificação

Após instalar, verifique:

```sh
# Iniciar serviço
./iniciar.sh
```

**Log esperado:**
```
[27/04/2026 20:30:00] Iniciando driver Chrome (modo headless)...
[27/04/2026 20:30:00] Usando webdriver-manager para gerenciar ChromeDriver...
[27/04/2026 20:30:01] ChromeDriver gerenciado automaticamente pelo webdriver-manager
[27/04/2026 20:30:01] Chrome encontrado em: /usr/bin/google-chrome-stable
```

## ?? Comparação

### Sem webdriver-manager (método atual)

```
1. Verificar versão do Chrome manualmente
2. Baixar ChromeDriver compatível
3. Colocar em /usr/local/bin/
4. Dar permissão de execução
5. Rezar para funcionar ??
```

### Com webdriver-manager (automático)

```
1. pip install webdriver-manager
2. Pronto! ?
```

## ?? Troubleshooting

### ImportError: No module named 'webdriver_manager'

**Solução**: Instalar no ambiente virtual correto
```sh
source venv/bin/activate
pip install webdriver-manager
```

### Erro ao baixar ChromeDriver

**Causa**: Firewall ou proxy bloqueando download

**Solução 1**: Baixar manualmente e colocar em cache
```sh
# Local do cache (Linux)
~/.wdm/drivers/chromedriver/linux64/147.0.7727.116/
```

**Solução 2**: Desabilitar webdriver-manager
```sh
pip uninstall webdriver-manager
# O código voltará a usar método padrão
```

### Driver incompatível mesmo com webdriver-manager

**Causa**: Cache corrompido

**Solução**: Limpar cache
```sh
rm -rf ~/.wdm/
# Próxima execução baixará novamente
```

## ?? Checklist de Instalação

- [ ] `git pull origin master` executado
- [ ] `./usar_webdriver_manager.sh` executado
- [ ] Mensagem "Instalacao Concluida!" apareceu
- [ ] `./iniciar.sh` iniciado com sucesso
- [ ] Log mostra "Usando webdriver-manager..."

## ?? Quando Usar

### Use webdriver-manager se:
- ? ChromeDriver manual não está funcionando
- ? Versões incompatíveis entre Chrome e ChromeDriver
- ? Quer instalação simplificada
- ? Quer atualizações automáticas

### Use método padrão se:
- ? ChromeDriver já funciona perfeitamente
- ? Ambiente air-gapped (sem internet)
- ? Quer controle total das versões

## ?? Desinstalação

Se quiser voltar ao método padrão:

```sh
source venv/bin/activate
pip uninstall webdriver-manager

# Código detecta automaticamente e volta ao método padrão
./iniciar.sh
```

## ?? Mais Informações

- GitHub: https://github.com/SergeyPirogov/webdriver_manager
- Documentação: https://pypi.org/project/webdriver-manager/

---

## ?? Resumo Rápido

```sh
# No servidor
cd ~/AviatorEstrela/AviatorEstrela
git pull
chmod +x usar_webdriver_manager.sh
./usar_webdriver_manager.sh
./iniciar.sh
```

**Pronto!** ChromeDriver gerenciado automaticamente! ??

---

**Atualizado**: Dezembro 2024  
**Compatível com**: Chrome 115+, Selenium 4.6+
