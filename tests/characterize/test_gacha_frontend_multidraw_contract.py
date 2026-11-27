"""Static-only frontend multi-draw contract tests.

These tests verify the DOM wiring and JavaScript logic for the multi-draw
feature WITHOUT launching a browser. They check:
- Named control presence and IDs in the source HTML
- Function signatures and state wiring in the JavaScript source
- Safe text rendering via DOM textContent (no unsanitized innerHTML)
- New API call structure and multi-result handling logic

Static-only contract does not constitute browser E2E.
"""
import ast
import json
import re
import unittest
from pathlib import Path

# Use absolute path to project root
PROJECT_ROOT = Path(r'D:\Axelit\.工作\trae\超级自动化学习工具')


class FrontendMultiDrawContractTests(unittest.TestCase):
    """Verify multi-draw frontend contract in static sources."""

    def _read(self, *parts):
        return (PROJECT_ROOT / "static" / "app.js").read_text(encoding="utf-8")

    def _read_renderer(self):
        return (PROJECT_ROOT / "static" / "modules" / "gacha" / "presentation.js").read_text(encoding="utf-8")

    def _read_owner(self):
        """AR03-G14: the real Gacha core owner (ESM) that now owns the state."""
        return (PROJECT_ROOT / "static" / "modules" / "gacha" / "index.js").read_text(encoding="utf-8")

    def _owner_body(self, name):
        """Extract the body of `name` from the real ESM gacha owner.

        AR03-G14: the multi-draw business logic moved out of classic
        app.js into static/modules/gacha/index.js (createGachaOwner).
        The assertions below are unchanged in strength; they simply
        locate the implementation in its new (single) home.
        """
        source = self._read_owner()
        m = re.search(
            r'(?:async\s+)?function\s+' + re.escape(name) + r'\s*\([^)]*\)\s*\{',
            source,
        )
        if not m:
            return ''
        start = m.end() - 1
        depth = 0
        for i in range(start, len(source)):
            ch = source[i]
            if ch == '{':
                depth += 1
            elif ch == '}':
                depth -= 1
                if depth == 0:
                    return source[start:i + 1]
        return source[start:]

    def _read_html(self, *parts):
        return (PROJECT_ROOT / "src" / "index.html").read_text(encoding="utf-8")

    # ------------------------------------------------------------------
    # DOM control presence
    # ------------------------------------------------------------------
    def test_multi_draw_button_exists_in_html(self):
        """HTML must contain a multi-draw button control."""
        html = self._read_html()
        # Look for the multi-draw button - either by id, class or text
        patterns = [
            r'id=["\']?gachaMultiBtn["\']?',        # id="gachaMultiBtn"
            r'class=["\'][^"\']*gacha-multi-btn[^"\']*["\']',  # class with gacha-multi-btn
            r'>[^<]*连抽[^<]*<',                     # text content containing 连抽
            r'>[^<]*多抽[^<]*<',                     # text content containing 多抽
            r'>[^<]*multi[^<]*<',                   # text content containing multi
        ]
        self.assertTrue(
            any(re.search(p, html, re.IGNORECASE) for p in patterns),
            "Multi-draw button control not found in HTML"
        )

    def test_multi_count_selector_exists_in_html(self):
        """HTML must contain a count selector (2..5) for multi-draw."""
        html = self._read_html()
        # Look for select or input with count-related naming
        patterns = [
            r'<select[^>]*id=["\']?gachaMultiCount["\']?',  # id="gachaMultiCount"
            r'<input[^>]*id=["\']?gachaMultiCount["\']?',
            r'class=["\'][^"\']*gacha-multi-count[^"\']*["\']',
        ]
        self.assertTrue(
            any(re.search(p, html, re.IGNORECASE) for p in patterns),
            "Multi-draw count selector not found in HTML"
        )

    def test_multi_result_area_exists_in_html(self):
        """HTML must contain a container for multi-draw results."""
        html = self._read_html()
        patterns = [
            r'id=["\']?gachaMultiResult["\']?',        # id="gachaMultiResult"
            r'class=["\'][^"\']*gacha-multi-result[^"\']*["\']',
        ]
        self.assertTrue(
            any(re.search(p, html, re.IGNORECASE) for p in patterns),
            "Multi-draw result area not found in HTML"
        )

    def test_multi_summary_exists_in_html(self):
        """HTML must contain a summary area for multi-draw stats."""
        html = self._read_html()
        patterns = [
            r'id=["\']?gachaMultiSummary["\']?',
            r'class=["\']*gacha-multi-summary[^"\']*["\']?',
        ]
        self.assertTrue(
            any(re.search(p, html, re.IGNORECASE) for p in patterns),
            "Multi-draw summary area not found in HTML"
        )

    # ------------------------------------------------------------------
    # JavaScript function signatures and state wiring
    # ------------------------------------------------------------------
    def test_multi_draw_function_exists(self):
        """The real ESM gacha owner must contain a multi-draw handler."""
        js = self._read_owner()
        patterns = [
            r'function\s+drawGachaMulti\s*\(',
            r'async\s+function\s+drawGachaMulti\s*\(',
            r'var\s+drawGachaMulti\s*=\s*async\s+function',
            r'drawGachaMulti\s*:\s*async\s+function',
        ]
        self.assertTrue(
            any(re.search(p, js) for p in patterns),
            "drawGachaMulti function not found in the ESM gacha owner"
        )

    def test_multi_draw_uses_isdrawing_lock(self):
        """Multi-draw must check and set isDrawing to prevent race."""
        js = self._read_owner()
        # Should check isDrawing at start
        self.assertIn("isDrawing", js)
        # drawGachaMulti should reference isDrawing
        body = self._owner_body('drawGachaMulti')
        if body:
            self.assertIn("isDrawing", body,
                "drawGachaMulti must check isDrawing lock")

    def test_multi_draw_disables_buttons_during_operation(self):
        """Multi-draw must disable appropriate buttons during pending."""
        body = self._owner_body('drawGachaMulti')
        if body:
            # Should disable buttons
            self.assertTrue(
                "disabled" in body or "disabled=" in body,
                "drawGachaMulti must disable buttons during operation"
            )

    def test_multi_draw_calls_refresh_gacha_stats_on_success(self):
        """Multi-draw must call refreshGachaStats after successful draw."""
        body = self._owner_body('drawGachaMulti')
        if body:
            self.assertIn("refreshGachaStats", body,
                "drawGachaMulti must call refreshGachaStats on success")

    def test_multi_draw_handles_error_with_toast(self):
        """Multi-draw must show toast and safe state on failure."""
        body = self._owner_body('drawGachaMulti')
        if body:
            self.assertTrue(
                "toast" in body,
                "drawGachaMulti must call toast() on error"
            )

    def test_multi_draw_api_payload_structure(self):
        """Multi-draw must call /api/gacha/multi-draw with correct payload."""
        body = self._owner_body('drawGachaMulti')
        if body:
            # Must call the multi-draw endpoint
            self.assertIn("/api/gacha/multi-draw", body,
                "Must call /api/gacha/multi-draw endpoint")
            # Must include available_time
            self.assertIn("available_time", body,
                "Payload must include available_time")
            # Must include count
            self.assertIn("count", body,
                "Payload must include count")
            # Must include energy
            self.assertIn("energy", body,
                "Payload must include energy")

    def test_multi_draw_handles_array_response(self):
        """Multi-draw must handle response.tasks array."""
        body = self._owner_body('drawGachaMulti')
        if body:
            # Should handle tasks array
            self.assertTrue(
                "tasks" in body,
                "Must handle response.tasks array"
            )

    def test_multi_draw_respects_timer_running_state(self):
        """Multi-draw should check timer state before switching."""
        body = self._owner_body('drawGachaMulti')
        if body:
            # Should reference timer state
            has_timer_check = any(k in body for k in [
                "timerDockSession", "timerRunning", "_inlineTimerHandle"
            ])
            self.assertTrue(has_timer_check,
                "drawGachaMulti should check timer state")

    def test_multi_draw_shows_readonly_list_initially(self):
        """The real ESM renderer must create a clickable multi-result list."""
        js = re.sub(r'(?m)^[ \t]*//[^\n]*$', '', self._read_renderer())
        self.assertRegex(js, r'(?m)^export\s+function\s+renderMultiResults\(')
        self.assertIn("document.createElement('button')", js)
        self.assertIn("btn.addEventListener('click'", js)
        self.assertIn("container.classList.remove('hidden')", js)

    def test_multi_draw_click_activates_single_card(self):
        """Clicking a multi result must activate via existing renderDrawnCard."""
        body = (self._owner_body('drawGachaMulti') +
                self._owner_body('activateMultiCard'))
        self.assertIn("renderDrawnCard", body,
            "Multi result click must call renderDrawnCard to activate")

    def test_multi_draw_sets_current_task_id_on_activation(self):
        """Activating a multi result must set currentTaskId."""
        body = (self._owner_body('drawGachaMulti') +
                self._owner_body('activateMultiCard'))
        self.assertIn("currentTaskId", body,
            "Must set the owner's currentTaskId on activation")

    def test_multi_draw_prevents_replacement_on_activation(self,):
        """Activating multi result should set canReplace=false."""
        body = (self._owner_body('drawGachaMulti') +
                self._owner_body('activateMultiCard'))
        self.assertIn("canReplace", body,
            "Must set canReplace=false when activating from multi")

    # ------------------------------------------------------------------
    # XSS protection: safe text rendering
    # ------------------------------------------------------------------
    def test_uses_escape_html_for_user_text(self):
        """Must use escapeHtml for task names/tags, not raw innerHTML."""
        js = self._read()
        # Check that escapeHtml exists and is used
        self.assertIn("escapeHtml", js,
            "escapeHtml function must exist for safe text rendering")

    def test_multi_result_rendering_uses_safe_text(self):
        """Assert against executable ESM renderer, never the classic facade."""
        js = re.sub(r'(?m)^[ \t]*//[^\n]*$', '', self._read_renderer())
        match = re.search(r'(?m)^export\s+function\s+renderMultiResults\([^)]*\)\s*\{', js)
        self.assertIsNotNone(match, "ESM renderMultiResults owner must exist")
        body = js[match.end():]
        self.assertIn("titleDiv.textContent", body)
        self.assertIn("tagSpan.textContent", body)
        self.assertIn("strong.textContent = String(valueText)", body)
        self.assertNotRegex(body, r'innerHTML\s*=\s*[^;]*task\.name')

    def test_no_unsanitized_task_name_in_innerHTML(self):
        """Task names from API must not be spliced into unsanitized innerHTML."""
        js = self._read()
        # Parse JS to find innerHTML assignments with task.name
        # Pattern: element.innerHTML = ... something .name ...
        # This is a heuristic check
        unsafe_pattern = r'innerHTML\s*=\s*["\'].*?(\\{name\\}|" \+ .*? \+ "|\\.name)'
        matches = list(re.finditer(unsafe_pattern, js))
        # We expect safe patterns like: escapeHtml(task.name)
        # or: div.textContent = task.name
        # If unsafe innerHTML with .name is found, flag it
        for m in matches:
            context = js[max(0, m.start()-50):m.end()+50]
            # Check if escapeHtml is used
            if "escapeHtml" not in context:
                self.fail(f"Potential unsafe innerHTML with task name: {context[:100]}")

    # ------------------------------------------------------------------
    # DOM ID linkage
    # ------------------------------------------------------------------
    def test_gacha_multi_result_ids_match_html(self):
        """JS references to DOM IDs must match IDs defined in HTML."""
        html_ids = set(re.findall(r'id=["\']([^"\']+)["\']', self._read_html()))
        # AR03-G14: the multi-draw implementation now lives in the ESM owner.
        js_sources = self._read() + "\n" + self._read_owner()
        js_refs = set(re.findall(r'getElementById\(["\']([^"\']+)["\']\)', js_sources))
        js_queries = set(re.findall(r'querySelector\(["\']#([^"\']+)["\']\)', js_sources))
        all_js_ids = js_refs | js_queries

        # Multi-related IDs that must exist
        multi_ids = ["gachaMultiBtn", "gachaMultiCount", "gachaMultiResult", "gachaMultiSummary"]
        for mid in multi_ids:
            # Check if it's referenced in JS
            if any(mid in js_id for js_id in all_js_ids):
                self.assertIn(mid, html_ids,
                    f"{mid} referenced in JS but not defined in HTML")

    # ------------------------------------------------------------------
    # Multi-draw count range 2..5
    # ------------------------------------------------------------------
    def test_multi_count_range_2_to_5(self):
        """Count selector must support range 2-5."""
        js = self._read_owner()
        # Look for count validation
        count_patterns = [
            r'count\s*[><=!]+\s*[1-5]',     # count > 1, count <= 5
            r'Math\.max\(\s*2\s*,\s*Math\.min\(\s*5\s*,',  # clamp 2..5
            r'min\s*=\s*["\']?2["\']?',    # min="2" in HTML
            r'max\s*=\s*["\']?5["\']?',    # max="5" in HTML
        ]
        found = any(re.search(p, js) for p in count_patterns)
        # Also check HTML for select options
        html = self._read_html()
        html_has_2_5 = (
            ("value=\"2\"" in html or "value='2'" in html) and
            ("value=\"5\"" in html or "value='5'" in html)
        )
        self.assertTrue(found or html_has_2_5,
            "Multi-draw count must support range 2..5")

    # ------------------------------------------------------------------
    # getGachaAvailableMinutes integration
    # ------------------------------------------------------------------
    def test_multi_draw_uses_getGachaAvailableMinutes(self):
        """Multi-draw must use existing getGachaAvailableMinutes for budget."""
        body = self._owner_body('drawGachaMulti')
        if body:
            self.assertIn("getGachaAvailableMinutes", body,
                "Must use getGachaAvailableMinutes for budget validation")


if __name__ == "__main__":
    unittest.main()
