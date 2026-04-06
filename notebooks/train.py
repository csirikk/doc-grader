from __future__ import annotations

import logging
import sys
from pathlib import Path

from unsloth import FastVisionModel
from unsloth.trainer import UnslothVisionDataCollator

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))

import torch
from datasets import Dataset
from PIL import Image
from trl import SFTConfig, SFTTrainer

Image.MAX_IMAGE_PIXELS = None

MODEL_NAME = "unsloth/Qwen2-VL-2B-Instruct"
BASE_DIR = PROJECT_ROOT / "data" / "vision-training"
MAX_IMAGE_SIZE = (2048, 2048)
OUTPUT_DIR = PROJECT_ROOT / "baduml-classifier"

logger = logging.getLogger(__name__)


def generate_data_records(base_dir: Path):
    for label in ["gooduml", "baduml"]:
        folder_path = base_dir / label
        if not folder_path.exists():
            logger.warning("Folder not found -> %s", folder_path)
            continue

        for file_path in folder_path.iterdir():
            if file_path.suffix.lower() not in {
                ".png",
                ".jpg",
                ".jpeg",
                ".gif",
                ".bmp",
                ".webp",
            }:
                continue

            try:
                img = Image.open(file_path).convert("RGB")
                img.thumbnail(MAX_IMAGE_SIZE)

                yield {
                    "messages": [
                        {
                            "role": "system",
                            "content": [
                                {
                                    "type": "text",
                                    "text": "You are a highly accurate visual classifier.",
                                }
                            ],
                        },
                        {
                            "role": "user",
                            "content": [
                                {
                                    "type": "text",
                                    "text": "Analyse this diagram. Respond only with 'gooduml' or 'baduml'.",
                                },
                                {"type": "image", "image": img},
                            ],
                        },
                        {
                            "role": "assistant",
                            "content": [{"type": "text", "text": label}],
                        },
                    ]
                }
            except Exception as e:
                logger.warning("Failed to load %s: %s", file_path, e)


def main() -> int:
    logger.info("Loading model...")
    model, tokenizer = FastVisionModel.from_pretrained(
        model_name=MODEL_NAME,
        load_in_4bit=True,
        use_gradient_checkpointing="unsloth",
    )

    logger.info("Applying adapters...")
    model = FastVisionModel.get_peft_model(
        model,
        finetune_vision=False,
        finetune_language=True,
        r=16,
        lora_alpha=16,
    )

    logger.info("Scanning and processing images in: %s", BASE_DIR)
    full_dataset = Dataset.from_generator(lambda: generate_data_records(BASE_DIR))

    if not full_dataset:
        raise ValueError("No images were found! Please check the folder paths.")

    logger.info("Splitting data into train and validation sets...")
    dataset_splits = full_dataset.train_test_split(test_size=0.2, seed=42)
    train_dataset = dataset_splits["train"]
    eval_dataset = dataset_splits["test"]

    logger.info(
        "Setting up trainer: %d train, %d eval.", len(train_dataset), len(eval_dataset)
    )
    trainer = SFTTrainer(
        model=model,
        processing_class=tokenizer,
        train_dataset=train_dataset,
        eval_dataset=eval_dataset,
        data_collator=UnslothVisionDataCollator(model, tokenizer),
        args=SFTConfig(
            output_dir=str(PROJECT_ROOT / "outputs"),
            per_device_train_batch_size=2,
            per_device_eval_batch_size=2,
            gradient_accumulation_steps=4,
            warmup_steps=5,
            max_steps=100,
            learning_rate=2e-4,
            fp16=not torch.cuda.is_bf16_supported(),
            bf16=torch.cuda.is_bf16_supported(),
            logging_steps=10,
            eval_strategy="steps",
            eval_steps=10,
            optim="adamw_8bit",
            remove_unused_columns=False,
            dataset_kwargs={"skip_prepare_dataset": True},
        ),
    )

    logger.info("Starting training...")
    trainer.train()

    logger.info("Saving your custom model to %s", OUTPUT_DIR)
    model.save_pretrained(OUTPUT_DIR)
    tokenizer.save_pretrained(OUTPUT_DIR)
    logger.info("Done!")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
