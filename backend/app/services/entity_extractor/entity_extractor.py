import json
import logging
import re
import unicodedata
from pathlib import Path
from typing import Any, Dict, List, Optional

import anyio
import torch
from fastapi.concurrency import run_in_threadpool
from transformers import pipeline

from app.interfaces.service_interfaces import EntityExtractionServiceInterface
from app.schemas.extraction import EntityDetail

logger = logging.getLogger(__name__)

# Labels are compared part by part when they do not match whole. Splitting on
# everything that is not a letter or a digit handles "maladies cardiovasculaires",
# "maladies_cardiovasculaires" and "MALADIES-CARDIOVASCULAIRES" alike.
LABEL_SEPARATORS = re.compile(r"[\W_]+")

# Inference is pinned to the CPU rather than left to whatever transformers finds.
# The runtime installs the CPU build of torch, so this is what would happen
# anyway - saying it means a machine that happens to carry an accelerator does
# not silently start copying clinical text onto it.
INFERENCE_DEVICE = "cpu"


def configure_inference_threads(inference_threads: int) -> None:
    """
    Cap the threads torch spends on one inference.

    Torch reads the host's core count once, at first use, and a container with a
    CPU quota below that count spends the difference on contention. Zero leaves
    the default alone, which is the right answer on a machine that is only
    running this.
    """
    if inference_threads > 0:
        torch.set_num_threads(inference_threads)


