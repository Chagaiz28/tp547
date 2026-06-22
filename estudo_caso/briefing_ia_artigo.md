# Briefing para IA redigir o artigo

## Objetivo do trabalho

Escrever um artigo em formato de conferência IEEE sobre o tema:

**Fila M/M/1 com Prioridade Dinâmica por Idade**

Duas classes de clientes:
- **Classe A**: normal
- **Classe B**: prioritária

Hipóteses do problema:
- chegadas das duas classes seguem processos de Poisson independentes;
- há **um único servidor**;
- o atendimento é **não preemptivo**;
- clientes da **Classe B** entram diretamente na fila de alta prioridade;
- clientes da **Classe A** entram na fila de baixa prioridade;
- se um cliente da Classe A esperar mais que **T** unidades de tempo na fila, ele é **promovido automaticamente** para a fila de alta prioridade.

O enunciado do PDF também exige **comparações com outros tipos de filas, distribuições de serviço e armazenamento**, então o código já inclui essas comparações. Portanto, sim: **foi necessário implementar também as filas de referência e os cenários de comparação**.

---

## Arquivos prontos no repositório

Todos os artefatos foram colocados em:

`/home/runner/work/tp547/tp547/estudo_caso`

Arquivos principais:
- `simulacao_prioridade_dinamica.py` → simulador principal
- `README.md` → instruções rápidas
- `resultados/resumo_resultados.md` → resumo em linguagem de relatório
- `resultados/resumo_cenarios.csv` → tabela consolidada dos cenários
- `resultados/resultados_por_replicacao.csv` → replicações individuais
- `resultados/referencias_teoricas.csv` → referências analíticas para FIFO e prioridade estrita
- `resultados/grafico_espera_disciplinas.svg`
- `resultados/grafico_sensibilidade_T.svg`
- `resultados/grafico_distribuicoes_servico.svg`
- `resultados/grafico_armazenamento.svg`

---

## O que o código faz

O arquivo `simulacao_prioridade_dinamica.py` implementa uma **simulação de eventos discretos**.

### Eventos modelados
- chegada da Classe A;
- chegada da Classe B;
- promoção por envelhecimento da Classe A;
- partida do servidor.

### Variáveis de estado do sistema
- servidor ocupado ou livre;
- fila de alta prioridade;
- fila de baixa prioridade;
- número médio de clientes na fila;
- número médio de clientes no sistema;
- utilização do servidor.

### Entidades
- clientes da Classe A;
- clientes da Classe B.

### Política de atendimento
- **FIFO** dentro de cada nível de prioridade;
- **não preemptiva**: um serviço em andamento não é interrompido;
- a promoção da Classe A acontece por evento agendado em `chegada + T`.

---

## Cenários já simulados

### 1. Comparação entre disciplinas de fila
Mesmos parâmetros-base, mudando apenas a disciplina:
- `fifo_mm1`
- `prioridade_estrita`
- `prioridade_dinamica`

### 2. Sensibilidade ao limiar T
- `T = 1`
- `T = 2`
- `T = 4`

### 3. Comparação entre distribuições de serviço
Mantendo a política dinâmica:
- serviço exponencial;
- serviço determinístico;
- serviço Erlang-2.

### 4. Comparação de armazenamento
Mantendo a política dinâmica:
- buffer infinito;
- buffer finito com 20 posições;
- buffer finito com 10 posições.

---

## Parâmetros-base usados nos experimentos

- `λ_A = 0.50`
- `λ_B = 0.25`
- `μ = 1.00`
- carga total `ρ = 0.75`
- `T = 2.0` no cenário-base
- `7` replicações independentes por cenário
- `25.000` partidas por replicação

Esses valores foram escolhidos porque deixam o sistema estável e, ao mesmo tempo, tornam visível o conflito entre prioridade da Classe B e justiça para a Classe A.

---

## Métricas calculadas

- espera média na fila da Classe A;
- espera média na fila da Classe B;
- espera média total;
- tempo médio no sistema por classe e total;
- percentil 95 da espera total;
- utilização do servidor;
- tamanho médio da fila;
- tamanho médio do sistema;
- vazão;
- taxa de perda para buffers finitos;
- fração de clientes da Classe A promovidos por envelhecimento.

---

## Resultados mais importantes para o texto do artigo

### Comparação entre disciplinas
Valores médios:

- **FIFO**
  - espera A = `3.1004`
  - espera B = `3.1085`
  - espera total = `3.1032`

- **Prioridade estrita**
  - espera A = `3.9422`
  - espera B = `1.0107`
  - espera total = `2.9562`

- **Prioridade dinâmica**
  - espera A = `3.3075`
  - espera B = `2.4002`
  - espera total = `3.0051`
  - fração promovida da Classe A = `49.36%`

### Interpretação recomendada
- a prioridade estrita favorece muito a Classe B, mas penaliza bastante a Classe A;
- a prioridade dinâmica reduz a injustiça sofrida pela Classe A sem eliminar totalmente o benefício da Classe B;
- o FIFO é o mais equilibrado entre classes, mas não oferece diferenciação de serviço para a Classe B.

