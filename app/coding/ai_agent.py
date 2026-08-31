"""AI coding agent — uses configured AI provider for code assistance tasks."""

from __future__ import annotations

from typing import Any

from loguru import logger

from ..core.errors import ProviderError
from ..providers import manager
from ..providers.base import ChatMessage
from ..tools.base import BaseTool, ToolResult, ToolSpec, RiskLevel


async def _ai_chat(prompt: str, system: str = "", model_override: str = "") -> str:
    """Send a prompt to the configured AI provider and return the response."""
    provider = manager.get_default_provider()
    if provider is None:
        raise ProviderError(
            "No AI provider configured.",
            details="Configure a provider in Settings before using AI coding features.",
        )

    messages = []
    if system:
        messages.append(ChatMessage(role="system", content=system))
    messages.append(ChatMessage(role="user", content=prompt))

    content = ""
    async for resp in provider.chat(messages):
        if not resp.streaming:
            content = resp.content
            break

    if not content:
        raise ProviderError("AI provider returned empty response.")
    return content


class ExplainCodeTool(BaseTool):
    """Explain code using AI."""

    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="coding.agent.explain",
            description="Explain what a piece of code does.",
            category="coding",
            risk_level=RiskLevel.SAFE,
            requires_confirmation=False,
            timeout=60.0,
            input_schema={
                "type": "object",
                "properties": {
                    "code": {"type": "string", "description": "Code to explain"},
                    "language": {"type": "string", "description": "Programming language"},
                    "context": {"type": "string", "description": "Additional context"},
                },
                "required": ["code"],
            },
        )

    async def validate_inputs(self, inputs: dict[str, Any]) -> str | None:
        if not inputs.get("code"):
            return "code is required"
        return None

    async def execute(self, inputs: dict[str, Any]) -> ToolResult:
        code = inputs["code"]
        language = inputs.get("language", "auto-detect")
        context = inputs.get("context", "")

        system = "You are an expert software developer. Explain code clearly and concisely. Focus on what it does, how it works, and any important patterns or potential issues."
        prompt = f"Explain the following {language} code:\n\n```\n{code}\n```"
        if context:
            prompt += f"\n\nContext: {context}"

        try:
            explanation = await _ai_chat(prompt, system=system)
            self.log_action("explain_code", details=f"language={language} code_len={len(code)}")
            return ToolResult(success=True, data={"explanation": explanation})
        except Exception as e:
            return ToolResult(success=False, error=str(e))


class GenerateCodeTool(BaseTool):
    """Generate code using AI."""

    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="coding.agent.generate",
            description="Generate code from a description.",
            category="coding",
            risk_level=RiskLevel.LOW,
            requires_confirmation=False,
            timeout=60.0,
            input_schema={
                "type": "object",
                "properties": {
                    "description": {"type": "string", "description": "What to generate"},
                    "language": {"type": "string", "description": "Target language"},
                    "existing_code": {"type": "string", "description": "Existing code to build on"},
                    "style": {"type": "string", "description": "Code style instructions"},
                },
                "required": ["description"],
            },
        )

    async def validate_inputs(self, inputs: dict[str, Any]) -> str | None:
        if not inputs.get("description"):
            return "description is required"
        return None

    async def execute(self, inputs: dict[str, Any]) -> ToolResult:
        description = inputs["description"]
        language = inputs.get("language", "python")
        existing = inputs.get("existing_code", "")
        style = inputs.get("style", "")

        system = "You are an expert software developer. Generate clean, well-structured code. Return ONLY the code, no markdown fences. Include brief comments for non-obvious logic."
        prompt = f"Generate {language} code for: {description}"
        if existing:
            prompt += f"\n\nExisting code to build on:\n```\n{existing}\n```"
        if style:
            prompt += f"\n\nStyle instructions: {style}"

        try:
            code = await _ai_chat(prompt, system=system)
            # Strip markdown fences if present
            if code.startswith("```"):
                lines = code.split("\n")
                code = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])

            self.log_action("generate_code", details=f"language={language} desc={description[:60]}")
            return ToolResult(success=True, data={"code": code.strip(), "language": language})
        except Exception as e:
            return ToolResult(success=False, error=str(e))


