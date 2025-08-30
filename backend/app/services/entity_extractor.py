from typing import List, Dict, Optional
from transformers import pipeline

from app.core.dependencies import get_ner_model_config
from app.interfaces.service_interfaces import EntityExtractionServiceInterface


class EntityExtractor(EntityExtractionServiceInterface):
    def __init__(self, model_name: Optional[str] = None):
        if model_name is None:
            try:
                model_name = get_ner_model_config().model_name
            except Exception as exc:
                raise ValueError(
                    "Model name must be provided or configured in settings."
                ) from exc

        self.ner_pipeline = pipeline(
            "ner",
            model=model_name,
            aggregation_strategy="simple",  # type: ignore
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
