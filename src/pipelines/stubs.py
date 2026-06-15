"""Stub pipelines for routes not yet ported in the first vertical slice.

Each stub raises `NotImplementedYet` with the notebook / function it should be
ported from. This keeps the routing layer and UI fully wired so the remaining
pipelines can be dropped in one by one without touching the rest of the app.

Porting source (consolidated exports):
    examples/nr1-sigpac/cr_nr_analysis/
        CR_Calculator.py                -> run_pipeline (Italy CR, muni-level)
        CR_OPT_Calculator.py            -> run_pipeline (Italy CR + competition + cvxpy)
        CR_OPT_Calculator_Spain.py      -> run_pipeline (Spain CR + cvxpy)
        NR_Seminativi_Calculator.py     -> run_pipeline (Italy NR, has-level + competition)
        NR_OPT_Seminativi_Calculator.py -> run_pipeline (Italy NR + cvxpy)
        NR1_Sigpac_Spain.py             -> Spain NR (already ported in nr_spain.py)
        Verdalia_feedstock_class.py     -> MunicipalityFeedstockCalculator (kton + heads)
        Verdalia_feedstock_class_has.py -> hectares (seminativi) variant

All of these read from Unity Catalog (Spark) in the notebooks. When ported they
must be rewritten against the PostgreSQL layer in `src.backend`
(`PrepGoldView` / `PrepDigestateView`), exactly like `nr_spain.py`.
"""

from src.pipelines.router import NotImplementedYet, PipelineInput, PipelineResult


def _todo(label: str, source: str) -> PipelineResult:
    raise NotImplementedYet(
        f"{label} is not implemented in this first slice.\n"
        f"Port from: {source}\n"
        f"Rewrite its Unity Catalog reads against the PostgreSQL layer (src.backend), "
        f"following the pattern in src/pipelines/nr_spain.py."
    )


def feedstock_spain(inputs: PipelineInput) -> PipelineResult:
    return _todo(
        "Spain feedstock availability",
        "Verdalia_feedstock_class.MunicipalityFeedstockCalculator (reuse PrepGoldView, flag='spain')",
    )


def feedstock_italy(inputs: PipelineInput) -> PipelineResult:
    return _todo(
        "Italy feedstock availability",
        "Verdalia_feedstock_class.MunicipalityFeedstockCalculator (reuse PrepGoldView, flag='italy')",
    )


def hectares_spain(inputs: PipelineInput) -> PipelineResult:
    # Hectare availability for Spain is the NR pivot without the N step.
    return _todo(
        "Spain hectare availability",
        "NR1_Sigpac_Spain.py pivot_results (subset of nr_spain.py — drop the N columns)",
    )


def hectares_italy(inputs: PipelineInput) -> PipelineResult:
    return _todo(
        "Italy hectare availability",
        "Verdalia_feedstock_class_has.run_pipeline (gdf_vulnerable, no_vuln, vul, prod_tipo, flag='italy')",
    )


def cr_spain(inputs: PipelineInput) -> PipelineResult:
    # Spain has a single CR notebook (no OPT / non-OPT split).
    return _todo("Spain CR (cover ratio)", "CR_OPT_Calculator_Spain.run_pipeline")


def cr_italy(inputs: PipelineInput) -> PipelineResult:
    src = "CR_OPT_Calculator.run_pipeline (OPT + competition)" if inputs.optimize else "CR_Calculator.run_pipeline (non-OPT)"
    return _todo("Italy CR (cover ratio)", src)


def nr_italy(inputs: PipelineInput) -> PipelineResult:
    src = (
        "NR_OPT_Seminativi_Calculator.run_pipeline (OPT)"
        if inputs.optimize
        else "NR_Seminativi_Calculator.run_pipeline (non-OPT)"
    )
    return _todo("Italy NR (nitrogen ratio)", src)
