# Agent Workflow

DeepMemo models learning as a stateful agent workflow instead of a one-shot LLM response.

## Core Loop

```text
1. User selects or enters a topic.
2. The system normalizes and classifies the topic.
3. The learning path orchestrator builds a structured path.
4. The question generator creates practice questions.
5. The user answers a question.
6. The evaluator scores the answer and produces feedback.
7. Mistakes are logged.
8. FSRS schedules future review.
9. The next session reuses memory and mistake history.
```

## Tool/Skill Capabilities

Current custom capabilities:

- `plan_learning_path`
- `generate_questions_batch`
- `evaluate_answer`
- `generate_explanation`
- `log_mistake`
- `get_topic_mistakes`
- `get_review_queue`
- `add_custom_question`

These are implemented as Python functions and modules. They are intentionally separated so they can be converted into standard function-calling tools later.

## Why a Staged Workflow

A single large prompt is hard to debug. DeepMemo uses staged modules so each step has a smaller responsibility:

- Topic normalization handles aliases and vague input.
- Topic classification decides whether the input is a subject or knowledge point.
- Scope inference adds prerequisites and domain context.
- Framework building creates a study structure.
- Orchestration stores traces and memory.

## Failure Handling

The agent includes fallback behavior for:

- malformed model output
- missing framework fields
- model provider errors
- unavailable backend service
- empty cache

The goal is not to hide failures, but to keep the application usable while preserving enough structure for debugging.
