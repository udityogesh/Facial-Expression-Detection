"""Fine-tune the existing emotion model with a validation split and augmentation."""

from pathlib import Path

import cv2
import numpy as np
from keras import Input, Model, Sequential
from keras.callbacks import EarlyStopping, ModelCheckpoint, ReduceLROnPlateau
from keras.layers import (
    InputLayer,
    RandomFlip,
    RandomRotation,
    RandomTranslation,
    RandomZoom,
)
from keras.models import model_from_json
from keras.optimizers import Adam
from keras.utils import to_categorical
from sklearn.metrics import classification_report, f1_score
from sklearn.model_selection import train_test_split
from sklearn.utils.class_weight import compute_class_weight


ROOT = Path(__file__).resolve().parent
LABELS = ["angry", "disgust", "fear", "happy", "neutral", "sad", "surprise"]
OUTPUT_DIR = ROOT / "training_output"
BATCH_SIZE = 128
MAX_EPOCHS = 30


def load_images(split: str) -> tuple[np.ndarray, np.ndarray]:
    images: list[np.ndarray] = []
    labels: list[int] = []
    split_dir = ROOT / "images" / split

    for class_id, emotion in enumerate(LABELS):
        class_dir = split_dir / emotion
        image_paths = sorted(
            path
            for path in class_dir.iterdir()
            if path.suffix.lower() in {".jpg", ".jpeg", ".png"}
        )
        if not image_paths:
            raise FileNotFoundError(f"No images found in {class_dir}")

        for path in image_paths:
            image = cv2.imread(str(path), cv2.IMREAD_GRAYSCALE)
            if image is None:
                raise ValueError(f"Unable to read image: {path}")
            if image.shape != (48, 48):
                image = cv2.resize(image, (48, 48))
            images.append(image)
            labels.append(class_id)

        print(f"{split}/{emotion}: {len(image_paths)} images")

    features = np.asarray(images, dtype=np.float32)[..., np.newaxis] / 255.0
    return features, np.asarray(labels, dtype=np.int64)


def build_finetuning_model() -> Model:
    with (ROOT / "emotiondetector.json").open(encoding="utf-8") as model_file:
        base_model = model_from_json(model_file.read())
    base_model.load_weights(str(ROOT / "emotiondetector.h5"))

    augmentation = Sequential(
        [
            RandomFlip("horizontal"),
            RandomRotation(0.04),
            RandomTranslation(0.05, 0.05),
            RandomZoom(0.05),
        ],
        name="training_augmentation",
    )
    inputs = Input(shape=(48, 48, 1))
    outputs = augmentation(inputs)
    for layer in base_model.layers:
        if not isinstance(layer, InputLayer):
            outputs = layer(outputs)

    model = Model(inputs, outputs, name="fine_tuned_emotion_detector")
    model.compile(
        optimizer=Adam(learning_rate=1e-4),
        loss="categorical_crossentropy",
        metrics=["accuracy"],
    )
    return model


def main() -> None:
    OUTPUT_DIR.mkdir(exist_ok=True)
    train_images, train_labels = load_images("train")

    fit_images, val_images, fit_labels, val_labels = train_test_split(
        train_images,
        train_labels,
        test_size=0.15,
        random_state=42,
        stratify=train_labels,
    )
    del train_images, train_labels

    class_ids = np.arange(len(LABELS))
    weights = compute_class_weight(
        class_weight="balanced",
        classes=class_ids,
        y=fit_labels,
    )
    class_weights = dict(zip(class_ids.tolist(), weights.tolist()))
    print("Training class weights:", class_weights)

    model = build_finetuning_model()

    candidate_weights = OUTPUT_DIR / "emotiondetector_candidate.weights.h5"
    callbacks = [
        ModelCheckpoint(
            str(candidate_weights),
            monitor="val_loss",
            save_best_only=True,
            save_weights_only=True,
            verbose=1,
        ),
        EarlyStopping(
            monitor="val_loss",
            patience=6,
            restore_best_weights=True,
            verbose=1,
        ),
        ReduceLROnPlateau(
            monitor="val_loss",
            patience=3,
            factor=0.5,
            min_lr=1e-6,
            verbose=1,
        ),
    ]

    model.fit(
        fit_images,
        to_categorical(fit_labels, num_classes=len(LABELS)),
        validation_data=(
            val_images,
            to_categorical(val_labels, num_classes=len(LABELS)),
        ),
        batch_size=BATCH_SIZE,
        epochs=MAX_EPOCHS,
        class_weight=class_weights,
        callbacks=callbacks,
    )
    model.load_weights(str(candidate_weights))

    test_images, test_labels = load_images("test")
    probabilities = model.predict(test_images, batch_size=BATCH_SIZE, verbose=1)
    predictions = probabilities.argmax(axis=1)
    accuracy = float(np.mean(predictions == test_labels))
    macro_f1 = float(
        f1_score(test_labels, predictions, labels=class_ids, average="macro")
    )
    report = classification_report(
        test_labels,
        predictions,
        labels=class_ids,
        target_names=LABELS,
        digits=4,
        zero_division=0,
    )

    model_json = OUTPUT_DIR / "emotiondetector_candidate.json"
    with model_json.open("w", encoding="utf-8") as model_file:
        model_file.write(model.to_json())
    model.save_weights(str(candidate_weights))

    report_path = OUTPUT_DIR / "evaluation.txt"
    report_path.write_text(
        f"Test accuracy: {accuracy:.4%}\n"
        f"Test macro F1: {macro_f1:.4f}\n\n"
        f"{report}",
        encoding="utf-8",
    )
    print(f"\nTest accuracy: {accuracy:.2%}")
    print(f"Test macro F1: {macro_f1:.4f}")
    print(report)
    print(f"Candidate model saved to: {OUTPUT_DIR}")
    print("The current application model files were not changed.")


if __name__ == "__main__":
    main()
