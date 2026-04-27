# Copyright (c) 2026 B-Tree Ventures, LLC
# SPDX-License-Identifier: LicenseRef-BSL-1.1
"""Branch-body lifter (Phase 2 of auto-lift).

Takes Python source plus a function name and emits a refactored
:class:`dendra.Switch` subclass:

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
``dendra.decorator`` / ``dendra.switch_class`` — its output imports
from them, not the other way around.
"""

from __future__ import annotations

import ast
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

    label: str                  # the literal string returned by the branch
    test: ast.expr | None       # condition (None for else / wildcard)
    body: list[ast.stmt]        # pre-return statements
    return_lineno: int          # for diagnostics
    is_else: bool = False       # True for the trailing else / case _


@dataclass
class _ExtractionResult:
    """Bundle of what _extract_branches produces."""

    branches: list[_Branch]
    leading_stmts: list[ast.stmt]
    chain_kind: str             # "if" or "match"
    chain_node: ast.AST         # the original If / Match node
    has_trailing_default: bool  # True if a bare `return <lit>` followed an if/elif
    trailing_default_label: str | None


# ----------------------------------------------------------------------
# Public API
# ----------------------------------------------------------------------


def lift_branches(source: str, function_name: str) -> str:
    """Lift the branch bodies of ``function_name`` into a Switch subclass.

    Parameters
    ----------
    source:
        Full Python source containing the target function.
    function_name:
        The name of the ``def`` to lift. Must be a top-level function
        (nested functions are out of scope for v1.1).

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
    return _build_switch_module(func)


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


def _build_switch_module(func: ast.FunctionDef) -> str:
    arg_names = _validate_args(func)

    # Refuse on globally-banned constructs anywhere in the body
    # (getattr / eval / exec / try-except-in-branch are all caught here
    # OR inside _extract_branches; we run the body-wide check first
    # to fail fast on dynamic dispatch).
    _check_for_dynamic_dispatch(func)

    extraction = _extract_branches(func)
    _check_no_shared_state(
        extraction.leading_stmts, extraction.branches, func.lineno
    )

    class_name = _class_name_for(func.name)
    multi_arg = len(arg_names) > 1

    module_body: list[ast.stmt] = []
    module_body.extend(_build_imports(multi_arg))
    if multi_arg:
        module_body.append(_build_args_dataclass(class_name, arg_names))
    module_body.append(
        _build_switch_class(class_name, arg_names, extraction, multi_arg)
    )

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


def _extract_branches(func: ast.FunctionDef) -> _ExtractionResult:
    """Walk the function body and return an :class:`_ExtractionResult`.

    ``leading_stmts`` are any statements that appear in the function
    body BEFORE the if/elif/else chain or match statement. They are
    used to detect shared mid-function state.
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

    if idx >= len(body):
        raise LiftRefused(
            reason="function has no if/elif or match chain to lift",
            line=func.lineno,
        )

    chain_node = body[idx]
    trailing = body[idx + 1:]
    has_trailing_default = False
    trailing_default_label: str | None = None

    if isinstance(chain_node, ast.If):
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
    )


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
        if (len(trailing) == 1
                and isinstance(trailing[0], ast.Return)
                and _is_string_literal_return(trailing[0])):
            label = trailing[0].value.value  # type: ignore[union-attr]
            branches.append(_Branch(
                label=label,
                test=None,
                body=[],
                return_lineno=trailing[0].lineno,
                is_else=True,
            ))
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


def _branch_from_block(
    stmts: list[ast.stmt], test: ast.expr | None, is_else: bool
) -> _Branch:
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
                        "try/except inside a branch body couples "
                        "exception flow to label selection"
                    ),
                    line=sub.lineno,
                )


def _extract_match(
    head: ast.Match, trailing: list[ast.stmt]
) -> list[_Branch]:
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
        branches.append(
            _branch_from_match_case(case, is_wildcard=is_wildcard)
        )
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
        out.append(ast.ImportFrom(
            module="dataclasses",
            names=[ast.alias(name="dataclass", asname=None)],
            level=0,
        ))
    out.append(ast.ImportFrom(
        module="dendra",
        names=[ast.alias(name="Switch", asname=None)],
        level=0,
    ))
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
    body.append(_build_rule(arg_names, extraction, multi_arg))
    for branch in extraction.branches:
        if not branch.body:
            continue  # no side effects, no _on_<label>
        body.append(_build_on_handler(branch, arg_names, multi_arg))

    cls = ast.ClassDef(
        name=class_name,
        bases=[ast.Name(id="Switch", ctx=ast.Load())],
        keywords=[],
        body=body,
        decorator_list=[],
        type_params=[],
    )
    return cls


