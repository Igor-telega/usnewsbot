import pickle
import os

STORAGE_FILE = "embeddings.pkl"

def get_embedding(text):
    return [0.1] * 1536  # временно фейковая заглушка

def load_embeddings():
    if os.path.exists(STORAGE_FILE):
        try:
            with open(STORAGE_FILE, "rb") as f:
                return pickle.load(f)
        except Exception as e:
            print("Error loading embeddings:", e)
    return {}

def save_embedding(title, embedding):
    try:
        data = load_embeddings()
        data[title] = embedding
        with open(STORAGE_FILE, "wb") as f:
            pickle.dump(data, f)
    except Exception as e:
        print("Error in save_embedding:", e)

def is_duplicate(embedding):
    try:
        data = load_embeddings()
        for existing in data.values():
            if cosine_similarity(existing, embedding) > 0.97:
                return True
    except Exception as e:
        print("Error in is_duplicate:", e)
    return False

def cosine_similarity(a, b):
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = sum(x * x for x in a) ** 0.5
    norm_b = sum(y * y for y in b) ** 0.5
    return dot / (norm_a * norm_b + 1e-8)
