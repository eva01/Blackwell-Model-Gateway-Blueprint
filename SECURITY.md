# Credentials and public distribution

The distributed blueprint must contain configuration templates and synthetic or sanitized evidence only. Generate new credentials during installation. Store live configuration, user keys, administrator credentials, databases, logs and acceptance records under private `runtime/` storage or an approved external secret store.

## Publication review — 6 November 2026

Local Gitleaks 8.30.1 scans and a manual review found no real credentials in the current tracked package. The scan included the working directory and all three locally reachable commits, including remote-tracking and recovery references. Additional rules cover this project's virtual-key format and long assigned backend credentials. No candidate credentials were submitted to an external validation service.

The manual review also checked the evidence and examples for deployment identifiers, addresses and private paths. Current examples use loopback addresses, placeholders and synthetic fixtures. Artifact SHA-256 values identify files/images; they are not API credentials. Git author attribution includes the maintainer's configured name and GitHub no-reply email.

**The older remote history still contains retired deployment identifiers and institution-specific material.** A clean local working tree or a local squash does not replace GitHub history. Publish the reviewed, flattened branch before changing repository visibility. Do not push recovery refs or use `git push --mirror`. Review the remote state again after updating it.

For the cleanest public release, publish this reviewed root commit to a new repository and keep the original repository private. If converting the original repository instead, consider GitHub's retained old objects as well as branch history: a force-push alone does not guarantee that old commits are inaccessible by their hashes. Follow [GitHub's sensitive-data removal guidance](https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/removing-sensitive-data-from-a-repository) if those retained objects must be purged.

At review time the GitHub repository was private, with one branch and no tags, releases, pull requests, issues or Actions artifacts. Repository content, reachable local history and that remote inventory were reviewed. This does not establish that copies outside the repository, provider-retained objects, old downloads, forks, wiki content or external systems contain no sensitive information. A scanner cannot prove that every arbitrary secret has been detected.

## Repeat the local credential scan

With Gitleaks installed, run from the repository root:

```bash
umask 077
mkdir -p runtime/publication-review
gitleaks dir . --config .gitleaks.toml --redact=100 --no-banner \
  --max-archive-depth 3 --report-format json \
  --report-path runtime/publication-review/files.json
gitleaks git . --log-opts="--all" --config .gitleaks.toml --redact=100 --no-banner \
  --report-format json --report-path runtime/publication-review/history.json
```

A nonzero scanner exit requires investigation. The directory scan can also find legitimate credentials in ignored runtime files; those must remain outside the published package. Keep reports private. Review every finding rather than adding a blanket allowlist. Inspect the exact tracked files and history you intend to publish; `.gitignore` does not remove already tracked files or old commits. The root configuration extends Gitleaks' standard rules instead of replacing them.

Environment variants, common credential formats, databases, logs and backup archives are ignored to reduce accidental additions. Explicit `git add -f` can bypass that protection. Publish tracked source files through Git or a reviewed source archive; do not distribute an entire working directory, its `.git` directory, runtime state or private recovery archives.

## If a real credential is discovered

Revoke or rotate it at the issuing system, remove it from distributable content and applicable Git history, and rescan. Deleting a file or changing repository visibility does not invalidate a credential or erase copies others already obtained. Contact the maintainer through an established private channel; do not paste credentials into a public issue, pull request, chat transcript or scanner report attachment.