def _build_evidence_input(arg_name: str) -> ast.FunctionDef:
    """Trivial evidence gatherer that returns the input verbatim.

    Phase 3 will replace this with one ``_evidence_<field>`` per
    detected hidden-state read.
    """
    return ast.FunctionDef(
        name="_evidence_input",
        args=ast.arguments(
            posonlyargs=[],
            args=[ast.arg(arg="self", annotation=None),
                  ast.arg(arg=arg_name, annotation=None)],
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
            body.append(_assign(
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
            ))
    else:
        body.append(_assign(
            arg_names[0],
            ast.Attribute(
                value=ast.Name(id="evidence", ctx=ast.Load()),
                attr="input",
                ctx=ast.Load(),
            ),
        ))

    if extraction.chain_kind == "if":
        body.append(_collapse_if_chain(
            extraction.chain_node,  # type: ignore[arg-type]
            extraction.has_trailing_default,
            extraction.trailing_default_label,
        ))
    else:
        body.append(_collapse_match(extraction.chain_node))  # type: ignore[arg-type]

    return ast.FunctionDef(
        name="_rule",
        args=ast.arguments(
            posonlyargs=[],
            args=[ast.arg(arg="self", annotation=None),
                  ast.arg(arg="evidence", annotation=None)],
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
                node.orelse = [ast.Return(
                    value=ast.Constant(value=trailing_default_label)
                )]
                break
            if len(node.orelse) == 1 and isinstance(node.orelse[0], ast.If):
                node = node.orelse[0]
                continue
            break
    return new_head


def _copy_if(node: ast.If) -> ast.If:
    """Copy an If node, replacing its body with ``return <label>``.

    The label is the string literal returned by the ORIGINAL branch's
    final return — we already validated it during extraction, so we
    can pull it back out here.
    """
    label = _branch_label(node.body)
    new_body = [ast.Return(value=ast.Constant(value=label))]
    new_orelse: list[ast.stmt] = []
    if node.orelse:
        if len(node.orelse) == 1 and isinstance(node.orelse[0], ast.If):
            new_orelse = [_copy_if(node.orelse[0])]
        else:
            else_label = _branch_label(node.orelse)
            new_orelse = [ast.Return(value=ast.Constant(value=else_label))]
    return ast.If(test=node.test, body=new_body, orelse=new_orelse)


def _collapse_match(node: ast.Match) -> ast.Match:
    """Copy a Match node, replacing each case body with
    ``return <label>``. Patterns are reused verbatim so the
    user's case structure round-trips intact.
    """
    new_cases: list[ast.match_case] = []
    for case in node.cases:
        label = _branch_label(case.body)
        new_cases.append(ast.match_case(
            pattern=case.pattern,
            guard=case.guard,
            body=[ast.Return(value=ast.Constant(value=label))],
        ))
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
) -> ast.FunctionDef:
    """Build _on_<label> from the branch's pre-return statements.

    For multi-arg input, we re-introduce local aliases so the original
    statements run unchanged (e.g., ``method = packed.method``).
    """
    body: list[ast.stmt] = []
    if multi_arg:
        for name in arg_names:
            body.append(_assign(
                name,
                ast.Attribute(
                    value=ast.Name(id="packed", ctx=ast.Load()),
                    attr=name,
                    ctx=ast.Load(),
                ),
            ))
    body.extend(branch.body)

    handler_arg = "packed" if multi_arg else arg_names[0]
    return ast.FunctionDef(
        name=f"_on_{branch.label}",
        args=ast.arguments(
            posonlyargs=[],
            args=[ast.arg(arg="self", annotation=None),
                  ast.arg(arg=handler_arg, annotation=None)],
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


# ----------------------------------------------------------------------
# Tiny AST helpers
# ----------------------------------------------------------------------


def _assign(name: str, value: ast.expr) -> ast.Assign:
    return ast.Assign(
        targets=[ast.Name(id=name, ctx=ast.Store())],
        value=value,
    )
