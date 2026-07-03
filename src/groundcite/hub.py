"""Módulo para empacotamento e exportação do GroundCite-Bench para o Hugging Face Hub de forma bi-língue.

Este módulo separa as instâncias locais de benchmark (português e inglês) em splits ('dev' e 'test'),
gera o Dataset Card com metadados YAML e realiza o upload para o repositório Hugging Face do usuário
através da API oficial.
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any

# Importações preguiçosas para evitar acoplamento rígido de dependências opcionais
try:
    from huggingface_hub import HfApi, create_repo
    _HAS_HF_HUB = True
except ImportError:
    _HAS_HF_HUB = False


class DatasetHubExporter:
    """Orquestrador responsável pelo particionamento e exportação do benchmark ao Hugging Face Datasets."""

    def __init__(
        self,
        pt_path: Path | str,
        en_path: Path | str,
        export_dir: Path | str | None = None
    ) -> None:
        self.pt_path = Path(pt_path)
        self.en_path = Path(en_path)
        
        if export_dir is None:
            # Cria pasta temporária de exportação dentro do workspace
            self.export_dir = Path(__file__).parent.parent.parent / "data" / "hub_export"
        else:
            self.export_dir = Path(export_dir)

    def _load_and_split(self, file_path: Path) -> dict[str, list[dict[str, Any]]]:
        """Carrega e particiona o arquivo JSONL de dados com base no split declarado em metadata."""
        splits: dict[str, list[dict[str, Any]]] = {"dev": [], "test": []}
        
        if not file_path.exists():
            logging.warning(f"Arquivo de dados não encontrado: {file_path}")
            return splits

        with open(file_path, "r", encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                try:
                    item = json.loads(line)
                    # Extrai o split do metadado de forma tolerante a falhas
                    metadata = item.get("metadata", {})
                    split_name = metadata.get("split", "test")
                    
                    if split_name not in splits:
                        splits[split_name] = []
                    splits[split_name].append(item)
                except Exception as e:
                    logging.error(f"Erro de parse no registro do dataset: {e}")
                    
        return splits

    def prepare_export_folder(self) -> Path:
        """Estrutura os arquivos fisicamente e gera o Dataset Card (README.md) com os metadados YAML."""
        self.export_dir.mkdir(parents=True, exist_ok=True)
        
        # 1. Carrega e particiona Português
        logging.info("Particionando subconjunto em português...")
        pt_splits = self._load_and_split(self.pt_path)
        pt_dir = self.export_dir / "pt"
        pt_dir.mkdir(parents=True, exist_ok=True)
        
        for split_name, samples in pt_splits.items():
            out_file = pt_dir / f"{split_name}.jsonl"
            logging.info(f"Gravando {len(samples)} instâncias PT no split '{split_name}' -> {out_file.name}")
            with open(out_file, "w", encoding="utf-8") as f:
                for s in samples:
                    f.write(json.dumps(s, ensure_ascii=False) + "\n")
                    
        # 2. Carrega e particiona Inglês
        logging.info("Particionando subconjunto em inglês...")
        en_splits = self._load_and_split(self.en_path)
        en_dir = self.export_dir / "en"
        en_dir.mkdir(parents=True, exist_ok=True)
        
        for split_name, samples in en_splits.items():
            out_file = en_dir / f"{split_name}.jsonl"
            logging.info(f"Gravando {len(samples)} instâncias EN no split '{split_name}' -> {out_file.name}")
            with open(out_file, "w", encoding="utf-8") as f:
                for s in samples:
                    f.write(json.dumps(s, ensure_ascii=False) + "\n")

        # 3. Cria o README.md como Dataset Card com os metadados YAML bi-língues consubstanciados
        readme_path = self.export_dir / "README.md"
        readme_content = """---
configs:
  - config_name: pt
    data_files:
      - split: dev
        path: "pt/dev.jsonl"
      - split: test
        path: "pt/test.jsonl"
  - config_name: en
    data_files:
      - split: dev
        path: "en/dev.jsonl"
      - split: test
        path: "en/test.jsonl"
license: mit
language:
  - pt
  - en
task_categories:
  - text-generation
tags:
  - rag
  - evaluation
  - hallucination
  - fact-checking
  - baseline
  - NLP
  - PT-BR
  - EN
---

# GroundCite-Bench 🚀

Este repositório contém o dataset oficial do benchmark **GroundCite-Bench**, voltado para a meta-avaliação rigorosa e calibração estatística de ferramentas de fact-checking e factualidade de RAG em cenários multilíngues.

