# Product Overview

## Product
Senior Training OS is an AI-powered training authorship platform built for the Senior X ERP ecosystem.

Its job is to transform a recorded expert workflow into reusable training assets with minimal manual production effort.

## Core Outcome
The system reduces the effort required to produce software training by converting one mapped workflow into multiple outputs from a shared source of truth.

## Source of Truth
The central artifact of the platform is the **roteiro**.

A roteiro is not just narration text. It is the structured instructional and technical representation of a workflow, used to drive:
- robot execution,
- video generation,
- SCORM simulation,
- PDF documentation,
- future in-app guidance experiences.

Whenever possible, changes in the system should preserve the roteiro as the primary contract between capture, generation, and delivery layers.

## Main Outputs
From one captured workflow, the platform can generate:
1. MP4 training video with narration
2. SCORM interactive simulator
3. PDF playbook / step-by-step documentation
4. Aura DAP support layer for in-product guidance

## Product Vision
This is not just a video generator.

The long-term vision is a training operating system that:
- captures expert knowledge once,
- structures it into reusable instructional intelligence,
- distributes it across multiple training formats,
- and enables future digital adoption experiences inside the ERP itself.

## AI Role in the Product
AI is used to:
- transform raw interaction logs into structured roteiros,
- improve resilience when the UI changes,
- support semantic understanding of actions and screens,
- and power Aura as an in-app guidance and question-answering layer.

## Key Concepts
- **Roteiro**: central structured workflow artifact
- **Biblioteca de Ações**: reusable mapped actions extracted from prior workflows
- **Aura**: AI assistant and DAP intelligence layer
- **Self-Healing**: ability to recover from UI changes using memory and vision-assisted strategies

## Primary Users
The main users are:
- corporate trainers,
- instructional designers,
- training operations teams,
- and future internal stakeholders responsible for scaling training production.

## What Kiro Should Optimize For
When assisting in this codebase, optimize for:
- reliability,
- low regression risk,
- reuse of captured knowledge,
- consistency across outputs,
- maintainability of the pipeline,
- and preservation of the roteiro as the system’s core artifact.

## What Kiro Should Avoid
Avoid suggestions that:
- break compatibility between pipeline stages,
- hardcode fragile assumptions without need,
- duplicate existing utilities or contracts,
- weaken safety around automation,
- or treat the project as a generic CRUD app instead of a workflow automation and training generation platform.