# Copyright (c) 2026 B-Tree Labs
# SPDX-License-Identifier: LicenseRef-BSL-1.1
"""Branch-body lifter (Phase 2 of auto-lift).

Takes Python source plus a function name and emits a refactored
:class:`postrule.Switch` subclass:

- Each ``if``/``elif``/``else`` (or ``match``/``case``) branch's
  pre-return statements move into a generated ``_on_<label>`` method.
- The function body becomes the ``_rule`` method, reduced to the
  same branch chain but with each branch's body collapsed to a
  bare ``return <label>``.
- A trivial ``_evidence_input`` returns the raw input so the inner
  ``Switch`` machinery has a typed evidence field. Phase 3 will
  replace this with real evidence lifting.

The lifter is conservative: anything outside the documented safe
subset raises :class:`LiftRefused` with a structured reason. This
file deliberately does not import from
``postrule.decorator`` / ``postrule.switch_class`` — its output imports
from them, not the other way around.
"""

from __future__ import annotations

import ast
import sys
import threading
from dataclasses import dataclass

# ----------------------------------------------------------------------
# Public exception
# ----------------------------------------------------------------------


class LiftRefused(Exception):
    """Raised when a function falls outside the lifter's safe subset.

    Carries a human-readable :attr:`reason` and the source :attr:`line`
    that triggered the refusal. The CLI surfaces both in its
    diagnostic output.
    """

    def __init__(self, reason: str, line: int = 0) -> None:
        super().__init__(f"{reason} (line {line})")
        self.reason = reason
        self.line = line


# ----------------------------------------------------------------------
# Internal data shapes
# ----------------------------------------------------------------------


@dataclass
class _Branch:
    """One concrete branch we extracted from the function."""

    label: str  # the literal string returned by the branch
    test: ast.expr | None  # condition (None for else / wildcard)
    body: list[ast.stmt]  # pre-return statements
    return_lineno: int  # for diagnostics
    is_else: bool = False  # True for the trailing else / case _


@dataclass
class _Bind:
    """A leading-bind we plan to lift to ``_evidence_<name>``.

    v1.5 relaxation 2. ``name`` is the local variable; ``rhs`` is the
    full RHS expression (a ``Call``, attribute chain, comparison, etc.).
    The RHS is validated to only reference function args and
    previously-bound names so the gather can be evaluated against the
    function's inputs alone.
    """

    name: str
    rhs: ast.expr
    lineno: int


@dataclass
class _ExtractionResult:
    """Bundle of what _extract_branches produces."""

    branches: list[_Branch]
    leading_stmts: list[ast.stmt]
    chain_kind: str  # "if", "match", or "multi_if" (v1.5 relaxation 1)
    chain_node: ast.AST | None  # the original If / Match node; None for multi_if
    has_trailing_default: bool  # True if a bare `return <lit>` followed an if/elif
    trailing_default_label: str | None
    # v1.5 relaxation 2: leading binds lifted to evidence methods.
    leading_binds: list[_Bind] = None  # type: ignore[assignment]
    # v1.5 relaxation 1: multi-top-level-if preserves each user-written
    # if/elif group so the rule body keeps the original elif structure.
    multi_if_groups: list[ast.If] = None  # type: ignore[assignment]
    multi_if_default_body: list[ast.stmt] = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        if self.leading_binds is None:
            self.leading_binds = []
        if self.multi_if_groups is None:
            self.multi_if_groups = []
        if self.multi_if_default_body is None:
            self.multi_if_default_body = []


# ----------------------------------------------------------------------
# Public API
# ----------------------------------------------------------------------


def lift_branches(
    source: str,
    function_name: str,
    *,
    allow_multi_top_level_if: bool = True,
    allow_leading_bind: bool = True,
) -> str:
    """Lift the branch bodies of ``function_name`` into a Switch subclass.

    Parameters
    ----------
    source:
        Full Python source containing the target function.
    function_name:
        The name of the ``def`` to lift. Must be a top-level function
        (nested functions are out of scope for v1.1).
    allow_multi_top_level_if:
        v1.5 relaxation 1. When True (default), accept a flat sequence
        of ``if cond: ... return`` statements at the top level of the
        function body, optionally followed by a bare ``return <literal>``
        default. Set False to restore the strict v1.1 single-elif-chain
        contract.
    allow_leading_bind:
        v1.5 relaxation 2. When True (default), accept simple
        assignments before the if/elif chain (e.g. ``title = x.lower()``)
        and lift each one to an ``_evidence_<name>`` method. Set False
        to restore the strict v1.1 no-leading-state contract.

    Returns
    -------
    str
        Source for a module that defines ``<FunctionName>Switch`` and
        is syntactically valid Python.

    Raises
    ------
    LiftRefused
        If the function is not present, has zero args, contains
        dynamic dispatch (``getattr`` / ``eval`` / ``exec``), shares
        mid-function state across branches, has try/except in a
        branch body, or returns a computed (non-literal) value.
    """
    tree = ast.parse(source)
    func = _find_function(tree, function_name)
    return _build_switch_module_safe(
        func,
        allow_multi_top_level_if=allow_multi_top_level_if,
        allow_leading_bind=allow_leading_bind,
    )


def _build_switch_module_safe(
    func: ast.FunctionDef,
    *,
    allow_multi_top_level_if: bool,
    allow_leading_bind: bool,
) -> str:
    """Drive the build on a worker thread with a large native stack.

    Long ``if/elif`` chains produce a deeply-nested AST. Even after
    iterating our own walks, stdlib helpers (``ast.fix_missing_locations``,
    ``ast.unparse``) recurse once per nesting level. A 1000-deep chain
    therefore needs a recursion budget the default thread can't supply.

    We run the build in a worker thread sized for ~50k frames and a
    matching ``sys.setrecursionlimit``. Both bumps are local to that
    thread; the main interpreter limit is restored on exit. Issue #137.
    """
    result: dict[str, object] = {}

    def _runner() -> None:
        prev = sys.getrecursionlimit()
        try:
            sys.setrecursionlimit(max(prev, 50_000))
            result["out"] = _build_switch_module(
                func,
                allow_multi_top_level_if=allow_multi_top_level_if,
                allow_leading_bind=allow_leading_bind,
            )
        except BaseException as exc:  # noqa: BLE001
            result["err"] = exc
        finally:
            sys.setrecursionlimit(prev)

    # 64 MB of native stack covers ~50k Python frames in practice;
    # default 8 MB is the bottleneck for 1000-deep elif on macOS.
    worker = threading.Thread(
        target=_runner,
        name=f"postrule-lift-{func.name}",
        daemon=True,
    )
    # threading.stack_size affects subsequently-started threads.
    prev_stack = threading.stack_size()
    threading.stack_size(64 * 1024 * 1024)
    try:
        worker.start()
    finally:
        # Restore so we don't leak the bump to other library threads.
        threading.stack_size(prev_stack if prev_stack > 0 else 0)
    worker.join()
    if "err" in result:
        raise result["err"]  # type: ignore[misc]
    return result["out"]  # type: ignore[return-value]


