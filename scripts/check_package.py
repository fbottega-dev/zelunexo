"""Valida o wheel instalado fora do checkout, em ambiente virtual temporário."""

import argparse
from email.parser import BytesParser
import json
import os
from pathlib import Path
import subprocess
import tempfile
import venv
from zipfile import ZipFile


def check_package(wheel: Path) -> None:
    wheel = wheel.resolve(strict=True)
    with ZipFile(wheel) as archive:
        names = set(archive.namelist())
        for asset in ("zelunexo/assets/report.css", "zelunexo/assets/report.js"):
            if asset not in names:
                raise RuntimeError(f"Recurso ausente no pacote: {asset}")
        metadata = next(name for name in names if name.endswith(".dist-info/METADATA"))
        expected_version = BytesParser().parsebytes(archive.read(metadata))["Version"]

    with tempfile.TemporaryDirectory(prefix="zelunexo-package-") as folder:
        root = Path(folder)
        environment = root / "venv"
        venv.EnvBuilder(with_pip=True).create(environment)
        binaries = environment / ("Scripts" if os.name == "nt" else "bin")
        python = binaries / ("python.exe" if os.name == "nt" else "python")
        command = binaries / ("zelunexo.exe" if os.name == "nt" else "zelunexo")
        process_env = {key: value for key, value in os.environ.items()
                       if key not in ("PYTHONPATH", "PYTHONHOME")}
        # A saída do comando instalado deve continuar UTF-8 mesmo neste ambiente.
        process_env["PYTHONIOENCODING"] = "ascii"
        work = root / "trabalho"
        work.mkdir()

        def run(*args: object) -> str:
            result = subprocess.run(
                [str(arg) for arg in args], cwd=work, env=process_env,
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=60,
            )
            if result.returncode:
                raise RuntimeError(result.stderr.decode("utf-8", errors="replace"))
            return result.stdout.decode("utf-8")

        run(python, "-m", "pip", "install", "--no-index", "--no-deps", wheel)
        assert run(command, "--version").strip() == f"Zelunexo {expected_version}"
        assert run(python, "-m", "zelunexo", "--version").strip() == f"Zelunexo {expected_version}"
        run(command, "demo", "coleção")
        run(command, "analisar", "coleção", "--html", "relatorio.html")
        assert "#1" in run(command, "historico")
        run(command, "exportar", 1, "--saida", "resultado.json", "--formato", "json")
        data = json.loads((work / "resultado.json").read_text(encoding="utf-8"))
        assert data["summary"]["scanned_files"] == 14
        assert data["summary"]["duplicate_groups"] == 4
        assert data["summary"]["redundant_files"] == 6
        html = (work / "relatorio.html").read_text(encoding="utf-8")
        assert "<style>" in html and ".sidebar" in html
        assert "<script>" in html and "addEventListener" in html
        assert "coleção" in html
    print(f"Pacote {wheel.name} aprovado: instalação isolada, comandos, HTML e JSON.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("wheel", type=Path)
    check_package(parser.parse_args().wheel)
