"""Gera um acervo fictício reproduzível, sem copiar arquivos do usuário."""

from pathlib import Path


def create_demo(destination: Path) -> int:
    destination = Path(destination)
    # mkdir exclusivo: um acervo existente nunca é sobrescrito.
    destination.mkdir(parents=True, exist_ok=False)
    guide = ("# Guia de identidade — Estúdio Horizonte (fictício)\n"
             "Paleta: terracota, papel e grafite. Usar margens generosas.\n" * 3200).encode()
    brief = ("Briefing fictício da Feira do Bairro\n"
             "Objetivo: reunir oficinas, exposições e pequenas editoras.\n" * 1700).encode()
    catalog = ("Coleção de referências fictícias\n"
               "Caderno artesanal | papel reciclado | edição de demonstração\n" * 5000).encode()
    poster = b'<svg xmlns="http://www.w3.org/2000/svg" width="800" height="600"><rect width="800" height="600" fill="#f2e9df"/><circle cx="400" cy="260" r="140" fill="#c9563f"/><text x="400" y="490" text-anchor="middle" font-size="42" fill="#252a2b">Feira do Bairro</text></svg>'
    files = {
        "projetos/horizonte/guia-identidade.md": guide,
        "entregas/guia-identidade-final.md": guide,
        "backup/guia-identidade-copia.md": guide,
        "projetos/feira/briefing.txt": brief,
        "backup/briefing-feirabairro.txt": brief,
        "referencias/catalogo-papelaria.txt": catalog,
        "backup/catalogo-papelaria.txt": catalog,
        "entregas/catalogo-revisado.txt": catalog,
        "projetos/feira/cartaz.svg": poster,
        "entregas/cartaz-aprovado.svg": poster,
        "projetos/feira/notas.md": b"# Pendencias ficticias\nRevisar o horario das oficinas.\n",
        "projetos/horizonte/notas.md": b"# Pendencias ficticias\nConferir as margens do material.\n",
        "referencias/leia-me.txt": "Acervo gerado pelo Zelunexo. Todos os dados são fictícios.\n".encode(),
        "referencias/rascunho-vazio.txt": b"",
        ".git/ignorado.txt": b"Este arquivo demonstra uma exclusao padrao.\n",
    }
    for relative, content in files.items():
        path = destination / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("xb") as stream:
            stream.write(content)
    return len(files)
