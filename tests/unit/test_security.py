"""Tests for security module — findings, lab, reports, scope."""

import asyncio
import os
import tempfile
import time

import pytest

from app.core.db import init_db


# ============================================================
# Findings
# ============================================================

class TestCreateFinding:
    def test_spec(self):
        from app.security.findings import CreateFindingTool
        tool = CreateFindingTool()
        assert tool.spec().name == "security.findings.create"

    def test_validate_empty_title(self):
        from app.security.findings import CreateFindingTool
        tool = CreateFindingTool()
        error = asyncio.run(tool.validate_inputs({"title": ""}))
        assert error is not None

    def test_validate_invalid_severity(self):
        from app.security.findings import CreateFindingTool
        tool = CreateFindingTool()
        error = asyncio.run(tool.validate_inputs({"title": "test", "severity": "invalid"}))
        assert error is not None

    def test_create_finding(self):
        asyncio.run(init_db())
        from app.security.findings import CreateFindingTool
        tool = CreateFindingTool()
        result = asyncio.run(tool.execute({
            "title": "SQL Injection in login",
            "severity": "critical",
            "affected_asset": "https://example.com/login",
            "description": "SQL injection vulnerability in login form",
            "remediation": "Use parameterized queries",
        }))
        assert result.success
        assert result.data["severity"] == "critical"


class TestListFindings:
    def test_spec(self):
        from app.security.findings import ListFindingsTool
        tool = ListFindingsTool()
        assert tool.spec().name == "security.findings.list"

    def test_list_empty(self):
        asyncio.run(init_db())
        from app.security.findings import ListFindingsTool
        tool = ListFindingsTool()
        result = asyncio.run(tool.execute({}))
        assert result.success
        assert isinstance(result.data["findings"], list)

    def test_list_with_severity_filter(self):
        asyncio.run(init_db())
        from app.security.findings import ListFindingsTool
        tool = ListFindingsTool()
        result = asyncio.run(tool.execute({"severity": "critical"}))
        assert result.success


class TestUpdateFinding:
    def test_spec(self):
        from app.security.findings import UpdateFindingTool
        tool = UpdateFindingTool()
        assert tool.spec().name == "security.findings.update"

    def test_validate_empty_id(self):
        from app.security.findings import UpdateFindingTool
        tool = UpdateFindingTool()
        error = asyncio.run(tool.validate_inputs({"id": ""}))
        assert error is not None


class TestFindingsSummary:
    def test_spec(self):
        from app.security.findings import FindingsSummaryTool
        tool = FindingsSummaryTool()
        assert tool.spec().name == "security.findings.summary"

    def test_summary(self):
        asyncio.run(init_db())
        from app.security.findings import FindingsSummaryTool
        tool = FindingsSummaryTool()
        result = asyncio.run(tool.execute({}))
        assert result.success
        assert "total" in result.data
        assert "by_severity" in result.data


# ============================================================
# Lab Mode
# ============================================================

class TestLabCreate:
    def test_spec(self):
        from app.security.lab import LabCreateTool
        tool = LabCreateTool()
        spec = tool.spec()
        assert spec.name == "security.lab.create"
        assert spec.requires_confirmation is True

    def test_validate_empty_name(self):
        from app.security.lab import LabCreateTool
        tool = LabCreateTool()
        error = asyncio.run(tool.validate_inputs({"name": ""}))
        assert error is not None

    def test_create_lab(self):
        asyncio.run(init_db())
        from app.security.lab import LabCreateTool
        tool = LabCreateTool()
        result = asyncio.run(tool.execute({
            "name": "Web App Assessment",
            "target": "https://example.com",
            "scope": "example.com, ports 80,443",
        }))
        assert result.success
        assert result.data["status"] == "idle"


class TestLabStatus:
    def test_spec(self):
        from app.security.lab import LabStatusTool
        tool = LabStatusTool()
        assert tool.spec().name == "security.lab.status"

    def test_list_labs(self):
        asyncio.run(init_db())
        from app.security.lab import LabStatusTool
        tool = LabStatusTool()
        result = asyncio.run(tool.execute({}))
        assert result.success
        assert isinstance(result.data["labs"], list)


class TestLabStart:
    def test_spec(self):
        from app.security.lab import LabStartTool
        tool = LabStartTool()
        assert tool.spec().name == "security.lab.start"

    def test_validate_empty_id(self):
        from app.security.lab import LabStartTool
        tool = LabStartTool()
        error = asyncio.run(tool.validate_inputs({"lab_id": ""}))
        assert error is not None


class TestLabStop:
    def test_spec(self):
        from app.security.lab import LabStopTool
        tool = LabStopTool()
        assert tool.spec().name == "security.lab.stop"


