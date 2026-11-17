import argparse
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["pipeline", "prepare", "migrate"])
    parser.add_argument("--smoke", action="store_true")
    parser.add_argument("--output", type=Path, default=Path.cwd())
    parser.add_argument("--env", default="")
    args = parser.parse_args()
    if args.command == "pipeline":
        from .evaluation import pipeline

        pipeline(args.output, args.smoke)
    elif args.command == "prepare":
        import json

        import joblib

        from .data import Sources
        from .evaluation import prepare
        from .forecast import CANDIDATE, Forecaster

        report = json.loads((args.output / "evaluation/results/metrics.json").read_text())
        model = (
            joblib.load(args.output / "evaluation/results/pooled-model.joblib")
            if report["chosen_method"] == CANDIDATE
            else Forecaster()
        )
        prepare(Sources(args.output / "evaluation/raw"), model, args.output / "data")
        print("Prepared forecasts exported without retraining.")
    else:
        from dotenv import load_dotenv

        from .config import settings
        from .repository import Repository

        if args.env:
            load_dotenv(args.env, override=True)
        config = settings()
        repo = Repository(config.migration_url)
        repo.migrate()
        from .artifacts import bundle, forecast_index

        repo.register(forecast_index(bundle()).values())
        print("CashPilot schema v1 initialized.")


if __name__ == "__main__":
    main()
