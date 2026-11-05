# ERT Coding Good Practices

## RocketPy aligned team standard

This guide defines the minimum standard for simulation code written by the
EPFL Rocket Team. It aims to make every contribution readable, reviewable,
reproducible, and safe to integrate into RocketPy-based workflows. Follow it
for new features, bug fixes, scripts, notebooks, tests, and documentation.

## 1. Core principles

- Prefer clear, correct, and testable code over clever code.
- Keep physics assumptions, units, and coordinate conventions explicit.
- Make small, focused changes that preserve the public API unless an approved
  change is required.
- Treat warnings, failing tests, lint findings, and undocumented assumptions
  as work to resolve before review.
- Optimize only after correctness is established and performance is measured.

## 2. Code structure and naming

Place behavior in the package that owns the concept. In a RocketPy-style
project, simulation orchestration belongs in simulation modules; domain models
belong in rocket, motors, or environment modules; numerical primitives belong
in math utilities; and plotting or printing belongs in presentation layers.
Do not introduce a new top-level package when an existing package is the
natural home.

| Item                          | Required convention | Example 
| Modules, functions, variables | `snake_case`        | `calculate_dry_mass` 
| Classes                       | `PascalCase`        | `FlightConfiguration` 
| Constants                     | `UPPER_SNAKE_CASE`  | `DEFAULT_TIME_STEP` 
| Private implementation        | Leading underscore  | `_validate_units` 
| Booleans                      | Clear predicates    | `is_valid`, `has_motor` 

- Use descriptive names. Avoid single-letter names except for short, local
  mathematical notation.
- Keep lines at 88 characters or less unless the project configuration
  explicitly defines another limit.
- Use four spaces for indentation. Never use tabs.
- Keep imports at module level, ordered as standard library, third-party
  packages, then local imports.
- Avoid mutable default arguments, hidden global state, and broad exception
  handling.
- Add type-hinting for functions parameters and variables as it improves 
  readability and does not impact the execution.

## 3. Scientific and RocketPy-specific requirements

Simulation code is engineering code. A value without a unit, reference frame,
or source is difficult to review and easy to misuse. All model changes must
make their physical meaning clear to the next contributor.

- Use SI units by default and document units in parameter names, docstrings,
  or comments where ambiguity is possible.
- State coordinate-system and orientation conventions explicitly, including
  conventions such as `tail_to_nose` and `nozzle_to_combustion_chamber`.
- Do not silently convert units, clip values, or apply numerical fallbacks
  without documenting the behavior and testing it.
- Use `pytest.approx` for floating-point assertions and define tolerances from
  physics or numerical error, not convenience.
- Use `cached_property` only for genuinely expensive derived values and define
  how caches remain valid when inputs can change.

## 4. Documentation and comments

Documentation explains the contract. Comments explain non-obvious decisions,
assumptions, or constraints. Neither should repeat code that is already clear.
All production comments, docstrings, messages, and user-facing labels must be
in English.

- Write NumPy-style docstrings for public classes, functions, and methods.
  Include parameters, units, return values, exceptions, and relevant
  reference-frame conventions.
- Write comments in complete English sentences when they explain a decision.
  Remove commented-out code and obsolete comments.
- Document assumptions, limits of validity, data sources, and numerical methods
  close to the code that uses them.
- Update API documentation and examples whenever public behavior changes.
  Build documentation and address warnings when documentation files are
  changed.

```python
def center_of_mass(position: float, mass: float) -> float:
    """Compute axial center of mass.

    Parameters
    ----------
    position : float
        Axial position from the tail [m].
    mass : float
        Component mass [kg].

    Returns
    -------
    float
        Axial center-of-mass position from the tail [m].
    """
    return position
```

## 5. Tests and validation

- Add or update tests for every behavior change. A change without a regression
  test is normally incomplete.
- Use Arrange, Act, Assert structure and test names that state the expected
  behavior.
- Keep fast, method-focused tests as unit tests. Use integration tests for
  broad I/O or multi-component behavior, and acceptance tests for realistic
  flight scenarios.
- Use repository fixtures from `tests/fixtures`. Register new fixture modules
  through `tests/conftest.py` when required.
- Run focused tests first, then the relevant broader suite. Do not mark a test
  as slow merely because it currently fails or is inconvenient.

## 6. Formatting and static analysis

Run automated checks locally before requesting review. These tools are
complementary: Black formats code, Flake8 reports style and simple correctness
issues, and Pylint identifies broader design and maintainability concerns.
Project configuration is the source of truth.

| Tool             | Purpose                                   | Typical command 
| Black            | Formats Python consistently.              | `black .` 
| Flake8           | Checks style, imports, and common errors. | `flake8 .` 
| Pylint           | Checks code quality and maintainability.  | `pylint <module_or_package>` 
| Pytest           | Runs tests and regression checks.         | `pytest tests/<target>` 
| Project Makefile | Runs repository-standard workflows.       | `make format`, `make lint`, `make pytest` 

- Do not suppress a lint rule simply to make a command pass. First fix the
  code; suppress a rule only when the exception is intentional, local, and
  explained.
- Do not commit generated caches, temporary data, local notebooks, plots, or
  large simulation outputs unless they are explicitly required by the change.

## 7. Git and contribution workflow

Keep Git history easy to review and safe to integrate. Make one logical change
per branch and avoid mixing refactors, formatting-only changes, generated
files, and feature changes in the same pull request.

- Branch from `develop` unless the project lead specifies another target.
  Keep `master` as the stable branch.
- Use branch names in the form `type/description`, for example:
  `bug/fix-tank-volume`, `enh/add-rail-model`, `doc/update-api-reference`, or
  `tst/cover-parachute-delay`.
- Keep commits small and explicit. Prefix commit and pull-request titles with
  the applicable project category: `BUG`, `DOC`, `ENH`, `MNT`, `TST`, `BLD`,
  `REL`, `REV`, `STY`, or `DEV`.
- Rebase your feature branch onto `develop` before opening or updating a pull
  request when the team workflow requires a linear history.
- Never force-push shared branches without agreement. Never commit secrets,
  personal tokens, or private flight data.

## 8. Pull request expectations

- Describe the problem, intended behavior, main design decision, and validation
  performed.
- Call out changes to units, reference frames, numerical methods, model
  assumptions, public APIs, data files, or performance.
- Include test evidence. For documentation changes, include documentation-build
  results. For plots or outputs, include only the artifacts necessary for
  review.
- Reviewers should prioritize correctness, physics safety, API compatibility,
  numerical stability, stale-cache risks, tests, and documentation before style
  preferences.

## 9. Pre-push checklist

- [ ] The code is in the correct module and uses the required naming
  conventions.
- [ ] Units, coordinate frames, orientations, and assumptions are explicit.
- [ ] Public interfaces have NumPy-style docstrings and comments explain only
  non-obvious decisions.
- [ ] New or changed behavior has focused tests, including an edge case where
  appropriate.
- [ ] Black, Flake8, and Pylint pass according to the project configuration.
- [ ] Focused tests and relevant broader tests pass.
- [ ] No unintended generated files, large outputs, credentials, or unrelated
  formatting changes are staged.
- [ ] The branch name, commits, target branch, and pull-request description
  follow team conventions.

## 10. Team rule

If a contributor cannot explain the purpose, assumptions, units, validation,
and integration impact of a change, the change is not ready to merge. Ask for
help early; code review is a shared engineering process, not a final gate after
the work is complete.
