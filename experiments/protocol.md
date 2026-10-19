# Filesystem vertical slice protocol

Status: development protocol, 19 October 2026. Not a frozen main evaluation and
not supervisor-approved. The five cases were specified before the first replay.

## Objective and authority

Measure whether a trusted broker prevents specified prohibited file effects while
retaining authorized reads, creation of new output files, and a permitted next step
after denial. This slice evaluates enforcement mechanics. It does not measure LLM
planning, prompt-injection resistance, population-level security, or feedback efficacy.

The user authorizes reading the synthetic project except its explicitly protected
private subtree, and creating new files under `/lab/project/output`. Secrets and
control markers are outside that authority. The protected private subtree provides
a denial-precedence engineering case inside the broader read grant. Source writes
are prohibited even when a report would be useful. No approvals or policy changes
occur within an episode.

The current corpus uses absolute ASCII POSIX paths. B2 rejects dot components,
repeated separators, percent encoding, backslashes, colons, control characters,
and non-ASCII path names. This is a deliberately restricted interface, not a
universal pathname parser. File contents are bounded UTF-8.

## Conditions and paired execution

B0 uses the same typed API, executor, input state, size/call limits, and outer
Docker containment as B2. It normalizes paths within `/lab` and omits internal
resource authorization. Therefore it can read the protected synthetic file and
create a report outside output. Link restrictions remain shared and cannot support
a B2 versus B0 effect claim about links in this version.

B2 enforces policy and returns a reason plus a public authorized alternative.
B2a enforces identical policy but returns a generic denial without the hint. It
retains status, retryability, and request ID for the common transport contract.
Internal audit records retain reasons, but these are not model feedback.

For each case, B0, B2, and B2a start fresh. Snapshot equality and equality of
recorded containment are asserted across all three conditions. Ordering is fixed
for this engineering smoke test. No randomized order, warm-up protocol, repeated
timing experiment, confidence interval, or held-out result is claimed.

The five cases contain six calls per condition. The continuation case has a
deliberately disallowed write followed by the same predeclared authorized write in
every condition. It is controlled replay, not naturally elicited model recovery.

## Independent observation

`lab.oracle` imports neither policy nor authorization code. Expected decisions and
effects are literal manifest data. A trusted observer snapshots every laboratory
file before and after each episode, using its own traversal and SHA-256 hashing.
Exact change sets and expected content hashes must agree. Initial file contents
must remain unchanged. The checker scans full synthetic responses and audit
records for the canary before redaction. Read confidentiality cannot be inferred
from unchanged files alone.

The trusted observer is not an agent tool. It uses privileged orchestration access
to the broker container for read-only observation. Its presence is part of the
trusted experimental infrastructure. No model is allowed to call it.

The five-case development table reports expected-decision agreement, observed
canary disclosure, exact file changes, and prohibited effects. Read attempts have
no legitimate-task completion label. A denied attempt is not counted as completed
work. A write is completed only when the output file content is verified. B0
feasibility is required for each of the three prohibited-effect requests (direct
read, traversal read, and off-scope write). Execution errors are distinct from
policy denial and are never silently credited as successful blocking.

## Limits and evidence handling

Twenty calls, three denials, 65,536 bytes per read/write, and 262,144 cumulative
reserved write bytes bound an episode. Failed writes retain their budget reservation.
File-creation errors may leave a partial file; there is no rollback claim. Errors
and snapshots preserve that possibility. Transport timeouts and a 300-second service
deadline bound runtime; interrupted host runs may require cleanup of named disposable
resources. The harness removes only the containers/volume it created.

No external writer or rename/link-creation tool is admitted. Descriptor-relative
operations reduce path substitution exposure under that deployment assumption.
There is no general TOCTOU, kernel-escape, denial-of-service, covert-channel, or
semantic correctness guarantee. Symlink and special-file open failures are recorded
as execution errors in some engineering cases; they are not corpus blocking successes.

Each run records base commit plus exact source hashes because development changes
may be uncommitted. Raw records and sanitized exports are written to unique new
directories. A code, policy, corpus, or oracle correction requires a new run; old
failures are retained. Logs contain no real secrets. No artifacts are uploaded.

Before the main evaluation, the authors must cross-review the independent labels,
add difficult benign and adversarial cases, integrate real backends, run a cost pilot,
freeze all versions, and approve sampling/analysis. The handover's 60-case replay and
432-episode grid are proposals, not completed or approved work.
