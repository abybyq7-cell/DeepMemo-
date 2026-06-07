from fastapi import FastAPI
from pydantic import BaseModel
from typing import Optional, Dict, Any
import logging

from ai_tutor import generate_questions_batch, evaluate_answer, generate_explanation
from tools.utils.logging_config import setup_logging

setup_logging()
logger = logging.getLogger(__name__)


class GenerateRequest(BaseModel):
    topic: str
    count: int = 15
    user_context: Optional[Dict[str, Any]] = None


class EvaluateRequest(BaseModel):
    topic: str
    question: str
    user_answer: str
    user_context: Optional[Dict[str, Any]] = None


class ExplainRequest(BaseModel):
    topic: str
    user_context: Optional[Dict[str, Any]] = None


app = FastAPI(title="DeepMemo API")


@app.get("/health")
def health():
    return {"status": "ok", "service": "deepmemo-api"}


@app.post("/generate")
def generate(req: GenerateRequest):
    try:
        questions = generate_questions_batch(req.topic, req.count, req.user_context)
        return {"questions": questions}
    except Exception as e:
        logger.exception("Generate API failed: %s", e)
        return {"error": str(e), "questions": []}


@app.post("/evaluate")
def evaluate(req: EvaluateRequest):
    try:
        result = evaluate_answer(req.topic, req.question, req.user_answer, user_context=req.user_context)
        return result
    except Exception as e:
        logger.exception("Evaluate API failed: %s", e)
        return {"is_correct": False, "content": f"Evaluation error: {str(e)}"}


@app.post("/explain")
def explain(req: ExplainRequest):
    try:
        content = generate_explanation(req.topic, user_context=req.user_context)
        return {"explanation": content}
    except Exception as e:
        logger.exception("Explain API failed: %s", e)
        return {"explanation": f"Error generating explanation: {str(e)}"}