# ============================================================
# Reports
# ============================================================

class TestGenerateReport:
    def test_spec(self):
        from app.security.reports import GenerateReportTool
        tool = GenerateReportTool()
        assert tool.spec().name == "security.reports.generate"

    def test_generate_markdown(self):
        asyncio.run(init_db())
        from app.security.reports import GenerateReportTool
        tool = GenerateReportTool()
        result = asyncio.run(tool.execute({"format": "markdown"}))
        assert result.success
        assert "NEXORA Security Assessment Report" in result.data["report"]

    def test_generate_html(self):
        asyncio.run(init_db())
        from app.security.reports import GenerateReportTool
        tool = GenerateReportTool()
        result = asyncio.run(tool.execute({"format": "html"}))
        assert result.success
        assert "<!DOCTYPE html>" in result.data["report"]

    def test_generate_with_save(self):
        asyncio.run(init_db())
        from app.security.reports import GenerateReportTool
        tool = GenerateReportTool()
        with tempfile.NamedTemporaryFile(suffix=".md", delete=False) as f:
            path = f.name
        try:
            result = asyncio.run(tool.execute({"format": "markdown", "save_path": path}))
            assert result.success
            assert os.path.exists(path)
            with open(path) as f:
                content = f.read()
            assert "NEXORA" in content
        finally:
            os.unlink(path)


# ============================================================
# Scope Management
# ============================================================

class TestScopeCheck:
    def test_spec(self):
        from app.security.scope import ScopeCheckTool
        tool = ScopeCheckTool()
        assert tool.spec().name == "security.scope.check"

    def test_validate_empty_target(self):
        from app.security.scope import ScopeCheckTool
        tool = ScopeCheckTool()
        error = asyncio.run(tool.validate_inputs({"target": ""}))
        assert error is not None

    def test_no_rules_allows_all(self):
        asyncio.run(init_db())
        from app.security.scope import ScopeCheckTool
        tool = ScopeCheckTool()
        result = asyncio.run(tool.execute({"target": "192.168.1.1"}))
        assert result.success
        assert result.data["in_scope"] is True

    def test_ip_match(self):
        from app.security.scope import _match_ip
        assert _match_ip("192.168.1.1", "192.168.1.1")
        assert _match_ip("192.168.1.1", "192.168.1.0/24")
        assert not _match_ip("192.168.1.1", "10.0.0.0/8")

    def test_domain_match(self):
        from app.security.scope import _match_domain
        assert _match_domain("example.com", "example.com")
        assert _match_domain("sub.example.com", "*.example.com")
        assert not _match_domain("evil.com", "*.example.com")

    def test_port_match(self):
        from app.security.scope import _match_port
        assert _match_port(80, "80")
        assert _match_port(80, "80,443")
        assert _match_port(443, "80-444")
        assert not _match_port(8080, "80,443")


class TestScopeAddRule:
    def test_spec(self):
        from app.security.scope import ScopeAddRuleTool
        tool = ScopeAddRuleTool()
        assert tool.spec().name == "security.scope.add"

    def test_validate_empty_fields(self):
        from app.security.scope import ScopeAddRuleTool
        tool = ScopeAddRuleTool()
        error = asyncio.run(tool.validate_inputs({"lab_id": ""}))
        assert error is not None


class TestScopeListRules:
    def test_spec(self):
        from app.security.scope import ScopeListRulesTool
        tool = ScopeListRulesTool()
        assert tool.spec().name == "security.scope.list"


# ============================================================
# Registry Integration
# ============================================================

class TestSecurityRegistry:
    def test_register_all(self):
        from app.tools.registry import ToolRegistry
        reg = ToolRegistry()
        from app.security.findings import register_finding_tools
        from app.security.lab import register_lab_tools
        from app.security.reports import register_report_tools
        from app.security.scope import register_scope_tools

        register_finding_tools(reg)
        register_lab_tools(reg)
        register_report_tools(reg)
        register_scope_tools(reg)

        tools = reg.list_tools()
        names = {t.name for t in tools}
        assert "security.findings.create" in names
        assert "security.findings.list" in names
        assert "security.findings.update" in names
        assert "security.findings.delete" in names
        assert "security.findings.summary" in names
        assert "security.lab.create" in names
        assert "security.lab.status" in names
        assert "security.lab.start" in names
        assert "security.lab.stop" in names
        assert "security.lab.delete" in names
        assert "security.reports.generate" in names
        assert "security.scope.check" in names
        assert "security.scope.add" in names
        assert "security.scope.list" in names
        assert "security.scope.delete" in names

        assert len(tools) == 15