### Ganhos/perdas que podem ser citados
- a prioridade dinâmica reduziu a espera da Classe A em **16.10%** em relação à prioridade estrita;
- a espera da Classe B aumentou **137.47%** em relação à prioridade estrita;
- em comparação ao FIFO, a prioridade dinâmica reduziu a espera da Classe B em **22.79%**.

---

## Sensibilidade ao limiar T

Resultados médios:

- **T = 1**
  - espera A = `3.1895`
  - espera B = `2.7181`
  - promoção A = `59.64%`

- **T = 2**
  - espera A = `3.3316`
  - espera B = `2.3995`
  - promoção A = `49.24%`

- **T = 4**
  - espera A = `3.5157`
  - espera B = `2.0189`
  - promoção A = `34.29%`

### Leitura recomendada
- quanto **menor** o valor de `T`, mais cedo a Classe A sobe de prioridade;
- isso melhora a espera da Classe A, mas reduz a vantagem da Classe B;
- quanto **maior** o valor de `T`, mais o sistema se aproxima da prioridade estrita.

---

## Distribuição de serviço

Resultados médios com política dinâmica:

- **Exponencial**
  - espera total = `2.9421`
  - P95 da espera = `10.6733`

- **Determinística**
  - espera total = `1.5145`
  - P95 da espera = `5.4116`

- **Erlang-2**
  - espera total = `2.2417`
  - P95 da espera = `8.1403`

### Interpretação recomendada
- reduzir a variabilidade do tempo de serviço melhora fortemente o desempenho da fila;
- por isso, o serviço determinístico apresentou os menores atrasos;
- a distribuição exponencial teve pior desempenho por causa da maior variabilidade.

---

## Armazenamento / capacidade de buffer

Resultados médios com política dinâmica:

- **Buffer infinito**
  - espera total = `2.9916`
  - perda = `0%`

- **Buffer 20**
  - espera total = `2.9591`
  - perda = `0.06%`

- **Buffer 10**
  - espera total = `2.4080`
  - perda = `1.44%`

### Interpretação recomendada
- buffers menores reduzem a ocupação e o atraso médio, mas introduzem perda;
- isso pode ser bom apenas em aplicações tolerantes a descarte;
- em aplicações sensíveis à perda, o buffer infinito ou maior é mais adequado.

---

## Validação analítica já incluída

O código compara os resultados simulados com fórmulas conhecidas para dois casos clássicos:

- **M/M/1 FIFO**
- **M/M/1 com prioridade estrita não preemptiva**

Checagem obtida:
- FIFO teórico: espera A = `3.0000`, espera B = `3.0000`
- FIFO simulado: espera A = `3.1004`, espera B = `3.1085`
- Prioridade estrita teórica: espera A = `4.0000`, espera B = `1.0000`
- Prioridade estrita simulada: espera A = `3.9422`, espera B = `1.0107`

Interpretação: a proximidade entre teoria e simulação ajuda a sustentar a corretude do simulador.

---

## Estrutura sugerida para o artigo

### Resumo
- apresentar rapidamente o problema;
- explicar a ideia de prioridade dinâmica por envelhecimento;
- resumir os principais resultados.

### Introdução
- contextualizar teoria de filas em redes e sistemas de comunicação;
- justificar diferenciação de serviço por classes;
- motivar o uso de envelhecimento para evitar injustiça ou quase-starvation da classe normal.

### Modelagem do sistema
- definir as duas classes;
- especificar o processo de chegada Poisson;
- especificar serviço exponencial no caso-base;
- explicar política não preemptiva;
- descrever o mecanismo de promoção da Classe A após `T`.

### Metodologia de simulação
- dizer que foi usada simulação de eventos discretos;
- listar entidades, variáveis de estado e eventos;
- explicar replicações independentes;
- listar métricas analisadas.

### Resultados
Sugestão de ordem:
1. comparar FIFO, prioridade estrita e prioridade dinâmica;
2. analisar sensibilidade ao parâmetro `T`;
3. comparar distribuições de serviço;
4. comparar capacidades de buffer.

### Conclusão
- afirmar que a prioridade dinâmica produz um compromisso entre eficiência para a Classe B e justiça para a Classe A;
- destacar que `T` controla diretamente esse compromisso;
- mencionar que a variabilidade do serviço e a capacidade de armazenamento também alteram fortemente o desempenho.

---

## Pontos que a IA redatora deve tomar cuidado

- não dizer que a política dinâmica é melhor em tudo; ela faz **trade-off**;
- deixar claro que o serviço é **não preemptivo**;
- separar bem espera na fila de tempo total no sistema;
- mencionar que os resultados dependem dos parâmetros escolhidos;
- citar que a validação com casos clássicos foi usada para verificar consistência do simulador.

---

## Frase-guia para o argumento central do artigo

A fila M/M/1 com prioridade dinâmica por idade funciona como um mecanismo intermediário entre o FIFO puro e a prioridade estrita: ela preserva parte do benefício da classe prioritária, mas reduz a penalização excessiva imposta à classe normal por meio de promoção automática após um tempo de espera controlado por `T`.
