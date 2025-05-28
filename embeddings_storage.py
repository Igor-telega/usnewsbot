import os
import pickle

STORAGE_FILE = "embeddings.pkl"

def get_embedding(text):
    return [0.1] * 1536  # временная заглушка

def cosine_similarity(a, b):
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = sum(x * x for x in a) ** 0.5
    norm_b = sum(y * y for y in b) ** 0.5
    return dot / (norm_a * norm_b)

def load_embeddings():
    if not os.path.exists(STORAGE_FILE):
        return {}
    try:
        with open(STORAGE_FILE, "rb") as f:
            return pickle.load(f)
    except Exception as e:
        print("Error loading embeddings:", e)
        return {}

def save_embedding(title, embedding):
    data = load_embeddings()
    data[title] = embedding
    try:
        with open(STORAGE_FILE, "wb") as f:
            pickle.dump(data, f)
    except Exception as e:
        print("Error saving embedding:", e)

def is_duplicate(new_embedding, threshold=0.95):
    data = load_embeddings()
    for title, emb in data.items():
        sim = cosine_similarity(new_embedding, emb)
        if sim > threshold:
            return True
    return False