Desenvolvido para fundamentar o artigo científico:
*"How Well Do RAG Evaluation Tools Ground Their Judgments? A Cross-Lingual Meta-Evaluation for Portuguese and English"*

---

## ⚡ Como Carregar Instantaneamente em Apenas Uma Linha de Código

Graças às configurações multi-subset nativas do repositório, você pode carregar os subconjuntos de forma isolada e limpa:

```python
from datasets import load_dataset

# 1. Carregar o benchmark nativo em Português
dataset_pt = load_dataset("{repo_id}", "pt")

# 2. Carregar o benchmark em Inglês (RAGTruth)
dataset_en = load_dataset("{repo_id}", "en")
```

Cada subconjunto é distribuído nos splits clássicos `dev` (validação e tuning) e `test` (meta-avaliação e testes estatísticos do paper).

---

## 📋 Atributos das Instâncias (Schema)

*   `id`: Identificador universal único da instância.
*   `question`: Pergunta contextualizada.
*   `answer`: Resposta sob julgamento gerada pela LLM.
*   `contexts`: Lista de documentos contextuais fornecidos como base.
*   `reference_answer`: Gabarito de validaçãofactual.
*   `lang`: Código de idioma (`pt-BR` ou `en-US`).
*   `gold`: Schema padrão-ouro contendo a decomposição atômica de claims (`gold.claims`) com spans de caracteres alinhados à evidência e mapeamento de alucinações.
*   `metadata`: Dicionário com subdivisões de split e tipo de falha (`fully_supported`, `partially_unsupported`, `contradicted`, `abstain_needed`).

---

## 📜 Licença e Citações

Este dataset é disponibilizado sob a licença **MIT**. Se você utilizar este benchmark em seus estudos, cite o nosso paper usando o arquivo `CITATION.cff` versão no repositório principal.
"""
        with open(readme_path, "w", encoding="utf-8") as f:
            f.write(readme_content.strip())
            
        logging.info(f"Pasta de exportação de dados bi-língues e README.md estruturados em: {self.export_dir}")
        return readme_path

    def push_to_hub(self, repo_id: str, token: str | None = None) -> bool:
        """Gera a estrutura física local e realiza o upload para o repositório do Hugging Face Datasets."""
        if not _HAS_HF_HUB:
            raise ImportError(
                "A biblioteca 'huggingface_hub' não está disponível. "
                "Por favor, execute 'pip install huggingface_hub' para habilitar a exportação ao Hub."
            )
            
        token = token or os.getenv("HUGGINGFACE_TOKEN")
        if not token:
            logging.warning(
                "Nenhum Hugging Face Token fornecido por parâmetro ou configurado no .env. "
                "O upload poderá falhar se o repositório for privado ou exigir autenticação."
            )
            
        # 1. Prepara a estrutura local de pastas e o README.md de subconjuntos
        readme_path = self.prepare_export_folder()
        
        # Ajusta o README para incluir o repo_id correto
        with open(readme_path, "r", encoding="utf-8") as f:
            content = f.read()
        content = content.replace("{repo_id}", repo_id)
        with open(readme_path, "w", encoding="utf-8") as f:
            f.write(content)

        # 2. Cria o repositório de dataset no HF Hub se ele não existir
        logging.info(f"Criando/Validando repositório de dataset no HF Hub: {repo_id}...")
        api = HfApi()
        try:
            create_repo(
                repo_id=repo_id,
                token=token,
                repo_type="dataset",
                private=False,
                exist_ok=True
            )
            logging.info("Repositório inicializado/validado no Hub com sucesso.")
        except Exception as e:
            logging.warning(f"Aviso ao inicializar o repositório no Hub: {e}. Prosseguindo com o upload.")

        # 3. Faz o upload da pasta estruturada local ao repositório no Hub
        logging.info(f"Iniciando o upload da pasta local '{self.export_dir}' para o repositório '{repo_id}'...")
        try:
            api.upload_folder(
                folder_path=str(self.export_dir),
                repo_id=repo_id,
                repo_type="dataset",
                token=token
            )
            logging.info(f"Upload concluído com sucesso absoluto! Acesse: https://huggingface.co/datasets/{repo_id}")
            return True
        except Exception as e:
            logging.error(f"Falha ao realizar o upload da pasta para o Hugging Face Hub: {e}")
            return False
