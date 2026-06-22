from __future__ import annotations

import argparse
import csv
import heapq
import itertools
import json
import math
import random
import statistics
from collections import deque
from dataclasses import dataclass
from pathlib import Path
from typing import Any


EVENT_PRIORITY = {
    "departure": 0,
    "promotion": 1,
    "arrival_A": 2,
    "arrival_B": 2,
}


@dataclass
class ScenarioConfig:
    group: str
    name: str
    discipline: str
    lambda_a: float
    lambda_b: float
    mu: float
    age_threshold: float
    service_distribution: str = "exponential"
    capacity: int | None = None
    target_completions: int = 25000
    replications: int = 7


@dataclass
class Customer:
    customer_id: int
    cls: str
    arrival_time: float
    service_time: float
    status: str = "new"
    service_start: float | None = None
    promoted: bool = False


def sample_service_time(distribution: str, mu: float, rng: random.Random) -> float:
    if distribution == "exponential":
        return rng.expovariate(mu)
    if distribution == "deterministic":
        return 1.0 / mu
    if distribution == "erlang2":
        return rng.gammavariate(2.0, 1.0 / (2.0 * mu))
    raise ValueError(f"Unsupported service distribution: {distribution}")


def confidence_interval_half_width(values: list[float]) -> float:
    if len(values) < 2:
        return 0.0
    return 1.96 * statistics.stdev(values) / math.sqrt(len(values))


def mean_or_zero(values: list[float]) -> float:
    return statistics.mean(values) if values else 0.0


