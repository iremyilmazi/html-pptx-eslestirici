"""Çok dilli metinleri yerel ONNX modeliyle karşılaştırmaya hazırlar."""

import argparse
import platform
from pathlib import Path
import sys


DEFAULT_MODEL_DIR = Path(__file__).resolve().parents[1] / 'modeller' / 'eslestirme'
MODEL_REPO = 'sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2'
MODEL_REVISION = 'e8f8c211226b894fcb81acc59f3b34ba3efd5f42'
TOKENIZER_FILE = 'tokenizer.json'
MODEL_DIMENSION = 384
MAX_TOKENS = 128
BATCH_SIZE = 24
INSTALL_COMMAND = 'python -m pip install -r requirements-otomatik.txt'
DOWNLOAD_COMMAND = 'python src\\local_embeddings.py'


def model_file():
    if platform.machine().lower() in {'arm64', 'aarch64'}:
        return 'onnx/model_qint8_arm64.onnx'
    return 'onnx/model_quint8_avx2.onnx'


def encode_texts(texts, model_dir=DEFAULT_MODEL_DIR):
    """Return unit-length float32 vectors, in input order, without network I/O."""
    try:
        import numpy as np
        import onnxruntime as ort
        from tokenizers import Tokenizer
    except ImportError as exc:
        raise RuntimeError(f'Otomatik eşleştirme paketlerini kurun. CMD komutu: {INSTALL_COMMAND}') from exc

    texts = [' '.join(text.split()) for text in texts]
    if not texts:
        return np.empty((0, MODEL_DIMENSION), dtype=np.float32)

    model_dir = Path(model_dir)
    onnx_path = model_dir / model_file()
    tokenizer_path = model_dir / TOKENIZER_FILE
    if not onnx_path.is_file() or not tokenizer_path.is_file():
        raise FileNotFoundError(f'Yerel eşleştirme modeli bulunamadı. Bir kez {DOWNLOAD_COMMAND} komutunu çalıştırın. Model klasörü: {model_dir}')

    try:
        ort.disable_telemetry_events()
        session = ort.InferenceSession(str(onnx_path), providers=['CPUExecutionProvider'])
        tokenizer = Tokenizer.from_file(str(tokenizer_path))
        tokenizer.enable_truncation(max_length=MAX_TOKENS)
        tokenizer.no_padding()
        pad_id = tokenizer.token_to_id('<pad>')
    except Exception as exc:
        raise RuntimeError(f'Yerel model açılamadı. {DOWNLOAD_COMMAND} komutunu yeniden çalıştırın. Ayrıntı: {exc}') from exc

    # Group similar lengths to minimize padding and encode repeated text once.
    unique_texts = sorted(set(texts), key=lambda text: (len(text), text))
    text_indices = {text: idx for idx, text in enumerate(unique_texts)}
    vectors = np.zeros((len(unique_texts), MODEL_DIMENSION), dtype=np.float32)
    input_names = {value.name for value in session.get_inputs()}
    for start in range(0, len(unique_texts), BATCH_SIZE):
        encodings = tokenizer.encode_batch(unique_texts[start:start + BATCH_SIZE])
        # Keep information past the first 128 tokens by pooling every window.
        windows = [(start + i, window) for i, encoding in enumerate(encodings)
                   for window in [encoding, *encoding.overflowing]]
        for offset in range(0, len(windows), BATCH_SIZE):
            batch = windows[offset:offset + BATCH_SIZE]
            shape = (len(batch), max(len(window.ids) for _, window in batch))
            ids = np.full(shape, pad_id, dtype=np.int64)
            mask = np.zeros(shape, dtype=np.int64)
            token_types = np.zeros(shape, dtype=np.int64)
            for i, (_, window) in enumerate(batch):
                length = len(window.ids)
                ids[i, :length] = window.ids
                mask[i, :length] = window.attention_mask
                token_types[i, :length] = window.type_ids
            inputs = {'input_ids': ids, 'attention_mask': mask}
            if 'token_type_ids' in input_names:
                inputs['token_type_ids'] = token_types
            hidden = session.run(['last_hidden_state'], inputs)[0]
            token_sums = np.einsum('btd,bt->bd', hidden, mask.astype(np.float32))
            np.add.at(vectors, [idx for idx, _ in batch], token_sums)

    # The L2-normalized sum equals the L2-normalized mask-weighted mean.
    vectors /= np.maximum(np.linalg.norm(vectors, axis=1, keepdims=True), 1e-12)
    return vectors[[text_indices[text] for text in texts]]


def download_model(model_dir=DEFAULT_MODEL_DIR):
    try:
        from huggingface_hub import snapshot_download
    except ImportError as exc:
        raise RuntimeError(f'Otomatik eşleştirme paketlerini kurun. CMD komutu: {INSTALL_COMMAND}') from exc

    model_dir = Path(model_dir)
    snapshot_download(
        repo_id=MODEL_REPO,
        revision=MODEL_REVISION,
        local_dir=model_dir,
        token=False,
        allow_patterns=[TOKENIZER_FILE, model_file()],
    )
    encode_texts(['Kurulum kontrolü', 'Setup check'], model_dir)


def main():
    parser = argparse.ArgumentParser(description='Herkese açık yerel eşleştirme modelini bir kez indirir.')
    parser.add_argument('--model-dir', default=DEFAULT_MODEL_DIR, type=Path)
    args = parser.parse_args()
    try:
        download_model(args.model_dir)
    except Exception as exc:
        print(f'Model kurulumu tamamlanamadı. {exc}', file=sys.stderr)
        return 1
    print(f'Yerel eşleştirme modeli hazır. {args.model_dir}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
