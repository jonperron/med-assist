from transformers import pipeline
from typing import List, Dict


class EntityExtractor:
    def __init__(self, model_name: str = "Jean-Baptiste/camembert-ner"):
        self.ner_pipeline = pipeline(
            "ner", model=model_name, aggregation_strategy="simple"
        )

    def extract_entities(self, text: str) -> Dict[str, List[str]]:
        """
        Extract named entities from the given text.
        """
        ner_results = self.ner_pipeline(text)

        entities: Dict[str, List[str]] = {
            "diseases": [],
            "symptoms": [],
            "treatments": [],
        }

        for ent in ner_results:
            label = ent["entity_group"].lower()
            word = ent["word"]

            if "maladie" in label or "disease" in label:
                entities["diseases"].append(word)
            elif "symptom" in label:
                entities["symptoms"].append(word)
            elif "treatment" in label or "medicament" in label:
                entities["treatments"].append(word)

        for key in entities:
            entities[key] = list(set(entities[key]))

        return entities
