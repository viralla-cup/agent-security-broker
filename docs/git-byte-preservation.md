# Git byte preservation

Source and evidence identities in this project hash actual file bytes, including
line endings. The root `.gitattributes` disables Git text conversion (`-text`) for
the source-manifest input directories, its four root inputs, the two additional
reviewed documents, and the explicitly listed public result directories being
packaged with this revision. This preserves both LF
and CRLF as recorded, independently of `core.autocrlf=true`, `input`, or `false`.
It leaves text diffs enabled; it does not mark these files as `binary`.

Do not normalize or reformat historical evidence, regenerate historical hashes,
or use a repository-wide `git add --renormalize .`. Stage the intended paths and
compare index blobs with the retained reviewed bytes before committing. Existing
Git history and already committed result blobs are unchanged. Four existing
source inputs need their reviewed CRLF bytes staged instead of the old normalized
LF blobs: `experiments/study-review-template.json`, `scripts/run_agent_pilot.py`,
`src/lab/pilot_evidence.py`, and `tests/test_expanded_study.py`. Their working files
are not rewritten. This is an explicit packaging correction, not an experiment.

Newly authored source should normally use LF. Preserve the recorded convention
when editing an existing hash-bound input. Editors can still change line endings:
attributes govern Git conversion, not editor saves. Adding another hash-bound
path outside these directories, including a new result directory, requires an
explicit attribute and verification. The evidence allowlist deliberately avoids
changing 937 historical result blobs that were previously stored as LF while the
local files use CRLF. Those older paths retain their legacy Git conversion behavior;
this correction does not claim to repair their cross-platform byte reproducibility.

For the approved Expanded Study v1.1 revision, `.gitattributes` and this document
are outside the existing 66-file source manifest and 70-file source snapshot.
They are also excluded from the Docker build context. The existing source and
plan digests must remain unchanged. There is no source-content or source-boundary
change requiring a repeat implementation review. A narrow independent packaging
check can verify the new Git rules; the verification report is implementer evidence,
not independent attestation or paid-run authorization. Do not represent the earlier
PASS as a review of these newly added packaging files.

Verification must compare raw index blobs, then restore a staged Git tree into
empty isolated directories using Git's checkout machinery with `core.autocrlf`
set to `true`, `input`, and `false`. No commit is needed (`git write-tree`, followed
by an isolated index and `git checkout-index`, suffices). Check all 34 final review
manifest entries, all 70 snapshot entries, all 66 current source hashes, and the
recomputed plan digest in each restored tree. Compare earlier review manifests
within their own packages; old source snapshots describe their own revisions.
Keep private `.local/` files, credentials, histories, and receipts out of the index.

The policy does not defeat overriding `.git/info/attributes`, global/custom
filters, editor rewrites, malicious host changes, or loss of private evidence.
Fresh-checkout verification is specific to the Git implementation tested; changing
attributes, filters, or the Git distribution warrants repeating the packaging check.
Original commits retain their original Git blobs. A source ZIP remains an exact
historical byte snapshot rather than proof that an older checkout had those bytes.
