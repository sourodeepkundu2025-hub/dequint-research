"""Small offline network example; not a substitute for a paper experiment."""

import json

from dequint.config import ModelConfig
from dequint.network import Network
from dequint.workload import make_workload


def main():
    config = ModelConfig(mesh_side=4, policy="midpoint", placement="restored")
    requests = make_workload(4, 8, 1000, 101, config.deadline_s)
    result = Network(config, requests, 101, "minimal_example", trace=True).run()
    print(json.dumps(result["summary"], indent=2))


if __name__ == "__main__":
    main()
