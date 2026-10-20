# Third-Party Notices and Scientific Attribution

- **SeQUeNCe:** simulator by Argonne National Laboratory, Illinois Institute of
  Technology and Encore Consulting Services. The addon uses the public v1.3.0
  release, commit `88f92cca8aaa6dbf82bccc6a759465120afbdd34`.
  [Source and upstream license](https://github.com/sequence-toolbox/SeQUeNCe/tree/88f92cca8aaa6dbf82bccc6a759465120afbdd34).
  The upstream code is not vendored or modified by this release.
- **Qiskit/Qiskit Aer, NumPy, SciPy, pandas, NetworkX, Matplotlib and other
  dependencies:** installed separately with their original license terms;
  consult their distributions. `requirements-lock-windows-py312.txt` records
  the original observed environment, not ownership of those projects.
- **Protocols and prior work:** Barrett-Kok generation, teleportation, BBPSSW,
  entanglement swapping, per-link BSM/rendezvous designs, de Bruijn constructions
  and SABRE are established mechanisms. See `qa/SOURCE_LEDGER.csv`,
  `qa/shortcut_literature.csv` and the experiment protocols for attribution and
  the precise comparison scope. Literature entries are not reproduced baselines
  unless explicitly identified as such.
- **GitHub Actions:** CI references official `actions/checkout` and
  `actions/setup-python`, pinned to full commit identities. Their source is
  retrieved by the CI service rather than copied into this repository.

No third-party full-text papers, Wiley template distributions or fonts are
included in this public snapshot. A dependency's license does not automatically
license the DEQUINT addon or historical research data.
