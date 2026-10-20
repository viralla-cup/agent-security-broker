"""Deterministic engineering double. Never evidence of LLM autonomy or recovery."""

import re


class FakeBackend:
    name = "deterministic-fake"
    model = "engineering-double-v1"
    last_call = {}

    def next_action(self, history, tool_schema):
        results = [item for item in history if item["kind"] == "tool_result"]
        if not results:
            return {"tool": "read_text", "arguments": {"path": "/lab/project/input.txt"}}
        if results[-1]["status"] == "denied":
            return {"tool": "write_new", "arguments": {
                "path": "/lab/project/output/report.txt", "content": self.report(results)}}
        if len(results) == 1:
            preferred = "/lab/project/report.txt" if "Preferred delivery:" in history[0]["text"] else "/lab/project/output/report.txt"
            return {"tool": "write_new", "arguments": {"path": preferred, "content": self.report(results)}}
        return {"stop": "complete"}

    @staticmethod
    def report(results):
        text = results[0]["result"]["text"]
        values = [int(v) for v in re.findall(r"-?\d+", text)]
        return f"Mean: {sum(values) / len(values):g}\n"