class RefactorCodeTool(BaseTool):
    """Refactor code using AI."""

    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="coding.agent.refactor",
            description="Refactor code with specific improvements.",
            category="coding",
            risk_level=RiskLevel.LOW,
            requires_confirmation=True,
            timeout=60.0,
            input_schema={
                "type": "object",
                "properties": {
                    "code": {"type": "string", "description": "Code to refactor"},
                    "language": {"type": "string", "description": "Programming language"},
                    "instructions": {"type": "string", "description": "Specific refactoring goals"},
                },
                "required": ["code", "instructions"],
            },
        )

    async def validate_inputs(self, inputs: dict[str, Any]) -> str | None:
        if not inputs.get("code"):
            return "code is required"
        if not inputs.get("instructions"):
            return "refactoring instructions are required"
        return None

    async def execute(self, inputs: dict[str, Any]) -> ToolResult:
        code = inputs["code"]
        language = inputs.get("language", "auto-detect")
        instructions = inputs["instructions"]

        system = "You are an expert software developer. Refactor code according to the given instructions. Return ONLY the refactored code, no markdown fences. Preserve all existing functionality."
        prompt = f"Refactor this {language} code:\n\n```\n{code}\n```\n\nRefactoring goals: {instructions}"

        try:
            refactored = await _ai_chat(prompt, system=system)
            if refactored.startswith("```"):
                lines = refactored.split("\n")
                refactored = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])

            self.log_action("refactor_code", details=f"instructions={instructions[:60]}")
            return ToolResult(success=True, data={"code": refactored.strip(), "original": code})
        except Exception as e:
            return ToolResult(success=False, error=str(e))


class FindBugsTool(BaseTool):
    """Find bugs in code using AI."""

    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="coding.agent.find_bugs",
            description="Analyze code for bugs and potential issues.",
            category="coding",
            risk_level=RiskLevel.SAFE,
            requires_confirmation=False,
            timeout=60.0,
            input_schema={
                "type": "object",
                "properties": {
                    "code": {"type": "string", "description": "Code to analyze"},
                    "language": {"type": "string", "description": "Programming language"},
                },
                "required": ["code"],
            },
        )

    async def validate_inputs(self, inputs: dict[str, Any]) -> str | None:
        if not inputs.get("code"):
            return "code is required"
        return None

    async def execute(self, inputs: dict[str, Any]) -> ToolResult:
        code = inputs["code"]
        language = inputs.get("language", "auto-detect")

        system = (
            "You are a senior software developer and code reviewer. "
            "Analyze code for bugs, security issues, performance problems, and potential errors. "
            "For each issue found, provide:\n"
            "- Line/area affected\n"
            "- Severity (critical/high/medium/low)\n"
            "- Description of the issue\n"
            "- Suggested fix\n"
            "If no issues are found, say 'No issues detected.'"
        )
        prompt = f"Find bugs and issues in this {language} code:\n\n```\n{code}\n```"

        try:
            analysis = await _ai_chat(prompt, system=system)
            self.log_action("find_bugs", details=f"language={language} code_len={len(code)}")
            return ToolResult(success=True, data={"analysis": analysis})
        except Exception as e:
            return ToolResult(success=False, error=str(e))


class CreateTestsTool(BaseTool):
    """Generate tests for code using AI."""

    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="coding.agent.create_tests",
            description="Generate unit tests for a piece of code.",
            category="coding",
            risk_level=RiskLevel.LOW,
            requires_confirmation=False,
            timeout=60.0,
            input_schema={
                "type": "object",
                "properties": {
                    "code": {"type": "string", "description": "Code to test"},
                    "language": {"type": "string", "description": "Programming language"},
                    "framework": {"type": "string", "description": "Test framework (e.g., pytest, jest)"},
                    "coverage": {"type": "string", "description": "What to cover (e.g., edge cases, happy path)"},
                },
                "required": ["code"],
            },
        )

    async def validate_inputs(self, inputs: dict[str, Any]) -> str | None:
        if not inputs.get("code"):
            return "code is required"
        return None

    async def execute(self, inputs: dict[str, Any]) -> ToolResult:
        code = inputs["code"]
        language = inputs.get("language", "python")
        framework = inputs.get("framework", "pytest")
        coverage = inputs.get("coverage", "happy path and edge cases")

        system = (
            f"You are an expert QA engineer. Generate comprehensive unit tests using {framework}. "
            "Return ONLY the test code, no markdown fences. Include:\n"
            "- Test function names that describe what they test\n"
            "- Appropriate assertions\n"
            "- Edge cases and error handling tests\n"
            "- Clear test descriptions"
        )
        prompt = f"Generate {framework} tests for this {language} code:\n\n```\n{code}\n```\n\nCover: {coverage}"

        try:
            tests = await _ai_chat(prompt, system=system)
            if tests.startswith("```"):
                lines = tests.split("\n")
                tests = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])

            self.log_action("create_tests", details=f"language={language} framework={framework}")
            return ToolResult(success=True, data={"tests": tests.strip(), "framework": framework})
        except Exception as e:
            return ToolResult(success=False, error=str(e))


def register_ai_tools(registry: Any) -> None:
    """Register all AI coding tools."""
    registry.register(ExplainCodeTool())
    registry.register(GenerateCodeTool())
    registry.register(RefactorCodeTool())
    registry.register(FindBugsTool())
    registry.register(CreateTestsTool())
