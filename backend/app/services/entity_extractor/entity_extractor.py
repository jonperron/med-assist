import json
from pathlib import Path
from typing import Any, Dict, List, Optional
from transformers import pipeline

from app.core.dependencies import get_ner_model_config
from app.interfaces.service_interfaces import EntityExtractionServiceInterface
from app.schemas.extraction import EntityDetail


class EntityExtractor(EntityExtractionServiceInterface):
    """
    Enhanced EntityExtractor supporting multiple language clinical NER models.
    Supports comprehensive medical entity extraction with configurable label mappings.

    The extractor uses language-specific label mapping configurations stored in JSON files,
    allowing easy support for different languages (French, Spanish, Danish, etc.).
    """

    def __init__(
        self,
        model_name: Optional[str] = None,
        label_mapping_file: Optional[str] = None,
        language: str = "fr",
    ):
        """
        Initialize the EntityExtractor.

        Args:
            model_name: Path to the NER model. If None, uses config default.
            label_mapping_file: Path to custom label mapping JSON. If None, uses default for language.
            language: Language code (e.g., 'fr', 'es', 'da'). Defaults to 'fr'.
        """
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
            aggregation_strategy="simple",
        )

        self.language = language
        self.label_mapping = self._load_label_mapping(label_mapping_file, language)
        self.categories = self._build_category_lookup()

    def _load_label_mapping(
        self,
        label_mapping_file: Optional[str],
        language: str = "fr",
    ) -> Dict[str, Any]:
        """
        Load label mapping configuration from JSON file.

        Args:
            label_mapping_file: Custom path to mapping file, or None for default
            language: Language code to determine default mapping file

        Returns:
            Dictionary containing the label mapping configuration
        """
        if label_mapping_file is None:
            # Determine default mapping file based on language
            config_dir = Path(__file__).parent / "label_mappings"

            # Use language code as filename (e.g., fr.json, es.json, da.json)
            default_file = config_dir / f"{language}.json"

            if not default_file.exists():
                raise FileNotFoundError(
                    f"No label mapping file found for language '{language}'. "
                    f"Expected file: {default_file}. "
                    f"Please create a mapping file or specify a custom label_mapping_file path."
                )

            label_mapping_file = str(default_file)

        try:
            with open(label_mapping_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except FileNotFoundError:
            raise FileNotFoundError(
                f"Label mapping file not found: {label_mapping_file}. "
                f"Please ensure the configuration file exists."
            )
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in label mapping file: {e}")

    def _build_category_lookup(self) -> Dict[str, str]:
        """
        Build a reverse lookup from labels to categories.

        Returns:
            Dictionary mapping label to category name
        """
        lookup = {}
        categories_config = self.label_mapping.get("categories", {})

        for category_name, category_data in categories_config.items():
            labels = category_data.get("labels", [])
            for label in labels:
                lookup[label.lower()] = category_name

        return lookup

    def _categorize_entity(self, entity_label: str) -> str:
        """
        Categorize an entity based on its label.

        Args:
            entity_label: The entity label from the NER model

        Returns:
            Category name for the entity
        """
        entity_label_lower = entity_label.lower()

        # Remove B- or I- prefix if present (BIO tagging)
        cleaned_label = entity_label_lower.replace("b-", "").replace("i-", "")

        # Look up in category mapping
        for label, category in self.categories.items():
            if label in cleaned_label:
                return category

        # Default category if no match
        return "other"

    def extract_entities(self, text: str) -> Dict[str, List[EntityDetail]]:
        """
        Extract named entities from clinical text with detailed information.

        Args:
            text: Clinical text to analyze

        Returns:
            Dictionary with categorized entities as EntityDetail instances
        """
        ner_results = self.ner_pipeline(text)

        # Initialize categories from config
        categories_config = self.label_mapping.get("categories", {})
        entities: Dict[str, List[EntityDetail]] = {
            category_name: [] for category_name in categories_config.keys()
        }

        for ent in ner_results:
            entity_label = ent["entity_group"]
            category = self._categorize_entity(entity_label)

            entity_detail = EntityDetail(
                text=ent["word"].strip(),
                label=entity_label,
                score=round(ent["score"], 3),
                start=ent["start"],
                end=ent["end"],
            )

            entities[category].append(entity_detail)

        # Remove duplicates while preserving order
        for category in entities:
            seen = set()
            unique_entities = []
            for entity in entities[category]:
                entity_key = (entity.text.lower(), entity.label)
                if entity_key not in seen:
                    seen.add(entity_key)
                    unique_entities.append(entity)
            entities[category] = unique_entities

        return entities

    def get_available_categories(self) -> Dict[str, str]:
        """
        Get available entity categories and their descriptions.

        Returns:
            Dictionary mapping category names to descriptions
        """
        categories_config = self.label_mapping.get("categories", {})
        return {
            name: data.get("description", "")
            for name, data in categories_config.items()
        }

    def get_mapping_info(self) -> Dict[str, Any]:
        """
        Get information about the current label mapping configuration.

        Returns:
            Dictionary with language, dataset, and description info
        """
        return {
            "language": self.label_mapping.get("language", "unknown"),
            "dataset": self.label_mapping.get("dataset", "unknown"),
            "description": self.label_mapping.get("description", ""),
        }
