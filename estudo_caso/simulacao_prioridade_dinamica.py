"""
Simulação de Fila M/M/1 com Prioridade Dinâmica por Idade
Baseada no estilo dos códigos de aula do professor (queuemm1partidas.ipynb).

Estilo do professor
-------------------
- Pré-gera vetores de tempos entre chegadas e de serviço (np.random.exponential)
- Usa índices k1a, k1b, k2 para percorrer esses vetores
- Estado do sistema: t (tempo), ls (servidor 0/1), lq (tamanho da fila)
- Loop principal: while k < n_partidas
- Três tipos de evento: chegada A, chegada B, partida

Extensões em relação ao código básico do professor
---------------------------------------------------
- Duas classes de chegada (Classe A e Classe B)
- Disciplinas: FIFO, prioridade estrita, prioridade dinâmica por envelhecimento
- Distribuições de serviço: exponencial, determinística, Erlang-2
- Capacidade de buffer finita opcional
- Múltiplas replicações independentes com agregação de métricas
"""

import argparse
import csv
import math
import os
import statistics

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt


# ---------------------------------------------------------------------------
# Simulação de uma replicação — estilo professor
# ---------------------------------------------------------------------------

def simula_replicacao(lambda_a, lambda_b, mu, T_age, n_partidas, semente,
                      disciplina="dinamica", dist_servico="exponencial",
                      capacidade=None):
    """
    Simula uma replicação.

    Parâmetros
    ----------
    lambda_a, lambda_b : taxas de chegada das classes A e B
    mu                 : taxa de serviço
    T_age              : limiar de envelhecimento (promoção A→fila alta)
    n_partidas         : número de partidas para encerrar
    semente            : semente do gerador aleatório
    disciplina         : "fifo" | "estrita" | "dinamica"
    dist_servico       : "exponencial" | "deterministico" | "erlang2"
    capacidade         : limite do sistema (None = infinito)
    """

    rng = np.random.RandomState(semente)

    # ---- Pré-geração dos vetores (estilo professor) -------------------------
    N = n_partidas * 40   # tamanho suficientemente grande

    int_a = rng.exponential(1.0 / lambda_a, N) if lambda_a > 0 else np.full(N, np.inf)
    int_b = rng.exponential(1.0 / lambda_b, N) if lambda_b > 0 else np.full(N, np.inf)

    if dist_servico == "exponencial":
        srv = rng.exponential(1.0 / mu, N)
    elif dist_servico == "deterministico":
        srv = np.full(N, 1.0 / mu)
    elif dist_servico == "erlang2":
        srv = rng.gamma(2.0, 1.0 / (2.0 * mu), N)
    else:
        raise ValueError(f"Distribuição desconhecida: {dist_servico}")

    # ---- Variáveis de estado (estilo professor) ----------------------------
    t    = 0.0        # tempo atual
    ls   = 0          # servidor: 0 = livre, 1 = ocupado
    lq   = 0          # número de clientes aguardando na fila
    k1a  = 0          # índice no vetor de chegadas A
    k1b  = 0          # índice no vetor de chegadas B
    k2   = 0          # índice no vetor de serviços (avança apenas ao iniciar serviço)
    k    = 0          # contador de partidas

    # Tempos dos próximos eventos (estilo professor: ta, td)
    ta_a = int_a[k1a]   # próxima chegada Classe A
    ta_b = int_b[k1b]   # próxima chegada Classe B
    td   = np.inf        # próxima partida (servidor livre no início)

    # ---- Estrutura de cada cliente ----------------------------------------
    # Lista: [t_chegada, classe, t_inicio_srv, promovido]
    # t_inicio_srv é definido apenas ao iniciar serviço (não na chegada à fila)
    fila_alta  = []   # alta prioridade (Classe B + Classe A promovida)
    fila_baixa = []   # baixa prioridade (Classe A ainda não promovida)
    fila_fifo  = []   # fila única para disciplina FIFO
    srv_cli    = None  # cliente em serviço no momento

    # ---- Acumuladores de área (Lei de Little) ------------------------------
    t_ult  = 0.0
    A_fila = 0.0   # ∫ lq dt
    A_sis  = 0.0   # ∫ (lq + ls) dt
    A_srv  = 0.0   # ∫ ls dt

    # ---- Acumuladores de métricas -----------------------------------------
    espera_A  = []   # tempo de espera na fila, Classe A
    espera_B  = []   # tempo de espera na fila, Classe B
    soj_A     = []   # tempo total no sistema, Classe A
    soj_B     = []   # tempo total no sistema, Classe B
    n_prom_A  = 0    # promoções da Classe A por envelhecimento
    n_ace_A   = 0    # clientes A aceitos no sistema
    n_ace_B   = 0    # clientes B aceitos no sistema
    n_perd_A  = 0    # clientes A perdidos (buffer cheio)
    n_perd_B  = 0    # clientes B perdidos (buffer cheio)
    n_cheg_A  = 0    # chegadas totais A
    n_cheg_B  = 0    # chegadas totais B

    # ---- Funções auxiliares -----------------------------------------------

    def atualiza_areas(t_novo):
        """Acumula integrais de área entre dois instantes (estilo professor)."""
        nonlocal t_ult, A_fila, A_sis, A_srv
        dt      = t_novo - t_ult
        A_fila += lq * dt
        A_sis  += (lq + ls) * dt
        A_srv  += ls * dt
        t_ult   = t_novo

    def inicia_servico(cliente):
        """
        Registra o início do serviço e agenda a partida.
        O tempo de serviço é retirado do vetor srv[k2] (estilo professor).
        """
        nonlocal ls, td, k2
        cliente[2] = t          # armazena t_inicio_srv para cálculo da espera
        ls  = 1
        td  = t + srv[k2]       # próxima partida (estilo professor: td = t + partidas[k2])
        k2 += 1                 # avança índice de serviço

    def despacha():
        """
        Inicia o atendimento do próximo cliente se o servidor está livre.
        Para disciplina dinâmica, aplica promoções por envelhecimento antes
        de selecionar o próximo cliente (verificação preguiçosa em cada despacho).
        """
        nonlocal lq, srv_cli

        if ls == 1:
            return   # servidor ocupado

        # Promoção preguiçosa: move para a fila alta todos os clientes da
        # fila baixa cujo tempo de espera já atingiu o limiar T_age
        if disciplina == "dinamica":
            ainda_baixa = []
            for c in fila_baixa:
                if t - c[0] >= T_age:
                    c[3] = True
                    fila_alta.append(c)
                    nonlocal n_prom_A
                    n_prom_A += 1
                else:
                    ainda_baixa.append(c)
            fila_baixa[:] = ainda_baixa

        # Seleciona o próximo cliente conforme a disciplina
        if disciplina == "fifo":
            if not fila_fifo:
                return
            prox = fila_fifo.pop(0)
        else:
            if fila_alta:
                prox = fila_alta.pop(0)
            elif fila_baixa:
                prox = fila_baixa.pop(0)
            else:
                return

        lq -= 1
        srv_cli = prox
        inicia_servico(prox)

    # ---- Loop principal (estilo professor: while k < n_partidas) -----------
    #
    # A cada iteração:
    #   1. Determina o próximo evento (chegada A, chegada B ou partida)
    #   2. Avança t para o instante do evento
    #   3. Atualiza as integrais de área (Lei de Little)
    #   4. Processa o evento

    while k < n_partidas:

        # Próximo evento: mínimo entre as três possibilidades
        prox = min(ta_a, ta_b, td)
        atualiza_areas(prox)
        t = prox

        # ---- Chegada Classe A (em caso de empate com td, chegada tem precedência)
        if ta_a <= ta_b and ta_a <= td:
            n_cheg_A += 1
            k1a  += 1
            ta_a  = t + int_a[k1a]   # próxima chegada A (estilo professor)

            if capacidade is not None and (lq + ls) >= capacidade:
                n_perd_A += 1        # descarta por buffer cheio
            else:
                n_ace_A += 1
                # Cria cliente: [t_chegada, classe, t_inicio_srv, promovido]
                c = [t, "A", None, False]
                if ls == 0 and lq == 0:
                    # Servidor livre: atende imediatamente (sem espera na fila)
                    srv_cli = c
                    inicia_servico(c)
                else:
                    # Servidor ocupado: enfileira
                    lq += 1
                    if disciplina == "fifo":
                        fila_fifo.append(c)
                    else:
                        fila_baixa.append(c)   # Classe A começa na fila de baixa prioridade

        # ---- Chegada Classe B
        elif ta_b <= ta_a and ta_b <= td:
            n_cheg_B += 1
            k1b  += 1
            ta_b  = t + int_b[k1b]

            if capacidade is not None and (lq + ls) >= capacidade:
                n_perd_B += 1
            else:
                n_ace_B += 1
                c = [t, "B", None, False]
                if ls == 0 and lq == 0:
                    srv_cli = c
                    inicia_servico(c)
                else:
                    lq += 1
                    if disciplina == "fifo":
                        fila_fifo.append(c)
                    else:
                        fila_alta.append(c)    # Classe B vai direto para a fila alta

        # ---- Partida
        else:
            k += 1   # conta a partida (estilo professor: k = k + 1)

            # Registra métricas do cliente que partiu
            if srv_cli is not None:
                espera  = srv_cli[2] - srv_cli[0]   # t_inicio_srv − t_chegada
                sojourn = t          - srv_cli[0]   # t_partida   − t_chegada
                if srv_cli[1] == "A":
                    espera_A.append(max(0.0, espera))
                    soj_A.append(sojourn)
                else:
                    espera_B.append(max(0.0, espera))
                    soj_B.append(sojourn)
                srv_cli = None

            ls  = 0          # libera o servidor
            td  = np.inf     # sem partida agendada enquanto servidor está livre
            despacha()       # se há cliente na fila, inicia_servico agendará novo td

    # ---- Cálculo das métricas ----------------------------------------------

    t_sim    = t if t > 0 else 1.0
    comp_A   = len(espera_A)
    comp_B   = len(espera_B)
    comp_tot = comp_A + comp_B
    n_cheg_t = n_cheg_A + n_cheg_B
    n_perd_t = n_perd_A + n_perd_B

    def media(lst):
        return sum(lst) / len(lst) if lst else 0.0

    def p95(lst):
        if not lst:
            return 0.0
        s   = sorted(lst)
        idx = max(0, min(len(s) - 1, math.ceil(0.95 * len(s)) - 1))
        return s[idx]

    all_waits = espera_A + espera_B

    return {
        "simulated_time":      t_sim,
        "server_utilization":  A_srv  / t_sim,
        "avg_queue_length":    A_fila / t_sim,
        "avg_system_length":   A_sis  / t_sim,
        "throughput":          comp_tot / t_sim,
        "mean_wait_A":         media(espera_A),
        "mean_wait_B":         media(espera_B),
        "mean_wait_total":     media(all_waits),
        "mean_sojourn_A":      media(soj_A),
        "mean_sojourn_B":      media(soj_B),
        "mean_sojourn_total":  media(soj_A + soj_B),
        "p95_wait_total":      p95(all_waits),
        "drop_rate_total":     n_perd_t / n_cheg_t  if n_cheg_t  else 0.0,
        "drop_rate_A":         n_perd_A / n_cheg_A  if n_cheg_A  else 0.0,
        "drop_rate_B":         n_perd_B / n_cheg_B  if n_cheg_B  else 0.0,
        "promoted_fraction_A": n_prom_A / n_ace_A   if n_ace_A   else 0.0,
        "completed_A":         comp_A,
        "completed_B":         comp_B,
    }


