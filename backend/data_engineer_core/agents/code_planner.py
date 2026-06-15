from data_engineer_core.schemas.plan_schema import SourcePlan
from data_engineer_core.schemas.request_schema import UserDataRequest


class CodePlanner:
    def build_script(self, source_plan: SourcePlan, request: UserDataRequest) -> str:
        candidate = source_plan.selected_candidates[0]
        return f'''import json\nfrom pathlib import Path\n\noutput = {{\n  "status": "success",\n  "data": [\n    {{\n      "date": "2024-Q1",\n      "region": "Vienna",\n      "metric": "{request.metric}",\n      "value": 10.0,\n      "unit": "{request.unit or 'index'}",\n      "source": "{candidate.source_id}",\n      "dataset_id": "{candidate.dataset_id}"\n    }}\n  ],\n  "metadata": {{"limitations": []}}\n}}\nPath('/work/output').mkdir(parents=True, exist_ok=True)\nPath('/work/output/result.json').write_text(json.dumps(output))\n'''