# ----------------------------------------------------------------------
# Function lookup + top-level guards
# ----------------------------------------------------------------------


def _find_function(tree: ast.Module, name: str) -> ast.FunctionDef:
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return node
    raise LiftRefused(reason=f"function {name!r} not found in source", line=0)


# ----------------------------------------------------------------------
# Top-level driver
# ----------------------------------------------------------------------


def _build_switch_module(
    func: ast.FunctionDef,
    *,
    allow_multi_top_level_if: bool,
    allow_leading_bind: bool,
) -> str:
    arg_names = _validate_args(func)

    # Refuse on globally-banned constructs anywhere in the body
    # (getattr / eval / exec / try-except-in-branch are all caught here
    # OR inside _extract_branches; we run the body-wide check first
    # to fail fast on dynamic dispatch).
    _check_for_dynamic_dispatch(func)

    extraction = _extract_branches(
        func,
        arg_names=arg_names,
        allow_multi_top_level_if=allow_multi_top_level_if,
        allow_leading_bind=allow_leading_bind,
    )
    # When leading-bind passthrough is enabled, validated binds have
    # already been peeled off the leading_stmts and recorded on the
    # extraction. Anything left in leading_stmts after that point is a
    # statement we couldn't lift, and the shared-state check still fires.
    _check_no_shared_state(extraction.leading_stmts, extraction.branches, func.lineno)

    class_name = _class_name_for(func.name)
    multi_arg = len(arg_names) > 1

    module_body: list[ast.stmt] = []
    module_body.extend(_build_imports(multi_arg))
    if multi_arg:
        module_body.append(_build_args_dataclass(class_name, arg_names))
    module_body.append(_build_switch_class(class_name, arg_names, extraction, multi_arg))

    new_module = ast.Module(body=module_body, type_ignores=[])
    ast.fix_missing_locations(new_module)
    return ast.unparse(new_module)


# ----------------------------------------------------------------------
# Validation passes
# ----------------------------------------------------------------------


def _validate_args(func: ast.FunctionDef) -> list[str]:
    """Return positional arg names (excluding self/cls) or refuse on
    zero-arg functions and *args/**kwargs-only functions.
    """
    posargs = list(func.args.posonlyargs) + list(func.args.args)
    # Strip leading self/cls if present (defensive — top-level funcs
    # shouldn't have them, but methods inside classes pasted into a
    # source string would).
    if posargs and posargs[0].arg in ("self", "cls"):
        posargs = posargs[1:]

    if not posargs:
        raise LiftRefused(
            reason="zero-argument function: not a classifier of an input",
            line=func.lineno,
        )
    return [a.arg for a in posargs]


def _check_for_dynamic_dispatch(func: ast.FunctionDef) -> None:
    for node in ast.walk(func):
        if isinstance(node, ast.Call):
            target = node.func
            name = None
            if isinstance(target, ast.Name):
                name = target.id
            elif isinstance(target, ast.Attribute):
                name = target.attr
            if name in ("eval", "exec"):
                raise LiftRefused(
                    reason=f"dynamic dispatch via {name!r} blocks static lifting",
                    line=getattr(node, "lineno", func.lineno),
                )
            if name == "getattr":
                # getattr with 2+ string-literal args is essentially attr
                # access; the hazard is the dynamic form. Refuse all
                # uses for v1 to keep the rule simple.
                raise LiftRefused(
                    reason="dynamic dispatch via 'getattr' blocks static lifting",
                    line=getattr(node, "lineno", func.lineno),
                )


# ----------------------------------------------------------------------
# Branch extraction
# ----------------------------------------------------------------------


def _extract_branches(
    func: ast.FunctionDef,
    *,
    arg_names: list[str],
    allow_multi_top_level_if: bool,
    allow_leading_bind: bool,
) -> _ExtractionResult:
    """Walk the function body and return an :class:`_ExtractionResult`.

    ``leading_stmts`` are any statements that appear in the function
    body BEFORE the if/elif/else chain or match statement. They are
    used to detect shared mid-function state.

    v1.5 relaxation 2: when ``allow_leading_bind`` is True, we peel off
    each leading ``Name = expr`` whose RHS only references function args
    and previously-bound names; those binds become ``_evidence_<name>``
    methods and are stripped from ``leading_stmts``. RHS expressions
    that read ``self.<attr>`` or globals are refused outright with a
    reason that points the user at the evidence lifter.

    v1.5 relaxation 1: when ``allow_multi_top_level_if`` is True and the
    function body is a flat sequence of top-level ``if`` statements
    (each ending in ``return <literal>``) followed by an optional
    default block ending in ``return <literal>``, we treat that as
    canonical (semantically equivalent to the elif chain) and emit
    ``chain_kind = "multi_if"``.
    """
    body = list(func.body)

    # Skip a leading docstring if present.
    leading_stmts: list[ast.stmt] = []
    idx = 0
    if (
        body
        and isinstance(body[0], ast.Expr)
        and isinstance(body[0].value, ast.Constant)
        and isinstance(body[0].value.value, str)
    ):
        idx = 1

    # Collect statements before the chain.
    while idx < len(body) and not isinstance(body[idx], (ast.If, ast.Match)):
        leading_stmts.append(body[idx])
        idx += 1

    # v1.5 relaxation 2: try to lift each leading statement as a bind.
    # Peel off as many as we can; whatever remains stays in leading_stmts
    # so the shared-state guard still catches non-bind state-shuffling.
    leading_binds: list[_Bind] = []
    if allow_leading_bind and leading_stmts:
        leading_stmts, leading_binds = _extract_leading_binds(leading_stmts, arg_names=arg_names)

    if idx >= len(body):
        raise LiftRefused(
            reason="function has no if/elif or match chain to lift",
            line=func.lineno,
        )

    chain_node = body[idx]
    trailing = body[idx + 1 :]
    has_trailing_default = False
    trailing_default_label: str | None = None
    multi_if_groups: list[ast.If] = []
    multi_if_default_body: list[ast.stmt] = []

    if isinstance(chain_node, ast.If):
        # v1.5 relaxation 1: probe whether this is the multi-top-level-if
        # shape before falling back to the strict single-elif-chain path.
        # The single-elif path uses node.orelse for its else; the
        # multi-if path uses TRAILING ifs at the same indent level.
        if allow_multi_top_level_if and _looks_like_multi_top_level_if(chain_node, trailing):
            (
                branches,
                multi_if_groups,
                multi_if_default_body,
                default_label,
            ) = _extract_multi_top_level_if(chain_node, trailing)
            chain_kind = "multi_if"
            # multi_if always requires a default; trailing_default_label
            # carries it for the codegen path.
            has_trailing_default = True
            trailing_default_label = default_label
            chain_node = None  # codegen reconstructs from groups
        else:
            branches, has_trailing_default, trailing_default_label = _extract_if_chain(
                chain_node, trailing
            )
            chain_kind = "if"
    else:
        branches = _extract_match(chain_node, trailing)
        chain_kind = "match"

    return _ExtractionResult(
        branches=branches,
        leading_stmts=leading_stmts,
        chain_kind=chain_kind,
        chain_node=chain_node,
        has_trailing_default=has_trailing_default,
        trailing_default_label=trailing_default_label,
        leading_binds=leading_binds,
        multi_if_groups=multi_if_groups,
        multi_if_default_body=multi_if_default_body,
    )


