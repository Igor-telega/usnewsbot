import numpy as np
import pickle
from openai import OpenAI
import os

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
openai_client = OpenAI(api_key=OPENAI_API_KEY)

def get_embedding(text):
    try:
        response = openai_client.embeddings.create(
            input=[text],
            model="text-embedding-3-small"
        )
        return response.data[0].embedding
    except Exception as e:
        print("Error in get_embedding:", e)
        return None

def cosine_similarity(vec1, vec2):
    v1 = np.array(vec1)
    v2 = np.array(vec2)
    return np.dot(v1, v2) / (np.linalg.norm(v1) * np.linalg.norm(v2))

def is_duplicate(new_embedding, file_path, threshold=0.9):
    if not os.path.exists(file_path):
        return False
    try:
        with open(file_path, "rb") as f:
            stored = pickle.load(f)
        for _, emb in stored:
            if cosine_similarity(emb, new_embedding) > threshold:
                return True
        return False
    except Exception as e:
        print("Error in is_duplicate:", e)
        return False

def save_embedding(title, embedding, file_path="embeddings_storage.py"):
    try:
        data = []
        if os.path.exists(file_path):
            with open(file_path, "rb") as f:
                data = pickle.load(f)
        data.append((title, embedding))
        with open(file_path, "wb") as f:
            pickle.dump(data, f)
    except Exception as e:
        print("Error in save_embedding:", e)
