# advanced_train.py
"""Advanced training script for the AI Student Support Chatbot.

Improvements over the original ``train.py``:
- Train/validation/test split (stratified)
- TF‑IDF vectorizer with n‑grams up to trigrams, max_features=10k, min_df=2, max_df=0.95
- Deep neural network with 3 hidden layers, batch‑norm, dropout and Xavier init (see ``model.py``)
- Batch training via ``DataLoader``
- Adam optimizer with learning‑rate scheduler (ReduceLROnPlateau)
- Early stopping (patience=10) based on validation loss
- Comprehensive evaluation metrics (accuracy, precision, recall, F1, confusion matrix, classification report) on the held‑out test set
- Model, vectorizer and label encoder persistence

Run with ``python advanced_train.py``. The script logs progress to console and writes a ``metrics.json`` file in the ``models`` directory.
"""

import logging
import os
from pathlib import Path

import torch
import torch.nn as nn
import torch.nn.functional as F
import torch.optim as optim
from torch.utils.data import DataLoader, TensorDataset

from sklearn.model_selection import train_test_split
from sklearn.metrics import (
    accuracy_score,
    precision_recall_fscore_support,
    classification_report,
    confusion_matrix,
)
from sklearn.utils.class_weight import compute_class_weight
import numpy as np

from utils import (
    load_dataset,
    load_model,
    preprocess_text,
    fit_vectorizer,
    fit_label_encoder,
    get_device,
    save_model,
    save_pickle,
    MODEL_PATH,
    VECTORIZER_PATH,
    LABEL_ENCODER_PATH,
    DATA_PATH,
)

from model import ChatbotModel