# ----------------------------------------------------------------------
# v1.5 relaxation 1: multi-top-level-if shape detection
# ----------------------------------------------------------------------


def _looks_like_multi_top_level_if(head: ast.If, trailing: list[ast.stmt]) -> bool:
    """Return True iff ``head`` participates in a flat fall-through
    sequence of top-level ifs.

    The shape we accept here is:

    .. code-block:: python

        if cond_a:
            ...
            return "a"
        if cond_b:           # <-- another top-level if, NOT elif
            ...
            return "b"
        ...optional default body...
        return "default"

    We keep the predicate cheap: it only fires when ``trailing`` begins
    with another ``If``. The tighter validation (each top-level if's
    body ends in a return literal, and the trailing block ends in a
    bare return) happens in :func:`_extract_multi_top_level_if`, which
    is allowed to raise ``LiftRefused`` for the not-quite-canonical
    shape (the user opted in by writing the flat form).
    """
    return bool(trailing) and isinstance(trailing[0], ast.If)


def _extract_multi_top_level_if(
    head: ast.If, trailing: list[ast.stmt]
) -> tuple[list[_Branch], list[ast.If], list[ast.stmt], str]:
    """Walk a flat fall-through sequence of top-level ifs.

    Returns ``(branches, if_groups, default_body, default_label)``:

    - ``branches`` is one ``_Branch`` per ARM (so a top-level if with
      its own ``elif``/``else`` contributes one ``_Branch`` per arm).
      Used for ``_on_<label>`` codegen.
    - ``if_groups`` is the list of original top-level ``ast.If`` nodes
      in source order. Codegen re-emits each group with its original
      elif structure preserved, then drops a bare default ``return``.
    - ``default_body`` is whatever statements remain after the last
      top-level if and before the bare default ``return``.
    - ``default_label`` is the literal returned by the bare trailing
      ``return``.

    Refuses if any top-level if has an ``else``/``elif`` (the user
    asked for flat fall-through, mixing the two shapes inside one chain
    is the v1.1 path), or if a non-final top-level if's body falls
    through without returning, or if there's no bare default return.
    """
    # Collect all the top-level ifs starting from head.
    all_ifs: list[ast.If] = [head]
    rest = list(trailing)
    while rest and isinstance(rest[0], ast.If):
        all_ifs.append(rest.pop(0))

    # Each top-level if must have NO orelse (mixing elif into the
    # multi-top-level-if shape would mean some arms exit via elif and
    # the rest fall through, which produces ambiguous semantics for the
    # rule body. Force the user back to the v1.1 path or strip the elif).
    # Exception: head can have an else IF that else returns — we already
    # handle that in _extract_if_chain. Here we explicitly require
    # orelse-empty for the v1.5 multi-if shape so the two paths don't
    # overlap.
    for if_node in all_ifs:
        if if_node.orelse:
            # User mixed elif/else into a fall-through chain. Take the
            # first if's branch + elif chain and treat the whole thing
            # as the v1.1 if/elif chain, then everything after this
            # if-with-orelse forms the multi-top-level-if continuation.
            # That's exactly what _extract_if_chain handles for the
            # head, so we let it run. We signal "not pure multi_if" by
            # raising; the caller hasn't committed to multi_if yet
            # because we run inside the multi_if path that's already
            # been chosen. Instead of raising, we record this and
            # return a hybrid representation: the v1.1 chain handles
            # the head's elif/else, and the trailing ifs (if all return)
            # are appended as flat branches afterward.
            # For v1.5 we keep the implementation simple: we accept
            # this as a hybrid only when each elif-arm and each
            # top-level-if-arm ends in a return literal.
            pass

    branches: list[_Branch] = []
    for if_node in all_ifs:
        if if_node.orelse:
            # Hybrid shape: this if has an elif/else chain. Walk it as
            # a sub-chain and emit each arm as its own _Branch. The
            # sub-chain's else (if any) becomes the *natural* default
            # IF this is also the last top-level if; otherwise the else
            # arm must also return (which it must, since each branch
            # ends in a return — we validate via _branch_from_block).
            sub_branches, _, _ = _extract_if_chain_arms_only(if_node)
            branches.extend(sub_branches)
        else:
            # Plain top-level if: body must end in a return literal.
            branches.append(_branch_from_block(if_node.body, test=if_node.test, is_else=False))

    # The rest must be: optional non-If statements forming a default
    # body, followed by exactly one ``return <string-literal>``.
    if not rest:
        raise LiftRefused(
            reason=(
                "multi-top-level-if chain has no bare default return "
                "(add a `return <literal>` at the end)"
            ),
            line=all_ifs[-1].lineno,
        )
    last = rest[-1]
    if not isinstance(last, ast.Return) or not _is_string_literal_return(last):
        raise LiftRefused(
            reason=(
                "multi-top-level-if chain must end in a bare `return <literal>` "
                "(non-final top-level if falls through without returning)"
            ),
            line=getattr(last, "lineno", all_ifs[-1].lineno),
        )
    default_label = last.value.value  # type: ignore[union-attr]
    default_body = rest[:-1]
    _validate_branch_body(default_body)

    # Append the synthetic "else" branch so existing codegen for
    # _on_<label> handlers fires for the default case too.
    branches.append(
        _Branch(
            label=default_label,
            test=None,
            body=default_body,
            return_lineno=last.lineno,
            is_else=True,
        )
    )
    return branches, all_ifs, default_body, default_label


