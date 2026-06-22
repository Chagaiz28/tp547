# Resumo dos Resultados da Simulação

## Validação Analítica

- **fifo_mm1_teorico**: espera A = `3.0000`, espera B = `3.0000`
- **prioridade_estrita_teorico**: espera A = `4.0000`, espera B = `1.0000`

## disciplinas

### fifo_mm1
- espera A = `3.0560` ± 0.1235
- espera B = `3.0509` ± 0.1192
- espera total = `3.0543`
- utilização = `0.7490`

### prioridade_estrita
- espera A = `4.0821` ± 0.1778
- espera B = `1.0099` ± 0.0196
- espera total = `3.0543`
- utilização = `0.7490`

### prioridade_dinamica
- espera A = `3.4790` ± 0.1335
- espera B = `2.2096` ± 0.1066
- espera total = `3.0543`
- utilização = `0.7490`
- fração promovida A = `48.65%`

## sensibilidade_T

### prioridade_dinamica_T1
- espera A = `3.3727` ± 0.1313
- espera B = `2.4210` ± 0.1080
- espera total = `3.0543`
- utilização = `0.7490`
- fração promovida A = `59.60%`

### prioridade_dinamica_T2
- espera A = `3.4790` ± 0.1335
- espera B = `2.2096` ± 0.1066
- espera total = `3.0543`
- utilização = `0.7490`
- fração promovida A = `48.65%`

### prioridade_dinamica_T4
- espera A = `3.6411` ± 0.1375
- espera B = `1.8871` ± 0.0998
- espera total = `3.0543`
- utilização = `0.7490`
- fração promovida A = `33.70%`

## distribuicoes_servico

### dinamica_servico_exponencial
- espera A = `3.4790` ± 0.1335
- espera B = `2.2096` ± 0.1066
- espera total = `3.0543`
- utilização = `0.7490`
- fração promovida A = `48.65%`

### dinamica_servico_deterministico
- espera A = `1.7900` ± 0.0250
- espera B = `0.8686` ± 0.0291
- espera total = `1.4818`
- utilização = `0.7484`
- fração promovida A = `34.53%`

### dinamica_servico_erlang2
- espera A = `2.6652` ± 0.0543
- espera B = `1.5473` ± 0.0382
- espera total = `2.2912`
- utilização = `0.7509`
- fração promovida A = `44.24%`

## armazenamento

### dinamica_buffer_infinito
- espera A = `3.4790` ± 0.1335
- espera B = `2.2096` ± 0.1066
- espera total = `3.0543`
- utilização = `0.7490`
- fração promovida A = `48.65%`

### dinamica_buffer_20
- espera A = `3.4382` ± 0.1511
- espera B = `2.1429` ± 0.1146
- espera total = `3.0048`
- utilização = `0.7481`
- fração promovida A = `48.79%`
- taxa de perda = `0.12%`

### dinamica_buffer_10
- espera A = `2.7891` ± 0.0752
- espera B = `1.6481` ± 0.0608
- espera total = `2.4074`
- utilização = `0.7380`
- fração promovida A = `45.75%`
- taxa de perda = `1.46%`
