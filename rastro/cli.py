"""Interface de terminal; coordena leitura, persistência e exportação."""

import argparse
import json
from pathlib import Path
import sqlite3
import sys

from . import __version__
from .demo import create_demo
from .domain import group_duplicates, summarize
from .scanner import scan_folder
from .storage import list_scans, load_scan, save_scan

DEFAULT_DATABASE = Path(".rastro/historico.sqlite3")


def terminal_text(value: object) -> str:
    # Um nome de arquivo pode conter controles de terminal em sistemas Unix.
    return "".join(char if char.isprintable() else f"\\u{ord(char):04x}" for char in str(value))


def format_bytes(value: int) -> str:
    amount = float(value)
    for unit in ("B", "KiB", "MiB", "GiB", "TiB"):
        if amount < 1024 or unit == "TiB":
            return f"{amount:.1f} {unit}" if unit != "B" else f"{value} B"
        amount /= 1024
    raise AssertionError("Unidade não encontrada")


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(
        prog="rastro", description="Encontre arquivos duplicados pelo conteúdo, sem alterar os originais.",
        epilog="Exemplo: python -m rastro analisar ./demo --html ./relatorio.html",
    )
    root.add_argument("--version", action="version", version=f"Rastro {__version__}")
    commands = root.add_subparsers(dest="command", required=True, title="comandos")
    demo = commands.add_parser("demo", help="criar arquivos fictícios em uma pasta nova")
    demo.add_argument("pasta", type=Path, help="pasta que ainda não existe")
    scan = commands.add_parser("analisar", help="analisar uma pasta e salvar o histórico")
    scan.add_argument("pasta", type=Path)
    scan.add_argument("--html", type=Path, help="novo relatório HTML fora da pasta analisada")
    scan.add_argument("--ignorar", action="append", default=[], metavar="PADRAO", help='exclusão adicional, repetível; exemplo: "*.tmp"')
    history = commands.add_parser("historico", help="listar as últimas 20 análises")
    export = commands.add_parser("exportar", help="gerar novamente um relatório salvo")
    export.add_argument("id", type=int, help="número da análise no histórico")
    export.add_argument("--saida", type=Path, required=True, help="arquivo novo; nunca sobrescreve")
    export.add_argument("--formato", choices=("html", "json"), default="html")
    for command in (scan, history, export):
        command.add_argument("--banco", type=Path, default=DEFAULT_DATABASE, help=f"histórico SQLite (padrão: {DEFAULT_DATABASE.as_posix()})")
    return root


def require_new_output(path: Path) -> None:
    if path.exists() or path.is_symlink():
        raise ValueError(f"A saída já existe: {path}. Escolha outro nome para preservá-la.")
    if not path.parent.is_dir():
        raise ValueError(f"A pasta de saída não existe: {path.parent}.")


def require_outside(source: Path, target: Path, label: str) -> None:
    if target.resolve().is_relative_to(source.resolve()):
        raise ValueError(f"{label} deve ficar fora da pasta analisada. Escolha outro caminho.")


def write_export(scan: dict, path: Path, output_format: str) -> None:
    require_new_output(path)
    if output_format == "html":
        from .report import render_html
        content = render_html(scan)
    else:
        content = json.dumps(
            {"schema_version": 1, **scan, "summary": summarize(scan), "groups": group_duplicates(scan["files"])},
            ensure_ascii=False, indent=2,
        ) + "\n"
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(content)


def execute(args: argparse.Namespace) -> int:
    if args.command == "demo":
        count = create_demo(args.pasta)
        print(f"Rastro · {count} arquivos fictícios criados em {terminal_text(args.pasta)}.")
        print("Próximo passo: python -m rastro analisar \"" + terminal_text(args.pasta) + '\" --html ./relatorio.html')
        return 0
    if args.command == "analisar":
        require_outside(args.pasta, args.banco, "O banco")
        if args.html:
            require_outside(args.pasta, args.html, "O relatório")
            require_new_output(args.html)
            if args.html.resolve() == args.banco.resolve():
                raise ValueError("Use caminhos diferentes para banco e relatório.")
        print(f"Analisando {terminal_text(args.pasta)}… Lendo o conteúdo em blocos.", file=sys.stderr)
        scan = scan_folder(args.pasta, args.ignorar)
        scan["id"] = save_scan(args.banco, scan)
        summary = summarize(scan)
        print(f"\nRastro · Análise #{scan['id']} · {'PARCIAL' if scan['issues'] else 'concluída'}")
        print(f"{summary['scanned_files']} arquivos lidos · {format_bytes(summary['total_bytes'])}")
        print(f"{summary['duplicate_groups']} grupos · {summary['redundant_files']} cópias excedentes · {format_bytes(summary['potential_bytes'])} redundantes")
        print("Estimativa de bytes lógicos. Nenhum arquivo original foi alterado.")
        print(f"Histórico salvo em {terminal_text(args.banco)}.")
        if scan["skipped"]:
            print(f"{len(scan['skipped'])} entradas ignoradas pela política de análise; veja o relatório.")
        if args.html:
            write_export(scan, args.html, "html")
            print(f"Abra o relatório: {terminal_text(args.html)}")
        if scan["issues"]:
            print(f"Atenção: {len(scan['issues'])} entradas não puderam ser analisadas.", file=sys.stderr)
            for issue in scan["issues"][:5]:
                print(f"  {terminal_text(issue['path'])}: {terminal_text(issue['message'])}", file=sys.stderr)
            print("Veja os detalhes exportando esta análise e repita após corrigir a causa.", file=sys.stderr)
            return 3
        return 0
    if args.command == "historico":
        scans = list_scans(args.banco)
        print("Rastro · Histórico (últimas 20 análises)\n")
        if not scans:
            print("Nenhuma análise salva. Comece com: python -m rastro analisar ./demo")
        for scan in scans:
            state = "parcial" if scan["issues_count"] else "completa"
            print(f"#{scan['id']} · {terminal_text(scan['created_at'])} · {terminal_text(scan['folder'])} · {state}")
            print(f"  {scan['scanned_files']} arquivos | {scan['duplicate_groups']} grupos | {format_bytes(scan['potential_bytes'])} redundantes")
        return 0
    scan = load_scan(args.banco, args.id)
    write_export(scan, args.saida, args.formato)
    print(f"Análise #{scan['id']} exportada para {terminal_text(args.saida)}.")
    return 0


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        return execute(args)
    except (OSError, ValueError, sqlite3.Error) as error:
        print(f"Erro: {terminal_text(error)}", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        print("\nOperação interrompida. Os arquivos originais foram preservados.", file=sys.stderr)
        return 130
