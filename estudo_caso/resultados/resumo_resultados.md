# Resumo automático do estudo de caso

## Configuração-base

- λ_A = 0,50 clientes/unidade de tempo
- λ_B = 0,25 clientes/unidade de tempo
- μ = 1,00 cliente/unidade de tempo
- Carga total ρ = 0,75
- Política proposta: fila M/M/1 não preemptiva com envelhecimento da Classe A após T unidades de tempo
- 7 replicações independentes por cenário, com 25.000 partidas por replicação

## Principais achados

- A prioridade dinâmica reduziu a espera média da Classe A em 16.10% frente à prioridade estrita.
- Em troca, a Classe B teve aumento de 137.47% na espera média em relação à prioridade estrita.
- Comparada ao FIFO puro, a política dinâmica reduziu a espera da Classe B em 22.79%.
- Serviço determinístico foi o melhor entre as distribuições testadas, com espera média total de 1.5145.
- Buffer finito de 10 posições reduziu a espera média total para 2.4080, mas introduziu perda média de 1.44%.
- No cenário-base, 49.36% das mensagens da Classe A precisaram ser promovidas por envelhecimento.

## Tabela 1 - Comparação entre disciplinas de fila

| Cenário | Espera A | Espera B | Espera total | Permanência total | Utilização | Fila média | Promoção A |
|---|---:|---:|---:|---:|---:|---:|---:|
| fifo_mm1 | 3.1004 | 3.1085 | 3.1032 | 4.1024 | 0.7514 | 2.3342 | 0.00% |
| prioridade_estrita | 3.9422 | 1.0107 | 2.9562 | 3.9568 | 0.7499 | 2.2164 | 0.00% |
| prioridade_dinamica | 3.3075 | 2.4002 | 3.0051 | 4.0091 | 0.7515 | 2.2502 | 49.36% |

## Tabela 2 - Sensibilidade ao limiar T

| Cenário | T | Espera A | Espera B | Espera total | Promoção A |
|---|---:|---:|---:|---:|---:|
| prioridade_dinamica_T1 | 1.00 | 3.1895 | 2.7181 | 3.0323 | 59.64% |
| prioridade_dinamica_T2 | 2.00 | 3.3316 | 2.3995 | 3.0219 | 49.24% |
| prioridade_dinamica_T4 | 4.00 | 3.5157 | 2.0189 | 3.0173 | 34.29% |

## Tabela 3 - Distribuição do tempo de serviço (política dinâmica)

| Cenário | Distribuição | Espera A | Espera B | Espera total | P95 espera |
|---|---|---:|---:|---:|---:|
| dinamica_servico_exponencial | exponential | 3.2456 | 2.3359 | 2.9421 | 10.6733 |
| dinamica_servico_deterministico | deterministic | 1.7857 | 0.9764 | 1.5145 | 5.4116 |
| dinamica_servico_erlang2 | erlang2 | 2.5239 | 1.6710 | 2.2417 | 8.1403 |

## Tabela 4 - Capacidade de armazenamento (política dinâmica)

| Cenário | Capacidade | Espera total | Vazão | Perda total | Fila média |
|---|---:|---:|---:|---:|---:|
| dinamica_buffer_infinito | ∞ | 2.9916 | 0.7528 | 0.00% | 2.2531 |
| dinamica_buffer_20 | 20 | 2.9591 | 0.7498 | 0.06% | 2.2190 |
| dinamica_buffer_10 | 10 | 2.4080 | 0.7400 | 1.44% | 1.7823 |

## Tabela 5 - Checagem teórica dos cenários clássicos

| Modelo | Espera A teórica | Espera A simulada | Espera B teórica | Espera B simulada |
|---|---:|---:|---:|---:|
| fifo_mm1 | 3.0000 | 3.1004 | 3.0000 | 3.1085 |
| prioridade_estrita | 4.0000 | 3.9422 | 1.0000 | 1.0107 |

## Leitura recomendada dos resultados

1. Explique que a prioridade dinâmica procura reduzir a injustiça sofrida pela Classe A sem perder totalmente o benefício concedido à Classe B.
2. Destaque que diminuir T favorece a Classe A mais rapidamente, porém reduz a vantagem da Classe B.
3. Discuta que serviço determinístico reduz variabilidade e, portanto, reduz filas e percentis de atraso.
4. Mostre que buffers menores controlam ocupação e atraso à custa de perdas, o que só é aceitável em aplicações tolerantes a descarte.
