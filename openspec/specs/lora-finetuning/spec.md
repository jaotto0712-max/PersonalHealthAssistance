# lora-finetuning Specification

## Purpose
LoRA fine-tuning of Phi-3-mini on prepared MedQuAD data on a cloud or HPC GPU, with recorded configuration and a model card.

## Requirements
### Requirement: LoRA training with PEFT
The training notebook SHALL fine-tune `microsoft/Phi-3-mini-4k-instruct` using the `peft` library with LoRA adapters (QLoRA 4-bit base) on the prepared training split, computing loss only on assistant tokens.

#### Scenario: Adapter produced
- **WHEN** training completes
- **THEN** a LoRA adapter directory with `adapter_config.json` and adapter weights is saved

### Requirement: Configurable and recorded hyperparameters
All hyperparameters (rank, alpha, dropout, target modules, learning rate, epochs, batch size, max sequence length, seed) SHALL be defined in one config cell and saved with the adapter.

#### Scenario: Config saved with adapter
- **WHEN** the adapter is saved
- **THEN** a `training_config.json` containing every hyperparameter is saved next to it

### Requirement: Validation monitoring
The notebook SHALL evaluate validation loss at regular intervals and SHALL keep the checkpoint with the lowest validation loss.

#### Scenario: Best checkpoint retained
- **WHEN** validation loss rises after an earlier minimum
- **THEN** the saved final adapter corresponds to the checkpoint with the lowest validation loss

### Requirement: Resumable training
The notebook SHALL save checkpoints to persistent storage and SHALL be able to resume from the latest checkpoint after a session interruption.

#### Scenario: Resume after disconnect
- **WHEN** the GPU session (Colab or HiPerGator) restarts and the notebook is re-run with resume enabled
- **THEN** training continues from the latest saved step instead of step 0

### Requirement: Model card
The training workflow SHALL produce a model card documenting base model, dataset and attribution, splits, hyperparameters, final losses, intended use, and limitations including that the model does not provide medical advice.

#### Scenario: Model card present
- **WHEN** the training workflow is complete
- **THEN** `training/model_card.md` exists and includes a limitations section

