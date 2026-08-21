import json
from pathlib import Path
from typing import Optional, List, Dict, Any
import typer
from pydantic import ValidationError
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.progress import track

from groundcite.schema import Sample, EvalResult
from groundcite.evaluator import Evaluator
from groundcite.backends.lexical import LexicalBackend
from groundcite.backends.local_nli import LocalNLIBackend
from groundcite.backends.hybrid import HybridBackend
from groundcite.backends.pricing import PRICING_MODELS, update_prices_cache
from groundcite.backends.exchange import SUPPORTED_CURRENCIES, convert_usd_to, update_exchange_cache

app = typer.Typer(
    name="groundcite",
    help="CLI para avaliação evidence-grounded de respostas RAG em PT e EN.",
    no_args_is_help=True
)

console = Console()


def _write_minimal_pdf(path: Path, title: str, lines: list[str]) -> None:
    """Write a tiny valid PDF fallback when optional report dependencies are absent."""
    safe_lines = [title, *lines]
    content_lines = ["BT", "/F1 12 Tf", "72 740 Td"]
    for index, line in enumerate(safe_lines[:24]):
        escaped = line.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
        if index:
            content_lines.append("0 -16 Td")
        content_lines.append(f"({escaped}) Tj")
    content_lines.append("ET")
    stream = "\n".join(content_lines).encode("latin-1", errors="replace")
    objects = [
        b"1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj\n",
        b"2 0 obj << /Type /Pages /Kids [3 0 R] /Count 1 >> endobj\n",
        b"3 0 obj << /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >> endobj\n",
        b"4 0 obj << /Type /Font /Subtype /Type1 /BaseFont /Helvetica >> endobj\n",
        b"5 0 obj << /Length " + str(len(stream)).encode("ascii") + b" >> stream\n" + stream + b"\nendstream endobj\n",
    ]
    pdf = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for obj in objects:
        offsets.append(len(pdf))
        pdf.extend(obj)
    xref_start = len(pdf)
    pdf.extend(f"xref\n0 {len(objects) + 1}\n".encode("ascii"))
    pdf.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        pdf.extend(f"{offset:010d} 00000 n \n".encode("ascii"))
    pdf.extend(
        f"trailer << /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref_start}\n%%EOF\n".encode("ascii")
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(bytes(pdf))

@app.command()
def version():
    """Exibe a versão atual da biblioteca GroundCite."""
    from groundcite import __version__
    console.print(f"[bold green]GroundCite-PTEN[/bold green] v{__version__}")

@app.command()
def validate(
    file_path: Path = typer.Argument(
        ...,
        exists=True,
        file_okay=True,
        dir_okay=False,
        readable=True,
        help="Caminho para o arquivo dataset JSONL a ser validado."
    )
):
    """
    Valida um arquivo dataset JSONL contra o schema Sample do GroundCite e emite estatísticas.
    """
    console.print(f"[bold blue]Iniciando validação do arquivo:[/bold blue] {file_path}")
    
    if not file_path.name.endswith(".jsonl"):
        console.print("[yellow]Aviso: O arquivo não possui a extensão .jsonl, mas será processado mesmo assim.[/yellow]")

    valid_count = 0
    invalid_count = 0
    languages: Dict[str, int] = {}
    context_counts: List[int] = []
    answer_lengths: List[int] = []
    errors: List[Dict[str, Any]] = []

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            for line_idx, line in enumerate(f, 1):
                line_str = line.strip()
                if not line_str:
                    continue
                
                try:
                    sample = Sample.model_validate_json(line_str)
                    valid_count += 1
                    
                    lang = sample.lang
                    languages[lang] = languages.get(lang, 0) + 1
                    context_counts.append(len(sample.contexts))
                    answer_lengths.append(len(sample.answer))
                    
                except ValidationError as ve:
                    invalid_count += 1
                    errors.append({
                        "line": line_idx,
                        "type": "Pydantic ValidationError",
                        "details": ve.errors()
                    })
                except json.JSONDecodeError as jde:
                    invalid_count += 1
                    errors.append({
                        "line": line_idx,
                        "type": "JSON Decode Error",
                        "details": str(jde)
                    })
                except Exception as e:
                    invalid_count += 1
                    errors.append({
                        "line": line_idx,
                        "type": "Unexpected Error",
                        "details": str(e)
                    })

    except Exception as e:
        console.print(f"[bold red]Erro ao abrir ou ler o arquivo:[/bold red] {e}")
        raise typer.Exit(code=1)

    if errors:
        console.print("\n[bold red][ERRO] Foram encontrados erros durante a validação:[/bold red]")
        for err in errors[:5]:
            console.print(Panel(
                f"[bold]Linha {err['line']}:[/bold] Tipo: {err['type']}\nDetalhes: {err['details']}",
                title=f"Erro na linha {err['line']}",
                border_style="red"
            ))
        if len(errors) > 5:
            console.print(f"[yellow]... e mais {len(errors) - 5} erros não exibidos.[/yellow]")

    status_style = "green" if invalid_count == 0 else "red"
    status_text = "PASS" if invalid_count == 0 else "FAIL"
    
    table = Table(title="Relatório Estatístico de Validação", title_style="bold cyan")
    table.add_column("Métrica", style="bold")
    table.add_column("Valor", justify="right")
    
    table.add_row("Total de linhas processadas", str(valid_count + invalid_count))
    table.add_row("Exemplos válidos", f"[green]{valid_count}[/green]")
    table.add_row("Exemplos inválidos", f"[{'red' if invalid_count > 0 else 'green'}]{invalid_count}[/{'red' if invalid_count > 0 else 'green'}]")
    
    lang_summary = ", ".join([f"{k} ({v})" for k, v in languages.items()])
    table.add_row("Idiomas detectados", lang_summary if lang_summary else "Nenhum")
    
    avg_contexts = sum(context_counts) / len(context_counts) if context_counts else 0.0
    avg_answer_len = sum(answer_lengths) / len(answer_lengths) if answer_lengths else 0.0
    table.add_row("Média de contextos por exemplo", f"{avg_contexts:.2f}")
    table.add_row("Média de caract. da resposta", f"{avg_answer_len:.1f}")
    
    console.print("\n")
    console.print(table)
    console.print("\n")
    
    console.print(Panel(
        f"[bold]Resultado Final de Validação: {status_text}[/bold]",
        style=status_style,
        expand=False
    ))
    
    if invalid_count > 0:
        raise typer.Exit(code=1)

@app.command()
def eval(
    file_path: Path = typer.Argument(
        ...,
        exists=True,
        file_okay=True,
        dir_okay=False,
        readable=True,
        help="Caminho para o arquivo dataset JSONL contendo os Samples de entrada RAG."
    ),
    backend: str = typer.Option(
        "lexical",
        "--backend", "-b",
        help="Backend de avaliação a ser utilizado ('lexical', 'local-nli' ou 'hybrid')."
    ),
    out: Optional[Path] = typer.Option(
        None,
        "--out", "-o",
        help="Caminho do arquivo JSONL de saída para salvar os resultados brutos da avaliação."
    ),
    currency: str = typer.Option(
        "BRL",
        "--currency", "-c",
        help="Moeda secundária para exibição da economia final (ex: BRL, EUR, GBP, JPY)."
    ),
    pricing_model: str = typer.Option(
        "gpt-4o",
        "--pricing-model", "-m",
        help="Modelo de precificação de referência de LLM a ser utilizado para estimativa de ROI."
    ),
    budget_usd: Optional[float] = typer.Option(
        None,
        "--budget-usd",
        help="Limite de orçamento em USD para chamadas a APIs de LLMs."
    ),
    tuned_config: Optional[Path] = typer.Option(
        None,
        "--tuned-config",
        help="Caminho para o JSON de configuração calibrado via comando 'tune'."
    )
):
    """
    Executa a avaliação de groundedness de RAG sobre um dataset JSONL de Samples.
    """
    currency = currency.upper().strip()
    if currency not in SUPPORTED_CURRENCIES:
        console.print(f"[bold red]Erro: Moeda '{currency}' não suportada.[/bold red]")
        console.print(f"Moedas suportadas: {', '.join(SUPPORTED_CURRENCIES.keys())}")
        raise typer.Exit(code=1)
        
    console.print(f"[bold blue]Iniciando avaliação do dataset:[/bold blue] {file_path}")
    console.print(f"[bold blue]Configurando Backend:[/bold blue] {backend}")
    
    # 1. Instanciação do Backend
    if backend == "lexical":
        inference_backend = LexicalBackend()
    elif backend == "local-nli":
        try:
            inference_backend = LocalNLIBackend()
        except Exception as e:
            console.print(f"[bold red]Erro ao inicializar o LocalNLIBackend:[/bold red] {e}")
            raise typer.Exit(code=1)
    elif backend == "hybrid":
        try:
            primary = LocalNLIBackend()
            if tuned_config is not None and tuned_config.exists():
                inference_backend = HybridBackend.from_tuned_config(
                    config_path=str(tuned_config),
                    primary_backend=primary
                )
                console.print(f"[green][OK] Carregada configuração calibrada de Pareto a partir de: {tuned_config}[/green]")
            else:
                inference_backend = HybridBackend(primary_backend=primary, pricing_model=pricing_model)
        except Exception as e:
            console.print(f"[bold red]Erro ao inicializar o HybridBackend:[/bold red] {e}")
            raise typer.Exit(code=1)
    else:
        console.print(f"[bold red]Erro: Backend '{backend}' desconhecido. Escolha 'lexical', 'local-nli' ou 'hybrid'.[/bold red]")
        raise typer.Exit(code=1)
        
    evaluator = Evaluator(backend=inference_backend)
    
    samples: List[Sample] = []
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            for line_idx, line in enumerate(f, 1):
                line_str = line.strip()
                if not line_str:
                    continue
                try:
                    samples.append(Sample.model_validate_json(line_str))
                except ValidationError as ve:
                    console.print(f"[red]Erro de validação de schema na linha {line_idx}:[/red] {ve}")
                    raise typer.Exit(code=1)
    except Exception as e:
        console.print(f"[bold red]Erro ao ler arquivo de entrada:[/bold red] {e}")
        raise typer.Exit(code=1)
        
    if not samples:
        console.print("[yellow]Aviso: Nenhuma amostra válida encontrada no dataset.[/yellow]")
        raise typer.Exit(code=0)
        
    results: List[EvalResult] = []
    accumulated_cost = 0.0
    
    # Processamento com barra de progresso visual
    for sample in track(samples, description="Avaliando amostras..."):
        if budget_usd is not None and accumulated_cost > budget_usd:
            console.print(f"[bold red]EXECUÇÃO ABORTADA: Limite de orçamento de USD {budget_usd:.4f} ultrapassado (Custo acumulado: USD {accumulated_cost:.5f})[/bold red]")
            raise typer.Exit(code=1)
            
        try:
            res = evaluator.evaluate(sample)
            results.append(res)
            if res.cost:
                accumulated_cost += res.cost.get("usd_estimate", 0.0)
        except Exception as e:
            console.print(f"[bold red]Erro ao avaliar amostra {sample.id}:[/bold red] {e}")
            raise typer.Exit(code=1)
            
    # Salvar resultados
    if out:
        try:
            out.parent.mkdir(parents=True, exist_ok=True)
            with open(out, "w", encoding="utf-8") as f:
                for res in results:
                    f.write(res.model_dump_json() + "\n")
            console.print(f"[green][OK] Resultados brutos salvos com sucesso em:[/green] {out}")
        except Exception as e:
            console.print(f"[bold red]Erro ao salvar resultados em {out}:[/bold red] {e}")
            raise typer.Exit(code=1)
            
    # Estatísticas Consolidadas de Avaliação
    total_samples = len(results)
    avg_claim_support = sum(r.scores.get("claim_support_rate", 0.0) for r in results) / total_samples
    avg_unsupported_span = sum(r.scores.get("span_support_unsupported_rate", 0.0) for r in results) / total_samples
    avg_abstention_risk = sum(r.scores.get("abstention_risk", 0.0) for r in results) / total_samples
    total_abstain_recs = sum(1 for r in results if r.scores.get("recommend_abstention", 0.0) > 0.5)
    total_usd_saved = sum(r.cost.get("usd_saved", 0.0) for r in results if r.cost)
    total_usd_estimate = sum(r.cost.get("usd_estimate", 0.0) for r in results if r.cost)
    
    table = Table(title="Estatísticas Consolidadas de RAG Evaluation", title_style="bold cyan")
    table.add_column("Métrica", style="bold")
    table.add_column("Média do Dataset", justify="right")
    
    table.add_row("Total de amostras avaliadas", str(total_samples))
    table.add_row("Fração de claims suportados (Groundedness)", f"{avg_claim_support * 100:.1f}%")
    table.add_row("Taxa de caracteres não suportados", f"{avg_unsupported_span * 100:.1f}%")
    table.add_row("Média de risco de abstenção", f"{avg_abstention_risk * 100:.1f}%")
    table.add_row("Abstenções recomendadas (Bloqueios)", f"{total_abstain_recs} ({total_abstain_recs / total_samples * 100:.1f}%)")
    
    converted_saved = convert_usd_to(total_usd_saved, currency)
    converted_estimate = convert_usd_to(total_usd_estimate, currency)
    
    table.add_row("Custo total real estimado (Gastos)", f"USD {total_usd_estimate:.5f} / {currency} {converted_estimate:.5f}")
    table.add_row("Custo total economizado (Economias)", f"[green]USD {total_usd_saved:.5f} / {currency} {converted_saved:.5f}[/green]")
    
    console.print("\n")
    console.print(table)
    console.print("\n")
    
@app.command()
def gate(
    results_path: Path = typer.Argument(
        ...,
        exists=True,
        file_okay=True,
        dir_okay=False,
        readable=True,
        help="Caminho para o arquivo JSONL de resultados gerados pelo comando 'eval'."
    ),
    min_claim_support: float = typer.Option(
        0.80,
        "--min-claim-support",
        help="Fração mínima de suporte de claims tolerada para o gate de CI passar (0.0 a 1.0)."
    ),
    max_unsupported_rate: float = typer.Option(
        0.20,
        "--max-unsupported-rate",
        help="Taxa de caracteres sem suporte máxima tolerada para o gate de CI passar (0.0 a 1.0)."
    )
):
    """
    Quality Gate de CI/CD para validação automatizada de regressão e suporte de respostas RAG.
    """
    console.print(f"[bold blue]Rodando Quality Gate para resultados em:[/bold blue] {results_path}")
    console.print(f"Limiares requeridos: min_claim_support={min_claim_support:.2f}, max_unsupported_rate={max_unsupported_rate:.2f}")
    
    results: List[Dict[str, Any]] = []
    try:
        with open(results_path, "r", encoding="utf-8") as f:
            for line_idx, line in enumerate(f, 1):
                line_str = line.strip()
                if not line_str:
                    continue
                try:
                    results.append(json.loads(line_str))
                except json.JSONDecodeError as jde:
                    console.print(f"[red]Erro de decodificação JSON na linha {line_idx}:[/red] {jde}")
                    raise typer.Exit(code=1)
    except Exception as e:
        console.print(f"[bold red]Erro ao ler o arquivo de resultados:[/bold red] {e}")
        raise typer.Exit(code=1)
        
    if not results:
        console.print("[red]Erro: O arquivo de resultados está vazio.[/red]")
        raise typer.Exit(code=1)
        
    # Computa as médias globais do dataset
    total = len(results)
    avg_claim_support = sum(res.get("scores", {}).get("claim_support_rate", 0.0) for res in results) / total
    avg_unsupported_rate = sum(res.get("scores", {}).get("span_support_unsupported_rate", 0.0) for res in results) / total
    
    # Valida thresholds
    passed_claim_support = avg_claim_support >= min_claim_support
    passed_unsupported_rate = avg_unsupported_rate <= max_unsupported_rate
    
    gate_passed = passed_claim_support and passed_unsupported_rate
    
    table = Table(title="Resultados do Quality Gate", title_style="bold cyan")
    table.add_column("Métrica", style="bold")
    table.add_column("Threshold", justify="center")
    table.add_column("Encontrado", justify="right")
    table.add_column("Status", justify="center")
    
    table.add_row(
        "Groundedness (Claim Support)",
        f">= {min_claim_support:.2f}",
        f"{avg_claim_support:.2f}",
        "[green]PASS[/green]" if passed_claim_support else "[red]FAIL[/red]"
    )
    
    table.add_row(
        "Alucinações (Unsupported Rate)",
        f"<= {max_unsupported_rate:.2f}",
        f"{avg_unsupported_rate:.2f}",
        "[green]PASS[/green]" if passed_unsupported_rate else "[red]FAIL[/red]"
    )
    
    console.print("\n")
    console.print(table)
    console.print("\n")
    
    if gate_passed:
        console.print(Panel(
            "[bold green][GATE PASS] As respostas RAG estão no nível de factualidade esperado.[/bold green]",
            border_style="green"
        ))
        raise typer.Exit(code=0)
    else:
        console.print(Panel(
            "[bold red][GATE FAIL] Respostas alucinadas detectadas acima do threshold máximo de tolerância.[/bold red]",
            border_style="red"
        ))
        raise typer.Exit(code=1)

@app.command()
def roi(
    results_path: Path = typer.Argument(
        ...,
        exists=True,
        file_okay=True,
        dir_okay=False,
        readable=True,
        help="Caminho para o arquivo JSONL de resultados gerados pelo comando 'eval'."
    ),
    currency: str = typer.Option(
        "BRL",
        "--currency", "-c",
        help="Código da moeda secundária para exibição das economias e gastos."
    ),
    export_html: Optional[Path] = typer.Option(
        None,
        "--export-html",
        help="Caminho do arquivo para exportar o dashboard HTML interativo."
    ),
    export_markdown: Optional[Path] = typer.Option(
        None,
        "--export-markdown",
        help="Caminho do arquivo para exportar o relatório simplificado em Markdown (PR Comment)."
    ),
    export_pdf: Optional[Path] = typer.Option(
        None,
        "--export-pdf",
        help="Caminho do arquivo para exportar o relatório corporativo MLOps consolidado em PDF de alta qualidade."
    ),
    pdf_max_samples: int = typer.Option(
        5,
        "--pdf-max-samples",
        help="Limite máximo de amostras com falhas/sucessos a detalhar no PDF corporativo."
    )
):
    """
    Consolida e exibe a análise financeira (ROI e gastos) a partir de um arquivo de resultados do eval.
    """
    currency = currency.upper().strip()
    if currency not in SUPPORTED_CURRENCIES:
        console.print(f"[bold red]Erro: Moeda '{currency}' não suportada.[/bold red]")
        console.print(f"Moedas suportadas: {', '.join(SUPPORTED_CURRENCIES.keys())}")
        raise typer.Exit(code=1)
        
    console.print(f"[bold blue]Analisando resultados financeiros de:[/bold blue] {results_path}")
    
    results: List[Dict[str, Any]] = []
    try:
        with open(results_path, "r", encoding="utf-8") as f:
            for line_idx, line in enumerate(f, 1):
                line_str = line.strip()
                if not line_str:
                    continue
                try:
                    results.append(json.loads(line_str))
                except json.JSONDecodeError as jde:
                    console.print(f"[red]Erro de decodificação JSON na linha {line_idx}:[/red] {jde}")
                    raise typer.Exit(code=1)
    except Exception as e:
        console.print(f"[bold red]Erro ao ler o arquivo de resultados:[/bold red] {e}")
        raise typer.Exit(code=1)
        
    if not results:
        console.print("[red]Erro: O arquivo de resultados está vazio.[/red]")
        raise typer.Exit(code=1)
        
    total_samples = len(results)
    total_usd_saved = 0.0
    total_usd_estimate = 0.0
    
    for res in results:
        cost_meta = res.get("cost", {})
        if cost_meta:
            total_usd_saved += cost_meta.get("usd_saved", 0.0)
            total_usd_estimate += cost_meta.get("usd_estimate", 0.0)
            
    total_cost_without_system = total_usd_saved + total_usd_estimate
    roi_percent = (total_usd_saved / total_cost_without_system * 100.0) if total_cost_without_system > 0 else 0.0
    roi_percent_rem = 100.0 - roi_percent
    
    converted_saved = convert_usd_to(total_usd_saved, currency)
    converted_estimate = convert_usd_to(total_usd_estimate, currency)
    converted_total = convert_usd_to(total_cost_without_system, currency)
    
    table = Table(title=f"Análise Financeira e ROI (USD vs {currency})", title_style="bold cyan")
    table.add_column("Métrica", style="bold")
    table.add_column("Dólar (Universal)", justify="right")
    table.add_column(f"Moeda de Comparação ({currency})", justify="right", style="green")
    
    table.add_row(
        "Amostras Avaliadas",
        str(total_samples),
        str(total_samples)
    )
    table.add_row(
        "Custo Real Estimado (Gastos)",
        f"USD {total_usd_estimate:.5f}",
        f"{currency} {converted_estimate:.5f}"
    )
    table.add_row(
        "Custo Economizado (Economias)",
        f"USD {total_usd_saved:.5f}",
        f"{currency} {converted_saved:.5f}"
    )
    table.add_row(
        "Custo Total Sem GroundCite",
        f"USD {total_cost_without_system:.5f}",
        f"{currency} {converted_total:.5f}"
    )
    
    console.print("\n")
    console.print(table)
    console.print("\n")
    
    console.print(Panel(
        f"[bold]Economia Financeira Gerada pelo GroundCite: {roi_percent:.2f}%[/bold]",
        style="green" if roi_percent > 0 else "yellow",
        expand=False
    ))
    
    # 1. Exportação em Markdown (PR Comment)
    if export_markdown:
        try:
            export_markdown.parent.mkdir(parents=True, exist_ok=True)
            
            md_content = f"""### 📊 Relatório Financeiro e ROI - GroundCite-PTEN

> [!NOTE]
> Relatório gerado a partir do arquivo de resultados `{results_path.name}`.
> A estimativa financeira foi calculada sob as taxas vigentes em USD e {currency}.

#### Resumo Executivo
* **Total de Amostras Avaliadas**: `{total_samples}`
* **Custo Real Estimado (Gastos)**: `USD {total_usd_estimate:.5f} / {currency} {converted_estimate:.5f}`
* **Custo Economizado (Economias)**: `USD {total_usd_saved:.5f} / {currency} {converted_saved:.5f}`
* **Custo Total Equivalente (Sem o Sistema)**: `USD {total_cost_without_system:.5f} / {currency} {converted_total:.5f}`

> [!TIP]
> **Retorno de Investimento (ROI):** 
> Com a utilização do fast-path do GroundCite, você obteve uma economia de **{roi_percent:.2f}%** em custos de tokens de API de LLMs!
"""
            with open(export_markdown, "w", encoding="utf-8") as f:
                f.write(md_content.strip())
            console.print(f"[green][OK] Relatório Markdown exportado com sucesso para: {export_markdown}[/green]")
        except Exception as e:
            console.print(f"[bold red]Erro ao exportar relatório Markdown:[/bold red] {e}")
            
    # 2. Exportação em HTML (Dashboard Premium)
    if export_html:
        try:
            export_html.parent.mkdir(parents=True, exist_ok=True)
            
            # Desenha a rosca donut dinâmica via SVG nativo (circunferência = 100)
            stroke_dasharray = f"{roi_percent:.5f}"
            stroke_dasharray_rem = f"{roi_percent_rem:.5f}"
            
            html_content = f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>GroundCite Financial Dashboard</title>
    <style>
        :root {{
            --bg-color: #0f172a;
            --card-bg: #1e293b;
            --text-color: #f8fafc;
            --text-muted: #94a3b8;
            --primary: #10b981;
            --danger: #ef4444;
            --accent: #3b82f6;
            --border: #334155;
        }}
        body {{
            font-family: 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
            background-color: var(--bg-color);
            color: var(--text-color);
            margin: 0;
            padding: 2rem;
            display: flex;
            justify-content: center;
            align-items: center;
            min-height: 100vh;
        }}
        .dashboard {{
            width: 100%;
            max-width: 900px;
            background-color: rgba(30, 41, 59, 0.7);
            backdrop-filter: blur(10px);
            border: 1px solid var(--border);
            border-radius: 16px;
            padding: 2.5rem;
            box-shadow: 0 10px 30px rgba(0,0,0,0.5);
        }}
        header {{
            text-align: center;
            margin-bottom: 2.5rem;
        }}
        header h1 {{
            font-size: 2.5rem;
            margin: 0;
            background: linear-gradient(135deg, #10b981, #3b82f6);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            font-weight: 800;
        }}
        header p {{
            color: var(--text-muted);
            margin: 0.5rem 0 0 0;
            font-size: 1rem;
        }}
        .content {{
            display: grid;
            grid-template-columns: 1.2fr 0.8fr;
            gap: 2rem;
        }}
        @media (max-width: 768px) {{
            .content {{
                grid-template-columns: 1fr;
            }}
        }}
        .metrics-grid {{
            display: flex;
            flex-direction: column;
            gap: 1.2rem;
        }}
        .metric-card {{
            background-color: var(--card-bg);
            border: 1px solid var(--border);
            border-radius: 12px;
            padding: 1.2rem 1.5rem;
            transition: transform 0.2s ease, box-shadow 0.2s ease;
        }}
        .metric-card:hover {{
            transform: translateY(-2px);
            box-shadow: 0 5px 15px rgba(0,0,0,0.3);
            border-color: var(--accent);
        }}
        .metric-card .label {{
            font-size: 0.85rem;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            color: var(--text-muted);
            margin-bottom: 0.4rem;
        }}
        .metric-card .value {{
            font-size: 1.6rem;
            font-weight: 700;
        }}
        .metric-card .sub-value {{
            font-size: 0.9rem;
            color: var(--primary);
            margin-top: 0.2rem;
        }}
        .metric-card .sub-value.danger {{
            color: var(--danger);
        }}
        .chart-panel {{
            background-color: var(--card-bg);
            border: 1px solid var(--border);
            border-radius: 12px;
            padding: 2rem;
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            text-align: center;
        }}
        .chart-title {{
            font-weight: 600;
            margin-bottom: 1.5rem;
        }}
        .svg-container {{
            position: relative;
            width: 180px;
            height: 180px;
        }}
        .roi-badge {{
            position: absolute;
            top: 50%;
            left: 50%;
            transform: translate(-50%, -50%);
            font-size: 1.8rem;
            font-weight: 800;
            color: var(--primary);
        }}
        .legend {{
            margin-top: 1.5rem;
            display: flex;
            flex-direction: column;
            gap: 0.6rem;
            font-size: 0.9rem;
            align-items: flex-start;
        }}
        .legend-item {{
            display: flex;
            align-items: center;
            gap: 0.5rem;
        }}
        .legend-color {{
            width: 12px;
            height: 12px;
            border-radius: 3px;
        }}
        .legend-color.saved {{ background-color: var(--primary); }}
        .legend-color.spent {{ background-color: var(--danger); }}
    </style>
</head>
<body>
    <div class="dashboard">
        <header>
            <h1>GroundCite Financial Dashboard</h1>
            <p>Auditoria de Retorno de Investimento e Custos de APIs de LLMs</p>
        </header>
        <div class="content">
            <div class="metrics-grid">
                <div class="metric-card">
                    <div class="label">Amostras Processadas</div>
                    <div class="value">{total_samples}</div>
                </div>
                <div class="metric-card">
                    <div class="label">Custo Real de API (Gastos)</div>
                    <div class="value">USD {total_usd_estimate:.5f}</div>
                    <div class="sub-value danger">{currency} {converted_estimate:.5f}</div>
                </div>
                <div class="metric-card">
                    <div class="label">Custo Evitado (Economias)</div>
                    <div class="value">USD {total_usd_saved:.5f}</div>
                    <div class="sub-value">{currency} {converted_saved:.5f}</div>
                </div>
                <div class="metric-card">
                    <div class="label">Custo Equivalente Sem GroundCite</div>
                    <div class="value">USD {total_cost_without_system:.5f}</div>
                    <div class="sub-value">{currency} {converted_total:.5f}</div>
                </div>
            </div>
            <div class="chart-panel">
                <div class="chart-title">Eficiência do Sistema</div>
                <div class="svg-container">
                    <svg width="100%" height="100%" viewBox="0 0 42 42" class="donut">
                        <circle class="donut-hole" cx="21" cy="21" r="15.91549430918954" fill="transparent"></circle>
                        <circle class="donut-ring" cx="21" cy="21" r="15.91549430918954" fill="transparent" stroke="#ef4444" stroke-width="4"></circle>
                        <circle class="donut-segment" cx="21" cy="21" r="15.91549430918954" fill="transparent" stroke="#10b981" stroke-width="4" stroke-dasharray="{stroke_dasharray} {stroke_dasharray_rem}" stroke-dashoffset="0"></circle>
                    </svg>
                    <div class="roi-badge">{roi_percent:.1f}%</div>
                </div>
                <div class="legend">
                    <div class="legend-item">
                        <div class="legend-color saved"></div>
                        <span>Economia Gerada ({roi_percent:.1f}%)</span>
                    </div>
                    <div class="legend-item">
                        <div class="legend-color spent"></div>
                        <span>Custo Gasto ({roi_percent_rem:.1f}%)</span>
                    </div>
                </div>
            </div>
        </div>
    </div>
</body>
</html>"""
            with open(export_html, "w", encoding="utf-8") as f:
                f.write(html_content.strip())
            console.print(f"[green][OK] Dashboard HTML exportado com sucesso para: {export_html}[/green]")
        except Exception as e:
            console.print(f"[bold red]Erro ao exportar dashboard HTML:[/bold red] {e}")
            
    # 3. Exportação em PDF Corporativo
    if export_pdf:
        try:
            console.print(f"[bold blue]Exportando relatório MLOps consolidado para PDF em:[/bold blue] {export_pdf}")
            from groundcite.integrations.pdf_generator import FactualPDFReportGenerator
            pdf_gen = FactualPDFReportGenerator(results, currency=currency, max_samples=pdf_max_samples)
            pdf_gen.export_pdf_file(str(export_pdf))
            console.print(f"[green][OK] Relatório PDF exportado com sucesso para: {export_pdf}[/green]")
        except ImportError as e:
            fallback_lines = [
                "Optional PDF dependencies are not installed.",
                "Install groundcite[report] for the full ReportLab report.",
                f"Samples: {total_samples}",
                f"Estimated cost: USD {total_usd_estimate:.5f}",
                f"Estimated savings: USD {total_usd_saved:.5f}",
                f"ROI: {roi_percent:.2f}%",
            ]
            _write_minimal_pdf(export_pdf, "GroundCite ROI Report", fallback_lines)
            console.print(f"[yellow][WARN] Relatório PDF fallback exportado para: {export_pdf} ({e})[/yellow]")
        except Exception as e:
            console.print(f"[bold red]Erro ao exportar relatório PDF:[/bold red] {e}")
            raise typer.Exit(code=1)

@app.command()
def pricing(
    currency: str = typer.Option(
        "BRL",
        "--currency", "-c",
        help="Código da moeda secundária a exibir (ex: BRL, EUR, GBP, JPY)."
    ),
    update: bool = typer.Option(
        False,
        "--update", "-u",
        help="Força a atualização dos caches de precificação e câmbio pela rede."
    )
):
    """
    Exibe a tabela comparativa de preços vigentes de APIs de LLMs do cache e o ROI na moeda local.
    """
    currency = currency.upper().strip()
    if currency not in SUPPORTED_CURRENCIES:
        console.print(f"[bold red]Erro: Moeda '{currency}' não suportada.[/bold red]")
        console.print(f"Moedas suportadas: {', '.join(SUPPORTED_CURRENCIES.keys())}")
        raise typer.Exit(code=1)
        
    if update:
        console.print("[bold blue]Forçando atualização dos caches via API de rede...[/bold blue]")
        try:
            update_prices_cache(force=True)
            update_exchange_cache(force=True)
            console.print("[green]Caches atualizados com sucesso via rede![/green]")
        except Exception as e:
            console.print(f"[yellow]Aviso: Falha na atualização via rede: {e}. Usando fallbacks.[/yellow]")
            
    table = Table(title=f"Precificação Vigente de APIs de LLMs (USD vs {currency})", title_style="bold cyan")
    table.add_column("Modelo/ID", style="bold")
    table.add_column("Input (USD/1M)", justify="right")
    table.add_column("Output (USD/1M)", justify="right")
    table.add_column(f"Input ({currency}/1M)", justify="right", style="green")
    table.add_column(f"Output ({currency}/1M)", justify="right", style="green")
    
    sorted_keys = sorted(PRICING_MODELS.keys())
    displayed_keys = set()
    for k in sorted_keys:
        has_long = any(other != k and other.endswith("/" + k) for other in sorted_keys)
        if has_long:
            continue
        displayed_keys.add(k)
        
    for k in sorted(displayed_keys):
        prices = PRICING_MODELS[k]
        inp_usd = prices["input"]
        out_usd = prices["output"]
        
        inp_converted = convert_usd_to(inp_usd, currency)
        out_converted = convert_usd_to(out_usd, currency)
        
        table.add_row(
            k,
            f"USD {inp_usd:.3f}",
            f"USD {out_usd:.3f}",
            f"{currency} {inp_converted:.3f}",
            f"{currency} {out_converted:.3f}"
        )
        
    console.print("\n")
    console.print(table)
    console.print("\n")

@app.command()
def report(
    results_path: Path = typer.Argument(
        ...,
        exists=True,
        file_okay=True,
        dir_okay=False,
        readable=True,
        help="Caminho para o arquivo JSONL de resultados gerados pelo comando 'eval'."
    ),
    format: str = typer.Option(
        "markdown",
        "--format", "-f",
        help="Formato de exportação do relatório ('markdown')."
    ),
    out: Optional[Path] = typer.Option(
        None,
        "--out", "-o",
        help="Caminho do arquivo de saída. Se omitido, imprime no terminal."
    )
):
    """
    Gera um relatório descritivo (Markdown) das métricas de avaliação e detalhes de spans.
    """
    if format.lower() != "markdown":
        console.print("[red]Erro: Atualmente apenas o formato 'markdown' é suportado.[/red]")
        raise typer.Exit(code=1)
        
    console.print(f"[bold blue]Gerando relatório para:[/bold blue] {results_path}")
    
    results: List[Dict[str, Any]] = []
    try:
        with open(results_path, "r", encoding="utf-8") as f:
            for line in f:
                line_str = line.strip()
                if line_str:
                    results.append(json.loads(line_str))
    except Exception as e:
        console.print(f"[bold red]Erro ao ler o arquivo de resultados:[/bold red] {e}")
        raise typer.Exit(code=1)
        
    if not results:
        console.print("[red]Erro: O arquivo de resultados está vazio.[/red]")
        raise typer.Exit(code=1)
        
    total_samples = len(results)
    avg_claim_support = sum(res.get("scores", {}).get("claim_support_rate", 0.0) for res in results) / total_samples
    avg_unsupported_rate = sum(res.get("scores", {}).get("span_support_unsupported_rate", 0.0) for res in results) / total_samples
    avg_abstention_risk = sum(res.get("scores", {}).get("abstention_risk", 0.0) for res in results) / total_samples
    
    md_content = "# Relatório de Avaliação RAG - GroundCite\n\n"
    md_content += f"**Arquivo analisado:** `{results_path.name}`\n"
    md_content += f"**Total de Amostras:** `{total_samples}`\n\n"
    
    md_content += "## Resumo de Factualidade\n\n"
    md_content += f"- **Claim Support (Groundedness):** {avg_claim_support * 100:.1f}%\n"
    md_content += f"- **Taxa de Alucinações (Unsupported Span Rate):** {avg_unsupported_rate * 100:.1f}%\n"
    md_content += f"- **Risco Médio de Abstenção:** {avg_abstention_risk * 100:.1f}%\n\n"
    
    md_content += "## Detalhamento de Claims Não Suportados (Top 5 amostras)\n\n"
    
    count_details = 0
    for res in results:
        claims = res.get("claims", [])
        unsupported = [c for c in claims if c.get("pred_label") in ("unsupported", "contradicted")]
        if unsupported:
            count_details += 1
            md_content += f"### Amostra ID: `{res.get('id', 'N/A')}`\n"
            md_content += f"- **Idioma:** {res.get('lang', 'N/A')}\n"
            for c in unsupported:
                label_str = c.get("pred_label", "").upper()
                emoji = "🔴" if label_str == "CONTRADICTED" else "🟡"
                md_content += f"  - {emoji} **{label_str}**: _{c.get('text', '')}_\n"
            md_content += "\n"
        if count_details >= 5:
            break
            
    if count_details == 0:
        md_content += "_Nenhum claim não suportado ou contraditório foi encontrado no dataset._\n\n"
        
    if out:
        try:
            out.parent.mkdir(parents=True, exist_ok=True)
            with open(out, "w", encoding="utf-8") as f:
                f.write(md_content)
            console.print(f"[green][OK] Relatório exportado com sucesso para: {out}[/green]")
        except Exception as e:
            console.print(f"[bold red]Erro ao exportar relatório:[/bold red] {e}")
            raise typer.Exit(code=1)
    else:
        # Se não salvou em arquivo, imprime no console
        from rich.markdown import Markdown
        console.print(Markdown(md_content))

@app.command()
def serve(
    host: str = typer.Option("127.0.0.1", "--host", help="Host para rodar o servidor."),
    port: int = typer.Option(8000, "--port", help="Porta para rodar o servidor."),
    backend: str = typer.Option("hybrid", "--backend", "-b", help="Backend de avaliação padrão.")
):
    """
    Sobe um servidor API REST ultra-leve (FastAPI) para rodar o GroundCite via HTTP.
    """
    try:
        import uvicorn
        from fastapi import FastAPI, HTTPException
    except ImportError:
        console.print("[bold red]FastAPI ou Uvicorn não instalados. Rode `pip install fastapi uvicorn`.[/bold red]")
        raise typer.Exit(code=1)
        
    console.print(f"[bold blue]Inicializando GroundCite REST API no backend: {backend}[/bold blue]")
    
    # 1. Instanciação do Backend fixo
    if backend == "lexical":
        inference_backend = LexicalBackend()
    elif backend == "local-nli":
        inference_backend = LocalNLIBackend()
    elif backend == "hybrid":
        primary = LocalNLIBackend()
        inference_backend = HybridBackend(primary_backend=primary, pricing_model="gpt-4o")
    else:
        console.print(f"[red]Erro: Backend '{backend}' inválido.[/red]")
        raise typer.Exit(code=1)
        
    evaluator = Evaluator(backend=inference_backend)
    
    api = FastAPI(
        title="GroundCite API",
        description="API de validação de Groundedness para sistemas RAG.",
        version="0.3.0"
    )
    
    @api.post("/evaluate", response_model=EvalResult)
    def evaluate_endpoint(sample: Sample):
        try:
            return evaluator.evaluate(sample)
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
            
    @api.get("/health")
    def health_check():
        return {"status": "healthy", "backend": backend}
        
    console.print(f"[green]Servidor rodando em http://{host}:{port}[/green]")
    uvicorn.run(api, host=host, port=port, log_level="info")

@app.command()
def tune(
    dataset_path: Path = typer.Argument(
        ...,
        exists=True,
        file_okay=True,
        dir_okay=False,
        readable=True,
        help="Caminho para o dataset JSONL de benchmark contendo gold labels."
    ),
    max_budget_usd: float = typer.Option(
        0.05,
        "--max-budget-usd",
        "-b",
        help="Orçamento financeiro máximo em USD permitido para o lote total."
    ),
    pricing_model: str = typer.Option(
        "gpt-4o",
        "--pricing-model",
        "-p",
        help="Nome do modelo de LLM de referência de fallback para estimativa de custos."
    ),
    output_path: Path = typer.Option(
        Path("hybrid_tuned_config.json"),
        "--out",
        "-o",
        help="Caminho do arquivo JSON onde salvaremos a configuração de threshold calibrada."
    ),
    llm_accuracy: float = typer.Option(
        0.92,
        "--llm-accuracy",
        help="Fator de acurácia da LLM Judge (0.0 a 1.0) para simulação de F1-Score realista."
    ),
    lang: str = typer.Option(
        "all",
        "--lang",
        help="Idioma para filtrar amostras ('pt-BR', 'en' ou 'all')."
    ),
    export_html: Path = typer.Option(
        Path("hybrid_pareto_curve.html"),
        "--export-html",
        help="Caminho do arquivo para exportar a curva de Pareto interativa em HTML."
    )
):
    """
    Calibra e otimiza matematicamente o threshold de abstenção do HybridBackend.
    Encontra a configuração exata (pareto-optimal) que maximiza o F1-score sob o limite de orçamento USD.
    """
    console.print(Panel(
        f"[bold green]Pareto Hybrid Optimizer (Fase 13)[/bold green]\n"
        f"Dataset: [cyan]{dataset_path}[/cyan]\n"
        f"Orçamento Limite: [yellow]USD {max_budget_usd:.4f}[/yellow]\n"
        f"LLM Ref: [magenta]{pricing_model}[/magenta]\n"
        f"Acurácia Sim: [blue]{llm_accuracy * 100:.1f}%[/blue]\n"
        f"Filtro Idioma: [yellow]{lang}[/yellow]",
        title="GroundCite Tuner"
    ))
    
    # 1. Carrega os samples com gold labels
    samples: List[Sample] = []
    try:
        with open(dataset_path, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    s = Sample.model_validate_json(line.strip())
                    if s.gold and s.gold.claims:
                        samples.append(s)
    except Exception as e:
        console.print(f"[bold red]Erro ao ler dataset:[/bold red] {e}")
        raise typer.Exit(code=1)
        
    if not samples:
        console.print("[bold red]Erro: Nenhuma amostra contendo gabarito (gold claims) foi encontrada no dataset.[/bold red]")
        raise typer.Exit(code=1)
        
    # Instancia o ParetoOptimizer modular do core
    from groundcite.optimizer import ParetoOptimizer
    optimizer = ParetoOptimizer(
        pricing_model=pricing_model,
        llm_accuracy=llm_accuracy,
        lang_filter=lang
    )
    
    # Executa otimização combinatória
    opt_res = optimizer.run_optimization(samples, max_budget_usd)
    grid_results = opt_res["grid_results"]
    best_run = opt_res["best_run"]
    max_llm_cost = opt_res["max_llm_cost"]
    
    if not best_run:
        console.print("[bold red]Erro: Otimizador de Pareto falhou ao processar os dados.[/bold red]")
        raise typer.Exit(code=1)
        
    tuned_threshold = best_run["threshold"]
    best_f1 = best_run["f1_score"]
    best_cost = best_run["cost_usd"]
    
    usd_saved = max_llm_cost - best_cost
    pct_saved = (usd_saved / max_llm_cost * 100.0) if max_llm_cost > 0 else 0.0
    
    console.print(f"Carregados [green]{opt_res['total_claims']}[/green] claims qualificados para otimização.")
    
    # 2. Apresenta o resultado com riqueza visual Rich
    table = Table(title="Grade de Pareto Controlada (Top 5 & Config Ótima)")
    table.add_column("Threshold", style="cyan")
    table.add_column("Custo Est. (USD)", style="yellow")
    table.add_column("Macro-F1 Esperado", style="green")
    table.add_column("Viável?", style="magenta")
    
    sample_points = [0.0, 0.25, 0.50, 0.75, 1.0]
    if tuned_threshold not in sample_points:
        sample_points.append(tuned_threshold)
    sample_points.sort()
    
    for sp in sample_points:
        run_info = next((r for r in grid_results if abs(r["threshold"] - sp) < 1e-5), None)
        if run_info:
            is_best = abs(sp - tuned_threshold) < 1e-5
            style = "bold blink green" if is_best else ""
            table.add_row(
                f"{sp:.2f}" + (" (Ótimo)" if is_best else ""),
                f"USD {run_info['cost_usd']:.4f}",
                f"{run_info['f1_score']:.4f}",
                "Sim" if run_info["cost_usd"] <= max_budget_usd else "Não",
                style=style
            )
            
    console.print(table)
    
    tuned_config = {
        "exact_match_threshold": tuned_threshold,
        "fast_path_contradiction": True,
        "pricing_model": pricing_model,
        "optimized_f1": best_f1,
        "estimated_cost_usd": best_cost,
        "max_llm_cost_usd": max_llm_cost,
        "usd_saved": usd_saved,
        "pct_saved": pct_saved,
        "llm_accuracy": llm_accuracy,
        "lang_filter": lang
    }
    
    # Salva configuração em JSON
    try:
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(tuned_config, f, ensure_ascii=False, indent=2)
        console.print(f"\n[bold green][OK] Configuração ótima salva com sucesso em:[/bold green] {output_path}")
    except Exception as e:
        console.print(f"[bold red]Erro ao salvar configuração ótima:[/bold red] {e}")
        raise typer.Exit(code=1)
        
    # Gera e salva o dashboard HTML da Fronteira de Pareto
    try:
        html_content = optimizer.generate_html_dashboard(
            grid_results=grid_results,
            tuned_threshold=tuned_threshold,
            pricing_model=pricing_model,
            max_budget_usd=max_budget_usd,
            best_run=best_run
        )
        with open(export_html, "w", encoding="utf-8") as f:
            f.write(html_content)
        console.print(f"[bold green][OK] Dashboard HTML da curva de Pareto gerado com sucesso em:[/bold green] {export_html}")
    except Exception as e:
        console.print(f"[bold red]Erro ao exportar dashboard HTML de Pareto:[/bold red] {e}")

@app.command()
def push_to_hub(
    repo_id: str = typer.Argument(
        ...,
        help="Identificador do repositório destino no Hugging Face (ex: 'Masteradilio/groundcite_bench')."
    ),
    token: Optional[str] = typer.Option(
        None,
        "--token", "-t",
        help="Token de autenticação do Hugging Face (se omitido, carrega do .env)."
    ),
    pt_dataset: Path = typer.Option(
        Path("data/samples/groundcite_bench_pt.jsonl"),
        "--pt-data",
        help="Caminho para o arquivo JSONL do subconjunto em português."
    ),
    en_dataset: Path = typer.Option(
        Path("data/samples/groundcite_bench_en.jsonl"),
        "--en-data",
        help="Caminho para o arquivo JSONL do subconjunto em inglês."
    )
):
    """
    Empacota e publica o benchmark bi-língue no Hugging Face Datasets.
    Particiona automaticamente nos splits 'dev' e 'test' e gera o Dataset Card de metadados YAML.
    """
    console.print(Panel(
        f"[bold green]Hugging Face Bench-Hub Exporter (Fase 15)[/bold green]\n"
        f"Repo ID: [cyan]{repo_id}[/cyan]\n"
        f"Dataset PT: [yellow]{pt_dataset}[/yellow]\n"
        f"Dataset EN: [yellow]{en_dataset}[/yellow]",
        title="GroundCite Exporter"
    ))
    
    if not pt_dataset.exists():
        console.print(f"[bold red]Erro: O arquivo em português não existe: {pt_dataset}[/bold red]")
        raise typer.Exit(code=1)
        
    if not en_dataset.exists():
        console.print(f"[bold red]Erro: O arquivo em inglês não existe: {en_dataset}[/bold red]")
        raise typer.Exit(code=1)
        
    try:
        from groundcite.hub import DatasetHubExporter
        exporter = DatasetHubExporter(
            pt_path=pt_dataset,
            en_path=en_dataset
        )
        success = exporter.push_to_hub(repo_id=repo_id, token=token)
        
        if success:
            console.print("\n[bold green][OK] Benchmark publicado com absoluto sucesso no Hugging Face Datasets![/bold green]")
            console.print(f"URL: [cyan]https://huggingface.co/datasets/{repo_id}[/cyan]\n")
        else:
            console.print("[bold red]Falha ao exportar para o Hub de Datasets. Verifique as credenciais e conexões.[/bold red]")
            raise typer.Exit(code=1)
            
    except Exception as e:
        console.print(f"[bold red]Erro ao executar a exportação para o Hub:[/bold red] {e}")
        raise typer.Exit(code=1)

@app.command()
def dashboard(
    port: int = typer.Option(8501, "--port", "-p", help="Porta onde o dashboard do Streamlit será executado.")
):
    """
    Inicia o Dashboard MLOps e Factual Playground interativo do GroundCite via Streamlit.
    """
    console.print(Panel(
        f"[bold green]GroundCite Interactive MLOps Dashboard & Playground[/bold green]\n"
        f"Acesse em: [cyan]http://localhost:{port}[/cyan]",
        title="GroundCite Dashboard"
    ))
    
    try:
        import subprocess
        import sys
        # Descobre o caminho absoluto do dashboard.py
        dashboard_path = Path(__file__).parent / "integrations" / "dashboard.py"
        
        # Executa o Streamlit em subprocesso usando o mesmo interpretador ativo
        cmd = [sys.executable, "-m", "streamlit", "run", str(dashboard_path), "--server.port", str(port)]
        subprocess.run(cmd)
    except Exception as e:
        console.print(f"[bold red]Erro ao iniciar o Streamlit Dashboard:[/bold red] {e}")
        console.print("[yellow]Verifique se o streamlit está instalado: pip install streamlit[/yellow]")
        raise typer.Exit(code=1)

if __name__ == "__main__":
    app()
