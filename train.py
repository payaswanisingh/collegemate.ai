"""Training script for the AI Student Support Chatbot.

Implements a production‑grade training pipeline:
- Stratified train/validation/test split (70%/15%/15%).
- TF‑IDF vectorisation and label encoding.
- Deep PyTorch model (ChatbotModel) with batch norm, dropout, Xavier init.
- Mini‑batch training via DataLoader.
- Adam optimiser with ReduceLROnPlateau learning‑rate scheduler.
- Early stopping (patience=5) based on validation loss.
- Comprehensive evaluation metrics (accuracy, precision, recall, f1, confusion matrix, classification report).
- Model checkpointing of the best validation model.
- Logging of progress to console and a training.log file.
"""

import logging
import os
from pathlib import Path
from typing import Tuple, Dict, Any

import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import DataLoader, TensorDataset

from sklearn.model_selection import train_test_split
from sklearn.metrics import (
    accuracy_score,
    precision_recall_fscore_support,
    confusion_matrix,
    classification_report,
)

from utils import (
    load_dataset,
    preprocess_text,
    fit_vectorizer,
    fit_label_encoder,
    get_device,
    save_model,
    DATA_PATH,
    MODEL_PATH,
)
from model import ChatbotModel

# ---------------------------------------------------------------------------
# Logging configuration
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)s:%(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[logging.StreamHandler(), logging.FileHandler("training.log")],
)
logger = logging.getLogger(__name__)


def split_dataset(df) -> Tuple[TensorDataset, TensorDataset, TensorDataset, int, int, Any, Any]:
    """Prepare data and return training, validation, test DataLoaders.

    Returns:
        train_loader, val_loader, test_loader, input_dim, num_classes, vectorizer, label_encoder
    """
    # Preprocess text
    df["processed"] = df["question"].apply(preprocess_text)

    # Stratified split into train+val and test (15% test)
    train_val_df, test_df = train_test_split(
        df,
        test_size=0.15,
        random_state=42,
        stratify=df["category"],
    )
    # Further split train_val into train and validation (approx 15% of original = 0.176 of train_val)
    train_df, val_df = train_test_split(
        train_val_df,
        test_size=0.176,
        random_state=42,
        stratify=train_val_df["category"],
    )

    # Fit TF‑IDF vectoriser on the full training set
    vectorizer = fit_vectorizer(train_df["processed"])
    label_encoder = fit_label_encoder(train_df["category"])

    # Helper to convert a DataFrame to a TensorDataset
    def df_to_dataset(sub_df):
        X = vectorizer.transform(sub_df["processed"]).toarray()
        y = label_encoder.transform(sub_df["category"])
        X_tensor = torch.tensor(X, dtype=torch.float32)
        y_tensor = torch.tensor(y, dtype=torch.long)
        return TensorDataset(X_tensor, y_tensor)

    train_dataset = df_to_dataset(train_df)
    val_dataset = df_to_dataset(val_df)
    test_dataset = df_to_dataset(test_df)

    input_dim = train_dataset.tensors[0].shape[1]
    num_classes = len(label_encoder.classes_)

    return (
        train_dataset,
        val_dataset,
        test_dataset,
        input_dim,
        num_classes,
        vectorizer,
        label_encoder,
    )


def evaluate(model: nn.Module, dataloader: DataLoader, device: torch.device) -> Tuple[float, Dict[str, Any]]:
    """Run inference on a dataloader and compute metrics.

    Returns:
        loss (placeholder 0.0 as loss is not computed here), metrics dict.
    """
    model.eval()
    all_preds = []
    all_labels = []
    with torch.no_grad():
        for X_batch, y_batch in dataloader:
            X_batch = X_batch.to(device)
            y_batch = y_batch.to(device)
            logits = model(X_batch)
            preds = torch.argmax(logits, dim=1)
            all_preds.extend(preds.cpu().numpy())
            all_labels.extend(y_batch.cpu().numpy())
    accuracy = accuracy_score(all_labels, all_preds)
    precision, recall, f1, _ = precision_recall_fscore_support(
        all_labels, all_preds, average="weighted", zero_division=0
    )
    cm = confusion_matrix(all_labels, all_preds)
    report = classification_report(all_labels, all_preds, output_dict=True, zero_division=0)
    metrics = {
        "accuracy": accuracy,
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "confusion_matrix": cm.tolist(),
        "classification_report": report,
    }
    return 0.0, metrics