def _extract_if_chain_arms_only(
    head: ast.If,
) -> tuple[list[_Branch], bool, str | None]:
    """Walk an if/elif/else sub-chain and return its arms as a flat
    list of ``_Branch``. Each arm's body must end in a string-literal
    return (otherwise this is a fall-through hazard).

    Used inside the multi-top-level-if path when one of the top-level
    ifs has an ``elif`` / ``else`` of its own.
    """
    branches: list[_Branch] = []
    node: ast.If | None = head
    while node is not None:
        branches.append(_branch_from_block(node.body, test=node.test, is_else=False))
        if not node.orelse:
            break
        if len(node.orelse) == 1 and isinstance(node.orelse[0], ast.If):
            node = node.orelse[0]
            continue
        # Plain else block.
        branches.append(_branch_from_block(node.orelse, test=None, is_else=True))
        node = None
    return branches, False, None


# ----------------------------------------------------------------------
# v1.5 relaxation 2: leading-bind extraction
# ----------------------------------------------------------------------


def _extract_leading_binds(
    leading_stmts: list[ast.stmt],
    *,
    arg_names: list[str],
) -> tuple[list[ast.stmt], list[_Bind]]:
    """Peel off leading ``Name = expr`` assignments whose RHS only
    references function arguments and previously-bound names.

    Returns ``(remaining_leading_stmts, binds)``. ``binds`` is in
    source order. Binds with side-effect-free RHS (or any ``Call``,
    per the v1.5 permissive rule) are accepted; binds reading
    ``self.<attr>`` or module globals are refused.

    The first non-bind statement (or the first bind we can't accept)
    aborts the peel: from that point on, statements stay in
    ``remaining_leading_stmts`` so the legacy shared-state guard fires
    on them.
    """
    binds: list[_Bind] = []
    bound_names: set[str] = set()
    available_names: set[str] = set(arg_names)
    remaining: list[ast.stmt] = []
    aborted = False
    for stmt in leading_stmts:
        if aborted:
            remaining.append(stmt)
            continue
        bind = _try_lift_leading_assign(stmt, available_names=available_names)
        if bind is None:
            # Not a liftable assign. Stop peeling — anything after this
            # gets the legacy shared-state treatment.
            aborted = True
            remaining.append(stmt)
            continue
        # Refuse if the bind name is reused (multiple assigns to the
        # same name confuse the gather semantics). Note: a bind name
        # that matches an arg name (the "normalize input" idiom, e.g.
        # ``db_type = db_type.lower()``) is FINE — references in the
        # rule body all rewrite to evidence.<name>, and the handler
        # parameter still sees the original input which the injected
        # bind statement immediately re-shadows.
        if bind.name in bound_names:
            raise LiftRefused(
                reason=(
                    f"leading bind {bind.name!r} is reassigned; "
                    "evidence fields must have a single definition"
                ),
                line=bind.lineno,
            )
        binds.append(bind)
        bound_names.add(bind.name)
        available_names.add(bind.name)
    return remaining, binds


def _try_lift_leading_assign(stmt: ast.stmt, *, available_names: set[str]) -> _Bind | None:
    """Return a ``_Bind`` if ``stmt`` is a single-target ``Name = expr``
    whose RHS only references function args, prior binds, callables,
    and module-style references; raise ``LiftRefused`` if the RHS reads
    ``self`` / ``cls`` directly so the user gets a specific refusal
    pointing them at the evidence lifter; return ``None`` if ``stmt``
    isn't a liftable shape (caller stops peeling).

    v1.5 permissive rule: any ``Call`` in the RHS is accepted, including
    callees and their receivers (``re`` in ``re.sub(...)``, helper
    functions in the enclosing module, etc.). Module imports and
    sibling function refs aren't hidden-state-on-an-instance, so we
    treat them as stable lookups for v1.5. Truly hidden state
    (``self.<attr>``, ``cls.<attr>``) still triggers refusal.
    """
    if not isinstance(stmt, ast.Assign):
        return None
    if len(stmt.targets) != 1:
        return None
    target = stmt.targets[0]
    if not isinstance(target, ast.Name):
        return None
    rhs = stmt.value

    # Always refuse on direct ``self`` / ``cls`` reads — those are the
    # evidence lifter's concern (instance / class state can mutate
    # between dispatches and must be sampled in the gather, not in
    # whatever order Python decides to run handlers).
    if _expr_reads_self_or_cls(rhs):
        raise LiftRefused(
            reason=(
                f"leading bind {target.id!r} reads from self/cls; "
                "use the evidence lifter (lift_evidence) for hidden state"
            ),
            line=stmt.lineno,
        )

    # If the RHS contains any Call, v1.5 is permissive: free names are
    # treated as either callable references (functions, classes) or
    # module-style imports (re, os, ...) which the user's gather will
    # resolve at run time the same way the original function did.
    if _expr_has_call(rhs):
        return _Bind(name=target.id, rhs=rhs, lineno=stmt.lineno)

    # No Call in the RHS — apply the stricter free-name check so we
    # don't silently lift a bind that depends on a mutable global like
    # a config singleton (e.g. ``over = x > THRESHOLD``).
    free_reads = _collect_free_name_reads(rhs, available_names=available_names)
    if free_reads:
        unknown = sorted(free_reads)
        raise LiftRefused(
            reason=(
                f"leading bind {target.id!r} reads from globals "
                f"({', '.join(unknown)}); use the evidence lifter for hidden state"
            ),
            line=stmt.lineno,
        )

    return _Bind(name=target.id, rhs=rhs, lineno=stmt.lineno)


def _expr_reads_self_or_cls(expr: ast.expr) -> bool:
    """True if ``expr`` reads ``self`` or ``cls`` anywhere as a Load."""
    for sub in ast.walk(expr):
        if (
            isinstance(sub, ast.Name)
            and isinstance(sub.ctx, ast.Load)
            and sub.id in ("self", "cls")
        ):
            return True
    return False


def _expr_has_call(expr: ast.expr) -> bool:
    """True if any subnode of ``expr`` is an ``ast.Call``."""
    return any(isinstance(sub, ast.Call) for sub in ast.walk(expr))


def _collect_free_name_reads(expr: ast.expr, *, available_names: set[str]) -> set[str]:
    """Return Name(Load) ids in ``expr`` that are NOT in ``available_names``
    and are NOT used as the function position of a ``Call``.

    A name in ``Call.func`` position counts as a callable lookup
    (``len``, ``str``, helper funcs, etc.) — v1.5 is permissive there.
    A name read anywhere else (a comparison, argument, subscript, etc.)
    must be a function arg or a prior bind.
    """
    # First collect all Names that appear in Call.func position
    # anywhere in the tree, so we can exclude them.
    callee_names: set[int] = set()
    for sub in ast.walk(expr):
        if isinstance(sub, ast.Call) and isinstance(sub.func, ast.Name):
            callee_names.add(id(sub.func))

    # Also exclude lambda / comprehension-bound locals: a name that
    # appears as a Lambda arg or comprehension target is locally bound
    # and not a free var. v1.5 keeps this simple — anything inside a
    # nested scope (Lambda, ListComp, etc.) we trust the user wrote,
    # because those scopes have their own local namespaces. Skip the
    # interior of nested scopes for free-name analysis.
    free: set[str] = set()
    for sub in ast.walk(expr):
        if isinstance(sub, ast.Name) and isinstance(sub.ctx, ast.Load):
            if id(sub) in callee_names:
                continue
            if sub.id in available_names:
                continue
            free.add(sub.id)
    return free


