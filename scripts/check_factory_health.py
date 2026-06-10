import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.hermes.factory_health_check import FactoryHealthChecker


def main() -> int:
    report = FactoryHealthChecker().run()

    print("\nFactory Health Check")
    print("--------------------")
    print(f"Overall Status: {report.status}")

    for result in report.results:
        print(f"\n[{result.status}] {result.check_name}")
        print(result.message)

    return 0 if report.passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
