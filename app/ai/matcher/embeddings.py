import numpy as np
from sentence_transformers import SentenceTransformer, util


class EmbeddingModel:
    def __init__(self, model_name: str):
        self._model = SentenceTransformer(model_name)
    
    def preprocess(self, text):
    # Приведение к нижнему регистру и удаление лишних символов
        return text.lower().replace('®', '').replace(',', ' ').strip()
    
    def score(self, query: str, candidates: list[str]) -> tuple[float, str, list[float]]:
        # Эталон и список для сравнения
        reference = self.preprocess(query)
        candidates_proc = [self.preprocess(item) for item in candidates]

        # Расчет эмбеддингов и сходства
        emb_ref = self._model.encode(reference, convert_to_tensor=True)
        emb_cands = self._model.encode(candidates_proc, convert_to_tensor=True)

        cos_scores = util.cos_sim(emb_ref, emb_cands).flatten()
        # print(cos_scores)
        best_idx = int(np.argmax(cos_scores))
        return float(cos_scores[best_idx]), candidates[best_idx], cos_scores.tolist()
    
    def score_old(self, query: str, candidates: list[str]) -> tuple[float, str, list[float]]:
        texts = [query] + candidates
        embeddings = self._model.encode(texts, normalize_embeddings=True, show_progress_bar=False)
        query_vec = embeddings[0:1]
        cand_vecs = embeddings[1:]
        sims = (query_vec @ cand_vecs.T).flatten()
        best_idx = int(np.argmax(sims))
        return float(sims[best_idx]), candidates[best_idx], sims.tolist()
    

# import torch
# from transformers import AutoTokenizer, AutoModelForSequenceClassification


# class EmbeddingModel_old:
#     def __init__(self, model_name: str):
#         self._tokenizer = AutoTokenizer.from_pretrained('sagteam/rubert-base-cased-mcn')
#         self._model = AutoModelForSequenceClassification.from_pretrained('sagteam/rubert-base-cased-mcn')
    
#     def preprocess(self, text):
#     # Приведение к нижнему регистру и удаление лишних символов
#         return text.lower().replace('®', '').replace(',', ' ').strip()
    
#     def score(self, query: str, candidates: list[str]) -> tuple[float, str, list[float]]:
#         # Эталон и список для сравнения
#         reference = self.preprocess(query)
#         candidates_proc = [self.preprocess(item) for item in candidates]

#         scores = []
#         for candidate in candidates_proc:
#             # Подготавливаем входные данные
#             inputs = self._tokenizer(reference, candidate, return_tensors='pt', truncation=True, padding=True)
#             with torch.no_grad():
#                 outputs = self._model(**inputs)
#             # Получаем "оценку похожести". Чем выше, тем лучше.
#             similarity_score = torch.softmax(outputs.logits, dim=-1)[0][1].item()
#             scores.append(similarity_score)
        
#         best_idx = int(np.argmax(scores))
#         return float(scores[best_idx]), candidates[best_idx], scores