# ---------------------------------------------------------------------------
# Logging configuration
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)s:%(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


def main() -> None:
    logger.info("Loading dataset from %s", DATA_PATH)
    df = load_dataset()

    # ---------------------------------------------------------------------
    # Pre‑process questions
    # ---------------------------------------------------------------------
    logger.info("Pre‑processing %d questions", len(df))
    df["processed"] = df["question"].apply(preprocess_text)

    # ---------------------------------------------------------------------
    # Train / validation / test split (stratified)
    # ---------------------------------------------------------------------
    X = df["processed"]
    y = df["category"]
    # Helper: attempt a stratified split but handle classes with too few
    # samples (which raise ValueError in sklearn). Strategy:
    # 1. Try a normal stratified split.
    # 2. If it fails, remove classes with <2 examples and retry.
    # 3. If it still fails, fall back to a non‑stratified split with a
    #    warning (shuffle preserved).
    def safe_train_test_split(X_series, y_series, test_size, random_state=42):
        try:
            return train_test_split(X_series, y_series, test_size=test_size, random_state=random_state, stratify=y_series)
        except ValueError as e:
            logger.warning("Stratified split failed: %s", e)
            counts = y_series.value_counts()
            rare = counts[counts < 2].index.tolist()
            if rare:
                removed = y_series.isin(rare).sum()
                logger.info(
                    "Removing %d samples from %d rare classes: %s",
                    int(removed),
                    len(rare),
                    rare,
                )
                mask = ~y_series.isin(rare)
                X_clean = X_series[mask]
                y_clean = y_series[mask]
                if len(y_clean) < 2:
                    logger.error("Not enough data after removing rare classes — falling back to non-stratified split.")
                    return train_test_split(X_series, y_series, test_size=test_size, random_state=random_state)
                try:
                    return train_test_split(X_clean, y_clean, test_size=test_size, random_state=random_state, stratify=y_clean)
                except ValueError:
                    logger.warning("Stratify still fails after removing rare classes — using non-stratified split.")
                    return train_test_split(X_series, y_series, test_size=test_size, random_state=random_state)
            else:
                logger.warning("No classes with <2 samples found; using non-stratified split.")
                return train_test_split(X_series, y_series, test_size=test_size, random_state=random_state)

    # First split off a test set (20%)
    X_temp, X_test, y_temp, y_test = safe_train_test_split(X, y, test_size=0.2, random_state=42)
    # Split the remaining into train (70%) and validation (10%)
    X_train, X_val, y_train, y_val = safe_train_test_split(
        X_temp, y_temp, test_size=0.125, random_state=42
    )

    logger.info(
        "Dataset split: %d train / %d val / %d test",
        len(X_train),
        len(X_val),
        len(X_test),
    )

    # ---------------------------------------------------------------------
    # TF‑IDF vectorizer (fit on training data only)
    # ---------------------------------------------------------------------
    logger.info("Fitting TF‑IDF vectorizer (ngram_range=(1,3), max_features=10000)")
    vectorizer = fit_vectorizer(
        X_train,
        ngram_range=(1, 3),
        max_features=10000,
        min_df=2,
        max_df=0.95,
    )

    # Transform all splits
    X_train_vec = vectorizer.transform(X_train).toarray()
    X_val_vec = vectorizer.transform(X_val).toarray()
    X_test_vec = vectorizer.transform(X_test).toarray()

    # Encode labels
    logger.info("Fitting label encoder")
    label_encoder = fit_label_encoder(y_train)
    y_train_enc = label_encoder.transform(y_train)
    y_val_enc = label_encoder.transform(y_val)
    y_test_enc = label_encoder.transform(y_test)

    # ---------------------------------------------------------------------
    # PyTorch tensors and DataLoader (batch training)
    # ---------------------------------------------------------------------
    device = get_device()
    logger.info("Using device: %s", device)

    train_dataset = TensorDataset(
        torch.tensor(X_train_vec, dtype=torch.float32),
        torch.tensor(y_train_enc, dtype=torch.long),
    )
    train_loader = DataLoader(train_dataset, batch_size=64, shuffle=True)

    # Validation tensors (no batching needed for metric calculation)
    X_val_t = torch.tensor(X_val_vec, dtype=torch.float32, device=device)
    y_val_t = torch.tensor(y_val_enc, dtype=torch.long, device=device)

    # ---------------------------------------------------------------------
    # Model initialisation
    # ---------------------------------------------------------------------
    input_dim = X_train_vec.shape[1]
    num_classes = len(label_encoder.classes_)
    model = ChatbotModel(input_dim=input_dim, num_classes=num_classes, dropout=0.2).to(device)

    # Compute class weights from the training labels to help with imbalance
    try:
        classes = np.unique(y_train_enc)
        cw = compute_class_weight(class_weight="balanced", classes=classes, y=y_train_enc)
        class_weights = torch.tensor(cw, dtype=torch.float32, device=device)
        criterion = nn.CrossEntropyLoss(weight=class_weights)
        logger.info("Using class weights for loss: %s", dict(zip(classes.tolist(), cw.tolist())))
    except Exception as e:
        logger.warning("Could not compute class weights (%s); falling back to unweighted loss", e)
        criterion = nn.CrossEntropyLoss()
    optimizer = optim.Adam(model.parameters(), lr=1e-3)
    scheduler = optim.lr_scheduler.ReduceLROnPlateau(
        optimizer, mode="min", factor=0.5, patience=5, verbose=True
    )

    # ---------------------------------------------------------------------
    # Training loop with early stopping
    # ---------------------------------------------------------------------
    epochs = 150
    early_stop_patience = 10
    best_val_loss = float("inf")
    epochs_no_improve = 0

    logger.info("Starting training for up to %d epochs", epochs)
    for epoch in range(1, epochs + 1):
        model.train()
        epoch_loss = 0.0
        for batch_X, batch_y in train_loader:
            batch_X = batch_X.to(device)
            batch_y = batch_y.to(device)
            optimizer.zero_grad()
            outputs = model(batch_X)
            loss = criterion(outputs, batch_y)
            loss.backward()
            optimizer.step()
            epoch_loss += loss.item() * batch_X.size(0)

        avg_train_loss = epoch_loss / len(train_loader.dataset)

        # -----------------------------------------------------------------
        # Validation evaluation (loss & metrics)
        # -----------------------------------------------------------------
        model.eval()
        with torch.no_grad():
            val_outputs = model(X_val_t)
            val_loss = criterion(val_outputs, y_val_t).item()
            val_preds = torch.argmax(val_outputs, dim=1).cpu().numpy()
            val_true = y_val_t.cpu().numpy()
            val_acc = accuracy_score(val_true, val_preds)

        scheduler.step(val_loss)

        logger.info(
            "Epoch %03d | Train Loss: %.4f | Val Loss: %.4f | Val Acc: %.2f%%",
            epoch,
            avg_train_loss,
            val_loss,
            val_acc * 100,
        )

        # Early stopping check
        if val_loss < best_val_loss:
            best_val_loss = val_loss
            epochs_no_improve = 0
            # Save the best model checkpoint
            save_model(model)
        else:
            epochs_no_improve += 1
            if epochs_no_improve >= early_stop_patience:
                logger.info(
                    "Early stopping triggered after %d epochs without improvement.",
                    early_stop_patience,
                )
                break

    # ---------------------------------------------------------------------
    # Final evaluation on the held‑out test set
    # ---------------------------------------------------------------------
    logger.info("Loading best model for test evaluation")
    from model import ChatbotModel as ModelClass
    # `load_model` requires the input dimensionality and number of classes
    # (these were computed earlier as `input_dim` and `num_classes`). Pass
    # them through so the model can be instantiated before loading weights.
    best_model = load_model(
        ModelClass,
        input_dim=input_dim,
        num_classes=num_classes,
        path=MODEL_PATH,
        device=device,
    )
    best_model.eval()
    X_test_t = torch.tensor(X_test_vec, dtype=torch.float32, device=device)
    y_test_t = torch.tensor(y_test_enc, dtype=torch.long, device=device)
    with torch.no_grad():
        test_outputs = best_model(X_test_t)
        test_preds = torch.argmax(test_outputs, dim=1).cpu().numpy()
    test_true = y_test_t.cpu().numpy()

    test_accuracy = accuracy_score(test_true, test_preds)
    precision, recall, f1, _ = precision_recall_fscore_support(
        test_true, test_preds, average="weighted", zero_division=0
    )
    # Only include labels that actually appear in the true or predicted arrays.
    present_labels = np.unique(np.concatenate([test_true, test_preds]))
    target_names = label_encoder.inverse_transform(present_labels)
    cls_report = classification_report(
        test_true, test_preds, labels=present_labels, target_names=target_names, zero_division=0
    )
    conf_mat = confusion_matrix(test_true, test_preds, labels=present_labels)

    logger.info("Test Accuracy: %.2f%%", test_accuracy * 100)
    logger.info("Test Precision: %.4f | Recall: %.4f | F1: %.4f", precision, recall, f1)
    logger.info("Classification Report:\n%s", cls_report)
    logger.info("Confusion Matrix:\n%s", conf_mat)

    # Save metrics to JSON for downstream consumption
    metrics = {
        "test_accuracy": test_accuracy,
        "test_precision": precision,
        "test_recall": recall,
        "test_f1": f1,
        "classification_report": cls_report,
        "confusion_matrix": conf_mat.tolist(),
    }
    metrics_path = Path(os.path.dirname(MODEL_PATH)) / "metrics.json"
    save_pickle(metrics, str(metrics_path))
    logger.info("Metrics saved to %s", metrics_path)


if __name__ == "__main__":
    main()