# ---------------------------------------------------------------------------
# Configurações dos cenários
# ---------------------------------------------------------------------------

BASE = dict(lambda_a=0.50, lambda_b=0.25, mu=1.0, T_age=2.0,
            n_partidas=25000, n_rep=7)

_b = {k: v for k, v in BASE.items() if k not in ("n_rep",)}

CENARIOS = [
    dict(grupo="disciplinas", nome="fifo_mm1",           disciplina="fifo",    **_b),
    dict(grupo="disciplinas", nome="prioridade_estrita",  disciplina="estrita", **_b),
    dict(grupo="disciplinas", nome="prioridade_dinamica", disciplina="dinamica",**_b),
    dict(grupo="sensibilidade_T", nome="prioridade_dinamica_T1", disciplina="dinamica",
         T_age=1.0, **{k: v for k, v in _b.items() if k != "T_age"}),
    dict(grupo="sensibilidade_T", nome="prioridade_dinamica_T2", disciplina="dinamica",
         T_age=2.0, **{k: v for k, v in _b.items() if k != "T_age"}),
    dict(grupo="sensibilidade_T", nome="prioridade_dinamica_T4", disciplina="dinamica",
         T_age=4.0, **{k: v for k, v in _b.items() if k != "T_age"}),
    dict(grupo="distribuicoes_servico", nome="dinamica_servico_exponencial",
         disciplina="dinamica", dist_servico="exponencial",    **_b),
    dict(grupo="distribuicoes_servico", nome="dinamica_servico_deterministico",
         disciplina="dinamica", dist_servico="deterministico", **_b),
    dict(grupo="distribuicoes_servico", nome="dinamica_servico_erlang2",
         disciplina="dinamica", dist_servico="erlang2",        **_b),
    dict(grupo="armazenamento", nome="dinamica_buffer_infinito",
         disciplina="dinamica", capacidade=None, **_b),
    dict(grupo="armazenamento", nome="dinamica_buffer_20",
         disciplina="dinamica", capacidade=20,   **_b),
    dict(grupo="armazenamento", nome="dinamica_buffer_10",
         disciplina="dinamica", capacidade=10,   **_b),
]