def quantile_or_zero(values: list[float], q: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    idx = max(0, min(len(ordered) - 1, math.ceil(q * len(ordered)) - 1))
    return ordered[idx]


def theoretical_baselines(lambda_a: float, lambda_b: float, mu: float) -> list[dict[str, Any]]:
    total_lambda = lambda_a + lambda_b
    rho = total_lambda / mu
    rho_a = lambda_a / mu
    second_moment = 2.0 / (mu * mu)

    fifo_wait = total_lambda / (mu * (mu - total_lambda))
    strict_wait_b = total_lambda * second_moment / (2.0 * (1.0 - lambda_b / mu))
    strict_wait_a = total_lambda * second_moment / (2.0 * (1.0 - lambda_b / mu) * (1.0 - rho))

    return [
        {
            "scenario": "fifo_mm1_teorico",
            "discipline": "fifo",
            "mean_wait_A_theoretical": fifo_wait,
            "mean_wait_B_theoretical": fifo_wait,
            "mean_sojourn_A_theoretical": fifo_wait + 1.0 / mu,
            "mean_sojourn_B_theoretical": fifo_wait + 1.0 / mu,
        },
        {
            "scenario": "prioridade_estrita_teorico",
            "discipline": "strict_priority",
            "mean_wait_A_theoretical": strict_wait_a,
            "mean_wait_B_theoretical": strict_wait_b,
            "mean_sojourn_A_theoretical": strict_wait_a + 1.0 / mu,
            "mean_sojourn_B_theoretical": strict_wait_b + 1.0 / mu,
        },
    ]


def default_scenarios() -> list[ScenarioConfig]:
    base = {
        "lambda_a": 0.50,
        "lambda_b": 0.25,
        "mu": 1.0,
        "age_threshold": 2.0,
        "target_completions": 25000,
        "replications": 7,
    }
    return [
        ScenarioConfig(group="disciplinas", name="fifo_mm1", discipline="fifo", **base),
        ScenarioConfig(group="disciplinas", name="prioridade_estrita", discipline="strict_priority", **base),
        ScenarioConfig(group="disciplinas", name="prioridade_dinamica", discipline="dynamic_aging", **base),
        ScenarioConfig(group="sensibilidade_T", name="prioridade_dinamica_T1", discipline="dynamic_aging", age_threshold=1.0, **{k: v for k, v in base.items() if k != "age_threshold"}),
        ScenarioConfig(group="sensibilidade_T", name="prioridade_dinamica_T2", discipline="dynamic_aging", age_threshold=2.0, **{k: v for k, v in base.items() if k != "age_threshold"}),
        ScenarioConfig(group="sensibilidade_T", name="prioridade_dinamica_T4", discipline="dynamic_aging", age_threshold=4.0, **{k: v for k, v in base.items() if k != "age_threshold"}),
        ScenarioConfig(group="distribuicoes_servico", name="dinamica_servico_exponencial", discipline="dynamic_aging", service_distribution="exponential", **base),
        ScenarioConfig(group="distribuicoes_servico", name="dinamica_servico_deterministico", discipline="dynamic_aging", service_distribution="deterministic", **base),
        ScenarioConfig(group="distribuicoes_servico", name="dinamica_servico_erlang2", discipline="dynamic_aging", service_distribution="erlang2", **base),
        ScenarioConfig(group="armazenamento", name="dinamica_buffer_infinito", discipline="dynamic_aging", capacity=None, **base),
        ScenarioConfig(group="armazenamento", name="dinamica_buffer_20", discipline="dynamic_aging", capacity=20, **base),
        ScenarioConfig(group="armazenamento", name="dinamica_buffer_10", discipline="dynamic_aging", capacity=10, **base),
    ]


def run_replication(config: ScenarioConfig, seed: int) -> dict[str, float | int | str | None]:
    rng = random.Random(seed)
    counter = itertools.count()
    events: list[tuple[float, int, int, str, int | None]] = []

    def schedule_event(time_value: float, kind: str, payload: int | None = None) -> None:
        heapq.heappush(events, (time_value, EVENT_PRIORITY[kind], next(counter), kind, payload))

    if config.lambda_a > 0:
        schedule_event(rng.expovariate(config.lambda_a), "arrival_A")
    if config.lambda_b > 0:
        schedule_event(rng.expovariate(config.lambda_b), "arrival_B")

    customers: dict[int, Customer] = {}
    high_queue: deque[int] = deque()
    low_queue: deque[int] = deque()
    fifo_queue: deque[int] = deque()

    metrics = {
        "A": {"arrivals": 0, "accepted": 0, "dropped": 0, "completed": 0, "wait_sum": 0.0, "sojourn_sum": 0.0, "promoted": 0, "wait_samples": [], "sojourn_samples": []},
        "B": {"arrivals": 0, "accepted": 0, "dropped": 0, "completed": 0, "wait_sum": 0.0, "sojourn_sum": 0.0, "promoted": 0, "wait_samples": [], "sojourn_samples": []},
    }

    next_customer_id = 0
    current_time = 0.0
    last_event_time = 0.0
    area_queue = 0.0
    area_system = 0.0
    busy_time = 0.0
    num_waiting = 0
    num_in_service = 0
    completed_total = 0

    def update_areas(new_time: float) -> None:
        nonlocal last_event_time, area_queue, area_system, busy_time
        delta = new_time - last_event_time
        area_queue += num_waiting * delta
        area_system += (num_waiting + num_in_service) * delta
        busy_time += num_in_service * delta
        last_event_time = new_time

    def pop_valid(queue: deque[int], status: str) -> Customer | None:
        while queue:
            customer = customers[queue.popleft()]
            if customer.status == status:
                return customer
        return None

    def dispatch(now: float) -> None:
        nonlocal num_waiting, num_in_service
        if num_in_service == 1:
            return
        customer: Customer | None
        if config.discipline == "fifo":
            customer = pop_valid(fifo_queue, "waiting_fifo")
        else:
            customer = pop_valid(high_queue, "waiting_high")
            if customer is None:
                customer = pop_valid(low_queue, "waiting_low")
        if customer is None:
            return
        num_waiting -= 1
        num_in_service = 1
        customer.status = "in_service"
        customer.service_start = now
        schedule_event(now + customer.service_time, "departure", customer.customer_id)

    def enqueue_customer(customer: Customer, now: float) -> None:
        nonlocal num_waiting, num_in_service
        metrics[customer.cls]["accepted"] += 1
        if num_in_service == 0 and num_waiting == 0:
            num_in_service = 1
            customer.status = "in_service"
            customer.service_start = now
            schedule_event(now + customer.service_time, "departure", customer.customer_id)
            return
        num_waiting += 1
        if config.discipline == "fifo":
            customer.status = "waiting_fifo"
            fifo_queue.append(customer.customer_id)
            return
        if customer.cls == "B":
            customer.status = "waiting_high"
            high_queue.append(customer.customer_id)
            return
        customer.status = "waiting_low"
        low_queue.append(customer.customer_id)
        if config.discipline == "dynamic_aging":
            schedule_event(now + config.age_threshold, "promotion", customer.customer_id)

    def handle_arrival(cls: str, now: float) -> None:
        nonlocal next_customer_id
        if cls == "A" and config.lambda_a > 0:
            schedule_event(now + rng.expovariate(config.lambda_a), "arrival_A")
        if cls == "B" and config.lambda_b > 0:
            schedule_event(now + rng.expovariate(config.lambda_b), "arrival_B")

        metrics[cls]["arrivals"] += 1
        customer = Customer(
            customer_id=next_customer_id,
            cls=cls,
            arrival_time=now,
            service_time=sample_service_time(config.service_distribution, config.mu, rng),
        )
        customers[next_customer_id] = customer
        next_customer_id += 1

        capacity = config.capacity
        if capacity is not None and (num_waiting + num_in_service) >= capacity:
            customer.status = "dropped"
            metrics[cls]["dropped"] += 1
            return
        enqueue_customer(customer, now)

    def handle_promotion(customer_id: int, now: float) -> None:
        customer = customers[customer_id]
        if customer.status != "waiting_low":
            return
        customer.status = "waiting_high"
        customer.promoted = True
        metrics[customer.cls]["promoted"] += 1
        high_queue.append(customer.customer_id)

    def handle_departure(customer_id: int, now: float) -> None:
        nonlocal num_in_service, completed_total
        customer = customers[customer_id]
        if customer.status != "in_service":
            return
        customer.status = "completed"
        num_in_service = 0
        completed_total += 1
        wait_time = (customer.service_start or now) - customer.arrival_time
        sojourn_time = now - customer.arrival_time
        cls_metrics = metrics[customer.cls]
        cls_metrics["completed"] += 1
        cls_metrics["wait_sum"] += wait_time
        cls_metrics["sojourn_sum"] += sojourn_time
        cls_metrics["wait_samples"].append(wait_time)
        cls_metrics["sojourn_samples"].append(sojourn_time)

    while completed_total < config.target_completions:
        event_time = events[0][0]
        update_areas(event_time)
        current_time = event_time

        current_batch: list[tuple[float, int, int, str, int | None]] = []
        while events and events[0][0] == event_time:
            current_batch.append(heapq.heappop(events))

        for _, _, _, kind, payload in current_batch:
            if kind == "arrival_A":
                handle_arrival("A", current_time)
            elif kind == "arrival_B":
                handle_arrival("B", current_time)
            elif kind == "promotion" and payload is not None:
                handle_promotion(payload, current_time)
            elif kind == "departure" and payload is not None:
                handle_departure(payload, current_time)

        dispatch(current_time)

    total_completed = metrics["A"]["completed"] + metrics["B"]["completed"]
    total_arrivals = metrics["A"]["arrivals"] + metrics["B"]["arrivals"]
    total_drops = metrics["A"]["dropped"] + metrics["B"]["dropped"]
    total_wait_sum = metrics["A"]["wait_sum"] + metrics["B"]["wait_sum"]
    total_sojourn_sum = metrics["A"]["sojourn_sum"] + metrics["B"]["sojourn_sum"]
    all_waits = metrics["A"]["wait_samples"] + metrics["B"]["wait_samples"]

    simulated_time = current_time if current_time > 0 else 1.0
    completed_a = int(metrics["A"]["completed"])
    completed_b = int(metrics["B"]["completed"])
    arrivals_a = int(metrics["A"]["arrivals"])

    return {
        "scenario": config.name,
        "group": config.group,
        "discipline": config.discipline,
        "service_distribution": config.service_distribution,
        "capacity": config.capacity,
        "age_threshold": config.age_threshold,
        "simulated_time": simulated_time,
        "server_utilization": busy_time / simulated_time,
        "avg_queue_length": area_queue / simulated_time,
        "avg_system_length": area_system / simulated_time,
        "throughput": total_completed / simulated_time,
        "mean_wait_A": metrics["A"]["wait_sum"] / completed_a if completed_a else 0.0,
        "mean_wait_B": metrics["B"]["wait_sum"] / completed_b if completed_b else 0.0,
        "mean_wait_total": total_wait_sum / total_completed if total_completed else 0.0,
        "mean_sojourn_A": metrics["A"]["sojourn_sum"] / completed_a if completed_a else 0.0,
        "mean_sojourn_B": metrics["B"]["sojourn_sum"] / completed_b if completed_b else 0.0,
        "mean_sojourn_total": total_sojourn_sum / total_completed if total_completed else 0.0,
        "p95_wait_total": quantile_or_zero(all_waits, 0.95),
        "drop_rate_total": total_drops / total_arrivals if total_arrivals else 0.0,
        "drop_rate_A": metrics["A"]["dropped"] / arrivals_a if arrivals_a else 0.0,
        "drop_rate_B": metrics["B"]["dropped"] / int(metrics["B"]["arrivals"]) if metrics["B"]["arrivals"] else 0.0,
        "promoted_fraction_A": metrics["A"]["promoted"] / int(metrics["A"]["accepted"]) if metrics["A"]["accepted"] else 0.0,
        "completed_A": completed_a,
        "completed_B": completed_b,
    }


def summarize_scenario(config: ScenarioConfig, replications: list[dict[str, Any]]) -> dict[str, Any]:
    summary: dict[str, Any] = {
        "scenario": config.name,
        "group": config.group,
        "discipline": config.discipline,
        "service_distribution": config.service_distribution,
        "capacity": config.capacity,
        "age_threshold": config.age_threshold,
        "replications": len(replications),
    }
    metric_keys = [
        "simulated_time",
        "server_utilization",
        "avg_queue_length",
        "avg_system_length",
        "throughput",
        "mean_wait_A",
        "mean_wait_B",
        "mean_wait_total",
        "mean_sojourn_A",
        "mean_sojourn_B",
        "mean_sojourn_total",
        "p95_wait_total",
        "drop_rate_total",
        "drop_rate_A",
        "drop_rate_B",
        "promoted_fraction_A",
    ]
    for key in metric_keys:
        values = [float(rep[key]) for rep in replications]
        summary[key] = mean_or_zero(values)
        summary[f"{key}_ci95"] = confidence_interval_half_width(values)
    return summary


def format_number(value: Any, digits: int = 4) -> str:
    if value is None:
        return "∞"
    if isinstance(value, str):
        return value
    return f"{float(value):.{digits}f}"


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        return
    fieldnames: list[str] = []
    for row in rows:
        for key in row:
            if key not in fieldnames:
                fieldnames.append(key)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def write_json(path: Path, data: Any) -> None:
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def svg_bar_chart(title: str, categories: list[str], series: list[tuple[str, list[float]]], y_label: str) -> str:
    width, height = 960, 560
    margin_left, margin_right, margin_top, margin_bottom = 80, 30, 80, 110
    plot_width = width - margin_left - margin_right
    plot_height = height - margin_top - margin_bottom
    max_value = max(max(values) for _, values in series) if series else 1.0
    max_value = max(max_value, 1e-9)
    colors = ["#2563eb", "#dc2626", "#16a34a", "#9333ea"]
    out = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="white"/>',
        f'<text x="{width/2}" y="36" text-anchor="middle" font-size="24" font-family="Arial">{title}</text>',
        f'<text x="24" y="{height/2}" transform="rotate(-90 24 {height/2})" text-anchor="middle" font-size="16" font-family="Arial">{y_label}</text>',
        f'<line x1="{margin_left}" y1="{height-margin_bottom}" x2="{width-margin_right}" y2="{height-margin_bottom}" stroke="#111"/>',
        f'<line x1="{margin_left}" y1="{margin_top}" x2="{margin_left}" y2="{height-margin_bottom}" stroke="#111"/>',
    ]
    for tick in range(6):
        value = max_value * tick / 5.0
        y = height - margin_bottom - plot_height * tick / 5.0
        out.append(f'<line x1="{margin_left}" y1="{y}" x2="{width-margin_right}" y2="{y}" stroke="#ddd"/>')
        out.append(f'<text x="{margin_left-10}" y="{y+5}" text-anchor="end" font-size="12" font-family="Arial">{value:.2f}</text>')
    groups = len(categories)
    group_width = plot_width / max(groups, 1)
    series_width = group_width * 0.7
    bar_width = series_width / max(len(series), 1)
    for i, category in enumerate(categories):
        x_group = margin_left + i * group_width + (group_width - series_width) / 2
        out.append(f'<text x="{margin_left + i * group_width + group_width/2}" y="{height-margin_bottom+28}" text-anchor="middle" font-size="12" font-family="Arial">{category}</text>')
        for j, (_, values) in enumerate(series):
            value = values[i]
            bar_height = 0.0 if max_value == 0 else (value / max_value) * plot_height
            x = x_group + j * bar_width
            y = height - margin_bottom - bar_height
            out.append(f'<rect x="{x:.2f}" y="{y:.2f}" width="{bar_width-6:.2f}" height="{bar_height:.2f}" fill="{colors[j % len(colors)]}"/>')
            out.append(f'<text x="{x + (bar_width-6)/2:.2f}" y="{y-8:.2f}" text-anchor="middle" font-size="11" font-family="Arial">{value:.2f}</text>')
    legend_x = margin_left
    legend_y = height - 38
    for j, (name, _) in enumerate(series):
        x = legend_x + j * 180
        out.append(f'<rect x="{x}" y="{legend_y}" width="18" height="18" fill="{colors[j % len(colors)]}"/>')
        out.append(f'<text x="{x+26}" y="{legend_y+14}" font-size="13" font-family="Arial">{name}</text>')
    out.append('</svg>')
    return "\n".join(out)


