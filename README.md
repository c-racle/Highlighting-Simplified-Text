# Highlighting Simplified Text

This repository hosts code, prompts, and scripts for the generation, training, and evaluation in experiments of the paper "Highlighting Simplified Text" for the seminar "Media Accessibility" in HS2025 at UZH. The project explores both pipeline and end-to-end approaches for automatically simplifying text and adding typographic highlights (e.g., bolding keywords, headings) in German, using LoRA adapters on Gemma-2-9B-Instruct.

## Overview

The goal of this project is to explore the automatic generation of highlighted simplified text for accessibility purposes, including target groups such as individuals with cognitive impairments or older adults.

Two approaches were implemented:

### Pipeline Approach

A two-step approach where a simplifier model first generates simplified text, followed by a highlighter model that annotates important elements (bold keywords, headings).

### End-to-End Approach

A single model that simultaneously simplifies text and adds Markdown highlights.

Both approaches are trained on a synthetic dataset created from the SimpleGerman V2.0 corpus using LLM-based preprocessing.

## Dataset

Source: SimpleGerman V2.0 by Battisti et al. (2020).
 (subset extracted for texts with typographic annotations).

### Synthetic dataset

Generated using Leo-mistral-hessian-ai-7b-chat (https://huggingface.co/LeoLM/leo-mistral-hessianai-7b-chat) for highlighted simplified texts.

Contains triplets of (original text, simplified text, highlighted simplified text).

**End-to-end training**: 250 synthetic examples.

**Pipeline training**:

- Simplifier: original → simplified text

- Highlighter: simplified → highlighted simplified text

Note: The synthetic dataset is designed to overcome limitations of the original annotations and small dataset size.

# Models and Training

Base model: Gemma-2-9B-Instruct (https://huggingface.co/google/gemma-2-9b-it)

Parameter-efficient fine-tuning: LoRA adapters

Training setup:
- Learning rate: 1e-4
- Epochs: 3
- Parameters updated: ~4.5M (~0.05% of 9B parameters)

Models included:
- simplifier (pipeline)
- highlighter (pipeline)
- end2end (simplification + highlighting)

Training scripts are provided for both pipeline and end-to-end approaches.

## Evaluation

### Automatic metrics:

SARI: Simplification quality

FKGL: Readability

Markdown F1: Highlighting accuracy (headings + bold spans)

### Preference voting (LLM-based):

Models used: Gemma-2-9B-Instruct, Leo-mistral-hessian-ai-7b-chat, GPT-4.1 (https://platform.openai.com/docs/models/gpt-4)

Categories: Simplification, Highlighting, Combined

Provides relative comparison of model outputs

Note: Human evaluation by the target group is recommended for real-world applications.