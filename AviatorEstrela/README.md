# ?? Aviator ML Intelligence (EstrelaBet)

Bem-vindo ao repositório oficial do projeto **Aviator ML Intelligence**!
Este projeto é um sistema automatizado para extração, análise preditiva e projeção de tendências do jogo Aviator da casa de apostas "EstrelaBet". O sistema atua de ponta a ponta: captura assíncrona dos resultados reais na roleta e processamento instantâneo via Machine Learning para o auxílio analítico dos próximos picos lucrativos.

---

## ?? Como Funciona
O projeto processa continuamente o histórico da plataforma através do Selenium, salva os resultados detectados em arquivos base, treina/sonda os dados acumulados através de Algoritmos Estatísticos (Regressões Logarítmicas) e Machine Learning Ensemble (SkLearn, RandomForest e GradientBoosting) para retornar alertas precisos em tela na porta local com Dashboard Flask interativo.

### O sistema é dividido nas duas versões e evoluções distintas:
1. **`AviatorService.py`** 
   * A versão original de rastreio de tendências da roleta. Utiliza Regressão baseada em *RandomForest* e janela de rolagem para achar gaps de tempos longos. Conta com alarmes sonoros clássicos via JS para alertas diretos na interface do usuário.
2. **`aviator_service2.py`** _(Recomendada - Versão Stacked Regime Detector)_
    * Uma versão evoluída, com detecção e classificação em tempo real do **Regime (Estado) do Jogo** (Seca Severa, Recuperação, Estável, Distribuição). 
    * Ajusta a janela de probabilidades na detecção com bases em *Stacked Ensemble* (GradientBoosting). 
    * Gráficos aprimorados e métricas adicionadas com suporte total de visualização de Rodadas até o próximo pico, cores dinâmicas para as saídas esperadas (`>2 roxo`, `>5 verde`, `>10 rosa`, `>50 azul`) e linha de projeções de trajetória e curvatura quadrática.

?? Recomenda-se hoje o uso irrestrito do script primário: **`aviator_service2.py`**

---

## ??? Requisitos de Instalação

Para que o robô possa interagir com o navegador Chrome de forma oculta (*headless*) e realizar todos esses cálculos complexos espacial/temporais na sua máquina, instale as dependências requisitadas. 

Abra seu terminal Python e instale usando nosso arquivo de dependências:

```bash
pip install -r requirements.txt
```

*(O arquivo carrega ferramentas sólidas como: Pandas, NumPy, Scikit-learn, joblib, Selenium, webdriver-manager e Flask)*

---

## ?? Como Executar

1. Para iniciar completamente o Web-Scraping (captação dos lances) em paridade com o Servidor Local de Interface do Dashboard rodando simultaneamente:

```bash
python aviator_service2.py
```

2. Acesse no seu navegador preferido (PC ou Mobile local): 
   ??? **[http://localhost:5000](http://localhost:5000)**

*(Opcional: Scripts de testes de carregamento do ML disponíveis como `test_ml.py` ajudam em debugar como os modelos estão calculando amostras sem logar no site.)*

---

## ?? Funcionalidades do Dashboard Web
O Painel Inteligente auto-gerado traz componentes vitais, como:
- **Painel "Geral"**: Frequências absolutas das últimas 100 rodadas fatiadas por cores estratégicas.
- **Painel de Ocorrências e Linha do Tempo Visual**: Gráfico traçado com histórico das múltiplas fatias.
- **Painel de Picos e Confiança Artificial**: Detalhamento em janelas precisas do momento exato de cada Spike pesado avaliando se o momento de "Entrar" baseia-se em Confiança Alta (`> 85%`) ou de Risco (Seca Severa).
- **Semáforo/Alarmes Sonoros Web**: Ao aceitar no botão "Som Ativado", o JavaScript dispara sons vibrantes (sawtooth / sines) avisando quando a janela de entrada está a menos de `1 minuto e meio` para as velas altas.

---

## ?? Configurações Customizáveis
Se preferir ajustar a taxa de amostragem no script (Em `aviator_service2.py`):
```python
# Tempo entre varreduras
INTERVALO_SEGUNDOS = 20

# Volume e histórico carregado no BD de Texto 
MAX_REGISTROS = 10000

# Contas e Autenticações (Apenas contas tipminer já logadas):
EMAIL = "seu_email_secreto"
SENHA = "sua_senha_secreta"
```

## ?? Mão na Massa (Como Colaborar)
A colaboração é altamente encorajada! Sinta-se orgulhoso em criar *Forks*, testar novos algarismos preditivos do SkLearn para o motor do jogo ou melhorar o design HTML.

**Passos básicos:**
1. Realize um *Fork* do repositório no seu GitHub.
2. Clone para sua IDE: `git clone https://github.com/marcossan73/AviatorEstrela.git`
3. Crie uma branch para explorar inovações: `git checkout -b feature/minha-regressao-tunada`
4. Trabalhe e debuge. (Faça *commits* semânticos como "Feat: Atualiza cores do threshold X")
5. Faça um *Push* da sua branch e submeta via Pull Request para revisão central!

> ?? *Nota*: Use e divirta-se analisando, mas lembre-se sempre de apostar responsavelmente dentro das leis em vigor para sua região. As projeções probabilísticas deste sistema analítico de dados auxiliam nas leituras, **mas nunca devem ser garantias de lucros reais cegos.** 

???? Divirta-se!