# ---------------------------------------------------------------------------
# Referências analíticas
# ---------------------------------------------------------------------------

def referencias_teoricas(lambda_a, lambda_b, mu):
    lam    = lambda_a + lambda_b
    rho_b  = lambda_b / mu
    rho    = lam / mu
    E_S2   = 2.0 / (mu * mu)

    Wq_fifo  = lam / (mu * (mu - lam))
    Wq_b_est = lam * E_S2 / (2.0 * (1.0 - rho_b))
    Wq_a_est = lam * E_S2 / (2.0 * (1.0 - rho_b) * (1.0 - rho))

    return [
        {"cenario": "fifo_mm1_teorico",
         "mean_wait_A_teorico": Wq_fifo,
         "mean_wait_B_teorico": Wq_fifo},
        {"cenario": "prioridade_estrita_teorico",
         "mean_wait_A_teorico": Wq_a_est,
         "mean_wait_B_teorico": Wq_b_est},
    ]


# ---------------------------------------------------------------------------
# Utilitários de I/O e estatísticas
# ---------------------------------------------------------------------------

def escreve_csv(caminho, linhas):
    if not linhas:
        return
    campos = []
    for l in linhas:
        for k in l:
            if k not in campos:
                campos.append(k)
    with open(caminho, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=campos)
        w.writeheader()
        w.writerows(linhas)