class EntityExtractor(EntityExtractionServiceInterface):
    """
    Enhanced EntityExtractor supporting multiple language clinical NER models.
    Supports comprehensive medical entity extraction with configurable label mappings.

    The extractor uses language-specific label mapping configurations stored in JSON files,
    allowing easy support for different languages (French, Spanish, Danish, etc.).
    """

    def __init__(
        self,
        model_name: str,
        label_mapping_file: Optional[str] = None,
        language: str = "fr",
        inference_threads: int = 0,
        max_concurrent_inferences: int = 1,
    ):
        """
        Initialize the EntityExtractor.

        The model name is passed in rather than read from the application
        configuration: a service that reaches back into the wiring that builds
        it makes the two modules import each other.

        Args:
            model_name: Path to the NER model.
            label_mapping_file: Path to custom label mapping JSON. If None, uses default for language.
            language: Language code (e.g., 'fr', 'es', 'da'). Defaults to 'fr'.
            inference_threads: Threads torch may use per inference. 0 keeps its default.
            max_concurrent_inferences: How many documents may be in the model at once.
        """
        configure_inference_threads(inference_threads)

        self.ner_pipeline = pipeline(
            "ner",
            model=model_name,
            aggregation_strategy="max",
            device=INFERENCE_DEVICE,
        )

        # Inference runs in a worker thread, so without this every request in
        # flight would hold its own copy of the activations. One at a time is
        # what keeps the model's peak memory a function of the largest document
        # rather than of how many arrived together.
        #
        # anyio's semaphore rather than asyncio's: the extractor is a
        # process-wide singleton, and asyncio's binds itself to whichever loop
        # first awaits it, which turns a second loop in the same process into a
        # RuntimeError.
        self.inference_slots = anyio.Semaphore(max_concurrent_inferences)

        self.language = language
        self.label_mapping = self.load_label_mapping(label_mapping_file, language)
        self.categories = self.build_category_lookup()
        self.report_unmapped_model_labels()

    def load_label_mapping(
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

    @staticmethod
    def normalize_label(label: str) -> str:
        """
        Fold a label to the form the lookup is keyed on.

        Case and accents are dropped so a mapping written `duree` still answers
        a model that emits `durée`. An unmatched label costs an entity its
        category, and for `patient_info` it costs an identifier its mask.
        """
        decomposed = unicodedata.normalize("NFKD", label.strip().lower())
        return "".join(char for char in decomposed if not unicodedata.combining(char))

    def build_category_lookup(self) -> Dict[str, str]:
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
                lookup[self.normalize_label(label)] = category_name

        return lookup

    def model_labels(self) -> List[str]:
        """
        The entity labels the loaded model can emit, when it declares them.

        A model that does not expose `id2label` - or a test double standing in
        for one - answers with nothing rather than raising.
        """
        config = getattr(getattr(self.ner_pipeline, "model", None), "config", None)
        id2label = getattr(config, "id2label", None)
        if not isinstance(id2label, dict):
            return []

        return [str(label) for label in id2label.values()]

    def unmapped_model_labels(self) -> List[str]:
        """Model labels this mapping sends to `other`, in sorted order."""
        return sorted(
            {
                label
                for label in self.model_labels()
                if self.strip_bio_prefix(label) != "o"
                and self.categorize_entity(label) == "other"
                and self.categories.get(self.strip_bio_prefix(label)) != "other"
            }
        )

    def report_unmapped_model_labels(self) -> None:
        """
        Say so when the model speaks labels the mapping does not know.

        A label vocabulary is model metadata, never patient data, so it is safe
        to log - and a silent mismatch is how a whole category stops being
        recognised, masking included.
        """
        unmapped = self.unmapped_model_labels()
        if unmapped:
            logger.warning(
                "The %s label mapping does not categorise %d model label(s): %s",
                self.language,
                len(unmapped),
                ", ".join(unmapped),
            )

    @classmethod
    def strip_bio_prefix(cls, entity_label: str) -> str:
        """Drop a leading BIO marker, which says where a span starts, not what it is."""
        label = cls.normalize_label(entity_label)
        if label.startswith(("b-", "i-")):
            return label[2:]
        return label

    def categorize_entity(self, entity_label: str) -> str:
        """
        Categorize an entity based on its label.

        Args:
            entity_label: The entity label from the NER model

        Returns:
            Category name for the entity
        """
        label = self.strip_bio_prefix(entity_label)

        category = self.categories.get(label)
        if category is not None:
            return category

        # A compound label is matched part by part - "maladies cardiovasculaires"
        # is answered by "cardiovasculaires" - but never by raw containment,
        # which made every label holding "dose" a dose and, worse, every label
        # holding "age" patient information.
        for part in LABEL_SEPARATORS.split(label):
            category = self.categories.get(part)
            if category is not None:
                return category

        return "other"

    async def extract_entities(self, text: str) -> Dict[str, List[EntityDetail]]:
        """
        Extract named entities from clinical text with detailed information.

        The model is synchronous and CPU-bound: a long document held the event
        loop for the whole of its inference, so every other request - including
        the health check - waited behind it. The work is handed to a worker
        thread instead, and only as many at a time as the deployment allows.

        Args:
            text: Clinical text to analyze

        Returns:
            Dictionary with categorized entities as EntityDetail instances
        """
        async with self.inference_slots:
            return await run_in_threadpool(self.run_inference, text)

    def run_inference(self, text: str) -> Dict[str, List[EntityDetail]]:
        """
        Run the model over one document and categorise what it emits.

        This is the blocking half of `extract_entities`, kept separate so it can
        be called on a worker thread. Nothing here touches the event loop.

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

        # Merge consecutive entities with the same label (for subword tokens only)
        merged_results: list[dict[str, Any]] = []
        for ent in ner_results:
            if (
                merged_results
                and merged_results[-1]["entity_group"] == ent["entity_group"]
                and merged_results[-1]["end"] == ent["start"]
            ):
                # Only merge if tokens are directly adjacent (no space between)
                prev = merged_results[-1]
                merged_word = text[prev["start"] : ent["end"]]
                merged_results[-1] = {
                    "entity_group": ent["entity_group"],
                    "word": merged_word,
                    "score": max(prev["score"], ent["score"]),  # Use max score
                    "start": prev["start"],
                    "end": ent["end"],
                }
            else:
                merged_results.append(ent)

        for ent in merged_results:
            entity_label = ent["entity_group"]
            category = self.categorize_entity(entity_label)

            # Use actual text from source instead of tokenizer's word (which may strip spaces)
            actual_text = text[ent["start"] : ent["end"]]

            entity_detail = EntityDetail(
                text=actual_text.strip(),
                label=entity_label,
                score=round(ent["score"], 3),
                start=ent["start"],
                end=ent["end"],
            )

            # A mapping need not declare the fallback category, and the model
            # decides what it emits, so the bucket is created on demand.
            entities.setdefault(category, []).append(entity_detail)

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