def svg_line_chart(title: str, x_values: list[float], series: list[tuple[str, list[float]]], x_label: str, y_label: str) -> str:
    width, height = 960, 560
    margin_left, margin_right, margin_top, margin_bottom = 80, 30, 80, 90
    plot_width = width - margin_left - margin_right
    plot_height = height - margin_top - margin_bottom
    min_x, max_x = min(x_values), max(x_values)
    if min_x == max_x:
        max_x += 1.0
    max_y = max(max(values) for _, values in series) if series else 1.0
    max_y = max(max_y, 1e-9)
    colors = ["#2563eb", "#dc2626", "#16a34a", "#9333ea"]
    out = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="white"/>',
        f'<text x="{width/2}" y="36" text-anchor="middle" font-size="24" font-family="Arial">{title}</text>',
        f'<text x="{width/2}" y="{height-20}" text-anchor="middle" font-size="16" font-family="Arial">{x_label}</text>',
        f'<text x="24" y="{height/2}" transform="rotate(-90 24 {height/2})" text-anchor="middle" font-size="16" font-family="Arial">{y_label}</text>',
        f'<line x1="{margin_left}" y1="{height-margin_bottom}" x2="{width-margin_right}" y2="{height-margin_bottom}" stroke="#111"/>',
        f'<line x1="{margin_left}" y1="{margin_top}" x2="{margin_left}" y2="{height-margin_bottom}" stroke="#111"/>',
    ]
    for tick in range(6):
        value = max_y * tick / 5.0
        y = height - margin_bottom - plot_height * tick / 5.0
        out.append(f'<line x1="{margin_left}" y1="{y}" x2="{width-margin_right}" y2="{y}" stroke="#ddd"/>')
        out.append(f'<text x="{margin_left-10}" y="{y+5}" text-anchor="end" font-size="12" font-family="Arial">{value:.2f}</text>')
    for x in x_values:
        x_pos = margin_left + (x - min_x) * plot_width / (max_x - min_x)
        out.append(f'<line x1="{x_pos}" y1="{height-margin_bottom}" x2="{x_pos}" y2="{margin_top}" stroke="#eee"/>')
        out.append(f'<text x="{x_pos}" y="{height-margin_bottom+24}" text-anchor="middle" font-size="12" font-family="Arial">{x:g}</text>')
    for j, (name, values) in enumerate(series):
        points = []
        for x, y in zip(x_values, values):
            x_pos = margin_left + (x - min_x) * plot_width / (max_x - min_x)
            y_pos = height - margin_bottom - (y / max_y) * plot_height
            points.append((x_pos, y_pos, y))
        path = " ".join(f'{x:.2f},{y:.2f}' for x, y, _ in points)
        color = colors[j % len(colors)]
        out.append(f'<polyline points="{path}" fill="none" stroke="{color}" stroke-width="3"/>')
        for x_pos, y_pos, y in points:
            out.append(f'<circle cx="{x_pos:.2f}" cy="{y_pos:.2f}" r="4" fill="{color}"/>')
            out.append(f'<text x="{x_pos:.2f}" y="{y_pos-10:.2f}" text-anchor="middle" font-size="11" font-family="Arial">{y:.2f}</text>')
    legend_x = margin_left
    legend_y = height - 52
    for j, (name, _) in enumerate(series):
        x = legend_x + j * 180
        color = colors[j % len(colors)]
        out.append(f'<line x1="{x}" y1="{legend_y+9}" x2="{x+18}" y2="{legend_y+9}" stroke="{color}" stroke-width="3"/>')
        out.append(f'<text x="{x+26}" y="{legend_y+14}" font-size="13" font-family="Arial">{name}</text>')
    out.append('</svg>')
    return "\n".join(out)


