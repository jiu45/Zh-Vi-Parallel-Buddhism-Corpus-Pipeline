"""Dóng các câu trong cùng một phần sách, chạy E5 và quy hoạch động trên CPU."""
import numpy as np

MODEL = "intfloat/multilingual-e5-small"


def vectorizer():
    from huggingface_hub import hf_hub_download, try_to_load_from_cache
    from tokenizers import Tokenizer
    import onnxruntime as ort

    def model_file(name):
        cached = try_to_load_from_cache(MODEL, name)
        if isinstance(cached, str):
            return cached
        print(f"Đang tải {name} của {MODEL}...", flush=True)
        return hf_hub_download(MODEL, name)

    tokenizer = Tokenizer.from_file(model_file("onnx/tokenizer.json"))
    tokenizer.enable_padding(pad_id=1, pad_token="<pad>")
    tokenizer.enable_truncation(max_length=512)
    options = ort.SessionOptions()
    options.intra_op_num_threads = 4
    session = ort.InferenceSession(model_file("onnx/model.onnx"),
                                   options, providers=["CPUExecutionProvider"])

    def encode(texts, language):
        result = []
        for i in range(0, len(texts), 16):
            batch = tokenizer.encode_batch(["query: " + s for s in texts[i:i+16]])
            ids = np.asarray([s.ids for s in batch], dtype=np.int64)
            mask = np.asarray([s.attention_mask for s in batch], dtype=np.int64)
            inputs = {"input_ids": ids, "attention_mask": mask, "token_type_ids": np.zeros_like(ids)}
            hidden = session.run(None, {k.name: inputs[k.name] for k in session.get_inputs()})[0]
            pooled = (hidden * mask[:,:,None]).sum(axis=1) / mask.sum(axis=1)[:,None]
            result.append(pooled / np.maximum(np.linalg.norm(pooled, axis=1, keepdims=True), 1e-8))
            done = i + len(batch)
            if done % 160 == 0 or done == len(texts):
                print(f"  E5 {language}: {done}/{len(texts)}", flush=True)
        return np.vstack(result).astype(np.float32)
    return encode


def windows(vectors):
    sums = np.vstack([np.zeros_like(vectors[:1]), vectors.cumsum(axis=0)])
    groups = {}
    for size in (1, 2, 3):
        delta = sums[size:] - sums[:-size]
        groups[size] = delta / np.maximum(np.linalg.norm(delta, axis=1, keepdims=True), 1e-8)
    return groups


def align(han, viet):
    """Return ordered, disjoint half-open ranges; a gap retains untranslated text."""
    n, m = len(han), len(viet)
    hs, vs = windows(han), windows(viet)
    steps = [(1,1),(1,2),(2,1),(1,3),(3,1),(2,2),(1,0),(0,1)]
    gap = -0.12
    # Keep only four DP rows. Store backpointers only inside the search band.
    prev = np.full((4,m+1), -np.inf)
    prev[0] = np.arange(m+1)*gap
    history = []
    for i in range(1,n+1):
        radius = max(110, int(m*.06), int(np.ceil(m/n))+2)
        center = round(i*m/n)
        lo, hi = max(0,center-radius), min(m,center+radius)
        js = np.arange(lo,hi+1)
        best = prev[(i-1)%4, js] + gap
        move = np.full(len(js),6,dtype=np.uint8)
        for k,(a,b) in enumerate(steps[:6]):
            if a > i or b > hi:
                continue
            start = max(b-lo,0)
            j = js[start:]
            similarity = vs[b][j-b] @ hs[a][i-a]
            score = prev[(i-a)%4, j-b] + similarity - .78 - .035*(a+b-2)
            better = score > best[start:]
            np.copyto(best[start:], score, where=better)
            move[start:][better] = k
        for j in range(1,len(js)):
            if best[j-1]+gap > best[j]:
                best[j], move[j] = best[j-1]+gap, 7
        prev[i%4].fill(-np.inf)
        prev[i%4,js] = best
        history.append((lo,move))
    path = []
    i,j = n,m
    while i or j:
        if i:
            lo, codes = history[i-1]
            a,b = steps[codes[j-lo]]
        else:
            a,b = 0,1
        path.append((i-a,i,j-b,j))
        i -= a
        j -= b
    return list(reversed(path))