def _extract_if_chain(
    head: ast.If, trailing: list[ast.stmt]
) -> tuple[list[_Branch], bool, str | None]:
    """Walk an if/elif/else chain.

    Returns ``(branches, has_trailing_default, trailing_default_label)``.
    ``has_trailing_default`` is True when the chain has no ``else`` arm
    but a bare ``return <literal>`` follows. The trailing default
    becomes a synthetic else-branch in the rule chain.
    """
    branches: list[_Branch] = []
    node: ast.If | None = head
    while node is not None:
        branches.append(_branch_from_block(node.body, test=node.test, is_else=False))
        if not node.orelse:
            # No else — trailing statements (if any) might form an
            # implicit "default" return. Check that.
            break
        if len(node.orelse) == 1 and isinstance(node.orelse[0], ast.If):
            node = node.orelse[0]  # elif
            continue
        # Plain else block.
        branches.append(_branch_from_block(node.orelse, test=None, is_else=True))
        node = None

    has_else = any(b.is_else for b in branches)
    has_trailing_default = False
    trailing_default_label: str | None = None
    if not has_else:
        # No else; require a trailing `return <literal>` as the default.
        if (
            len(trailing) == 1
            and isinstance(trailing[0], ast.Return)
            and _is_string_literal_return(trailing[0])
        ):
            label = trailing[0].value.value  # type: ignore[union-attr]
            branches.append(
                _Branch(
                    label=label,
                    test=None,
                    body=[],
                    return_lineno=trailing[0].lineno,
                    is_else=True,
                )
            )
            has_trailing_default = True
            trailing_default_label = label
        elif trailing:
            first = trailing[0]
            if isinstance(first, ast.If):
                raise LiftRefused(
                    reason=(
                        "function has multiple top-level if statements rather "
                        "than a single if/elif/else chain (refactor to elif)"
                    ),
                    line=first.lineno,
                )
            raise LiftRefused(
                reason="statements after if/elif chain are not a simple default return",
                line=first.lineno,
            )
        else:
            raise LiftRefused(
                reason="if/elif chain has no else branch and no default return",
                line=head.lineno,
            )
    elif trailing:
        raise LiftRefused(
            reason="unexpected statements after if/elif/else chain",
            line=trailing[0].lineno,
        )

    return branches, has_trailing_default, trailing_default_label


def _branch_from_block(stmts: list[ast.stmt], test: ast.expr | None, is_else: bool) -> _Branch:
    """Pull the trailing return out of a branch body, validate the rest."""
    if not stmts:
        raise LiftRefused(reason="empty branch body", line=0)

    last = stmts[-1]
    if not isinstance(last, ast.Return):
        raise LiftRefused(
            reason="branch does not end in a return statement",
            line=getattr(last, "lineno", 0),
        )
    if not _is_string_literal_return(last):
        raise LiftRefused(
            reason="branch returns a computed value, not a string-literal label",
            line=last.lineno,
        )
    label = last.value.value  # type: ignore[union-attr]

    pre = stmts[:-1]
    _validate_branch_body(pre)

    return _Branch(
        label=label,
        test=test,
        body=pre,
        return_lineno=last.lineno,
        is_else=is_else,
    )


def _is_string_literal_return(ret: ast.Return) -> bool:
    return (
        ret.value is not None
        and isinstance(ret.value, ast.Constant)
        and isinstance(ret.value.value, str)
    )


def _validate_branch_body(stmts: list[ast.stmt]) -> None:
    """Refuse on try/except inside a branch body. (Other dynamic-dispatch
    hazards are caught by the function-wide pass earlier.)
    """
    for stmt in stmts:
        for sub in ast.walk(stmt):
            if isinstance(sub, (ast.Try,)):
                raise LiftRefused(
                    reason=(
                        "try/except inside a branch body couples exception flow to label selection"
                    ),
                    line=sub.lineno,
                )


def _extract_match(head: ast.Match, trailing: list[ast.stmt]) -> list[_Branch]:
    """Lift a ``match`` statement with literal cases and an optional
    wildcard default. Captures-with-guards and class-patterns are
    out of v1 scope.
    """
    if trailing:
        raise LiftRefused(
            reason="unexpected statements after match block",
            line=trailing[0].lineno,
        )
    branches: list[_Branch] = []
    seen_wildcard = False
    for case in head.cases:
        if case.guard is not None:
            raise LiftRefused(
                reason="match case with guard is outside the safe subset",
                line=case.pattern.lineno,
            )
        is_wildcard = isinstance(case.pattern, ast.MatchAs) and case.pattern.pattern is None
        # We intentionally don't translate the case's pattern into an
        # `if` test — the rule body keeps the match shape verbatim.
        # ``test`` is only used to reconstruct an if-chain, so we
        # leave it None for match arms.
        branches.append(_branch_from_match_case(case, is_wildcard=is_wildcard))
        if is_wildcard:
            seen_wildcard = True

    if not seen_wildcard:
        raise LiftRefused(
            reason="match statement has no wildcard default case",
            line=head.lineno,
        )
    return branches


def _branch_from_match_case(case: ast.match_case, is_wildcard: bool) -> _Branch:
    if not case.body:
        raise LiftRefused(reason="empty match case body", line=case.pattern.lineno)
    last = case.body[-1]
    if not isinstance(last, ast.Return):
        raise LiftRefused(
            reason="match case does not end in a return statement",
            line=getattr(last, "lineno", case.pattern.lineno),
        )
    if not _is_string_literal_return(last):
        raise LiftRefused(
            reason="match case returns a computed value, not a string-literal label",
            line=last.lineno,
        )
    label = last.value.value  # type: ignore[union-attr]
    pre = case.body[:-1]
    _validate_branch_body(pre)
    return _Branch(
        label=label,
        test=None,
        body=pre,
        return_lineno=last.lineno,
        is_else=is_wildcard,
    )


# ----------------------------------------------------------------------
# Shared-state detector
# ----------------------------------------------------------------------


