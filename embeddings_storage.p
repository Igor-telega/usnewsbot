import json
import os
import numpy as np

EMBEDDINGS_FILE = "embeddings.json"
SIMILARITY_THRESHOLD = 0.88

def load_embeddings():
    if not os.path.exists(EMBEDDINGS_FILE):
        return []
    with open(EMBEDDINGS_FILE, "r") as file:
        return json.load(file)

def save_embedding(title, embedding):
    embeddings = load_embeddings()
    embeddings.append({
        "title": title,
        "embedding": embedding
    })
    with open(EMBEDDINGS_FILE, "w") as file:
        json.dump(embeddings, file)

def cosine_similarity(a, b):
    a = np.array(a)
    b = np.array(b)
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))

def is_duplicate(new_embedding):
    embeddings = load_embeddings()
    for entry in embeddings:
        similarity = cosine_similarity(new_embedding, entry["embedding"])
        if similarity > SIMILARITY_THRESHOLD:
            return True
    return False
