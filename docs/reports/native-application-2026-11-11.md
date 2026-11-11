# Native application validation

The 1.1.0 source candidate adds a genuine Windows Tk workbench over the existing model core.
These are observed local results from the patched CPython 3.14.10/Tcl 9.0.4/Tk 9.0.4 SDK and
isolated dependencies. Hosted exact-source results, release publication and installation
must be recorded separately; this report does not claim they have already occurred.

## Source and core gates

- Full selected Python suite after profile-boundary review: **87 passed, 1 PostgreSQL integration test deselected**,
  original-core branch-aware coverage **97.16%**, above the unchanged 95% floor.
  The denominator is `ml_observatory`; it does not pretend the native GUI/build code has
  that coverage. Native adapter/archive/identity regressions are included in the 87.
- Separate actual Tk-control suite: **3 passed**. It exercises real control callbacks,
  valid and invalid data, explicit promotion cancellation/acceptance, inference, busy close,
  retained profile ownership and minimum-window help/exit controls.
- Ruff source/format checks and original strict mypy passed. The core benchmark measured
  800 training records in **1.312 seconds** and 5000 inferences with **0.0166 ms p95** on this
  PC, below unchanged 30-second / 5-ms budgets. These are local synthetic-workload results,
  not a general performance guarantee.
- Both Kubernetes objects validated. Combined original/native locked dependency audit:
  **no known vulnerabilities found** at the time of the check. Existing PostgreSQL and
  container checks are left to their real hosted jobs; Docker on this PC was unchanged.

## Actual native acceptance

The source-bound prototype is deliberately labeled `sourceDirty: true`; it is not a clean
published release. Its complete PyInstaller scientific-library/Tk directory runs with only
System32 on the child PATH, loading its bundled Python/Tk/scientific runtime. This is not a
claim that those tools were removed from the test PC. Actual relocated
executable acceptance requires two normal-exit launches against one marked synthetic profile:

1. Prepare and validate 1200 editable service-health observations; train the real logistic
   and compact-MLP candidates. Verify that neither is automatically promoted.
2. Inspect hash-verified evidence, cancel then explicitly confirm eligible promotion,
   assign a shadow challenger, execute an actual champion/shadow prediction, compute PSI
   across eight features, and export/re-read the actual dossier without overwriting a file.
3. Invalid JSON is rejected while the last valid dataset remains intact. Reopen without
   training and compare exact retained model IDs, champion and dataset digest; run another
   real prediction and close through the normal lifecycle.

The independent tests also corrupt a prior champion's actual artifact and prove rollback
refuses it before changing deployment. Restoring the exact artifact permits real rollback.
No arbitrary serialized/executable models, external requests or normal account data are used.

Independent source review identified two admission gaps before publication: Windows directory
junction ancestors and frozen profiles selected inside the application/resource tree. Both
are now refused before directory creation, locking or SQLite access. Real marked-store tests
use an actual Windows junction and both frozen roots, verify every preexisting target file
remains byte-identical and prove missing descendants remain uncreated. A separate test keeps
legitimate source-development `.runtime` profiles allowed. The focused profile/identity suite
passes **14 tests**; the full and actual-Tk counts above were rerun after this correction.

## Failures retained and corrected

An early test compared Python tuple evidence with its correct JSON array round trip. The
oracle now compares the exact serialized structure; no product field is omitted. Another
Windows harness wrote an LF protocol marker using text-mode newline translation, producing
CRLF. The application correctly refused that marker before opening its profile. The harness
now writes exact binary marker bytes, with a regression proving the distinction. The failed
prototype/proof directories remain separate from passing fresh runs. Neither failure was
hidden through an increased deadline, a rerun allowance or relaxed model quality assertions.

## Scope

The Windows package is unsigned and single-OS-owner, with plaintext durable local data.
Prepared synthetic observations do not validate arbitrary industries or real production
failure prediction. Hash-verified dossiers expose recorded evaluation rather than rerunning
it. Native tests do not certify every display configuration, clean machine or operating
system. See [native usage, data, bounds and recovery](../native-application.md).