def ci95(valores):
    if len(valores) < 2:
        return 0.0
    return 1.96 * statistics.stdev(valores) / math.sqrt(len(valores))


def media_ou_zero(lst):
    return sum(lst) / len(lst) if lst else 0.0


def sumariza(nome, grupo, cfg, reps):
    s = {"cenario": nome, "grupo": grupo,
         "disciplina":   cfg.get("disciplina", ""),
         "dist_servico": cfg.get("dist_servico", "exponencial"),
         "capacidade":   cfg.get("capacidade", None),
         "T_age":        cfg.get("T_age", ""),
         "n_reps":       len(reps)}
    metricas = [
        "simulated_time", "server_utilization", "avg_queue_length",
        "avg_system_length", "throughput",
        "mean_wait_A", "mean_wait_B", "mean_wait_total",
        "mean_sojourn_A", "mean_sojourn_B", "mean_sojourn_total",
        "p95_wait_total", "drop_rate_total", "drop_rate_A", "drop_rate_B",
        "promoted_fraction_A",
    ]
    for m in metricas:
        vals = [r[m] for r in reps]
        s[m]           = media_ou_zero(vals)
        s[f"{m}_ci95"] = ci95(vals)
    return s


# ---------------------------------------------------------------------------
# Gráficos
# ---------------------------------------------------------------------------

