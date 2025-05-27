import tiktoken
import numpy as np
import openai
import os
import json

def get_embedding(text, model="text-embedding-3-small"):
    response = openai.embeddings.create(
        input=text,
        model=model
    )
    return response.data[0].embedding

def cosine_similarity(a, b):
    return np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))

def save_embedding(title, embedding, path="embeddings_storage.py"):
    data = {"title": title, "embedding": embedding}
    with open(path, "a") as f:
        f.write(json.dumps(data) + "\n")

def load_embeddings(path="embeddings_storage.py"):
    embeddings = []
    if not os.path.exists(path):
        return embeddings
    with open(path, "r") as f:
        for line in f:
            try:
                data = json.loads(line.strip())
                embeddings.append(data["embedding"])
            except Exception:
                continue
    return embeddings

def is_duplicate(new_emb, path="embeddings_storage.py", threshold=0.91):
    existing_embs = load_embeddings(path)
    return any(cosine_similarity(new_emb, emb) > threshold for emb in existing_embs)
