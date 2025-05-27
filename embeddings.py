import tiktoken
import numpy as np
import openai

def get_embedding(text, model="text-embedding-3-small"):
    response = openai.embeddings.create(
        input=text,
        model=model
    )
    return response.data[0].embedding

def cosine_similarity(a, b):
    return np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))

def is_duplicate(new_emb, existing_embs, threshold=0.91):
    return any(cosine_similarity(new_emb, emb) > threshold for emb in existing_embs)

def save_embedding(title, embedding, path="embeddings_storage.py"):
    with open(path, "a") as f:
        f.write(f"({repr(title)}, {embedding}),\n")