def grafico_disciplinas(resumos, out_dir):
    disc  = [r for r in resumos if r["grupo"] == "disciplinas"]
    nomes = [r["cenario"].replace("_", " ") for r in disc]
    x = np.arange(len(nomes)); w = 0.25
    fig, ax = plt.subplots(figsize=(9, 5))
    ax.bar(x - w, [r["mean_wait_A"]     for r in disc], w, label="Classe A")
    ax.bar(x,     [r["mean_wait_B"]     for r in disc], w, label="Classe B")
    ax.bar(x + w, [r["mean_wait_total"] for r in disc], w, label="Total")
    ax.set_xticks(x); ax.set_xticklabels(nomes, fontsize=9)
    ax.set_ylabel("Espera média na fila"); ax.set_title("Comparação entre disciplinas de fila")
    ax.legend(); fig.tight_layout()
    fig.savefig(os.path.join(out_dir, "grafico_espera_disciplinas.svg")); plt.close(fig)


def grafico_sensibilidade_T(resumos, out_dir):
    sens   = [r for r in resumos if r["grupo"] == "sensibilidade_T"]
    T_vals = [float(r["T_age"]) for r in sens]
    fig, ax = plt.subplots(figsize=(7, 4))
    ax.plot(T_vals, [r["mean_wait_A"] for r in sens], "o-", label="Espera A")
    ax.plot(T_vals, [r["mean_wait_B"] for r in sens], "s-", label="Espera B")
    ax.set_xlabel("Limiar T"); ax.set_ylabel("Espera média na fila")
    ax.set_title("Sensibilidade ao limiar de envelhecimento T"); ax.legend()
    fig.tight_layout(); fig.savefig(os.path.join(out_dir, "grafico_sensibilidade_T.svg")); plt.close(fig)


def grafico_distribuicoes(resumos, out_dir):
    grp   = [r for r in resumos if r["grupo"] == "distribuicoes_servico"]
    nomes = [r["dist_servico"] for r in grp]
    x = np.arange(len(nomes)); w = 0.35
    fig, ax = plt.subplots(figsize=(7, 4))
    ax.bar(x - w/2, [r["mean_wait_total"] for r in grp], w, label="Espera média total")
    ax.bar(x + w/2, [r["p95_wait_total"]  for r in grp], w, label="P95 espera total")
    ax.set_xticks(x); ax.set_xticklabels(nomes, fontsize=9)
    ax.set_ylabel("Espera na fila"); ax.set_title("Comparação entre distribuições de serviço")
    ax.legend(); fig.tight_layout()
    fig.savefig(os.path.join(out_dir, "grafico_distribuicoes_servico.svg")); plt.close(fig)


def grafico_armazenamento(resumos, out_dir):
    grp   = [r for r in resumos if r["grupo"] == "armazenamento"]
    nomes = [str(r["capacidade"]) if r["capacidade"] else "infinito" for r in grp]
    x = np.arange(len(nomes)); w = 0.35
    fig, ax1 = plt.subplots(figsize=(7, 4))
    ax1.bar(x - w/2, [r["mean_wait_total"]       for r in grp], w,
            label="Espera média total", color="steelblue")
    ax1.set_ylabel("Espera média total")
    ax2 = ax1.twinx()
    ax2.bar(x + w/2, [r["drop_rate_total"] * 100 for r in grp], w,
            label="Taxa de perda (%)", color="tomato")
    ax2.set_ylabel("Taxa de perda (%)")
    ax1.set_xticks(x); ax1.set_xticklabels(nomes)
    ax1.set_title("Comparação de armazenamento (buffer)")
    l1, n1 = ax1.get_legend_handles_labels(); l2, n2 = ax2.get_legend_handles_labels()
    ax1.legend(l1 + l2, n1 + n2, loc="upper right")
    fig.tight_layout(); fig.savefig(os.path.join(out_dir, "grafico_armazenamento.svg")); plt.close(fig)


# ---------------------------------------------------------------------------
# Resumo em Markdown
# ---------------------------------------------------------------------------

