"""Gera um relatório HTML independente e offline, sem alterar os arquivos analisados."""

from datetime import datetime, timezone
from html import escape
from importlib.resources import files

from .domain import group_duplicates, summarize


def format_size(value: int) -> str:
    """Formata uma quantidade de bytes lógicos em unidades binárias explícitas."""
    if value < 0:
        raise ValueError("O tamanho não pode ser negativo.")
    amount = float(value)
    for unit in ("B", "KiB", "MiB", "GiB", "TiB", "PiB"):
        if amount < 1024 or unit == "PiB":
            if unit == "B":
                return f"{int(amount)} B"
            return f"{amount:.1f}".replace(".", ",") + f" {unit}"
        amount /= 1024
    raise AssertionError("Unidade fora do intervalo previsto")


def _number(value: int) -> str:
    return f"{value:,}".replace(",", ".")


def _date(value: str) -> str:
    try:
        moment = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if moment.tzinfo is None:
            moment = moment.replace(tzinfo=timezone.utc)
        moment = moment.astimezone(timezone.utc)
        months = ("jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez")
        return f"{moment.day:02d} {months[moment.month - 1]} {moment.year} · {moment:%H:%M} UTC"
    except (ValueError, TypeError, AttributeError):
        return str(value)


def _metric(label: str, value: str, note: str, *, accent: bool = False) -> str:
    return (
        f'<article class="metric{ " metric-accent" if accent else ""}">'
        f'<h3>{escape(label)}</h3><p class="metric-value">{escape(value)}</p>'
        f'<p class="metric-note">{escape(note)}</p></article>'
    )


def _group(group: dict, index: int) -> str:
    paths = group["paths"]
    rows = "".join(
        f'<li><span class="file-index" aria-hidden="true">{position:02d}</span>'
        f'<span class="file-path">{escape(path)}</span>'
        f'<span class="file-size">{format_size(group["size"])}</span></li>'
        for position, path in enumerate(paths, start=1)
    )
    return f"""<details class="duplicate-group" data-files="{len(paths)}" open>
      <summary>
        <span class="group-symbol" aria-hidden="true">≋</span>
        <span class="group-heading"><span class="group-name">Grupo {index:02d}</span>
          <span class="group-description">{len(paths)} arquivos · {format_size(group['size'])} cada</span></span>
        <span class="group-potential"><strong>{format_size(group['potential_bytes'])}</strong><span>excedente lógico</span></span>
        <span class="chevron" aria-hidden="true"></span>
      </summary>
      <div class="group-content">
        <p class="list-caption">Caminhos relativos à pasta analisada</p>
        <ol class="file-list">{rows}</ol>
        <p class="hash"><span>SHA-256</span><code>{escape(group['sha256'])}</code></p>
      </div>
    </details>"""


def _entry_list(entries: list[dict], message_key: str) -> str:
    return '<ul class="entry-list">' + "".join(
        f'<li><code>{escape(str(item.get("path", "")))}</code>'
        f'<span>{escape(str(item.get(message_key, "")))}</span></li>'
        for item in entries
    ) + "</ul>"


