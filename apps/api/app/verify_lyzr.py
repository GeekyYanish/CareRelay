from __future__ import annotations

import asyncio
import json

from .orchestration import LyzrSuperFlowOrchestrator, OrchestrationError, make_orchestrator


async def verify() -> int:
    orchestrator = make_orchestrator()
    if not isinstance(orchestrator, LyzrSuperFlowOrchestrator):
        print(json.dumps({"connected": False, "error": "ORCHESTRATOR_PROVIDER must be lyzr"}))
        return 2
    try:
        result = await orchestrator.verify()
    except OrchestrationError as exc:
        print(json.dumps({"connected": False, "error_code": exc.code, "message": str(exc)}))
        return 1
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(verify()))