def _check_no_shared_state(
    leading_stmts: list[ast.stmt],
    branches: list[_Branch],
    fallback_lineno: int,
) -> None:
    """If any name assigned in a leading statement is read inside more
    than one branch (test or body), refuse: that's shared mid-function
    state and lifting it requires evidence-lifting (Phase 3).
    """
    assigned_names: set[str] = set()
    for stmt in leading_stmts:
        for sub in ast.walk(stmt):
            if isinstance(sub, ast.Assign):
                for target in sub.targets:
                    for name_node in _names_assigned(target):
                        assigned_names.add(name_node)
            elif isinstance(sub, (ast.AnnAssign, ast.AugAssign)) and isinstance(
                sub.target, ast.Name
            ):
                assigned_names.add(sub.target.id)

    if not assigned_names:
        return

    def _branch_reads(branch: _Branch) -> set[str]:
        reads: set[str] = set()
        nodes: list[ast.AST] = list(branch.body)
        if branch.test is not None:
            nodes.append(branch.test)
        for node in nodes:
            for sub in ast.walk(node):
                if isinstance(sub, ast.Name) and isinstance(sub.ctx, ast.Load):
                    reads.add(sub.id)
        return reads

    branch_reads = [_branch_reads(b) for b in branches]
    for name in assigned_names:
        readers = sum(1 for reads in branch_reads if name in reads)
        if readers >= 2:
            raise LiftRefused(
                reason=(
                    f"shared mid-function state: {name!r} is assigned before "
                    "the if/elif chain and read in multiple branches"
                ),
                line=fallback_lineno,
            )
        if readers == 1:
            # Read in only one branch — still hazardous if the leading
            # assignment has side effects. Conservative: refuse.
            raise LiftRefused(
                reason=(
                    f"mid-function state: {name!r} is assigned before the "
                    "if/elif chain (use Phase 3 evidence lifting to handle this)"
                ),
                line=fallback_lineno,
            )


def _names_assigned(target: ast.expr) -> list[str]:
    if isinstance(target, ast.Name):
        return [target.id]
    if isinstance(target, (ast.Tuple, ast.List)):
        out: list[str] = []
        for elt in target.elts:
            out.extend(_names_assigned(elt))
        return out
    return []


# ----------------------------------------------------------------------
# Codegen — build the output AST
# ----------------------------------------------------------------------


def _class_name_for(func_name: str) -> str:
    parts = func_name.split("_")
    camel = "".join(p[:1].upper() + p[1:] for p in parts if p)
    return f"{camel}Switch"


def _build_imports(multi_arg: bool) -> list[ast.stmt]:
    out: list[ast.stmt] = []
    if multi_arg:
        out.append(
            ast.ImportFrom(
                module="dataclasses",
                names=[ast.alias(name="dataclass", asname=None)],
                level=0,
            )
        )
    out.append(
        ast.ImportFrom(
            module="postrule",
            names=[ast.alias(name="Switch", asname=None)],
            level=0,
        )
    )
    return out


def _build_args_dataclass(class_name: str, arg_names: list[str]) -> ast.stmt:
    """For multi-arg functions emit a packed dataclass.

    The dataclass deliberately uses ``object`` as the field type — Phase
    3 will pull real type annotations from the user's signature. For
    Phase 2 the dataclass exists only as a packing convenience.
    """
    base_name = class_name.removesuffix("Switch")
    dc_name = f"_{base_name}Args"
    fields: list[ast.stmt] = [
        ast.AnnAssign(
            target=ast.Name(id=name, ctx=ast.Store()),
            annotation=ast.Name(id="object", ctx=ast.Load()),
            value=None,
            simple=1,
        )
        for name in arg_names
    ]
    cls = ast.ClassDef(
        name=dc_name,
        bases=[],
        keywords=[],
        body=fields,
        decorator_list=[ast.Name(id="dataclass", ctx=ast.Load())],
        type_params=[],
    )
    return cls


def _build_switch_class(
    class_name: str,
    arg_names: list[str],
    extraction: _ExtractionResult,
    multi_arg: bool,
) -> ast.ClassDef:
    handler_arg_name = "packed" if multi_arg else arg_names[0]

    body: list[ast.stmt] = []
    body.append(_build_evidence_input(handler_arg_name))
    # v1.5 relaxation 2: emit one _evidence_<name> per leading bind.
    for bind in extraction.leading_binds:
        body.append(_build_evidence_for_bind(bind, arg_names, multi_arg, extraction.leading_binds))
    body.append(_build_rule(arg_names, extraction, multi_arg))
    for branch in extraction.branches:
        if not branch.body and not _branch_handler_needs_binds(branch, extraction.leading_binds):
            continue  # no side effects, no _on_<label>
        body.append(_build_on_handler(branch, arg_names, multi_arg, extraction.leading_binds))

    cls = ast.ClassDef(
        name=class_name,
        bases=[ast.Name(id="Switch", ctx=ast.Load())],
        keywords=[],
        body=body,
        decorator_list=[],
        type_params=[],
    )
    return cls


def _branch_handler_needs_binds(branch: _Branch, leading_binds: list[_Bind]) -> bool:
    """A handler body that REFERENCES a leading-bind name needs the
    bind statements injected at the top. We never add a handler for
    a no-side-effect branch just because of binds: only emit if the
    body has work to do.
    """
    return False  # binds alone don't justify a handler — body must have work


def _build_evidence_for_bind(
    bind: _Bind,
    arg_names: list[str],
    multi_arg: bool,
    all_binds: list[_Bind],
) -> ast.FunctionDef:
    """Emit ``_evidence_<bind.name>`` whose body re-runs the bind
    expression against the function's inputs.

    For chained binds (later binds referencing earlier binds), we
    inline all PRIOR binds at the top of the gather body so each name
    the user wrote resolves locally inside the gather. This duplicates
    work across gathers (each gather re-runs the prefix it needs), but
    keeps semantics straightforward and matches the v1.5 permissive
    spirit. v2 may consolidate via ``self._evidence_<prior>(arg)``
    references if duplication shows up as a perf issue.
    """
    handler_arg = "packed" if multi_arg else arg_names[0]
    body: list[ast.stmt] = []
    if multi_arg:
        for name in arg_names:
            body.append(
                _assign(
                    name,
                    ast.Attribute(
                        value=ast.Name(id="packed", ctx=ast.Load()),
                        attr=name,
                        ctx=ast.Load(),
                    ),
                )
            )
    # Inline prior binds in source order, stopping at this bind.
    for prior in all_binds:
        if prior.name == bind.name:
            break
        body.append(_assign(prior.name, prior.rhs))
    body.append(ast.Return(value=bind.rhs))

    return ast.FunctionDef(
        name=f"_evidence_{bind.name}",
        args=ast.arguments(
            posonlyargs=[],
            args=[
                ast.arg(arg="self", annotation=None),
                ast.arg(arg=handler_arg, annotation=None),
            ],
            vararg=None,
            kwonlyargs=[],
            kw_defaults=[],
            kwarg=None,
            defaults=[],
        ),
        body=body,
        decorator_list=[],
        returns=ast.Name(id="object", ctx=ast.Load()),
        type_params=[],
    )


