"""tests/characterize/test_gacha_frontend_a11y.py

Static-only contract tests for the P0 multi-draw hardening.

These tests read the project source files directly (no Flask, no DB) and
verify the three Controller FINDINGS from the NEets_FOLLOWUP review:

1. No unsanitized API data in renderMultiResults innerHTML
2. Native <button type="button"> for each result with aria-pressed + keyboard
3. Activation reuses the issued card without a new multi-draw POST

The tests are static-only and do NOT count as browser E2E. The separate
Playwright spec tests/e2e/gacha-multidraw-safe.spec.js provides isolated
browser coverage.

"""
import re
import unittest
from pathlib import Path

PROJECT_ROOT = Path(r'D:\Axelit\.工作\trae\超级自动化学习工具')
APP_JS = PROJECT_ROOT / 'static' / 'app.js'
RENDER_JS = PROJECT_ROOT / 'static' / 'modules' / 'gacha' / 'presentation.js'
# AR03-G14: the real Gacha core owner (single/multi/care draw, replace chain,
# unified behavior events) lives in the ESM module, not in classic app.js.
GACHA_OWNER_JS = PROJECT_ROOT / 'static' / 'modules' / 'gacha' / 'index.js'
INDEX_HTML = PROJECT_ROOT / 'src' / 'index.html'


def _read(p):
    return p.read_text(encoding='utf-8')