def escreve_resumo_md(resumos, refs, out_dir):
    linhas = ["# Resumo dos Resultados da Simulação\n",
              "## Validação Analítica\n"]
    for r in refs:
        linhas.append(f"- **{r['cenario']}**: espera A = `{r['mean_wait_A_teorico']:.4f}`, "
                      f"espera B = `{r['mean_wait_B_teorico']:.4f}`")
    linhas.append("")
    grupos = {}
    for r in resumos:
        grupos.setdefault(r["grupo"], []).append(r)
    for grupo, itens in grupos.items():
        linhas.append(f"## {grupo}\n")
        for r in itens:
            linhas.append(f"### {r['cenario']}")
            linhas.append(f"- espera A = `{r['mean_wait_A']:.4f}` ± {r['mean_wait_A_ci95']:.4f}")
            linhas.append(f"- espera B = `{r['mean_wait_B']:.4f}` ± {r['mean_wait_B_ci95']:.4f}")
            linhas.append(f"- espera total = `{r['mean_wait_total']:.4f}`")
            linhas.append(f"- utilização = `{r['server_utilization']:.4f}`")
            if r.get("promoted_fraction_A", 0) > 0:
                linhas.append(f"- fração promovida A = `{r['promoted_fraction_A']*100:.2f}%`")
            if r.get("drop_rate_total", 0) > 0:
                linhas.append(f"- taxa de perda = `{r['drop_rate_total']*100:.2f}%`")
            linhas.append("")
    with open(os.path.join(out_dir, "resumo_resultados.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(linhas))


# ---------------------------------------------------------------------------
# Execução principal
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Simulação M/M/1 prioridade dinâmica")
    parser.add_argument("--output-dir", default="resultados")
    args = parser.parse_args()

    out_dir = args.output_dir
    os.makedirs(out_dir, exist_ok=True)

    n_rep      = BASE["n_rep"]
    todas_reps = []
    resumos    = []

    print("Iniciando simulações...")
    for cfg in CENARIOS:
        nome  = cfg["nome"]
        grupo = cfg["grupo"]
        reps  = []
        sim_args = dict(
            lambda_a     = cfg["lambda_a"],
            lambda_b     = cfg["lambda_b"],
            mu           = cfg["mu"],
            T_age        = cfg.get("T_age", 2.0),
            n_partidas   = cfg["n_partidas"],
            disciplina   = cfg["disciplina"],
            dist_servico = cfg.get("dist_servico", "exponencial"),
            capacidade   = cfg.get("capacidade", None),
        )
        print(f"  {nome} ({n_rep} replicações)...", end=" ", flush=True)
        for rep_id in range(n_rep):
            res = simula_replicacao(semente=1000 + rep_id * 37, **sim_args)
            res["cenario"] = nome
            res["grupo"]   = grupo
            res["rep_id"]  = rep_id
            reps.append(res)
            todas_reps.append(res)
        print("ok")
        resumos.append(sumariza(nome, grupo, cfg, reps))

    refs = referencias_teoricas(BASE["lambda_a"], BASE["lambda_b"], BASE["mu"])

    escreve_csv(os.path.join(out_dir, "resultados_por_replicacao.csv"), todas_reps)
    escreve_csv(os.path.join(out_dir, "resumo_cenarios.csv"),           resumos)
    escreve_csv(os.path.join(out_dir, "referencias_teoricas.csv"),      refs)
    escreve_resumo_md(resumos, refs, out_dir)

    grafico_disciplinas(resumos,     out_dir)
    grafico_sensibilidade_T(resumos, out_dir)
    grafico_distribuicoes(resumos,   out_dir)
    grafico_armazenamento(resumos,   out_dir)

    print(f"\nResultados gravados em: {out_dir}/")

    print("\n=== Referências analíticas ===")
    for r in refs:
        print(f"  {r['cenario']}: Wq_A={r['mean_wait_A_teorico']:.4f}, "
              f"Wq_B={r['mean_wait_B_teorico']:.4f}")

    print("\n=== Resumo dos resultados ===")
    fmt = "{:<42s} {:>8s} {:>8s} {:>8s} {:>10s}"
    print(fmt.format("Cenário", "Wq_A", "Wq_B", "Wq_tot", "Prom_A%"))
    print("-" * 82)
    for r in resumos:
        prom = f"{r['promoted_fraction_A']*100:.1f}" if r.get("promoted_fraction_A", 0) > 0 else "-"
        print(fmt.format(r["cenario"][:42],
                         f"{r['mean_wait_A']:.4f}",
                         f"{r['mean_wait_B']:.4f}",
                         f"{r['mean_wait_total']:.4f}",
                         prom))


if __name__ == "__main__":
    main()
