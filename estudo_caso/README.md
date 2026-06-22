# Estudo de caso - Fila M/M/1 com prioridade dinâmica por idade

Este diretório contém uma implementação completa do estudo de caso do tema **"Fila M/M/1 com Prioridade Dinâmica por Idade"**.

## O que foi entregue

- `simulacao_prioridade_dinamica.py`: simulador de eventos discretos e gerador automático de resultados.
- `resultados/`: tabelas e gráficos já gerados para o relatório.
- `briefing_ia_artigo.md`: briefing detalhado para outra IA redigir o artigo final.

## Modelo implementado

- Duas classes de clientes: `A` e `B`.
- Chegadas Poisson independentes para as duas classes.
- Um único servidor.
- Política não preemptiva.
- A classe `B` entra diretamente na fila de alta prioridade.
- A classe `A` entra inicialmente em baixa prioridade e é promovida automaticamente após permanecer mais que `T` unidades de tempo esperando.

## Comparações incluídas

1. **Disciplinas de fila**
   - FIFO sem prioridade.
   - Prioridade estrita sem envelhecimento.
   - Prioridade dinâmica por idade.
2. **Sensibilidade ao limiar `T`**
   - `T = 1`, `T = 2` e `T = 4`.
3. **Distribuição de serviço**
   - Exponencial.
   - Determinística.
   - Erlang-2.
4. **Armazenamento**
   - Buffer infinito.
   - Buffer finito com 20 posições.
   - Buffer finito com 10 posições.

## Métricas geradas

- Espera média na fila por classe e total.
- Tempo médio no sistema por classe e total.
- Percentil 95 da espera total.
- Utilização do servidor.
- Tamanho médio da fila e do sistema.
- Vazão.
- Taxa de perdas para buffers finitos.
- Fração de clientes da classe A promovidos por envelhecimento.

## Como executar novamente

```bash
cd /home/runner/work/tp547/tp547/estudo_caso
python simulacao_prioridade_dinamica.py --output-dir resultados
```

## Saídas principais

- `resultados/resumo_resultados.md`: resumo pronto para alimentar o relatório.
- `resultados/resumo_cenarios.csv`: tabela consolidada de todos os cenários.
- `resultados/grafico_espera_disciplinas.svg`
- `resultados/grafico_sensibilidade_T.svg`
- `resultados/grafico_distribuicoes_servico.svg`
- `resultados/grafico_armazenamento.svg`

## Observação importante

Sim, para este trabalho faz sentido implementar **as filas de comparação também**, porque o enunciado pede explicitamente **tabelas e gráficos comparando a fila proposta com outros tipos de filas, distribuições de serviço e armazenamento**.