class MultiDrawHardeningContractTests(unittest.TestCase):
    """Static-source contract checks for multi-draw hardening."""

    @classmethod
    def setUpClass(cls):
        cls.js = _read(APP_JS)
        cls.render_js = _read(RENDER_JS)
        cls.owner_js = _read(GACHA_OWNER_JS)
        cls.html = _read(INDEX_HTML)

    # ------------------------------------------------------------------
    # Locator helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _extract_function_body(source, name):
        """Return the body of `name` found in `source` (brace-matched)."""
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

    def _owner_function_body(self, name):
        """AR03-G14: Gacha core functions now live in the ESM owner."""
        return self._extract_function_body(self.owner_js, name)
    def _render_function_body(self):
        """Inspect the real ESM renderer, not comments in the app.js facade."""
        source = self.render_js
        m = re.search(
            r'^export\s+function\s+renderMultiResults\s*\([^)]*\)\s*\{',
            source, re.MULTILINE,
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
                    return re.sub(r'(?m)^[ \t]*//[^\n]*$', '', source[start:i + 1])
        return ''

    def _activate_function_body(self):
        """AR03-G14: activateMultiCard now lives in the ESM gacha owner."""
        return self._owner_function_body('activateMultiCard')

    # ==============================================================
    # Defect 1: no unsanitized innerHTML for user/API fields
    # ==============================================================
    def test_render_multi_results_contains_no_innerHTML_assignment(self):
        """renderMultiResults must not assign to .innerHTML at all."""
        body = self._render_function_body()
        self.assertTrue(body, 'renderMultiResults must exist in static/app.js')
        self.assertNotRegex(
            body,
            r'\.innerHTML\s*=',
            'renderMultiResults must not assign to .innerHTML. '
            'All dynamic text must use textContent with static icon class names only.',
        )

    def test_render_multi_results_summary_uses_textcontent_for_numbers(self):
        """total_minutes and remaining_minutes must use textContent."""
        body = self._render_function_body()
        self.assertIn('total_minutes', body)
        self.assertIn('remaining_minutes', body)
        self.assertRegex(
            body,
            r'\.textContent\s*=\s*String\(',
            'renderMultiResults must use textContent for numeric stats',
        )
        self.assertNotRegex(
            body,
            r"innerHTML\s*=\s*['\"`][^'`]*\$\{",
            'renderMultiResults must not splice numbers into an HTML template literal',
        )

    def test_render_multi_results_trusted_icons_are_class_only(self):
        """Icon classes must be static Font Awesome literals (no interpolation)."""
        body = self._render_function_body()
        chip_calls = re.findall(
            r"appendSummaryChip\(\s*['\"]([^'\"]+)['\"]\s*,",
            body,
        )
        self.assertGreaterEqual(
            len(chip_calls), 3,
            'renderMultiResults must call appendSummaryChip with at least three '
            'literal Font Awesome classes',
        )
        for chip in chip_calls:
            self.assertTrue(
                chip.startswith('fa-solid fa-'),
                f'Icon class literal must be Font Awesome: {chip!r}',
            )
            self.assertNotIn('${', chip)
        self.assertIn(
            'icon.className = iconClass',
            body,
            'appendSummaryChip must set icon.className (DOM)',
        )

    def test_render_multi_results_task_name_uses_textcontent(self):
        """Task name must be assigned via .textContent, not innerHTML."""
        body = self._render_function_body()
        self.assertRegex(
            body,
            r'\.textContent\s*=\s*(?:task\.name|task\.name\s*\|\|\s*[\'"]未知任务[\'"])',
            'Task name must be via .textContent in renderMultiResults',
        )
        unsafe = re.search(r"innerHTML\s*=\s*['\"`][^'\"]*task\.name", body)
        self.assertIsNone(
            unsafe,
            'task.name must never be concatenated into an innerHTML string',
        )

    def test_render_multi_results_tag_uses_textcontent(self):
        """Tag text must be assigned via .textContent."""
        body = self._render_function_body()
        self.assertRegex(
            body,
            r'\.textContent\s*=\s*(?:tags\[0\]|.*tags\[0\].*)',
            'Tag must be via .textContent in renderMultiResults',
        )

    # ==============================================================
    # Defect 2: native button + keyboard semantics
    # ==============================================================
    def test_multi_item_is_native_button_with_button_type(self):
        """Each result must be <button type="button">, not <div>."""
        body = self._render_function_body()
        self.assertRegex(
            body,
            r"createElement\(\s*['\"]button['\"]\s*\)",
            'renderMultiResults must createElement("button")',
        )
        self.assertRegex(
            body,
            r"\.type\s*=\s*['\"]button['\"]",
            'renderMultiResults must set button.type = "button"',
        )

    def test_multi_item_uses_textcontent_for_label(self):
        """Accessible name must come from task.name via textContent."""
        body = self._render_function_body()
        self.assertRegex(
            body,
            r"\.textContent\s*=\s*(?:task\.name|task\.name\s*\|\|\s*'未知任务')",
            'Button accessible name must come from task.name via textContent',
        )

    def test_multi_item_has_aria_pressed_toggle(self):
        """aria-pressed must be set on each button."""
        body = self._render_function_body()
        self.assertIn(
            'aria-pressed',
            body,
            'renderMultiResults must set aria-pressed on buttons',
        )

    def test_activate_multi_card_toggles_aria_pressed(self):
        """activateMultiCard must flip aria-pressed on chosen button."""
        body = self._activate_function_body()
        self.assertIn(
            'aria-pressed',
            body,
            'activateMultiCard must update aria-pressed',
        )
        self.assertRegex(
            body,
            r"setAttribute\(['\"]aria-pressed['\"]\s*,\s*['\"]false['\"]\)",
            'activateMultiCard must set aria-pressed="false" on unselected items',
        )

    def test_multi_item_activation_uses_real_button_click(self):
        """Must use a native button with click handler (no tabindex hack)."""
        body = self._render_function_body()
        self.assertIn(
            'addEventListener',
            body,
            'renderMultiResults must add a click handler',
        )
        self.assertNotRegex(
            body,
            r"setAttribute\(\s*['\"]tabindex['\"]",
            'renderMultiResults must not assign tabindex',
        )

    # ==============================================================
    # Defect 3: activation reuses single-draw without new POST
    # ==============================================================
    def test_activate_multi_card_does_not_call_multi_draw_api(self):
        """activateMultiCard must NOT call /api/gacha/multi-draw."""
        body = self._activate_function_body()
        self.assertNotIn(
            '/api/gacha/multi-draw', body,
            'activateMultiCard must not issue a multi-draw POST',
        )
        self.assertNotIn(
            'api(', body,
            'activateMultiCard must not invoke the api() wrapper either',
        )

    def test_activate_multi_card_calls_existing_render_drawn_card(self):
        """Activation must call renderDrawnCard."""
        body = self._activate_function_body()
        self.assertIn(
            'renderDrawnCard', body,
            'activateMultiCard must call renderDrawnCard',
        )

    def test_activate_multi_card_sets_can_replace_false(self):
        """Activating from multi must disable replacement."""
        body = self._activate_function_body()
        self.assertRegex(
            body,
            r"canReplace\s*=\s*false",
            'activateMultiCard must set gachaState.canReplace = false',
        )

    def test_draw_gacha_multi_does_not_call_api_on_activation(self):
        """drawGachaMulti must call /api/gacha/multi-draw exactly once."""
        body = self._owner_function_body('drawGachaMulti')
        self.assertTrue(body, 'drawGachaMulti must exist in the ESM gacha owner')
        occurrences = body.count('/api/gacha/multi-draw')
        self.assertEqual(
            occurrences, 1,
            f'drawGachaMulti must call /api/gacha/multi-draw exactly once, got {occurrences}',
        )

    # ==============================================================
    # Defect 1 extra: general contract across all multi-draw functions
    # ==============================================================
    def test_no_user_field_in_innerHTML_inside_multi_functions(self):
        """response.*/task.* must not be spliced into innerHTML strings."""
        offenders = []
        for fname in ('renderMultiResults', 'activateMultiCard', 'drawGachaMulti'):
            pattern = (
                r'(?:async\s+)?function\s+' + re.escape(fname)
                + r'\s*\([^)]*\)\s*\{'
            )
            # AR03-G14: activateMultiCard / drawGachaMulti live in the ESM owner.
            source = self.render_js if fname == 'renderMultiResults' else self.owner_js
            if fname == 'renderMultiResults':
                pattern = r'^export\s+function\s+renderMultiResults\s*\([^)]*\)\s*\{'
            m = re.search(pattern, source, re.MULTILINE)
            if not m:
                self.fail('Missing production function: ' + fname)
            start = m.end() - 1
            depth = 0
            for i in range(start, len(source)):
                ch = source[i]
                if ch == '{':
                    depth += 1
                elif ch == '}':
                    depth -= 1
                    if depth == 0:
                        body = source[start:i + 1]
                        break
            else:
                self.fail('Unbalanced production function: ' + fname)
            body = re.sub(r'(?m)^[ \t]*//[^\n]*$', '', body)
            if re.search(r"innerHTML\s*=\s*['\"`][^'\"]*response\.", body):
                offenders.append(fname + '/response.')
            if re.search(r"innerHTML\s*=\s*['\"`][^'\"]*task\.", body):
                offenders.append(fname + '/task.')
            if re.search(
                r"innerHTML\s*=\s*['\"`][^'\"]*\$\{(?:response|task|totalMinutes|remainingMinutes)",
                body
            ):
                offenders.append(fname + '/interp')
        self.assertEqual(
            offenders, [],
            f'User/API fields must not be spliced into innerHTML: {offenders}',
        )

    # ==============================================================
    # HTML: DOM id linkage (existing ids must remain)
    # ==============================================================
    def test_html_multi_ids_still_present(self):
        """The four multi-draw DOM ids must remain in src/index.html."""
        for required in (
            'gachaMultiRow', 'gachaMultiBtn', 'gachaMultiCount',
            'gachaMultiResult', 'gachaMultiSummary', 'gachaMultiList',
        ):
            self.assertRegex(
                self.html,
                r'id=["\']' + re.escape(required) + r'["\']',
                f'index.html must contain id="{required}"',
            )

    def test_html_button_label_keeps_aria_compatible_text(self):
        """The button text "连抽" stays as a static label in the HTML."""
        self.assertIn(
            '\u8fde\u62bd',  # 连抽
            self.html,
            'Multi-draw button text "连抽" must remain in the HTML template',
        )

    # ==============================================================
    # M1.2 — renderDrawnCard payload safety + selection focus
    # ==============================================================
    def _render_drawn_card_body(self):
        m = re.search(
            r'function\s+renderDrawnCard\s*\([^)]*\)\s*\{',
            self.js,
        )
        if not m:
            return ''
        start = m.end() - 1
        depth = 0
        for i in range(start, len(self.js)):
            ch = self.js[i]
            if ch == '{':
                depth += 1
            elif ch == '}':
                depth -= 1
                if depth == 0:
                    return self.js[start:i + 1]
        return self.js[start:]

    def test_render_drawn_card_escapes_task_id_in_onclick(self):
        """task.id must NOT appear unescaped in onclick attributes.

        Real renderDrawnCard previously interpolated task.id directly into
        onclick="startTask(N)" — a value such as '1);alert(1)//' would
        execute arbitrary JS.  The body must not contain any onclick="..."
        where task.id is concatenated in adjacent string concatenation.
        """
        body = self._render_drawn_card_body()
        self.assertTrue(body, 'renderDrawnCard must exist')
        # Dangerous pattern: a JS string fragment is closed, '+ task.id'
        # is concatenated, then a new string fragment is opened. This
        # is exactly the form found in renderDrawnCard today:
        #   onclick="startTask(' + task.id + ')"
        offenders = re.findall(
            r"onclick\s*=\s*['\"][^'\"]{0,200}['\"]\s*\+\s*task\.id",
            body,
        )
        self.assertEqual(
            offenders, [],
            'task.id must not be concatenated into onclick= attributes '
            'via string '+' (close-quote + task.id + open-quote). '
            'Found: ' + repr(offenders),
        )

    def test_render_drawn_card_escapes_task_priority(self):
        """task.priority must be HTML-escaped before insertion.

        The current renderDrawnCard concatenates `' + (task.priority || '?') + '`
        into a string fragment that ends up in innerHTML.  A hostile
        priority string ('</span><script>...</script><span>') breaks
        out of the span and injects script markup. The fix must wrap
        the field in escapeHtml().
        """
        body = self._render_drawn_card_body()
        self.assertTrue(body, 'renderDrawnCard must exist')
        # Catch any concatenation of task.priority into the innerHTML
        # template literal, including the (task.priority || '?') wrapper.
        # We look for any nearby escapeHtml(...) covering the field;
        # absence means unsafe.
        # The simplest safe-enough check: is the substring 'escapeHtml(task.priority'
        # or 'escapeHtml((task.priority' present in the body?
        unsafe = not (
            re.search(r"escapeHtml\(\s*\(?\s*task\.priority", body)
            or re.search(r"escapeHtml\(\s*String\(\s*task\.priority", body)
        )
        self.assertFalse(
            unsafe,
            'task.priority must be wrapped in escapeHtml(...) before being '
            'concatenated into innerHTML. Body excerpt: ' + body[:200],
        )

    def test_render_drawn_card_escapes_task_estimated_time(self):
        """task.estimated_time must be HTML-escaped before insertion."""
        body = self._render_drawn_card_body()
        unsafe = not (
            re.search(r"escapeHtml\(\s*String\(\s*task\.estimated_time", body)
            or re.search(
                r"escapeHtml\(\s*\(?\s*task\.estimated_time\s*\)?",
                body,
            )
        )
        self.assertFalse(
            unsafe,
            'task.estimated_time must be wrapped in escapeHtml(...) '
            '(or use textContent) before being concatenated into '
            'innerHTML. Body excerpt: ' + body[:200],
        )

    def test_render_drawn_card_html_escapes_linked_note_path(self):
        """linked_note_path must escape < > & (not only quotes) so an
        attacker cannot inject a <script> tag via the path.

        The current renderDrawnCard only escapes \\, ', and " when
        building safeNotePath. A path containing '>' can still break
        out of the surrounding HTML attribute and inject arbitrary
        markup. The fix must also run escapeHtml() (or a < > &
        substitution) on the path before embedding.
        """
        body = self._render_drawn_card_body()
        self.assertTrue(body, 'renderDrawnCard must exist')
        # Detect whether the body wraps linked_note_path (or its safe-
        # escaping helper) in escapeHtml(). The current body uses an ad-hoc
        # replace chain that escapes \\\\ ' " but NOT < > &.
        # We allow either of:
        #   - escapeHtml(safeNotePath)
        #   - escapeHtml(task.linked_note_path)
        #   - escapeHtml applied to the path before injection
        # Otherwise the path remains HTML-injection-vulnerable.
        path_block = re.search(
            r"linked_note_path[\s\S]{0,400}",
            body,
        )
        self.assertTrue(path_block, 'renderDrawnCard must reference linked_note_path')
        block = path_block.group(0)
        # Look for an escapeHtml() call that wraps the path, OR for a
        # pattern that replaces < and > in the path. The current code
        # only replaces \\, ', " — that is NOT enough.
        safe_via_escapeHtml = 'escapeHtml' in block
        safe_via_lt_gt = bool(re.search(
            r"\.replace\(/[<>&]/g",
            block,
        ))
        # If we instead see a data-* attribute pattern (e.g.
        # card.dataset.notePath = task.linked_note_path) and the
        # onclick reads it back via .getAttribute, the inline embedding
        # is also safe.
        safe_via_data_attr = bool(re.search(
            r"data-note-path",
            body,
        )) and bool(re.search(
            r"openNoteFromCard", body,
        ))
        self.assertTrue(
            safe_via_escapeHtml or safe_via_lt_gt or safe_via_data_attr,
            'linked_note_path must be escaped for < > & (escapeHtml or '
            'data-attr lookup). Current block:\n' + block,
        )

    def test_activate_multi_card_focuses_selected_button(self):
        """activateMultiCard must keep keyboard focus on the selected card.

        Without .focus() the keyboard user who pressed Enter or Space has
        no visible focus indicator after activation, breaking the
        a11y loop. This is required by M1.2 goal (1).
        """
        body = self._activate_function_body()
        self.assertTrue(body, 'activateMultiCard must exist')
        self.assertRegex(
            body,
            r"\.focus\s*\(",
            'activateMultiCard must call .focus() on the selected button '
            'so keyboard users do not lose focus after activation.',
        )

    # ==============================================================
    # M1.3A — card -> timer/feedback: startTask fallback + numeric guard
    # ==============================================================
    def _start_task_body(self):
        """AR03-G15.2：startTask 的业务实现已迁至 Task Lifecycle owner。

        static/app.js 只保留薄 facade；真正的实现（findTaskById 安全
        回退、numeric id 归一化、幂等锁、estimated_time 归一化、replace
        chain 收尾）位于 static/modules/tasks/lifecycle.js。
        """
        owner_body = self._lifecycle_function_body('startTask')
        if owner_body:
            return owner_body
        # 回退：owner 尚未接管时，仍检查 classic facade。
        m = re.search(
            r'(?:async\s+)?function\s+startTask\s*\([^)]*\)\s*\{',
            self.js,
        )
        if not m:
            return ''
        start = m.end() - 1
        depth = 0
        for i in range(start, len(self.js)):
            ch = self.js[i]
            if ch == '{':
                depth += 1
            elif ch == '}':
                depth -= 1
                if depth == 0:
                    return self.js[start:i + 1]
        return self.js[start:]

    def test_start_task_resolves_task_via_safe_cache_fallback(self):
        """startTask must resolve the task from a safe cache when
        allTasks.find(...) returns undefined.

        M1.2 case C documented the failure where the rendered card is
        startable ONLY via allTasks — which is populated asynchronously
        from /api/tasks. M1.3A requires a fallback that uses the
        in-render-state of the card (issued results cache or any local
        data keyed by the chosen id) so the button works on first draw.

        AR03-G15.2: the lookup now lives in the Task Lifecycle owner
        (findTaskById), which walks drawn card -> multi draw results ->
        allTasks. The classic facade no longer carries the cache tokens,
        so the contract is asserted against the owner implementation.
        """
        body = self._start_task_body()
        self.assertTrue(body, 'startTask must exist in the Task Lifecycle owner')
        # The owner must resolve the task through its dedicated lookup.
        self.assertRegex(
            body,
            r"findTaskById\s*\(",
            'startTask must resolve the task through findTaskById(). '
            'Body excerpt: ' + body[:300],
        )
        resolver = self._lifecycle_function_body('findTaskById')
        self.assertTrue(
            resolver,
            'the Task Lifecycle owner must implement findTaskById',
        )
        # The resolver must consult the safe stores in order:
        # drawn card -> multi draw results -> allTasks.
        cache_hits = sum(
            1 for tok in (
                'getDrawnTask', 'getMultiDrawResults', 'getTasks',
            ) if tok in resolver
        )
        self.assertGreaterEqual(
            cache_hits, 2,
            'findTaskById must consult the safe task caches '
            '(getDrawnTask / getMultiDrawResults / getTasks) '
            'when allTasks.find fails. Body excerpt: ' + resolver[:300],
        )
        self.assertIn(
            'getDrawnTask', resolver,
            'findTaskById must fall back to the drawn card cache',
        )
        self.assertIn(
            'getMultiDrawResults', resolver,
            'findTaskById must fall back to the multi draw results cache',
        )

    def test_start_task_coerces_numeric_task_id(self):
        """startTask must coerce taskId to a numeric id before lookup.

        The onclick= handler emits startTask(parseInt(task.id,10)) today,
        but hostile payloads or programmatic callers could pass a
        non-numeric. We require explicit numeric coercion (parseInt /
        isFinite / etc.) before the allTasks lookup so a string like
        '2);alert(1)//' can't break out of the function call expression.
        """
        body = self._start_task_body()
        self.assertTrue(body, 'startTask must exist')
        # Coercion shape: parseInt(taskId, 10) followed by isFinite / Number check.
        self.assertRegex(
            body,
            r"parseInt\s*\(\s*taskId\s*,\s*10\s*\)",
            'startTask must parseInt(taskId, 10) to a finite integer '
            'before lookup. Body excerpt: ' + body[:300],
        )
        self.assertRegex(
            body,
            r"isFinite\s*\(",
            'startTask must validate finite-ness of the coerced id.',
        )

    def test_start_task_has_reentrancy_guard(self):
        """startTask must drop a second immediate activation while the
        /api/timer/start POST is pending.

        TEST B's reentrancy dimension: while pending, a second scripted
        startTask(id) call must not issue a second POST. The guard tracks
        the in-flight task id in a module-level variable (e.g.
        _pendingStartTaskId). The guard is cleared in the same finally
        block that wraps the api() call, so subsequent valid clicks
        (after pending settles) still work.
        """
        body = self._start_task_body()
        self.assertTrue(body, 'startTask must exist')
        # Accept any of the project's inflight-state fields. The guard
        # must be cleared in a finally block so a rejected request doesn't
        # strand future valid calls.
        guard_pattern = (
            r"(?:var|let|const)\s+_?\w*[Pp]ending(?:Start)?\w*\s*=\s*"
            r"(?:null|0|false)"
        )
        # Look for the guard in the body; if not inside, fall back to a
        # file-level regex on the owner source (the guard lives at module
        # scope just above the function in the Task Lifecycle owner).
        in_body = re.search(guard_pattern, body)
        in_file = re.search(guard_pattern, self.js)
        in_owner = re.search(guard_pattern, self._lifecycle_source())
        self.assertIsNotNone(
            in_body or in_owner or in_file,
            'startTask must declare a module-level inflight guard '
            '(e.g. var _pendingStartTaskId = null). Body excerpt: '
            + body[:400],
        )
        # The owner must use the dedicated guard variable.
        self.assertIn(
            '_pendingStartTaskId', body,
            'the Task Lifecycle owner startTask must use _pendingStartTaskId '
            'as the in-flight lock. Body excerpt: ' + body[:400],
        )
        # Finally block must clear the guard so a future valid click works.
        self.assertIn(
            'finally',
            body,
            'startTask must clear the inflight guard in a finally block '
            'so a rejected /api/timer/start leaves the card re-clickable.',
        )

    def test_render_drawn_card_uses_safe_action_id_binding(self):
        """The four action buttons (start/skip/refuse/replace) must not
        embed task.id as a raw token in onclick="fn(N)" strings.

        If the function takes id from a data-* attribute via JS binding,
        or uses JSON.stringify(task.id), the regex below is satisfied.
        """
        body = self._render_drawn_card_body()
        # Forbidden pattern: onclick="...fn(<raw task.id>)..."
        offenders = re.findall(
            r"onclick\s*=\s*['\"]startTask\(['\"]?\s*\+?\s*task\.id",
            body,
        )
        offenders += re.findall(
            r"onclick\s*=\s*['\"]handleSkip\(['\"]?\s*\+?\s*task\.id",
            body,
        )
        offenders += re.findall(
            r"onclick\s*=\s*['\"]handleRefuse\(['\"]?\s*\+?\s*task\.id",
            body,
        )
        offenders += re.findall(
            r"onclick\s*=\s*['\"]showReplaceReason\(['\"]?\s*\+?\s*task\.id",
            body,
        )
        self.assertEqual(
            offenders, [],
            'task.id must not be concatenated raw into onclick=... fn(task.id)'
            ' strings. Use data-* + addEventListener, or JSON.stringify, '
            'or escapeHtml. Found: ' + repr(offenders),
        )

    # ==============================================================
    # M1.3B — startTask: estimated_time must be a finite positive int
    # before reaching the DOM or the /api/timer/start body.
    # ==============================================================
    def test_start_task_coerces_estimated_time_to_finite_int(self):
        """startTask must coerce task.estimated_time to a finite
        positive integer in [1, 480] before concatenating into
        rightPanel.innerHTML or posting to /api/timer/start.

        M1.3B finding: the legacy code used
            var planned = task.estimated_time || 30;
        which lets a hostile string such as
            '"><img src=x onerror="alert(1)">'
        flow into both the innerHTML literal AND the JSON body sent
        to /api/timer/start (the BP then writes a non-integer into
        planned_minutes). The fix is to coerce via Number() + Math.floor
        + isFinite, fall back to 30 for non-positive / out-of-range
        values, and only THEN concatenate.
        """
        body = self._start_task_body()
        self.assertTrue(body, 'startTask must exist in the Task Lifecycle owner')
        # The body must reference Number(task.estimated_time) and
        # isFinite, and bind the sanitized value to a local var
        # named `planned` (the variable consumed by both innerHTML
        # and the /api/timer/start body).
        self.assertRegex(
            body,
            r"Number\s*\(\s*task\.estimated_time\s*\)",
            'startTask must read task.estimated_time via Number(...) '
            'so non-numeric strings are coerced before DOM/API use.',
        )
        self.assertRegex(
            body,
            r"isFinite\s*\(",
            'startTask must validate the coerced estimated_time with isFinite().',
        )
        # `planned` must be assigned from the sanitized expression,
        # not directly from `task.estimated_time`. The legacy
        # `var planned = task.estimated_time || 30;` would match a
        # naive regex; the contract requires the assignment to come
        # from a Math.floor / isFinite / range-guard expression.
        m = re.search(r"var\s+planned\s*=\s*([^;]+);", body)
        self.assertTrue(
            m,
            'startTask must declare `var planned = ...;` from a '
            'sanitized expression. Body excerpt: ' + body[:400],
        )
        rhs = m.group(1)
        self.assertIn(
            'isFinite', rhs,
            '`planned` must be derived from an isFinite-guarded expression. '
            'Current RHS: ' + rhs,
        )
        self.assertNotIn(
            'task.estimated_time ||',
            rhs,
            'The legacy `task.estimated_time || 30` short-circuit is no '
            'longer safe for hostile string values. Use isFinite + range '
            'guard instead. Current RHS: ' + rhs,
        )
        # AR03-G15.2: the owner keeps the finite-integer + 1..480 range
        # guard on the sanitized value.
        self.assertIn(
            'Math.floor', rhs,
            '`planned` must be an integer (Math.floor) check. Current RHS: '
            + rhs,
        )
        self.assertRegex(
            rhs,
            r">=\s*1\b",
            '`planned` must enforce the lower bound of 1 minute. '
            'Current RHS: ' + rhs,
        )
        self.assertRegex(
            rhs,
            r"<=\s*480\b",
            '`planned` must enforce the upper bound of 480 minutes. '
            'Current RHS: ' + rhs,
        )

    def test_start_task_does_not_concat_raw_estimated_time_into_innerhtml(self):
        """startTask must not splice `+ planned +` with an unsanitized
        estimated_time path into an innerHTML literal.

        The body must use a `planned` variable that has been
        isFinite-guarded (verified by the previous test). This test
        additionally confirms that the innerHTML literal does NOT
        splice `task.estimated_time` raw — only the sanitized
        `planned` may appear.
        """
        body = self._start_task_body()
        self.assertTrue(body, 'startTask must exist')
        # Forbidden: any direct `+ task.estimated_time +` inside an
        # innerHTML concatenation block.
        offenders = re.findall(
            r"\+ task\.estimated_time \+", body
        )
        offenders += re.findall(
            r"\+ task\.estimated_time\b(?!\s*\|\|)", body
        )
        self.assertEqual(
            offenders, [],
            'task.estimated_time must NOT be concatenated into an '
            'innerHTML template literal. Use the sanitized `planned` '
            'variable instead. Found: ' + repr(offenders),
        )

    # ==============================================================
    # M1.3D — completeWithFeedback / submitFeedback / cancelFeedback
    # must NOT fabricate observations or POST before explicit user
    # confirmation.
    # ==============================================================
    def _complete_with_feedback_body(self):
        m = re.search(
            r'async\s+function\s+completeWithFeedback\s*\([^)]*\)\s*\{',
            self.js,
        )
        if not m:
            return ''
        start = m.end() - 1
        depth = 0
        for i in range(start, len(self.js)):
            ch = self.js[i]
            if ch == '{':
                depth += 1
            elif ch == '}':
                depth -= 1
                if depth == 0:
                    return self.js[start:i + 1]
        return self.js[start:]

    def _submit_feedback_body(self):
        m = re.search(
            r'function\s+submitFeedback\s*\(\s*\)\s*\{',
            self.js,
        )
        if not m:
            return ''
        start = m.end() - 1
        depth = 0
        for i in range(start, len(self.js)):
            ch = self.js[i]
            if ch == '{':
                depth += 1
            elif ch == '}':
                depth -= 1
                if depth == 0:
                    return self.js[start:i + 1]
        return self.js[start:]

    def _cancel_feedback_body(self):
        m = re.search(
            r'function\s+cancelFeedback\s*\(\s*\)\s*\{',
            self.js,
        )
        if not m:
            return ''
        start = m.end() - 1
        depth = 0
        for i in range(start, len(self.js)):
            ch = self.js[i]
            if ch == '{':
                depth += 1
            elif ch == '}':
                depth -= 1
                if depth == 0:
                    return self.js[start:i + 1]
        return self.js[start:]

    # --------------------------------------------------------------
    # AR03-G15.2 helpers — owner / facade semantics
    # --------------------------------------------------------------
    def _lifecycle_source(self):
        """The Task Lifecycle owner source (unique feedback/care owner)."""
        return _read(
            PROJECT_ROOT / 'static' / 'modules' / 'tasks' / 'lifecycle.js'
        )

    def _lifecycle_function_body(self, name):
        """Owner-side implementation of `name` (holds the business state)."""
        return self._extract_function_body(self._lifecycle_source(), name)

    def test_complete_with_feedback_does_not_post_hardcoded_observation(self):
        """completeWithFeedback must be a thin facade delegating to the
        Task Lifecycle owner; the owner opens the feedback flow and never
        fabricates an observation.

        M1.3D 契约：不得直接 POST 伪造的 /api/tasks/<id>/feedback。
        AR03-G15.2：反馈采集归 owner（openFeedback），app.js 的
        completeWithFeedback 只做委托；app.js 仍保留纯 DOM 适配器。
        """
        body = self._complete_with_feedback_body()
        self.assertTrue(
            body,
            'completeWithFeedback must exist in static/app.js',
        )
        # (a) 不得直接 POST 反馈端点（伪造观测值的原始缺陷）。
        offenders = re.findall(
            r"['\"`]\s*\+\s*['\"`]\s*\+\s*['\"`]\s*/feedback['\"`]",
            body,
        )
        offenders += re.findall(
            r"api\(\s*['\"`]\s*/api/tasks/[^)]*?/feedback['\"`]",
            body,
        )
        self.assertEqual(
            offenders, [],
            'completeWithFeedback must NOT issue /api/tasks/<id>/feedback '
            'directly. Feedback must flow through the explicit '
            'feedbackModal (submitFeedback) so the user controls the '
            'value. Found: ' + repr(offenders),
        )
        # (b) app.js 侧必须是委托 owner 的薄 facade。
        self.assertIn(
            '__taskLifecycleOwner',
            body,
            'completeWithFeedback must read the single Task Lifecycle owner '
            '(window.__taskLifecycleOwner).',
        )
        self.assertIn(
            'owner.completeWithFeedback',
            body,
            'completeWithFeedback must forward (id, opts) to '
            'owner.completeWithFeedback instead of implementing the flow.',
        )
        # (c) 打开反馈表单由 owner 编排（classic 层只提供 DOM 适配器）。
        owner_body = self._lifecycle_function_body('completeWithFeedback')
        self.assertTrue(
            owner_body,
            'the Task Lifecycle owner must implement completeWithFeedback',
        )
        self.assertIn(
            'openFeedback(',
            owner_body,
            'owner.completeWithFeedback must open the feedback flow via '
            'openFeedback(...) so the user explicitly submits energy/mood.',
        )
        self.assertNotIn(
            '/feedback',
            owner_body,
            'owner.completeWithFeedback must not POST the feedback endpoint '
            'itself — that belongs to the explicit submitFeedback step.',
        )
        # (d) app.js 保留纯 DOM 适配器 openFeedbackModalForTask。
        adapter = self._extract_function_body(self.js, 'openFeedbackModalForTask')
        self.assertTrue(
            adapter,
            'app.js must keep the openFeedbackModalForTask DOM adapter',
        )
        self.assertNotIn(
            '/api/',
            adapter,
            'the openFeedbackModalForTask adapter must be DOM-only '
            '(no API calls).',
        )
        # (e) 关怀过渡不得由 facade 直接调用。
        self.assertNotRegex(
            body,
            r"showCareModal\s*\(\s*id\s*,",
            'completeWithFeedback must NOT directly call '
            'showCareModal(id, ...) — care transition is now handled by '
            'transitionToCareModal() after explicit feedback submit/cancel.',
        )

    def test_submit_feedback_posts_user_selected_values_only(self):
        """submitFeedback must be a thin facade; the owner posts only the
        user-selected values and keeps the modal open on failure.

        M1.3D 契约：只上报用户选中的精力 / 心情；失败时保留 modal 供重试。
        AR03-G15.2：心情 / 重入锁 / API 序列都在 Task Lifecycle owner；
        app.js 只保留 readFeedbackEnergy 等纯 DOM 适配器。
        """
        body = self._submit_feedback_body()
        self.assertTrue(
            body,
            'submitFeedback must exist in static/app.js',
        )
        # (a) facade 委托 owner，且自身不做 DOM 取值、不持有业务状态。
        self.assertIn(
            '_lifecycleOwner()',
            body,
            'submitFeedback must resolve the owner through _lifecycleOwner()',
        )
        self.assertIn(
            'owner.submitFeedback',
            body,
            'submitFeedback must delegate to owner.submitFeedback.',
        )
        self.assertNotIn(
            "getElementById('fbEnergy')",
            body,
            'submitFeedback facade must not read the DOM input — energy is '
            'read by the owner through the readFeedbackEnergy adapter.',
        )
        self.assertNotIn(
            'feedbackMood',
            body,
            'submitFeedback facade must not own the mood state (owner does).',
        )
        self.assertNotIn(
            '_pendingFeedbackSubmit',
            body,
            'submitFeedback facade must not own the reentrancy lock '
            '(owner does).',
        )
        # (b) app.js 保留纯 DOM 适配器 readFeedbackEnergy（读 #fbEnergy）。
        adapter = self._extract_function_body(self.js, 'readFeedbackEnergy')
        self.assertTrue(
            adapter,
            'app.js must keep the readFeedbackEnergy DOM adapter',
        )
        self.assertIn(
            "getElementById('fbEnergy')",
            adapter,
            'the readFeedbackEnergy adapter must read energy from #fbEnergy',
        )
        self.assertNotIn(
            '/api/',
            adapter,
            'the readFeedbackEnergy adapter must be DOM-only (no API calls).',
        )
        # (c) app.js 不得再持有反馈业务状态。
        self.assertNotIn(
            'feedbackMood',
            self.js,
            'app.js must not own the feedback mood state (owner does).',
        )
        self.assertNotIn(
            '_pendingFeedbackSubmit',
            self.js,
            'app.js must not own the feedback reentrancy lock (owner does).',
        )
        # (d) owner 持有业务状态与 API 序列。
        owner_src = self._lifecycle_source()
        owner_body = self._lifecycle_function_body('submitFeedback')
        self.assertTrue(
            owner_body,
            'the Task Lifecycle owner must implement submitFeedback',
        )
        self.assertIn(
            'feedbackMood',
            owner_src,
            'the owner must own the current feedback mood state.',
        )
        self.assertIn(
            '_pendingFeedbackSubmit',
            owner_body,
            'the owner must use the _pendingFeedbackSubmit reentrancy guard '
            'to dedupe rapid duplicate clicks.',
        )
        self.assertIn(
            'readEnergy()',
            owner_body,
            'the owner must read the energy value via the injected adapter.',
        )
        self.assertIn(
            'readMood()',
            owner_body,
            'the owner must read the mood value from its own state.',
        )
        self.assertIn(
            'energy_after',
            owner_body,
            'the owner must post the user-selected energy value.',
        )
        self.assertIn(
            'mood_after',
            owner_body,
            'the owner must post the user-selected mood value.',
        )
        self.assertIn(
            '/feedback',
            owner_body,
            'the owner must issue the feedback POST on explicit submit.',
        )
        # (e) owner 必须有显式 .catch，且失败路径不得关闭 modal。
        self.assertIn(
            '.catch(',
            owner_body,
            'owner.submitFeedback must have an explicit .catch handler for '
            'the POST promise so failures surface to the user.',
        )
        catch_block = re.search(
            r"\.catch\s*\(\s*function\s*\([^)]*\)\s*\{([\s\S]*?)\}\s*\)",
            owner_body,
        )
        if catch_block:
            catch_body = catch_block.group(1)
            self.assertNotIn(
                'closeModal',
                catch_body,
                'owner.submitFeedback catch block must NOT close the modal '
                '(failure path leaves the modal open for retry).',
            )

    def test_cancel_feedback_zero_network(self):
        """cancelFeedback must remain a zero-network path, now owned by
        the Task Lifecycle owner.

        M1.3D 契约：取消反馈零网络请求，但必须关闭反馈 modal 并进入关怀。
        AR03-G15.2：app.js 是薄 facade；关闭与过渡由 owner 执行。
        """
        body = self._cancel_feedback_body()
        self.assertTrue(
            body,
            'cancelFeedback must exist in static/app.js',
        )
        # Must not call api() or fetch or any /api/... URL.
        self.assertNotRegex(
            body,
            r"\bapi\s*\(",
            'cancelFeedback must not invoke api() — cancellation is a '
            'zero-network path.',
        )
        self.assertNotIn(
            '/api/',
            body,
            'cancelFeedback must not reference any /api/... endpoint.',
        )
        # (a) facade 委托 owner。
        self.assertIn(
            '_lifecycleOwner()',
            body,
            'cancelFeedback must resolve the owner through _lifecycleOwner()',
        )
        self.assertIn(
            'owner.cancelFeedback',
            body,
            'cancelFeedback must delegate to owner.cancelFeedback.',
        )
        # (b) owner 侧：关闭反馈 modal + 过渡关怀，且零网络。
        owner_body = self._lifecycle_function_body('cancelFeedback')
        self.assertTrue(
            owner_body,
            'the Task Lifecycle owner must implement cancelFeedback',
        )
        self.assertIn(
            "closeModal('feedbackModal')",
            owner_body,
            'owner.cancelFeedback must close the feedback modal.',
        )
        self.assertIn(
            'transitionToCareModal',
            owner_body,
            'owner.cancelFeedback must transition to the care modal so '
            'the care same/switch/rest choices remain reachable after '
            'cancellation.',
        )
        self.assertNotRegex(
            owner_body,
            r"\bapi\s*\(",
            'owner.cancelFeedback must not invoke api() — cancellation is a '
            'zero-network path.',
        )
        self.assertNotIn(
            '/api/',
            owner_body,
            'owner.cancelFeedback must not reference any /api/... endpoint.',
        )


    # ==============================================================
    # M02-S03-G01-W04 — continuous replace chain contract
    # ==============================================================
    # Gacha core functions that AR03-G14 moved into the ESM owner.
    _OWNER_FUNCTIONS = (
        'doReplace', 'showReplaceReason', 'readAllowRepeatReplaced',
        'resetReplaceChain', 'drawGacha', 'drawGachaMulti',
        'drawGachaWithCategory', 'activateMultiCard',
    )
    # AR03-G15.2: Task Lifecycle owner functions (static/modules/tasks/
    # lifecycle.js). startTask business logic lives there, not in the
    # classic app.js facade and not in the Gacha owner.
    _LIFECYCLE_OWNER_FUNCTIONS = (
        'startTask',
        # AR03-G15.3: skip / refuse also moved into the Task Lifecycle owner.
        # app.js keeps only a thin classic facade delegating to it.
        'handleSkip',
        'handleRefuse',
    )

    def _function_body(self, name):
        """Locate a function body in its single production home.

        AR03-G14: the Gacha core (draw / multi / care / replace / chain) is
        owned by static/modules/gacha/index.js. AR03-G15.2: the task
        lifecycle (startTask) is owned by static/modules/tasks/lifecycle.js.
        Everything else stays in classic static/app.js.
        """
        if name in self._OWNER_FUNCTIONS:
            return self._owner_function_body(name)
        if name in self._LIFECYCLE_OWNER_FUNCTIONS:
            return self._lifecycle_function_body(name)
        m = re.search(
            r'(?:async\s+)?function\s+' + re.escape(name) + r'\s*\([^)]*\)\s*\{',
            self.js,
        )
        if not m:
            return ''
        start = m.end() - 1
        depth = 0
        for i in range(start, len(self.js)):
            ch = self.js[i]
            if ch == '{':
                depth += 1
            elif ch == '}':
                depth -= 1
                if depth == 0:
                    return self.js[start:i + 1]
        return self.js[start:]

    def test_replace_reason_is_never_defaulted_to_other(self):
        """doReplace must NOT silently fall back to reason='other'."""
        body = self._function_body('doReplace')
        self.assertTrue(body, 'doReplace must exist in static/app.js')
        self.assertNotRegex(
            body,
            r"reasonEl\s*\?\s*reasonEl\.value\s*:\s*['\"]other['\"]",
            'doReplace must not default a missing reason to "other"',
        )
        self.assertRegex(
            body,
            r"if\s*\(\s*!reasonEl\s*\)\s*\{",
            'doReplace must bail out when the user has not selected a reason',
        )

    def test_replace_form_has_no_preselected_reason(self):
        """No reason radio may be rendered pre-checked."""
        body = self._function_body('showReplaceReason')
        self.assertTrue(body, 'showReplaceReason must exist in static/app.js')
        self.assertNotRegex(
            body,
            r'id="rr_\w+"[^>]*checked',
            'showReplaceReason must not pre-check any reason radio',
        )
        self.assertNotRegex(
            body,
            r'name="reason"[^>]*checked',
            'no reason radio may carry a checked attribute',
        )
        for value in ('low_energy', 'no_time', 'similar_done', 'other'):
            self.assertIn(
                'value="' + value + '"', body,
                f'reason radio {value} must remain in the replace form',
            )

    def test_replace_form_has_both_chain_switches_with_contract_labels(self):
        """Both switches must exist with the Controller-approved wording."""
        body = self._function_body('showReplaceReason')
        self.assertIn('rr_allow_repeat', body,
                      'switch A must exist in the replace form')
        self.assertIn('rr_hide_today', body,
                      'switch B must exist in the replace form')
        self.assertIn('允许曾被更换的卡牌再次抽出', body,
                      'switch A wording must match the product contract')
        self.assertIn('我今天内不想再看到这张卡', body,
                      'switch B wording must match the product contract')
        self.assertRegex(
            body,
            r"id\s*=\s*['\"]rr_allow_repeat['\"][^>]*>|"
            r"type=\"checkbox\" id=\"rr_allow_repeat\"",
            'switch A must be a real checkbox input',
        )
        self.assertIn('type="checkbox"', body,
                      'both switches must be native checkboxes')

    def test_hide_today_is_never_preselected_and_not_chain_state(self):
        """Switch B defaults to unchecked on every form and lives outside state."""
        body = self._function_body('showReplaceReason')
        self.assertRegex(
            body,
            r"hideEl\.checked\s*=\s*false",
            'switch B must be reset to unchecked every time the form opens',
        )
        # AR03-G14: the chain state now lives in the ESM owner closure;
        # hide_today must still be read from the form, never persisted as
        # chain state.
        self.assertNotRegex(
            self.owner_js,
            r"hide_today\s*:\s*(?:gachaState|state)\.\w+",
            'hide_today must be read from the form, not kept in the owner state',
        )

    def test_replace_request_sends_chain_fields(self):
        """doReplace must send the three documented new fields."""
        body = self._function_body('doReplace')
        for field in (
            'replaced_task_ids', 'allow_repeat_replaced', 'hide_today',
        ):
            self.assertIn(field, body,
                          f'doReplace must send {field} to /api/gacha/replace')
        # Legacy fields must stay.
        for field in ('task_id', 'reason', 'pool', 'energy',
                      'available_time', 'preferred_tag'):
            self.assertIn(field, body,
                          f'doReplace must keep the legacy field {field}')

    def test_successful_replace_appends_to_chain_and_keeps_replacing(self):
        """A successful replace grows the chain and keeps canReplace true."""
        body = self._function_body('doReplace')
        # AR03-G14: the chain state now lives in the ESM owner's closure
        # (`state.replacedTaskIds` / `state.canReplace`).
        self.assertRegex(
            body,
            r"(?:gachaState|state)\.replacedTaskIds\s*=",
            'a successful replace must record the old id in the chain',
        )
        self.assertRegex(
            body,
            r"(?:gachaState|state)\.canReplace\s*=\s*true",
            'a single-draw replace must stay replaceable (no permanent false)',
        )
        # The failure path must not update the chain or the current card.
        catch_block = re.search(
            r"catch\s*\([^)]*\)\s*\{([\s\S]*?)\n\s*\}\s*\n\s*\}", body
        )
        self.assertTrue(catch_block, 'doReplace must have a catch block')
        self.assertNotIn('replacedTaskIds', catch_block.group(1),
                         'the failure path must not touch the chain')
        self.assertNotIn('currentTaskId', catch_block.group(1),
                         'the failure path must not touch the current card id')

    def test_chain_state_lives_in_gacha_state_not_localstorage(self):
        # AR03-G14: the chain state lives in the ESM owner's closure state,
        # not in classic app.js and never in localStorage.
        self.assertRegex(
            self.owner_js,
            r"replacedTaskIds\s*:",
            'the gacha owner state must carry the chain of replaced task ids',
        )
        self.assertRegex(
            self.owner_js,
            r"allowRepeatReplaced\s*:",
            'the gacha owner state must carry the allow-repeat switch state',
        )
        self.assertNotIn(
            'localStorage', self._function_body('doReplace'),
            'the chain must not be persisted to localStorage',
        )

    def test_chain_is_reset_on_accept_skip_refuse_new_draw_and_page_leave(self):
        """Every agreed chain end point must call resetReplaceChain."""
        resetter = self._function_body('resetReplaceChain')
        self.assertTrue(resetter, 'resetReplaceChain must exist')
        self.assertIn('replacedTaskIds', resetter)
        self.assertIn('allowRepeatReplaced', resetter)

        for name in ('showPage', 'startTask', 'handleSkip', 'handleRefuse',
                     'drawGacha', 'drawGachaMulti', 'drawGachaWithCategory'):
            with self.subTest(function=name):
                body = self._function_body(name)
                self.assertTrue(body, f'{name} must exist')
                self.assertIn(
                    'resetReplaceChain', body,
                    f'{name} must end the replace chain',
                )

    def test_multi_activated_card_still_cannot_be_replaced(self):
        """The multi-issued constraint (canReplace=false) must survive."""
        body = self._function_body('activateMultiCard')
        self.assertRegex(
            body,
            r"canReplace\s*=\s*false",
            'activateMultiCard must still disable replacement',
        )


if __name__ == '__main__':
    unittest.main()
