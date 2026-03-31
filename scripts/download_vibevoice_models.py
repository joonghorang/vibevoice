from __future__ import annotations

from pathlib import Path
import sys

from dotenv import load_dotenv
from huggingface_hub import HfApi, hf_hub_download


ROOT_DIR = Path(__file__).resolve().parents[1]
load_dotenv(ROOT_DIR / ".env")
sys.path.insert(0, str(ROOT_DIR / "services" / "asr-server"))


def main() -> None:
    from app.config import settings

    cache_dir = settings.vibevoice_cache_dir
    cache_dir.mkdir(parents=True, exist_ok=True)

    print(f"Downloading VibeVoice assets into {cache_dir} ...")
    api = HfApi()

    download_repo(
        api=api,
        repo_id=settings.vibevoice_model_id,
        cache_dir=cache_dir,
        skip_prefixes=("figures/",),
    )
    download_repo(
        api=api,
        repo_id=settings.vibevoice_acoustic_tokenizer_id,
        cache_dir=cache_dir,
        skip_prefixes=(),
    )

    print("Done. Models are cached locally and ready for offline reuse.")


def download_repo(
    *,
    api: HfApi,
    repo_id: str,
    cache_dir: Path,
    skip_prefixes: tuple[str, ...],
) -> None:
    print(f"- Downloading repo: {repo_id}")
    files = api.list_repo_files(repo_id=repo_id, repo_type="model")
    filtered_files = [
        file_name
        for file_name in files
        if not any(file_name.startswith(prefix) for prefix in skip_prefixes)
    ]

    for file_name in filtered_files:
        print(f"  - {file_name}")
        hf_hub_download(
            repo_id=repo_id,
            filename=file_name,
            repo_type="model",
            cache_dir=str(cache_dir),
        )


if __name__ == "__main__":
    main()
