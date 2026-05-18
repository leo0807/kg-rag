from __future__ import annotations

import logging

from .detector import detect_mcq_type
from .solvers.definition import DefinitionMCQSolver
from .solvers.general import GeneralMCQSolver
from .solvers.order import OrderMCQSolver
from .types import MCQType

logger = logging.getLogger(__name__)

SOLVER_REGISTRY = {
    MCQType.ORDER: OrderMCQSolver,
    MCQType.DEFINITION: DefinitionMCQSolver,
    MCQType.GENERAL: GeneralMCQSolver,
}


def route_mcq(mcq, driver, llm, reranker=None):
    mcq_type = detect_mcq_type(mcq.stem, mcq.options)
    solver_cls = SOLVER_REGISTRY.get(mcq_type, GeneralMCQSolver)
    if solver_cls is GeneralMCQSolver:
        logger.warning("MCQ题型未识别，使用GENERAL兜底: %s", mcq.stem[:80])
    return solver_cls(driver, llm, reranker)