def train_model(
    train_dataset: TensorDataset,
    val_dataset: TensorDataset,
    input_dim: int,
    num_classes: int,
    device: torch.device,
    epochs: int = 100,
    batch_size: int = 32,
    patience: int = 5,
) -> Tuple[nn.Module, Dict[str, Any]]:
    """Train the model with early stopping and LR scheduler.

    Returns the best model (state dict loaded) and a dict containing training history.
    """
    train_loader = DataLoader(train_dataset, batch_size=batch_size, shuffle=True)
    val_loader = DataLoader(val_dataset, batch_size=batch_size, shuffle=False)

    model = ChatbotModel(input_dim=input_dim, num_classes=num_classes).to(device)
    criterion = nn.CrossEntropyLoss()
    optimizer = optim.Adam(model.parameters(), lr=1e-3)
    scheduler = optim.lr_scheduler.ReduceLROnPlateau(
        optimizer, mode="min", factor=0.5, patience=2, verbose=True
    )

    best_val_loss = float("inf")
    epochs_no_improve = 0
    best_state_dict = None
    history = {"epoch": [], "train_loss": [], "val_loss": []}

    for epoch in range(1, epochs + 1):
        model.train()
        epoch_loss = 0.0
        for X_batch, y_batch in train_loader:
            X_batch = X_batch.to(device)
            y_batch = y_batch.to(device)
            optimizer.zero_grad()
            logits = model(X_batch)
            loss = criterion(logits, y_batch)
            loss.backward()
            optimizer.step()
            epoch_loss += loss.item() * X_batch.size(0)
        avg_train_loss = epoch_loss / len(train_loader.dataset)

        # Validation loss
        model.eval()
        val_loss = 0.0
        with torch.no_grad():
            for X_batch, y_batch in val_loader:
                X_batch = X_batch.to(device)
                y_batch = y_batch.to(device)
                logits = model(X_batch)
                loss = criterion(logits, y_batch)
                val_loss += loss.item() * X_batch.size(0)
        avg_val_loss = val_loss / len(val_loader.dataset)

        # Scheduler step
        scheduler.step(avg_val_loss)

        logger.info(
            "Epoch %d/%d – Train loss: %.4f – Val loss: %.4f",
            epoch,
            epochs,
            avg_train_loss,
            avg_val_loss,
        )

        # Early stopping check
        if avg_val_loss < best_val_loss:
            best_val_loss = avg_val_loss
            best_state_dict = model.state_dict()
            epochs_no_improve = 0
            # Save checkpoint immediately
            save_model(model)
        else:
            epochs_no_improve += 1
            if epochs_no_improve >= patience:
                logger.info("Early stopping triggered after %d epochs", epoch)
                break

        history["epoch"].append(epoch)
        history["train_loss"].append(avg_train_loss)
        history["val_loss"].append(avg_val_loss)

    # Load best weights before returning
    if best_state_dict is not None:
        model.load_state_dict(best_state_dict)
    return model, history


def main() -> None:
    logger.info("Loading dataset from %s", DATA_PATH)
    df = load_dataset()
    device = get_device()
    logger.info("Using device: %s", device)

    (
        train_dataset,
        val_dataset,
        test_dataset,
        input_dim,
        num_classes,
        vectorizer,
        label_encoder,
    ) = split_dataset(df)

    model, history = train_model(
        train_dataset=train_dataset,
        val_dataset=val_dataset,
        input_dim=input_dim,
        num_classes=num_classes,
        device=device,
        epochs=150,
        batch_size=32,
        patience=5,
    )

    # Evaluate on test set using the best model
    test_loader = DataLoader(test_dataset, batch_size=32, shuffle=False)
    _, test_metrics = evaluate(model, test_loader, device)
    logger.info("Test set metrics: %s", test_metrics)

    # Persist the final model (already saved during early stopping)
    logger.info("Training complete. Model saved to %s", MODEL_PATH)

if __name__ == "__main__":
    main()