def render_html(scan: dict) -> str:
    """Gera HTML acessível e escapa os textos da análise para impedir injeção de código."""
    stats = summarize(scan)
    groups = group_duplicates(scan["files"])
    folder = escape(scan["folder"])
    date = escape(_date(scan["created_at"]))
    total = stats["total_bytes"]
    potential = stats["potential_bytes"]
    percent = min(100, max(0, potential * 100 / total)) if total else 0
    percent_label = f"{percent:.1f}".replace(".", ",")
    issues = scan.get("issues", [])
    skipped = scan.get("skipped", [])
    excludes = scan.get("excludes", [])
    status = "Análise parcial" if issues else "Análise concluída"
    scan_id = f"ANÁLISE #{escape(str(scan['id']))}" if scan.get("id") is not None else "ANÁLISE LOCAL"
    metrics = "".join((
        _metric("Arquivos analisados", _number(stats["scanned_files"]), "com leitura e hash concluídos"),
        _metric("Volume analisado", format_size(total), "soma dos tamanhos dos arquivos"),
        _metric("Grupos duplicados", _number(stats["duplicate_groups"]), f'{_number(stats["redundant_files"])} arquivos excedentes'),
        _metric("Excedente lógico", format_size(potential), "estimativa para sua revisão", accent=True),
    ))
    group_html = "".join(_group(group, index) for index, group in enumerate(groups, start=1))
    if not groups:
        title = "Nenhum grupo duplicado." if stats["scanned_files"] else "Nenhum arquivo analisado."
        description = (
            "Não há grupos de arquivos não vazios com o mesmo tamanho e SHA-256."
            if stats["scanned_files"]
            else "Confira a pasta escolhida, as exclusões e os detalhes da análise abaixo."
        )
        if issues:
            description += " Há falhas de leitura; o resultado cobre apenas os arquivos analisados."
        group_html = f'<div class="empty-state"><span aria-hidden="true">○</span><h3>{title}</h3><p>{description}</p></div>'
    warning = ""
    if issues:
        warning = f"""<aside class="warning" role="note"><span class="warning-symbol" aria-hidden="true">!</span>
          <div><strong>Esta análise está parcial.</strong><p>{_number(len(issues))} ocorrência(s) impediram a análise completa.
          Os números abaixo consideram apenas os arquivos registrados. <a href="#scope">Ver ocorrências</a>.</p></div></aside>"""
    exceptions = ""
    if issues:
        exceptions += f'<details class="scope-details"><summary>Ocorrências de leitura <span>{len(issues)}</span></summary>{_entry_list(issues, "message")}</details>'
    if skipped:
        exceptions += f'<details class="scope-details"><summary>Itens ignorados <span>{len(skipped)}</span></summary>{_entry_list(skipped, "reason")}</details>'
    if excludes:
        patterns = "".join(f"<li><code>{escape(pattern)}</code></li>" for pattern in excludes)
        exceptions += f'<details class="scope-details"><summary>Padrões de exclusão <span>{len(excludes)}</span></summary><ul class="excludes">{patterns}</ul></details>'
    if not exceptions:
        exceptions = '<p class="scope-clean">Nenhuma ocorrência ou item ignorado foi registrado.</p>'
    filter_controls = """
        <div class="group-tools" id="group-tools" hidden>
          <div class="search-field"><label for="file-search">Buscar por caminho</label>
            <div class="search-input"><svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="10.5" cy="10.5" r="6.5"/><path d="m16 16 5 5"/></svg>
              <input id="file-search" type="search" placeholder="Ex.: faculdade / proposta.pdf" autocomplete="off">
              <button type="button" id="clear-search" aria-label="Limpar busca" hidden>×</button></div></div>
          <div class="select-field"><label for="group-filter">Quantidade de arquivos</label>
            <select id="group-filter"><option value="all">Todos os grupos</option><option value="3">3 ou mais arquivos</option></select></div>
        </div>
        <div class="results-toolbar" id="results-toolbar" hidden>
          <p id="result-count" role="status" aria-live="polite"></p>
          <div class="expand-buttons"><button type="button" id="expand-all">Expandir grupos</button><span aria-hidden="true">/</span><button type="button" id="collapse-all">Recolher grupos</button></div>
        </div>
        <div class="empty-state" id="no-results" hidden><span aria-hidden="true">⌕</span><h3>Nenhum grupo corresponde à busca.</h3><p>Experimente outro trecho do caminho ou selecione todos os grupos.</p></div>
        <noscript><p class="noscript-note">Todos os grupos estão disponíveis abaixo. A busca precisa de JavaScript.</p></noscript>
    """ if groups else ""
    return f"""<!doctype html>
<html lang="pt-BR">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="color-scheme" content="light"><meta name="description" content="Relatório local de arquivos duplicados, gerado pelo Zelunexo.">
<title>Zelunexo — {folder}</title><style>{_CSS}</style></head>
<body>
<a class="skip-link" href="#main">Pular para o relatório</a>
<aside class="sidebar">
  <a class="brand" href="#overview" aria-label="Zelunexo, início do relatório"><svg viewBox="0 0 36 36" aria-hidden="true"><path d="M8 26V10h9v16h11V10"/><path d="M8 18h20"/></svg><span>zelunexo<span class="brand-dot">.</span></span></a>
  <p class="brand-caption">Um olhar sobre seus arquivos.</p>
  <p class="nav-caption">SEU RELATÓRIO</p>
  <nav aria-label="Seções do relatório">
    <a href="#overview"><span>01</span>Visão geral<svg viewBox="0 0 16 16" aria-hidden="true"><path d="M3 8h10M9 4l4 4-4 4"/></svg></a>
    <a href="#duplicates"><span>02</span>Duplicados<span class="nav-count">{stats['duplicate_groups']}</span></a>
    <a href="#scope"><span>03</span>Sobre a análise</a>
  </nav>
  <div class="sidebar-folder"><span>PASTA ANALISADA</span><strong>{folder}</strong><p>Caminhos exibidos a partir desta pasta.</p></div>
  <div class="sidebar-footer"><span class="offline-dot"></span><strong>Local, do início ao fim.</strong><p>Seus arquivos continuam com você.</p></div>
</aside>
<main id="main">
  <div class="topbar"><span>ORGANIZAÇÃO COMEÇA COM CLAREZA</span><button class="print-button" id="print-report" type="button" hidden><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M7 8V3h10v5M7 17H3V9h18v8h-4M7 14h10v7H7z"/></svg>Imprimir relatório</button></div>
  <section id="overview" aria-labelledby="overview-title">
    <header class="hero"><div><p class="eyebrow">{scan_id}</p><h1 id="overview-title">Sua pasta,<br><em>em perspectiva.</em></h1><p class="hero-description">Encontre o que se repete. Revise com calma.<br>Um mapa dos seus arquivos, sem mover ou apagar nada.</p></div>
      <div class="analysis-meta"><span class="status{' status-partial' if issues else ''}"><span aria-hidden="true"></span>{status}</span><span class="meta-label">PASTA</span><strong>{folder}</strong><time datetime="{escape(scan['created_at'])}">{date}</time></div>
    </header>
    {warning}
    <div class="metrics">{metrics}</div>
    <div class="volume-panel"><div class="volume-heading"><div><h2>O espaço em perspectiva</h2><p>Distribuição do volume lógico analisado</p></div><strong>{percent_label}<span>%</span><small>excedente</small></strong></div>
      <div class="volume-bar" role="img" aria-label="{percent_label}% do volume analisado corresponde ao excedente lógico estimado"><span style="width:{percent:.4f}%"></span></div>
      <div class="volume-legend"><span><i class="legend-base" aria-hidden="true"></i>Base de comparação <strong>{format_size(total - potential)}</strong></span><span><i class="legend-extra" aria-hidden="true"></i>Excedente lógico <strong>{format_size(potential)}</strong></span></div>
      <p class="estimate-note">A estimativa desconta uma cópia por grupo. Não indica um arquivo original nem garante espaço livre em disco.</p>
    </div>
  </section>
  <section id="duplicates" class="duplicates-section" aria-labelledby="duplicates-title">
    <div class="section-heading"><div><p class="eyebrow">02 / REVISÃO DE ARQUIVOS</p><h2 id="duplicates-title">O que se repete<span class="heading-dot">.</span></h2></div><span class="section-badge">TAMANHO + SHA-256</span></div>
    <p class="section-description">Cada grupo reúne arquivos com o mesmo tamanho e hash SHA-256. Nenhum deles é escolhido como original.</p>
    {filter_controls}
    <div id="groups">{group_html}</div>
  </section>
  <section id="scope" class="scope-section" aria-labelledby="scope-title">
    <div class="section-heading"><div><p class="eyebrow">03 / CONTEXTO E CRITÉRIOS</p><h2 id="scope-title">Sobre a análise<span class="heading-dot">.</span></h2></div></div>
    <div class="method-grid"><article><span class="method-number">01</span><h3>Conteúdo, além do nome</h3><p>Os grupos comparam tamanho e SHA-256. Arquivos vazios entram na contagem, mas não nos grupos.</p></article><article><span class="method-number">02</span><h3>Uma fotografia da pasta</h3><p>O relatório retrata a análise de {date}. Mudanças posteriores nos arquivos não aparecem aqui.</p></article><article><span class="method-number">03</span><h3>Decisões nas suas mãos</h3><p>O Zelunexo apenas analisa. Revise a finalidade de cada cópia antes de organizar seus arquivos.</p></article></div>
    <div class="scope-record"><div class="scope-record-heading"><h3>Registro da análise</h3><p>{_number(len(issues))} ocorrência(s) · {_number(len(skipped))} item(ns) ignorado(s)</p></div>{exceptions}</div>
  </section>
  <footer class="report-footer"><span><strong>zelunexo.</strong> Clareza para organizar.</span><span>Relatório offline · Tamanhos em unidades binárias (1 KiB = 1.024 B)</span></footer>
</main><script>{_JS}</script></body></html>"""


_CSS = files("zelunexo").joinpath("assets/report.css").read_text(encoding="utf-8")


_JS = files("zelunexo").joinpath("assets/report.js").read_text(encoding="utf-8")