def filter_group(summary_rows: list[dict[str, Any]], group: str) -> list[dict[str, Any]]:
    return [row for row in summary_rows if row["group"] == group]


def write_markdown_summary(path: Path, summary_rows: list[dict[str, Any]], theory_rows: list[dict[str, Any]]) -> None:
    disciplines = filter_group(summary_rows, "disciplinas")
    thresholds = filter_group(summary_rows, "sensibilidade_T")
    services = filter_group(summary_rows, "distribuicoes_servico")
    capacities = filter_group(summary_rows, "armazenamento")

    dynamic = next(row for row in disciplines if row["discipline"] == "dynamic_aging")
    strict = next(row for row in disciplines if row["discipline"] == "strict_priority")
    fifo = next(row for row in disciplines if row["discipline"] == "fifo")
    deterministic = next(row for row in services if row["service_distribution"] == "deterministic")
    exponential = next(row for row in services if row["service_distribution"] == "exponential")
    infinite_buffer = next(row for row in capacities if row["capacity"] is None)
    buffer_10 = next(row for row in capacities if row["capacity"] == 10)

    lines = [
        "# Resumo automático do estudo de caso",
        "",
        "## Configuração-base",
        "",
        "- λ_A = 0,50 clientes/unidade de tempo",
        "- λ_B = 0,25 clientes/unidade de tempo",
        "- μ = 1,00 cliente/unidade de tempo",
        "- Carga total ρ = 0,75",
        "- Política proposta: fila M/M/1 não preemptiva com envelhecimento da Classe A após T unidades de tempo",
        "- 7 replicações independentes por cenário, com 25.000 partidas por replicação",
        "",
        "## Principais achados",
        "",
        f"- A prioridade dinâmica reduziu a espera média da Classe A em {100.0 * (strict['mean_wait_A'] - dynamic['mean_wait_A']) / strict['mean_wait_A']:.2f}% frente à prioridade estrita.",
        f"- Em troca, a Classe B teve aumento de {100.0 * (dynamic['mean_wait_B'] - strict['mean_wait_B']) / strict['mean_wait_B']:.2f}% na espera média em relação à prioridade estrita.",
        f"- Comparada ao FIFO puro, a política dinâmica reduziu a espera da Classe B em {100.0 * (fifo['mean_wait_B'] - dynamic['mean_wait_B']) / fifo['mean_wait_B']:.2f}%.",
        f"- Serviço determinístico foi o melhor entre as distribuições testadas, com espera média total de {deterministic['mean_wait_total']:.4f}.",
        f"- Buffer finito de 10 posições reduziu a espera média total para {buffer_10['mean_wait_total']:.4f}, mas introduziu perda média de {100.0 * buffer_10['drop_rate_total']:.2f}%.",
        f"- No cenário-base, {100.0 * dynamic['promoted_fraction_A']:.2f}% das mensagens da Classe A precisaram ser promovidas por envelhecimento.",
        "",
        "## Tabela 1 - Comparação entre disciplinas de fila",
        "",
        "| Cenário | Espera A | Espera B | Espera total | Permanência total | Utilização | Fila média | Promoção A |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in disciplines:
        lines.append(
            f"| {row['scenario']} | {row['mean_wait_A']:.4f} | {row['mean_wait_B']:.4f} | {row['mean_wait_total']:.4f} | {row['mean_sojourn_total']:.4f} | {row['server_utilization']:.4f} | {row['avg_queue_length']:.4f} | {100.0 * row['promoted_fraction_A']:.2f}% |"
        )

    lines.extend([
        "",
        "## Tabela 2 - Sensibilidade ao limiar T",
        "",
        "| Cenário | T | Espera A | Espera B | Espera total | Promoção A |",
        "|---|---:|---:|---:|---:|---:|",
    ])
    for row in thresholds:
        lines.append(
            f"| {row['scenario']} | {row['age_threshold']:.2f} | {row['mean_wait_A']:.4f} | {row['mean_wait_B']:.4f} | {row['mean_wait_total']:.4f} | {100.0 * row['promoted_fraction_A']:.2f}% |"
        )

    lines.extend([
        "",
        "## Tabela 3 - Distribuição do tempo de serviço (política dinâmica)",
        "",
        "| Cenário | Distribuição | Espera A | Espera B | Espera total | P95 espera |",
        "|---|---|---:|---:|---:|---:|",
    ])
    for row in services:
        lines.append(
            f"| {row['scenario']} | {row['service_distribution']} | {row['mean_wait_A']:.4f} | {row['mean_wait_B']:.4f} | {row['mean_wait_total']:.4f} | {row['p95_wait_total']:.4f} |"
        )

    lines.extend([
        "",
        "## Tabela 4 - Capacidade de armazenamento (política dinâmica)",
        "",
        "| Cenário | Capacidade | Espera total | Vazão | Perda total | Fila média |",
        "|---|---:|---:|---:|---:|---:|",
    ])
    for row in capacities:
        capacity = "∞" if row["capacity"] is None else str(row["capacity"])
        lines.append(
            f"| {row['scenario']} | {capacity} | {row['mean_wait_total']:.4f} | {row['throughput']:.4f} | {100.0 * row['drop_rate_total']:.2f}% | {row['avg_queue_length']:.4f} |"
        )

    lines.extend([
        "",
        "## Tabela 5 - Checagem teórica dos cenários clássicos",
        "",
        "| Modelo | Espera A teórica | Espera A simulada | Espera B teórica | Espera B simulada |",
        "|---|---:|---:|---:|---:|",
    ])
    theory_map = {row["discipline"]: row for row in theory_rows}
    for row in [fifo, strict]:
        theory = theory_map[row["discipline"]]
        lines.append(
            f"| {row['scenario']} | {theory['mean_wait_A_theoretical']:.4f} | {row['mean_wait_A']:.4f} | {theory['mean_wait_B_theoretical']:.4f} | {row['mean_wait_B']:.4f} |"
        )

    lines.extend([
        "",
        "## Leitura recomendada dos resultados",
        "",
        "1. Explique que a prioridade dinâmica procura reduzir a injustiça sofrida pela Classe A sem perder totalmente o benefício concedido à Classe B.",
        "2. Destaque que diminuir T favorece a Classe A mais rapidamente, porém reduz a vantagem da Classe B.",
        "3. Discuta que serviço determinístico reduz variabilidade e, portanto, reduz filas e percentis de atraso.",
        "4. Mostre que buffers menores controlam ocupação e atraso à custa de perdas, o que só é aceitável em aplicações tolerantes a descarte.",
    ])

    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_charts(output_dir: Path, summary_rows: list[dict[str, Any]]) -> None:
    disciplines = filter_group(summary_rows, "disciplinas")
    services = filter_group(summary_rows, "distribuicoes_servico")
    thresholds = sorted(filter_group(summary_rows, "sensibilidade_T"), key=lambda row: row["age_threshold"])
    capacities = sorted(filter_group(summary_rows, "armazenamento"), key=lambda row: float("inf") if row["capacity"] is None else row["capacity"])

    discipline_labels = [row["scenario"] for row in disciplines]
    (output_dir / "grafico_espera_disciplinas.svg").write_text(
        svg_bar_chart(
            "Espera média por disciplina",
            discipline_labels,
            [("Classe A", [row["mean_wait_A"] for row in disciplines]), ("Classe B", [row["mean_wait_B"] for row in disciplines])],
            "tempo médio na fila",
        ),
        encoding="utf-8",
    )

    service_labels = [row["service_distribution"] for row in services]
    (output_dir / "grafico_distribuicoes_servico.svg").write_text(
        svg_bar_chart(
            "Impacto da distribuição de serviço",
            service_labels,
            [("Espera total", [row["mean_wait_total"] for row in services]), ("P95 da espera", [row["p95_wait_total"] for row in services])],
            "tempo",
        ),
        encoding="utf-8",
    )

    x_thresholds = [float(row["age_threshold"]) for row in thresholds]
    (output_dir / "grafico_sensibilidade_T.svg").write_text(
        svg_line_chart(
            "Sensibilidade ao limiar T",
            x_thresholds,
            [("Espera Classe A", [row["mean_wait_A"] for row in thresholds]), ("Espera Classe B", [row["mean_wait_B"] for row in thresholds]), ("Promoção Classe A (%)", [100.0 * row["promoted_fraction_A"] for row in thresholds])],
            "T (unidades de tempo)",
            "métrica",
        ),
        encoding="utf-8",
    )

    x_capacities = [40.0 if row["capacity"] is None else float(row["capacity"]) for row in capacities]
    capacity_labels = ["∞" if row["capacity"] is None else str(row["capacity"]) for row in capacities]
    chart_svg = svg_line_chart(
        "Capacidade de armazenamento x desempenho",
        x_capacities,
        [("Espera total", [row["mean_wait_total"] for row in capacities]), ("Perda total (%)", [100.0 * row["drop_rate_total"] for row in capacities]), ("Fila média", [row["avg_queue_length"] for row in capacities])],
        "capacidade (∞ representada por 40)",
        "métrica",
    )
    for src, dst in zip(["40"], ["∞"]):
        chart_svg = chart_svg.replace(f">{src}<", f">{dst}<")
    (output_dir / "grafico_armazenamento.svg").write_text(chart_svg, encoding="utf-8")

    (output_dir / "legenda_capacidades.txt").write_text(
        "No gráfico de armazenamento, o ponto x=40 representa o buffer infinito, apenas para permitir a visualização em linha.\n",
        encoding="utf-8",
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Simula a fila M/M/1 com prioridade dinâmica por idade.")
    parser.add_argument("--output-dir", default="resultados", help="Diretório de saída para tabelas e gráficos.")
    parser.add_argument("--seed", type=int, default=20260624, help="Semente base das replicações.")
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    scenarios = default_scenarios()
    raw_rows: list[dict[str, Any]] = []
    summary_rows: list[dict[str, Any]] = []

    for scenario_index, config in enumerate(scenarios):
        scenario_replications = []
        for replication_index in range(config.replications):
            seed = args.seed + scenario_index * 1000 + replication_index
            result = run_replication(config, seed)
            result["replication"] = replication_index + 1
            raw_rows.append(result)
            scenario_replications.append(result)
        summary_rows.append(summarize_scenario(config, scenario_replications))

    theory_rows = theoretical_baselines(scenarios[0].lambda_a, scenarios[0].lambda_b, scenarios[0].mu)
    theory_map = {row["discipline"]: row for row in theory_rows}
    for row in summary_rows:
        theory = theory_map.get(row["discipline"])
        if theory is not None:
            row["mean_wait_A_theoretical"] = theory["mean_wait_A_theoretical"]
            row["mean_wait_B_theoretical"] = theory["mean_wait_B_theoretical"]
            row["mean_wait_A_relative_error"] = (row["mean_wait_A"] - theory["mean_wait_A_theoretical"]) / theory["mean_wait_A_theoretical"]
            row["mean_wait_B_relative_error"] = (row["mean_wait_B"] - theory["mean_wait_B_theoretical"]) / theory["mean_wait_B_theoretical"]

    write_csv(output_dir / "resultados_por_replicacao.csv", raw_rows)
    write_csv(output_dir / "resumo_cenarios.csv", summary_rows)
    write_csv(output_dir / "referencias_teoricas.csv", theory_rows)
    write_json(output_dir / "resumo_cenarios.json", summary_rows)
    write_markdown_summary(output_dir / "resumo_resultados.md", summary_rows, theory_rows)
    write_charts(output_dir, summary_rows)

    print(f"Resultados gerados em: {output_dir.resolve()}")


if __name__ == "__main__":
    main()
