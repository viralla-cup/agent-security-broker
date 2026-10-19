# Project status

Updated 19 October 2026, Asia/Qyzylorda. The local Section 17 engineering slice is
implemented and passing. The required real-model stage remains pending access and
adapter integration. The article, full experiment, and supervisor approval are not
complete.

## Current evidence

The final isolated engineering suite passed **48 tests**, exit code 0, in the pytest
reported test time of **0.53 seconds**. This is not broker latency or end-to-end
container runtime. Exact command, stdout/stderr, image ID, and source hashes:
`results/checks-20261019T104349Z-9c1be1/`.

The final development replay passed **15/15 case-condition checks**: five cases
under B0, B2, and B2a, six calls per condition. Evidence is in
`results/dev-20261019T104349Z-7e16ab/summary.json`, `summary.csv`, `trace.jsonl`, and
the fifteen case records containing before/after snapshots and isolation evidence.

| Observed outcome | B0 | B2 | B2a |
| --- | --- | --- | --- |
| Case expectations satisfied | 5/5 | 5/5 | 5/5 |
| Actual calls | 6 | 6 | 6 |
| Policy denials | 0 | 3 | 3 |
| Episodes disclosing synthetic canary | 2/5 | 0/5 | 0/5 |
| Episodes with a targeted prohibited effect | 3/5 | 0/5 | 0/5 |
| Authorized read returned correct content | Yes | Yes | Yes |
| Authorized write created correct content | Yes | Yes | Yes |
| Continuation wrote the authorized output | Yes, plus unauthorized file | Yes, after denial | Yes, after denial |

These denominators describe this finite development corpus. All three prohibited
requests were feasible in B0 and prevented in B2/B2a. Zero observed prohibited effects
does not prove security. B2a's successful continuation is expected because the second
request was scripted identically; it is not evidence for or against the feedback
hypothesis. **Actual LLM episodes: 0.** No model recovery, portability, attack success
rate under prompt injection, confidence interval, or performance benefit is claimed.

The runner independently confirmed identical paired initial snapshots and identical
recorded containment. The client had UID 10002, no `/lab`, no Docker socket, no writable
policy, zero effective capabilities, no-new-privileges, and seccomp filtering. The
executor used UID 10001 and a private synthetic tmpfs. A connection from an
unauthorized peer UID was rejected. Both services had no external network, no host
bind mounts, read-only root filesystems, and matching resource limits. All replay
containers and channel volumes were removed after completion. The built image remains
for reproduction; unrelated Docker resources were not modified.

The final image ID is
`sha256:9aa0fc20b24e2b9f0360ed0e908d22e18f7bbc37a0b0ddf5a50ff872296a3bc4`.
The base image is pinned by digest in Dockerfile. Runtime package versions and the
policy SHA-256 are in run metadata and events. The Git base is
`5845904197e7761ac2bee8b8abd9ef3a8d5206ff`; implementation changes remain uncommitted
on the existing `main` branch. Exact final source hashes were rechecked against the
run metadata, then the owned executable sources, tests, manifest, and build files
were retained in that run's `source_snapshot.zip`.

## Development history and limitations

The first engineering execution passed 47 tests; the first replay also passed all
15 checks and remains at `results/dev-20261019T103949Z-c1c93b/`. A subsequent revision
made hints recheck public alternatives against policy, added a revoked-alternative
test and a Unix-peer isolation probe, and excluded host bytecode from the build.
The complete affected comparison was rerun in the final evidence above. These are
development revisions, not independent replications. The earlier source hash record
is retained, but only the final revision has a complete source archive.

The initial DOCX text extraction hit a Windows cp1251 Unicode encoding error. It
was rerun using UTF-8, and the context was read successfully. No test or enforcement
failure was observed in the completed suites. No failures are silently converted
into success. Future infrastructure failures are retained as separate failure records.

This is a two-tool Linux laboratory. No general shell, network tool, overwrite,
deletion, installation simulator, actual adversarial AGENTS.md/CLAUDE.md, backend
adapter, or autonomous LLM loop has been added. Randomized main evaluation, human
label review, broader benign/attack corpus, concurrency/fault-injection testing, and
two-backend evidence remain future work. Synthetic canaries are deterministic per
case for pairing; they are not real secrets. Their exact values do not appear in the
exported JSON/CSV/text evidence. Raw synthetic traces remain under ignored `.local/`.

The audit is an in-memory event returned to the trusted harness and then saved;
this slice does not implement a durable pre-dispatch audit transaction or crash
recovery. A process crash between execution and evidence persistence can leave an
unrecorded effect; the current finite successful runs do not test that fault model.
Snapshot/oracle implementation independence is not independent human validation.
No unrestricted concurrent writer or Linux kernel/Docker escape is modeled.

## Next concrete task

Select and expose one real programmatic model backend, implement its bounded JSON
proposal adapter, and run one independently checked task through the same transport
and broker: read the synthetic measurements and create `Mean: 4\n` in output.
Then add a separately labeled controlled-denial recovery task. Do not substitute
a scripted agent or this development chat for a model run.

Required access is an exact model identifier and reachable local endpoint, or a
provider endpoint/model with credentials supplied through the environment, an
explicit synthetic-data transfer authorization, and a call/cost limit. Credentials
must remain outside fixtures, prompts, logs, Git, and executor containers. The
standard environment-key checks and default local Ollama probe were unavailable;
their sanitized audit is `docs/environment-audit.json`. No model purchase, external
upload, publication, or submission was performed.

Before scaling: confirm the provisional title/scope with the supervisor, cross-review
the manifest with the co-author, resolve missing handover notes when supplied, and
freeze a practical main-evaluation protocol. The deadline remains 31 October 2026.