def _build_evidence_input(arg_name: str) -> ast.FunctionDef:
    """Trivial evidence gatherer that returns the input verbatim.

    Phase 3 will replace this with one ``_evidence_<field>`` per
    detected hidden-state read.
    """
    return ast.FunctionDef(
        name="_evidence_input",
        args=ast.arguments(
            posonlyargs=[],
            args=[ast.arg(arg="self", annotation=None), ast.arg(arg=arg_name, annotation=None)],
            vararg=None,
            kwonlyargs=[],
            kw_defaults=[],
            kwarg=None,
            defaults=[],
        ),
        body=[ast.Return(value=ast.Name(id=arg_name, ctx=ast.Load()))],
        decorator_list=[],
        returns=ast.Name(id="object", ctx=ast.Load()),
        type_params=[],
    )


def _build_rule(
    arg_names: list[str],
    extraction: _ExtractionResult,
    multi_arg: bool,
) -> ast.FunctionDef:
    """Build the _rule method: unpack the single arg (or unpack each
    field of the synthetic dataclass), then re-emit the original
    branch chain with each branch body collapsed to ``return <label>``.

    Re-emitting from the original ``If``/``Match`` AST node (rather
    than from the flat ``branches`` list) preserves match patterns,
    elif structure, and conditional expressions exactly as the user
    wrote them.
    """
    body: list[ast.stmt] = []
    if multi_arg:
        for name in arg_names:
            body.append(
                _assign(
                    name,
                    ast.Attribute(
                        value=ast.Attribute(
                            value=ast.Name(id="evidence", ctx=ast.Load()),
                            attr="input",
                            ctx=ast.Load(),
                        ),
                        attr=name,
                        ctx=ast.Load(),
                    ),
                )
            )
    else:
        body.append(
            _assign(
                arg_names[0],
                ast.Attribute(
                    value=ast.Name(id="evidence", ctx=ast.Load()),
                    attr="input",
                    ctx=ast.Load(),
                ),
            )
        )

    bind_names = {b.name for b in extraction.leading_binds}
    if extraction.chain_kind == "if":
        chain_stmt = _collapse_if_chain(
            extraction.chain_node,  # type: ignore[arg-type]
            extraction.has_trailing_default,
            extraction.trailing_default_label,
        )
        if bind_names:
            chain_stmt = _rewrite_bind_reads(chain_stmt, bind_names)
        body.append(chain_stmt)
    elif extraction.chain_kind == "multi_if":
        flat_stmts = _collapse_multi_top_level_if(
            extraction.multi_if_groups,
            extraction.trailing_default_label or "",
        )
        if bind_names:
            flat_stmts = [_rewrite_bind_reads(s, bind_names) for s in flat_stmts]
        body.extend(flat_stmts)
    else:
        match_stmt = _collapse_match(extraction.chain_node)  # type: ignore[arg-type]
        if bind_names:
            match_stmt = _rewrite_bind_reads(match_stmt, bind_names)
        body.append(match_stmt)

    return ast.FunctionDef(
        name="_rule",
        args=ast.arguments(
            posonlyargs=[],
            args=[ast.arg(arg="self", annotation=None), ast.arg(arg="evidence", annotation=None)],
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


def _collapse_if_chain(
    head: ast.If,
    has_trailing_default: bool,
    trailing_default_label: str | None,
) -> ast.stmt:
    """Walk the original if/elif/else AST and emit a copy whose
    branch bodies are each just ``return <label>``. Test expressions
    are reused as-is.

    If the original chain had no ``else`` and we synthesized a default
    from a trailing ``return <literal>``, attach that as the final
    ``else`` arm of the copy.
    """
    new_head = _copy_if(head)
    if has_trailing_default and trailing_default_label is not None:
        # Attach as the deepest else.
        node = new_head
        while True:
            if not node.orelse:
                node.orelse = [ast.Return(value=ast.Constant(value=trailing_default_label))]
                break
            if len(node.orelse) == 1 and isinstance(node.orelse[0], ast.If):
                node = node.orelse[0]
                continue
            break
    return new_head


def _copy_if(node: ast.If) -> ast.If:
    """Copy an If node, replacing its body with ``return <label>``.

    The label is the string literal returned by the ORIGINAL branch's
    final return, validated during extraction so we pull it back out
    here. We walk the ``orelse`` linked list iteratively (not
    recursively) because a 1000-deep elif chain otherwise blows
    Python's recursion stack (issue #137).

    Strategy: walk the elif chain top-to-bottom collecting each
    ``(test, label)`` plus the optional terminal else-label, then
    rebuild the chain bottom-up so the deepest ``If`` is constructed
    first and each enclosing ``If`` references it as its ``orelse``.
    """
    chain: list[tuple[ast.expr, str]] = []
    terminal_else_label: str | None = None
    cursor: ast.If | None = node
    while cursor is not None:
        chain.append((cursor.test, _branch_label(cursor.body)))
        orelse = cursor.orelse
        if not orelse:
            cursor = None
            break
        if len(orelse) == 1 and isinstance(orelse[0], ast.If):
            cursor = orelse[0]
            continue
        terminal_else_label = _branch_label(orelse)
        cursor = None

    # Build bottom-up.
    if terminal_else_label is not None:
        new_orelse: list[ast.stmt] = [ast.Return(value=ast.Constant(value=terminal_else_label))]
    else:
        new_orelse = []
    new_node: ast.If | None = None
    for test, label in reversed(chain):
        new_body: list[ast.stmt] = [ast.Return(value=ast.Constant(value=label))]
        new_node = ast.If(test=test, body=new_body, orelse=new_orelse)
        new_orelse = [new_node]
    assert new_node is not None  # chain has at least the head node
    return new_node


def _collapse_multi_top_level_if(
    if_groups: list[ast.If],
    default_label: str,
) -> list[ast.stmt]:
    """Build the rule body for the v1.5 multi-top-level-if shape.

    Each user-written top-level ``if`` group keeps its original elif/
    else structure (so ``elif`` stays an ``elif`` in the output). Each
    arm's body is collapsed to ``return <label>``. After the last
    group we emit a bare ``return <default_label>``.
    """
    out: list[ast.stmt] = []
    for group in if_groups:
        out.append(_copy_if(group))
    out.append(ast.Return(value=ast.Constant(value=default_label)))
    return out


def _rewrite_bind_reads(node: ast.AST, bind_names: set[str]) -> ast.AST:
    """Rewrite ``Name(bind)`` → ``evidence.<bind>`` in-place inside
    test expressions and match subjects of the rule chain.

    Only Load contexts of names in ``bind_names`` are rewritten. Store
    contexts (e.g. comprehension target names that happen to share an
    id) are left alone. The rewrite is shallow on the chain skeleton
    but recursive on each test/subject because boolean ops and
    comparisons can nest the bind reference arbitrarily deep.
    """
    if isinstance(node, ast.If):
        node.test = _rewrite_bind_reads_in_expr(node.test, bind_names)
        # Body of the rule's _rule chain is already collapsed to
        # ``return <label>`` so it can't reference binds. The orelse,
        # if it's an If, recurses; if it's a Return, stays as is.
        if node.orelse and isinstance(node.orelse[0], ast.If):
            _rewrite_bind_reads(node.orelse[0], bind_names)
        return node
    if isinstance(node, ast.Match):
        node.subject = _rewrite_bind_reads_in_expr(node.subject, bind_names)
        # Patterns in match cases are not expressions; we leave them
        # alone. Case bodies are already ``return <label>`` post
        # collapse.
        return node
    if isinstance(node, ast.Return):
        # Default returns in the multi_if chain — no expressions to rewrite.
        return node
    return node


def _rewrite_bind_reads_in_expr(expr: ast.expr, bind_names: set[str]) -> ast.expr:
    """Recursively replace ``Name(<bind>)`` with ``evidence.<bind>``
    inside an expression tree. Returns the (possibly new) root node.
    """

    class _Rewriter(ast.NodeTransformer):
        def visit_Name(self, n: ast.Name) -> ast.AST:  # noqa: N802
            if n.id in bind_names and isinstance(n.ctx, ast.Load):
                return ast.Attribute(
                    value=ast.Name(id="evidence", ctx=ast.Load()),
                    attr=n.id,
                    ctx=ast.Load(),
                )
            return n

    return _Rewriter().visit(expr)  # type: ignore[return-value]


def _collapse_match(node: ast.Match) -> ast.Match:
    """Copy a Match node, replacing each case body with
    ``return <label>``. Patterns are reused verbatim so the
    user's case structure round-trips intact.
    """
    new_cases: list[ast.match_case] = []
    for case in node.cases:
        label = _branch_label(case.body)
        new_cases.append(
            ast.match_case(
                pattern=case.pattern,
                guard=case.guard,
                body=[ast.Return(value=ast.Constant(value=label))],
            )
        )
    return ast.Match(subject=node.subject, cases=new_cases)


def _branch_label(stmts: list[ast.stmt]) -> str:
    last = stmts[-1]
    if not isinstance(last, ast.Return) or not _is_string_literal_return(last):
        # Should never happen — extraction validated this already.
        raise LiftRefused(
            reason="internal: branch tail return is not a string literal",
            line=getattr(last, "lineno", 0),
        )
    return last.value.value  # type: ignore[union-attr]


def _build_on_handler(
    branch: _Branch,
    arg_names: list[str],
    multi_arg: bool,
    leading_binds: list[_Bind] | None = None,
) -> ast.FunctionDef:
    """Build _on_<label> from the branch's pre-return statements.

    For multi-arg input, we re-introduce local aliases so the original
    statements run unchanged (e.g., ``method = packed.method``).

    v1.5 relaxation 2: when the user lifted a leading bind and the
    handler body references that bound name, we re-introduce the bind
    locally at the top of the handler. The handler argument is the
    original input, so we just replay the bind's RHS verbatim. This
    duplicates work the gather already did, but keeps the handler
    body's reference to the bound name resolvable without changing
    its source. Bind names not referenced by the body are skipped.
    """
    body: list[ast.stmt] = []
    if multi_arg:
        for name in arg_names:
            body.append(
                _assign(
                    name,
                    ast.Attribute(
                        value=ast.Name(id="packed", ctx=ast.Load()),
                        attr=name,
                        ctx=ast.Load(),
                    ),
                )
            )
    if leading_binds:
        body.extend(_binds_used_by_branch(branch, leading_binds))
    body.extend(branch.body)

    handler_arg = "packed" if multi_arg else arg_names[0]
    return ast.FunctionDef(
        name=f"_on_{branch.label}",
        args=ast.arguments(
            posonlyargs=[],
            args=[ast.arg(arg="self", annotation=None), ast.arg(arg=handler_arg, annotation=None)],
            vararg=None,
            kwonlyargs=[],
            kw_defaults=[],
            kwarg=None,
            defaults=[],
        ),
        body=body,
        decorator_list=[],
        returns=None,
        type_params=[],
    )


def _binds_used_by_branch(branch: _Branch, leading_binds: list[_Bind]) -> list[ast.stmt]:
    """Return the subset of leading binds that the handler body needs,
    in source order, plus any prior binds those needed binds reference.

    Each emitted statement is a local assign reproducing the user's
    original ``name = expr`` so the original branch body runs unchanged.
    """
    if not leading_binds:
        return []
    name_to_bind = {b.name: b for b in leading_binds}
    # Collect names read inside the branch body.
    body_reads: set[str] = set()
    for stmt in branch.body:
        for sub in ast.walk(stmt):
            if isinstance(sub, ast.Name) and isinstance(sub.ctx, ast.Load):
                body_reads.add(sub.id)
    # Walk the bind list in source order; include a bind if the body
    # reads it, OR if a transitively-needed later bind reads it.
    needed: set[str] = set()
    for bind in leading_binds:
        if bind.name in body_reads:
            needed.add(bind.name)
    # Resolve transitive dependencies among binds (e.g. body uses
    # ``length``; ``length = len(lower)`` needs ``lower`` too).
    changed = True
    while changed:
        changed = False
        for bind in leading_binds:
            if bind.name not in needed:
                continue
            for sub in ast.walk(bind.rhs):
                if (
                    isinstance(sub, ast.Name)
                    and isinstance(sub.ctx, ast.Load)
                    and sub.id in name_to_bind
                    and sub.id not in needed
                ):
                    needed.add(sub.id)
                    changed = True
    out: list[ast.stmt] = []
    for bind in leading_binds:
        if bind.name in needed:
            out.append(_assign(bind.name, bind.rhs))
    return out


# ----------------------------------------------------------------------
# Tiny AST helpers
# ----------------------------------------------------------------------


def _assign(name: str, value: ast.expr) -> ast.Assign:
    return ast.Assign(
        targets=[ast.Name(id=name, ctx=ast.Store())],
        value=value,
    )
