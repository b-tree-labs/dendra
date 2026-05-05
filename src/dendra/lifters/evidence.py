# Copyright (c) 2026 B-Tree Labs
# SPDX-License-Identifier: LicenseRef-BSL-1.1
"""Evidence lifter (Phase 3 of auto-lift).

Takes Python source plus a function name and emits a refactored
:class:`dendra.Switch` subclass in which each piece of hidden state
the original function read becomes its own ``_evidence_<name>``
method. The rule body is rewritten to consult ``evidence.<name>`` in
place of the original hidden-state expression.

v1 SAFE subset:

1. Module-global Name reads. Subscripted globals like
   ``FEATURE_FLAGS["fast_lane"]`` lift to a single field whose name
   is the subscript key.
2. ``self.<attr>`` reads (one level). ``self.cache_state`` lifts to a
   ``_evidence_cache_state`` method.
3. Mid-function binds: ``user = db.lookup(text)`` followed by a read
   of ``user`` (or ``user.<attr>``) inside a branch test. The bind
   line is dropped from the rule and reissued inside the gather.

v1.1 extensions:

4. Short-circuit Optional handling. ``if cheap_check(user) or
   expensive_db_lookup(user):`` lifts each Call operand into its own
   evidence field. Successive fields gate on prior fields so lazy
   evaluation semantics are preserved (later fields return ``None``
   when prior fields already short-circuited).
5. Mutable closure snapshot. Free variables read from an enclosing
   function (the ``flags`` in ``def make_router(flags): def route(text):
   if flags["fast_lane"]: ...``) lift to evidence fields. Mutable
   captures are read at dispatch time; ``typing.Final`` and frozen-type
   annotations get a default-arg snapshot taken once at decoration time.
6. ``@evidence_via_probe(field="probe_expr(...)")`` overrides the
   side_effect_evidence refusal: the lifter uses the probe expression
   for the gather and rewrites references to the dropped bind in the
   rule body to the new evidence field.
7. ``@evidence_inputs(field=lambda ...: ...)`` overrides the
   dynamic_dispatch refusal: the lifter emits the lambda body as the
   gather and rewrites matching expressions in the rule body to the
   new evidence field. Hazards not covered by an annotation still
   trigger refusal.

REFUSED categories:

- Side-effect-bearing evidence where the branch body itself runs
  side-effect statements AND no ``@evidence_via_probe`` annotation is
  present.
- Dynamic dispatch (``getattr``) not covered by ``@evidence_inputs``.
- ``eval`` / ``exec``.
- Zero-arg functions ("not a classifier of an input").
- Multi-arg functions whose parameters lack annotations.

The lifter delegates hazard detection to
:func:`dendra.analyzer.analyze_function_source` for top-level functions
and applies its own narrower refusals where the analyzer is broader
than the safe subset warrants.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass

from dendra.analyzer import LiftStatus, analyze_function_source
from dendra.lifters.branch import LiftRefused

# ----------------------------------------------------------------------
# Public API
# ----------------------------------------------------------------------


# Hazard categories the evidence lifter refuses on outright. We
# intentionally OMIT ``side_effect_evidence`` from this set: the safe
# subset includes mid-function binds (``user = db.lookup(text)``) which
# the analyzer flags broadly. The lifter applies its own narrower
# refusal in :func:`_check_side_effect_branches` so the analyzer's
# diagnostic stays informative without blocking the safe pattern.
_REFUSAL_CATEGORIES = {
    "not_a_classifier",
    "eval_exec",
    "dynamic_dispatch",
    "multi_arg_no_annotation",
}


def lift_evidence(source: str, function_name: str) -> str:
    """Lift hidden-state reads in ``function_name`` into evidence methods.

    Parameters
    ----------
    source:
        Full Python source containing the target function. The function
        may be at module level or nested inside another ``def`` (closure
        cases).
    function_name:
        The name of the ``def`` to lift.

    Returns
    -------
    str
        Source for a module that defines ``<FunctionName>Switch``.

    Raises
    ------
    LiftRefused
        On any safe-subset violation.
    """
    tree = ast.parse(source)
    func, enclosing = _find_function(tree, function_name)

    # Pull v1.1 annotations off the function's decorator list before any
    # hazard analysis. They override the analyzer's broader refusals for
    # the exact patterns they cover.
    probe_overrides = _extract_probe_overrides(func)
    inputs_overrides = _extract_inputs_overrides(func)

    # Delegate refusal detection to the analyzer for top-level functions.
    # Nested functions can't be analyzed (the analyzer requires a
    # top-level def), so we skip the delegation in that case and rely on
    # the lifter's own narrower checks.
    if enclosing is None:
        analysis = analyze_function_source(source, function_name)
        if analysis.lift_status is LiftStatus.REFUSED:
            for hz in analysis.hazards:
                if hz.severity != "error":
                    continue
                if hz.category not in _REFUSAL_CATEGORIES:
                    continue
                # Annotation overrides: the user has explicitly declared
                # a safe lift for this hazard category.
                if (
                    hz.category == "dynamic_dispatch"
                    and inputs_overrides
                    and _all_getattrs_covered(func, inputs_overrides)
                ):
                    continue
                raise LiftRefused(reason=f"{hz.category}: {hz.reason}", line=hz.line)

    arg_names = _validate_args(func)

    closure_names = _detect_closure_names(func, enclosing) if enclosing else set()
    closure_kinds = _classify_closure_captures(closure_names, enclosing)

    extraction = _extract_evidence(
        func,
        arg_names,
        probe_overrides=probe_overrides,
        inputs_overrides=inputs_overrides,
        closure_names=closure_names,
        closure_kinds=closure_kinds,
    )
    _check_side_effect_branches(extraction, probe_overrides)

    return _build_switch_module(func, arg_names, extraction, closure_kinds)


# ----------------------------------------------------------------------
# Internal data shapes
# ----------------------------------------------------------------------


@dataclass
class _Evidence:
    """One evidence field we plan to emit.

    ``name`` is the field name (also the suffix of the generated
    ``_evidence_<name>`` method). ``expr`` is the expression we'll
    return from the gatherer. ``replace_pred`` matches AST nodes in
    the rule body that should be rewritten to ``evidence.<name>``.
    """

    name: str
    expr: ast.expr
    replace_pred: object  # Callable[[ast.AST], bool]


@dataclass
class _Extraction:
    arg_passthroughs: list[_Evidence]
    hidden_evidence: list[_Evidence]
    rule_body: list[ast.stmt]  # function body with mid-func binds dropped
    branch_bodies_have_side_effects: bool
    # v1.1: short-circuit chains lift to a list of fields whose
    # gatherers depend on prior fields. Each entry is keyed by field
    # name and stores (gather_body, prior_field_names, op_kind) where
    # op_kind is "or" or "and" so the gather can short-circuit
    # consistently.
    short_circuit_chains: list[_ShortCircuitChain]


@dataclass
class _ShortCircuitChain:
    """A BoolOp lift plan. ``operands`` lists the per-Call evidence
    fields in source order; ``op`` is "or" or "and"; ``original_node``
    is the BoolOp the rule body must replace.
    """

    op: str
    operands: list[_Evidence]
    original_node: ast.BoolOp


# ----------------------------------------------------------------------
# Function lookup + arg validation
# ----------------------------------------------------------------------


def _find_function(tree: ast.Module, name: str) -> tuple[ast.FunctionDef, ast.FunctionDef | None]:
    """Locate ``name`` in ``tree`` and return ``(func, enclosing)``.

    ``enclosing`` is the immediately containing FunctionDef if ``func``
    is nested (the closure case), else ``None``. Top-level wins over
    nested definitions of the same name.
    """
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return node, None
    # Walk nested defs.
    for outer in ast.walk(tree):
        if not isinstance(outer, ast.FunctionDef):
            continue
        for inner in outer.body:
            if isinstance(inner, ast.FunctionDef) and inner.name == name:
                return inner, outer
    raise LiftRefused(reason=f"function {name!r} not found in source", line=0)


def _validate_args(func: ast.FunctionDef) -> list[str]:
    """Return positional arg names (excluding self/cls)."""
    posargs = list(func.args.posonlyargs) + list(func.args.args)
    if posargs and posargs[0].arg in ("self", "cls"):
        posargs = posargs[1:]
    if not posargs:
        raise LiftRefused(
            reason="not_a_classifier: zero-argument function",
            line=func.lineno,
        )
    return [a.arg for a in posargs]


# ----------------------------------------------------------------------
# v1.1: annotation extraction
# ----------------------------------------------------------------------


# Probe expressions that name any of these builtins are refused outright.
# An attacker-supplied annotation cannot turn `dendra init --auto-lift`
# into a code-injection vector: the literal probe string is spliced into
# generated source, so even though the LIFTER never `eval`s it, an
# unsuspecting user who later imports the generated module would fire it.
# We refuse so the unsafe expression never reaches the generated file.
_FORBIDDEN_PROBE_BUILTINS = frozenset(
    {"__import__", "eval", "exec", "compile", "open", "getattr", "setattr", "delattr"}
)


def _probe_calls_forbidden_builtin(expr: ast.expr) -> str | None:
    """Return the offending builtin name if ``expr`` calls any forbidden
    builtin (anywhere in its sub-expression tree), else None.
    """
    for node in ast.walk(expr):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id in _FORBIDDEN_PROBE_BUILTINS
        ):
            return node.func.id
    return None


def _extract_probe_overrides(func: ast.FunctionDef) -> dict[str, ast.expr]:
    """Pull ``@evidence_via_probe(field="probe_expr")`` annotations.

    Returns a dict mapping each declared field name to the parsed AST
    expression of the probe call. The decorator is removed from the
    function's decorator list in-place so codegen does not echo it.

    Refuses probe expressions that call any builtin in
    ``_FORBIDDEN_PROBE_BUILTINS``. Such probes would otherwise be
    spliced verbatim into generated source - a code-injection risk
    against any user who imports the generated module.
    """
    out: dict[str, ast.expr] = {}
    keep: list[ast.expr] = []
    for dec in func.decorator_list:
        if (
            isinstance(dec, ast.Call)
            and isinstance(dec.func, ast.Name)
            and dec.func.id == "evidence_via_probe"
        ):
            for kw in dec.keywords:
                if kw.arg is None or not isinstance(kw.value, ast.Constant):
                    continue
                if not isinstance(kw.value.value, str):
                    continue
                try:
                    parsed = ast.parse(kw.value.value, mode="eval").body
                except SyntaxError:
                    continue
                forbidden = _probe_calls_forbidden_builtin(parsed)
                if forbidden is not None:
                    raise LiftRefused(
                        reason=(
                            f"unsafe_probe: @evidence_via_probe({kw.arg}=...) "
                            f"calls forbidden builtin {forbidden!r}. The "
                            "probe expression is spliced into generated "
                            "code; refusing to write it to disk."
                        ),
                        line=getattr(dec, "lineno", 0),
                    )
                out[kw.arg] = parsed
            continue
        keep.append(dec)
    func.decorator_list = keep
    return out


def _extract_inputs_overrides(
    func: ast.FunctionDef,
) -> dict[str, ast.expr]:
    """Pull ``@evidence_inputs(field=lambda ...: <expr>)`` annotations.

    Returns a dict mapping each declared field name to the AST of the
    lambda's body expression. The decorator is removed from the
    function's decorator list in-place.
    """
    out: dict[str, ast.expr] = {}
    keep: list[ast.expr] = []
    for dec in func.decorator_list:
        if (
            isinstance(dec, ast.Call)
            and isinstance(dec.func, ast.Name)
            and dec.func.id == "evidence_inputs"
        ):
            for kw in dec.keywords:
                if kw.arg is None or not isinstance(kw.value, ast.Lambda):
                    continue
                out[kw.arg] = kw.value.body
            continue
        keep.append(dec)
    func.decorator_list = keep
    return out


def _all_getattrs_covered(func: ast.FunctionDef, inputs_overrides: dict[str, ast.expr]) -> bool:
    """True iff every ``getattr`` Call in ``func`` body appears as a
    sub-expression of at least one annotated lambda body. Annotations
    that don't cover all dynamic accesses leave the lifter in refuse.
    """
    covered_exprs = list(inputs_overrides.values())
    for node in ast.walk(func):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "getattr"
        ) and not any(_ast_contains(cov, node) for cov in covered_exprs):
            return False
    return True


def _ast_contains(haystack: ast.AST, needle: ast.AST) -> bool:
    """Structural equality search: True if ``needle`` appears anywhere
    inside ``haystack`` (or equals it).
    """
    needle_dump = ast.dump(needle)
    return any(ast.dump(sub) == needle_dump for sub in ast.walk(haystack))


# ----------------------------------------------------------------------
# v1.1: closure detection
# ----------------------------------------------------------------------


_FROZEN_TYPE_NAMES = {"str", "int", "float", "bool", "tuple", "frozenset", "bytes"}


def _detect_closure_names(func: ast.FunctionDef, enclosing: ast.FunctionDef) -> set[str]:
    """Return names read by ``func`` that resolve to a parameter or
    local of ``enclosing`` (i.e. closure captures, not globals).
    """
    enc_locals: set[str] = set()
    for arg in (
        list(enclosing.args.posonlyargs)
        + list(enclosing.args.args)
        + list(enclosing.args.kwonlyargs)
    ):
        enc_locals.add(arg.arg)
    for node in ast.walk(enclosing):
        if isinstance(node, ast.Assign):
            for tgt in node.targets:
                if isinstance(tgt, ast.Name):
                    enc_locals.add(tgt.id)

    func_locals: set[str] = set()
    for arg in list(func.args.posonlyargs) + list(func.args.args):
        func_locals.add(arg.arg)
    for node in ast.walk(func):
        if isinstance(node, ast.Assign):
            for tgt in node.targets:
                if isinstance(tgt, ast.Name):
                    func_locals.add(tgt.id)

    captured: set[str] = set()
    for node in ast.walk(func):
        if (
            isinstance(node, ast.Name)
            and isinstance(node.ctx, ast.Load)
            and node.id in enc_locals
            and node.id not in func_locals
        ):
            captured.add(node.id)
    return captured


def _classify_closure_captures(
    captured: set[str], enclosing: ast.FunctionDef | None
) -> dict[str, str]:
    """Classify each captured name as ``"frozen"`` (snapshot once at
    decoration time) or ``"mutable"`` (re-read every dispatch).

    Frozen if the enclosing parameter's annotation is ``Final``,
    ``Final[...]``, or one of the canonical frozen types
    (``str``, ``int``, ``tuple``, ``frozenset``).
    """
    if enclosing is None:
        return {}
    annotations: dict[str, ast.expr | None] = {}
    for arg in (
        list(enclosing.args.posonlyargs)
        + list(enclosing.args.args)
        + list(enclosing.args.kwonlyargs)
    ):
        annotations[arg.arg] = arg.annotation

    out: dict[str, str] = {}
    for name in captured:
        ann = annotations.get(name)
        out[name] = "frozen" if _annotation_is_frozen(ann) else "mutable"
    return out


def _annotation_is_frozen(ann: ast.expr | None) -> bool:
    if ann is None:
        return False
    # Plain `Final` or `Final[...]`.
    if isinstance(ann, ast.Name) and ann.id == "Final":
        return True
    if (
        isinstance(ann, ast.Subscript)
        and isinstance(ann.value, ast.Name)
        and ann.value.id == "Final"
    ):
        return True
    # Bare frozen-type names.
    return bool(isinstance(ann, ast.Name) and ann.id in _FROZEN_TYPE_NAMES)


# ----------------------------------------------------------------------
# Evidence extraction
# ----------------------------------------------------------------------


def _extract_evidence(
    func: ast.FunctionDef,
    arg_names: list[str],
    *,
    probe_overrides: dict[str, ast.expr] | None = None,
    inputs_overrides: dict[str, ast.expr] | None = None,
    closure_names: set[str] | None = None,
    closure_kinds: dict[str, str] | None = None,
) -> _Extraction:
    """Walk the function body and build the lifter plan.

    Order of fields in the output:
      1. One passthrough evidence per arg.
      2. v1.1 ``@evidence_inputs`` and ``@evidence_via_probe`` annotated
         fields (in declaration order).
      3. Hidden-state evidence in source order (subscripted globals,
         ``self.<attr>`` reads, mid-function binds, closure captures,
         short-circuit operands).
    """
    probe_overrides = probe_overrides or {}
    inputs_overrides = inputs_overrides or {}
    closure_names = closure_names or set()
    closure_kinds = closure_kinds or {}

    body = list(func.body)
    # Strip a leading docstring if present.
    if (
        body
        and isinstance(body[0], ast.Expr)
        and isinstance(body[0].value, ast.Constant)
        and isinstance(body[0].value.value, str)
    ):
        body = body[1:]

    arg_passthroughs = [
        _Evidence(
            name=name,
            expr=ast.Name(id=name, ctx=ast.Load()),
            replace_pred=_match_bare_name(name),
        )
        for name in arg_names
    ]

    seen_field_names: set[str] = {ev.name for ev in arg_passthroughs}
    annotation_evidence: list[_Evidence] = []

    # v1.1: @evidence_inputs annotations. Each lambda's body becomes a
    # gather; rule-body matches against the body expression rewrite to
    # evidence.<field>.
    for field, gather_body in inputs_overrides.items():
        seen_field_names.add(field)
        annotation_evidence.append(
            _Evidence(
                name=field,
                expr=gather_body,
                replace_pred=_match_ast_equals(gather_body),
            )
        )

    # First-pass strip: collect mid-function ``Assign-to-Call`` binds.
    # ``@evidence_via_probe`` reroutes a bind into an annotation field
    # using the probe expression as the gather; the original side-effect
    # call line is dropped from the rule body so the branch lifter can
    # later relocate it into the chosen ``_on_*`` handler. Without an
    # annotation, the bind lifts as v1's standard mid-bind evidence.
    bind_evidence: list[_Evidence] = []
    bind_names: set[str] = set()
    rule_body: list[ast.stmt] = []
    probe_field_iter = iter(probe_overrides.items()) if probe_overrides else None
    for stmt in body:
        if (
            isinstance(stmt, ast.Assign)
            and len(stmt.targets) == 1
            and isinstance(stmt.targets[0], ast.Name)
            and isinstance(stmt.value, ast.Call)
        ):
            bind_name = stmt.targets[0].id
            if _name_read_after(bind_name, body, after=stmt):
                if probe_field_iter is not None:
                    try:
                        field, probe_expr = next(probe_field_iter)
                    except StopIteration:
                        rule_body.append(stmt)
                        continue
                    seen_field_names.add(field)
                    # If the probe expression already extracts a trailing
                    # attribute (e.g. ``api.charge_probe(req).ok``), match
                    # ``<bind>.<that_attr>`` in the rule body and replace
                    # the whole Attribute (so we don't double-access).
                    probe_attr = _trailing_attr(probe_expr)
                    if probe_attr is not None:
                        _refuse_if_attr_mismatch(body, bind_name, probe_attr, field)
                        pred = _match_name_attr(bind_name, probe_attr)
                    else:
                        pred = _match_bare_name(bind_name)
                    annotation_evidence.append(
                        _Evidence(
                            name=field,
                            expr=probe_expr,
                            replace_pred=pred,
                        )
                    )
                    continue
                bind_evidence.append(
                    _Evidence(
                        name=bind_name,
                        expr=stmt.value,
                        replace_pred=_match_bare_name(bind_name),
                    )
                )
                bind_names.add(bind_name)
                seen_field_names.add(bind_name)
                continue
        rule_body.append(stmt)

    arg_set = set(arg_names)

    # v1.1: detect short-circuit BoolOp(Or/And, [Call, Call, ...]) in If
    # tests and lift each Call operand to an evidence field.
    short_circuit_chains: list[_ShortCircuitChain] = []
    for stmt in rule_body:
        for if_node in _iter_if_nodes(stmt):
            test = if_node.test
            if isinstance(test, ast.BoolOp) and all(isinstance(v, ast.Call) for v in test.values):
                op = "or" if isinstance(test.op, ast.Or) else "and"
                operand_fields: list[_Evidence] = []
                for call in test.values:
                    field_name = _short_circuit_field_name(call, seen_field_names)
                    seen_field_names.add(field_name)
                    operand_fields.append(
                        _Evidence(
                            name=field_name,
                            expr=call,
                            replace_pred=lambda _n: False,  # rewrite handled at chain level
                        )
                    )
                short_circuit_chains.append(
                    _ShortCircuitChain(
                        op=op,
                        operands=operand_fields,
                        original_node=test,
                    )
                )

    # Second pass: hidden-state reads (globals, self.attr, closures).
    hidden_evidence: list[_Evidence] = []

    # Track parent links so we can tell whether a Name(closure) read is
    # a bare reference (lift the whole capture) or a sub-node of a
    # Subscript/Attribute (lift the specific subscript instead).
    parent_map = _parent_map(rule_body)

    # First, lift closure Subscripts. Mark the closure var as "consumed"
    # so the bare-Name pass below skips redundant whole-capture lifts.
    closure_consumed: set[str] = set()
    for node in _walk_rule_nodes(rule_body):
        if (
            isinstance(node, ast.Subscript)
            and isinstance(node.value, ast.Name)
            and node.value.id in closure_names
            and isinstance(node.slice, ast.Constant)
            and isinstance(node.slice.value, str)
        ):
            field_name = _safe_field_name(node.slice.value, seen_field_names)
            if field_name in seen_field_names:
                continue
            seen_field_names.add(field_name)
            closure_consumed.add(node.value.id)
            hidden_evidence.append(
                _Evidence(
                    name=field_name,
                    expr=node,
                    replace_pred=_match_subscript(node),
                )
            )

    for node in _walk_rule_nodes(rule_body):
        # Closure captures: Name reads that resolve to enclosing scope
        # AND are not already consumed by a subscript lift. We also
        # require the Name to appear as a stand-alone value (not as the
        # ``.value`` of a Subscript/Attribute) so we don't double-lift.
        if (
            isinstance(node, ast.Name)
            and isinstance(node.ctx, ast.Load)
            and node.id in closure_names
            and node.id not in arg_set
            and node.id not in closure_consumed
        ):
            parent = parent_map.get(id(node))
            if isinstance(parent, ast.Subscript) and parent.value is node:
                continue
            if isinstance(parent, ast.Attribute) and parent.value is node:
                # `flags.attr` would mean we lift `flags.attr`, not `flags`.
                # Emit the bare closure as evidence; rule body matches `flags`.
                pass
            field_name = _safe_field_name(node.id, seen_field_names)
            if field_name in seen_field_names:
                continue
            seen_field_names.add(field_name)
            hidden_evidence.append(
                _Evidence(
                    name=field_name,
                    expr=ast.Name(id=node.id, ctx=ast.Load()),
                    replace_pred=_match_bare_name(node.id),
                )
            )
            continue

        # Subscripted module global: FEATURE_FLAGS["fast_lane"]
        if (
            isinstance(node, ast.Subscript)
            and isinstance(node.value, ast.Name)
            and node.value.id not in arg_set
            and node.value.id != "self"
            and node.value.id not in closure_names
            and isinstance(node.slice, ast.Constant)
            and isinstance(node.slice.value, str)
        ):
            field_name = _safe_field_name(node.slice.value, seen_field_names)
            if field_name in seen_field_names:
                continue
            seen_field_names.add(field_name)
            target_node = node
            hidden_evidence.append(
                _Evidence(
                    name=field_name,
                    expr=target_node,
                    replace_pred=_match_subscript(target_node),
                )
            )
            continue

        # self.<attr>
        if (
            isinstance(node, ast.Attribute)
            and isinstance(node.value, ast.Name)
            and node.value.id == "self"
        ):
            field_name = _safe_field_name(node.attr, seen_field_names)
            if field_name in seen_field_names:
                continue
            seen_field_names.add(field_name)
            hidden_evidence.append(
                _Evidence(
                    name=field_name,
                    expr=ast.Attribute(
                        value=ast.Name(id="self", ctx=ast.Load()),
                        attr=node.attr,
                        ctx=ast.Load(),
                    ),
                    replace_pred=_match_self_attr(node.attr),
                )
            )
            continue

    short_circuit_evidence: list[_Evidence] = []
    for chain in short_circuit_chains:
        short_circuit_evidence.extend(chain.operands)

    return _Extraction(
        arg_passthroughs=arg_passthroughs,
        hidden_evidence=(
            annotation_evidence + bind_evidence + short_circuit_evidence + hidden_evidence
        ),
        rule_body=rule_body,
        branch_bodies_have_side_effects=_any_branch_body_has_side_effects(rule_body),
        short_circuit_chains=short_circuit_chains,
    )


def _iter_if_nodes(stmt: ast.stmt):
    for node in ast.walk(stmt):
        if isinstance(node, ast.If):
            yield node


def _short_circuit_field_name(call: ast.Call, taken: set[str]) -> str:
    """Derive a field name for a short-circuit Call operand.

    Convention: take the first underscore-segment of the called func's
    name (e.g. ``cheap_check`` → ``cheap``) and append ``_ok``. For
    attribute calls like ``api.charge(req)``, use the attribute name's
    first segment.
    """
    raw = _call_func_root_name(call)
    base = f"{raw}_ok" if raw else "field_ok"
    return _safe_field_name(base, taken)


def _call_func_root_name(call: ast.Call) -> str:
    func = call.func
    if isinstance(func, ast.Name):
        first = func.id.split("_", 1)[0]
        return first
    if isinstance(func, ast.Attribute):
        first = func.attr.split("_", 1)[0]
        return first
    return ""


def _match_ast_equals(target: ast.expr):
    """Predicate matching any AST node structurally equal to ``target``."""
    target_dump = ast.dump(target)

    def pred(node: ast.AST) -> bool:
        return ast.dump(node) == target_dump

    return pred


def _walk_rule_nodes(stmts: list[ast.stmt]):
    for stmt in stmts:
        yield from ast.walk(stmt)


def _parent_map(stmts: list[ast.stmt]) -> dict[int, ast.AST]:
    """Build an id-keyed map from each AST node to its immediate parent.

    Used to disambiguate ``Name`` reads that appear as the ``.value`` of
    a ``Subscript`` or ``Attribute`` (sub-expression) versus standalone.
    """
    out: dict[int, ast.AST] = {}
    for stmt in stmts:
        for parent in ast.walk(stmt):
            for child in ast.iter_child_nodes(parent):
                out[id(child)] = parent
    return out


def _name_read_after(name: str, body: list[ast.stmt], after: ast.stmt) -> bool:
    seen = False
    for stmt in body:
        if stmt is after:
            seen = True
            continue
        if not seen:
            continue
        for sub in ast.walk(stmt):
            if isinstance(sub, ast.Name) and sub.id == name and isinstance(sub.ctx, ast.Load):
                return True
    return False


def _safe_field_name(raw: str, taken: set[str]) -> str:
    """Coerce an arbitrary string into a valid Python identifier and
    de-collide against names already in use.
    """
    out = "".join(ch if ch.isalnum() or ch == "_" else "_" for ch in raw)
    if not out or out[0].isdigit():
        out = f"_{out}"
    base = out
    n = 2
    while out in taken:
        out = f"{base}_{n}"
        n += 1
    return out


# ----------------------------------------------------------------------
# Predicate factories - each returns a callable matching specific AST
# shapes the rule rewriter should replace with ``evidence.<name>``.
# ----------------------------------------------------------------------


def _match_bare_name(name: str):
    def pred(node: ast.AST) -> bool:
        return isinstance(node, ast.Name) and node.id == name and isinstance(node.ctx, ast.Load)

    return pred


def _match_name_attr(name: str, attr: str):
    """Match ``Attribute(Name(name), attr)`` in Load context.

    Used when an ``@evidence_via_probe`` expression already extracts a
    trailing attribute, so the rule body's ``<bind>.<attr>`` should
    rewrite to ``evidence.<field>`` (dropping the redundant ``.attr``).
    """

    def pred(node: ast.AST) -> bool:
        return (
            isinstance(node, ast.Attribute)
            and isinstance(node.value, ast.Name)
            and node.value.id == name
            and node.attr == attr
            and isinstance(node.ctx, ast.Load)
        )

    return pred


def _trailing_attr(expr: ast.expr) -> str | None:
    """Return the trailing ``.attr`` of an expression, if any.

    ``api.charge_probe(req).ok`` -> ``"ok"``. ``api.charge_probe(req)``
    -> ``None``. We only consider the outermost shape: an Attribute
    whose ``.value`` is a Call (or anything other than a bare Name) is
    a meaningful trailing attribute the probe extracts.
    """
    if isinstance(expr, ast.Attribute) and not isinstance(expr.value, ast.Name):
        return expr.attr
    return None


def _refuse_if_attr_mismatch(
    body: list[ast.stmt], bind_name: str, probe_attr: str, field: str
) -> None:
    """Refuse if the rule body accesses ``<bind>.<other_attr>`` where
    ``other_attr`` differs from the probe's trailing attribute. The
    probe extracted ``probe_attr``, so any other attribute access on
    the dropped bind cannot be served by the lifted evidence.
    """
    for stmt in body:
        for node in ast.walk(stmt):
            if (
                isinstance(node, ast.Attribute)
                and isinstance(node.value, ast.Name)
                and node.value.id == bind_name
                and node.attr != probe_attr
            ):
                raise LiftRefused(
                    reason=(
                        f"evidence_via_probe: probe for field {field!r} "
                        f"extracts .{probe_attr} but the rule body reads "
                        f".{node.attr} on {bind_name!r}; the lifted "
                        "evidence cannot serve a different attribute"
                    ),
                    line=getattr(node, "lineno", 0),
                )


def _match_subscript(target: ast.Subscript):
    target_value_id = target.value.id  # type: ignore[attr-defined]
    target_key = target.slice.value  # type: ignore[attr-defined]

    def pred(node: ast.AST) -> bool:
        return (
            isinstance(node, ast.Subscript)
            and isinstance(node.value, ast.Name)
            and node.value.id == target_value_id
            and isinstance(node.slice, ast.Constant)
            and node.slice.value == target_key
        )

    return pred


def _match_self_attr(attr: str):
    def pred(node: ast.AST) -> bool:
        return (
            isinstance(node, ast.Attribute)
            and isinstance(node.value, ast.Name)
            and node.value.id == "self"
            and node.attr == attr
        )

    return pred


# ----------------------------------------------------------------------
# Side-effect refusal - narrower than the analyzer's
# ----------------------------------------------------------------------


def _any_branch_body_has_side_effects(rule_body: list[ast.stmt]) -> bool:
    """True if any if/elif branch body contains a statement other than
    a single ``return`` of a literal. Mid-function binds were already
    pulled out, so anything left in a branch body is action-shaped.
    """
    for stmt in rule_body:
        for sub in ast.walk(stmt):
            if isinstance(sub, ast.If) and (
                _branch_body_has_side_effects(sub.body) or _branch_body_has_side_effects(sub.orelse)
            ):
                return True
    return False


def _branch_body_has_side_effects(stmts: list[ast.stmt]) -> bool:
    for stmt in stmts:
        if isinstance(stmt, ast.If):
            # Recurse via _any_branch_body_has_side_effects on caller side.
            continue
        if isinstance(stmt, ast.Return):
            continue
        return True
    return False


def _check_side_effect_branches(
    extraction: _Extraction, probe_overrides: dict[str, ast.expr] | None = None
) -> None:
    """Refuse when a mid-function bind is present AND any branch body
    has side-effect statements. That's the ``response = api.charge(...);
    if response.ok: notify(req); return 'charged'`` pattern: lifting
    the gather would replay the side-effect call on every dispatch
    while the branch action runs separately, the very pattern the
    analyzer's ``side_effect_evidence`` hazard warns about.

    ``@evidence_via_probe`` overrides the refusal when the user has
    declared a probe for the bind: the lifter substitutes the probe in
    the gather, and the original side-effect call is left in the rule
    body for the branch lifter to relocate into the chosen ``_on_*``
    handler.
    """
    if probe_overrides:
        return
    has_mid_bind = any(isinstance(ev.expr, ast.Call) for ev in extraction.hidden_evidence)
    if has_mid_bind and extraction.branch_bodies_have_side_effects:
        raise LiftRefused(
            reason=(
                "side_effect_evidence: a mid-function call result is read in "
                "a branch test AND that branch runs side-effect statements; "
                "lifting the gather would re-fire side effects every dispatch"
            ),
            line=0,
        )


# ----------------------------------------------------------------------
# Codegen
# ----------------------------------------------------------------------


def _class_name_for(func_name: str) -> str:
    parts = func_name.split("_")
    camel = "".join(p[:1].upper() + p[1:] for p in parts if p)
    return f"{camel}Switch"


def _build_switch_module(
    func: ast.FunctionDef,
    arg_names: list[str],
    extraction: _Extraction,
    closure_kinds: dict[str, str] | None = None,
) -> str:
    class_name = _class_name_for(func.name)
    closure_kinds = closure_kinds or {}

    module_body: list[ast.stmt] = []
    module_body.append(
        ast.ImportFrom(
            module="dendra",
            names=[ast.alias(name="Switch", asname=None)],
            level=0,
        )
    )
    module_body.append(_build_switch_class(class_name, func, arg_names, extraction, closure_kinds))

    new_module = ast.Module(body=module_body, type_ignores=[])
    ast.fix_missing_locations(new_module)
    return ast.unparse(new_module)


def _build_switch_class(
    class_name: str,
    func: ast.FunctionDef,
    arg_names: list[str],
    extraction: _Extraction,
    closure_kinds: dict[str, str],
) -> ast.ClassDef:
    body: list[ast.stmt] = []
    all_evidence = extraction.arg_passthroughs + extraction.hidden_evidence
    # Track which arg-names per evidence method need a short-circuit
    # gating prefix.
    chain_priors = _short_circuit_priors(extraction.short_circuit_chains)
    for ev in all_evidence:
        kind = closure_kinds.get(_evidence_capture_name(ev))
        priors = chain_priors.get(ev.name)
        body.append(
            _build_evidence_method(
                ev, func, arg_names, closure_kind=kind, short_circuit_priors=priors
            )
        )
    body.append(_build_rule(arg_names, extraction))

    return ast.ClassDef(
        name=class_name,
        bases=[ast.Name(id="Switch", ctx=ast.Load())],
        keywords=[],
        body=body,
        decorator_list=[],
        type_params=[],
    )


def _short_circuit_priors(
    chains: list[_ShortCircuitChain],
) -> dict[str, tuple[str, list[str]]]:
    """For each operand field after the first in any chain, list the
    prior-field names whose truthiness short-circuits this one.

    Returns ``field_name -> (op, [prior_field_names])``.
    """
    out: dict[str, tuple[str, list[str]]] = {}
    for chain in chains:
        priors: list[str] = []
        for ev in chain.operands:
            if priors:
                out[ev.name] = (chain.op, list(priors))
            priors.append(ev.name)
    return out


def _evidence_capture_name(ev: _Evidence) -> str:
    """Return the closure variable name an evidence wraps, if any.

    Matches both bare-Name evidence (``flags``) and Subscript evidence
    whose value is a Name (``flags["fast_lane"]`` carries ``flags``).
    """
    if isinstance(ev.expr, ast.Name):
        return ev.expr.id
    if isinstance(ev.expr, ast.Subscript) and isinstance(ev.expr.value, ast.Name):
        return ev.expr.value.id
    return ""


def _build_evidence_method(
    ev: _Evidence,
    func: ast.FunctionDef,
    arg_names: list[str],
    *,
    closure_kind: str | None = None,
    short_circuit_priors: tuple[str, list[str]] | None = None,
) -> ast.FunctionDef:
    """Build a single ``_evidence_<name>`` method.

    Method args mirror the original function's positional parameters
    (preserving annotations) so the Switch base class can build its
    evidence dataclass schema. ``closure_kind`` adds a default-arg
    snapshot for frozen closure captures plus a docstring noting the
    snapshot timing. ``short_circuit_priors`` injects gate logic so
    later operands return ``None`` when prior operands already
    short-circuited.
    """
    args = [ast.arg(arg="self", annotation=None)]
    arg_lookup = {a.arg: a for a in (list(func.args.posonlyargs) + list(func.args.args))}
    for name in arg_names:
        original = arg_lookup.get(name)
        annotation = original.annotation if original is not None else None
        args.append(ast.arg(arg=name, annotation=annotation))

    defaults: list[ast.expr] = []
    body: list[ast.stmt] = []

    if closure_kind == "frozen":
        # Default arg snapshot: evaluated once at class-body execution.
        capture_name = _evidence_capture_name(ev)
        captured_arg = f"_captured_{capture_name}"
        args.append(ast.arg(arg=captured_arg, annotation=None))
        defaults.append(ast.Name(id=capture_name, ctx=ast.Load()))
        body.append(
            ast.Expr(
                value=ast.Constant(
                    value=(
                        f"Decoration-time snapshot: closure `{capture_name}` "
                        "annotated as Final or a frozen type, captured once."
                    )
                )
            )
        )
        # Replace the live closure name with the captured arg in the
        # gather expression.
        gather_expr = _replace_name(ev.expr, capture_name, captured_arg)
        body.append(ast.Return(value=gather_expr))
    elif closure_kind == "mutable":
        capture_name = _evidence_capture_name(ev)
        body.append(
            ast.Expr(
                value=ast.Constant(
                    value=(
                        f"Dispatch-time snapshot: re-reads closure `{capture_name}` on every call."
                    )
                )
            )
        )
        body.append(ast.Return(value=ev.expr))
    elif short_circuit_priors is not None:
        op, priors = short_circuit_priors
        # Build the gating prefix: for ``or``, return None when ANY prior
        # field is truthy. For ``and``, return None when ANY prior field
        # is falsy.
        for prior in priors:
            call_prior = ast.Call(
                func=ast.Attribute(
                    value=ast.Name(id="self", ctx=ast.Load()),
                    attr=f"_evidence_{prior}",
                    ctx=ast.Load(),
                ),
                args=[ast.Name(id=n, ctx=ast.Load()) for n in arg_names],
                keywords=[],
            )
            if op == "or":
                test: ast.expr = call_prior
            else:  # "and"
                test = ast.UnaryOp(op=ast.Not(), operand=call_prior)
            body.append(
                ast.If(
                    test=test,
                    body=[ast.Return(value=ast.Constant(value=None))],
                    orelse=[],
                )
            )
        body.append(ast.Return(value=ev.expr))
    else:
        body.append(ast.Return(value=ev.expr))

    return ast.FunctionDef(
        name=f"_evidence_{ev.name}",
        args=ast.arguments(
            posonlyargs=[],
            args=args,
            vararg=None,
            kwonlyargs=[],
            kw_defaults=[],
            kwarg=None,
            defaults=defaults,
        ),
        body=body,
        decorator_list=[],
        returns=ast.Name(id="object", ctx=ast.Load()),
        type_params=[],
    )


def _replace_name(expr: ast.expr, old: str, new: str) -> ast.expr:
    """Return a clone of ``expr`` with every ``Name(old)`` rewritten to
    ``Name(new)``.
    """
    cloned = _clone(expr)

    class _Renamer(ast.NodeTransformer):
        def visit_Name(self, node: ast.Name) -> ast.AST:  # noqa: N802
            if node.id == old:
                return ast.Name(id=new, ctx=node.ctx)
            return node

    return _Renamer().visit(cloned)


def _build_rule(arg_names: list[str], extraction: _Extraction) -> ast.FunctionDef:
    """Build ``_rule(self, evidence)``.

    For each piece of evidence with a non-trivial source (hidden state),
    rewrite matching nodes in the rule body to ``evidence.<name>``.
    For arg passthroughs, rebind the local at the top of the rule
    *only if* the rewritten body still reads the bare arg name.

    Short-circuit chains are rewritten BEFORE per-evidence rewrites so
    the BoolOp's component Calls don't double-match (a short-circuit
    operand can otherwise look like a normal mid-bind expression).
    """
    sc_rewritten = _rewrite_short_circuit(extraction.rule_body, extraction.short_circuit_chains)
    rewritten = _rewrite_body(sc_rewritten, extraction.hidden_evidence)

    body: list[ast.stmt] = []
    for arg_name in arg_names:
        if _name_used_in(arg_name, rewritten):
            body.append(
                ast.Assign(
                    targets=[ast.Name(id=arg_name, ctx=ast.Store())],
                    value=ast.Attribute(
                        value=ast.Name(id="evidence", ctx=ast.Load()),
                        attr=arg_name,
                        ctx=ast.Load(),
                    ),
                )
            )
    body.extend(rewritten)

    return ast.FunctionDef(
        name="_rule",
        args=ast.arguments(
            posonlyargs=[],
            args=[
                ast.arg(arg="self", annotation=None),
                ast.arg(arg="evidence", annotation=None),
            ],
            vararg=None,
            kwonlyargs=[],
            kw_defaults=[],
            kwarg=None,
            defaults=[],
        ),
        body=body,
        decorator_list=[],
        returns=ast.Name(id="str", ctx=ast.Load()),
        type_params=[],
    )


def _rewrite_body(body: list[ast.stmt], evidence: list[_Evidence]) -> list[ast.stmt]:
    """Return a rewritten copy of ``body`` where every node matching an
    evidence's predicate is replaced with ``evidence.<name>``.
    """
    return [_RewriteEvidence(evidence).visit(_clone(stmt)) for stmt in body]


def _rewrite_short_circuit(
    body: list[ast.stmt], chains: list[_ShortCircuitChain]
) -> list[ast.stmt]:
    """Replace each chain's ``BoolOp`` original_node with a ``BoolOp``
    over ``evidence.<field>`` references.
    """
    if not chains:
        return body
    return [_RewriteShortCircuit(chains).visit(_clone(stmt)) for stmt in body]


class _RewriteShortCircuit(ast.NodeTransformer):
    def __init__(self, chains: list[_ShortCircuitChain]) -> None:
        self._chains = chains

    def visit_BoolOp(self, node: ast.BoolOp) -> ast.AST:  # noqa: N802
        for chain in self._chains:
            if ast.dump(node) == ast.dump(chain.original_node):
                return ast.BoolOp(
                    op=chain.original_node.op,
                    values=[
                        ast.Attribute(
                            value=ast.Name(id="evidence", ctx=ast.Load()),
                            attr=ev.name,
                            ctx=ast.Load(),
                        )
                        for ev in chain.operands
                    ],
                )
        return self.generic_visit(node)


def _clone(node):
    """Deep-clone a node so mutating the copy doesn't affect the input."""
    if isinstance(node, list):
        return [_clone(n) for n in node]
    if not isinstance(node, ast.AST):
        return node
    new = type(node)()
    for field, value in ast.iter_fields(node):
        if isinstance(value, list):
            setattr(new, field, [_clone(v) for v in value])
        elif isinstance(value, ast.AST):
            setattr(new, field, _clone(value))
        else:
            setattr(new, field, value)
    for attr in ("lineno", "col_offset", "end_lineno", "end_col_offset"):
        if hasattr(node, attr):
            setattr(new, attr, getattr(node, attr))
    return new


class _RewriteEvidence(ast.NodeTransformer):
    """Replace AST nodes matching any evidence's predicate with
    ``evidence.<name>``.
    """

    def __init__(self, evidence: list[_Evidence]) -> None:
        self._evidence = evidence

    def visit(self, node):
        for ev in self._evidence:
            if ev.replace_pred(node):  # type: ignore[misc]
                return ast.Attribute(
                    value=ast.Name(id="evidence", ctx=ast.Load()),
                    attr=ev.name,
                    ctx=ast.Load(),
                )
        return self.generic_visit(node)


def _name_used_in(name: str, stmts: list[ast.stmt]) -> bool:
    for stmt in stmts:
        for sub in ast.walk(stmt):
            if isinstance(sub, ast.Name) and sub.id == name and isinstance(sub.ctx, ast.Load):
                return True
    return False
