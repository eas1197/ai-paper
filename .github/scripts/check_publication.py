"""I21: fail closed on obvious private artifacts before publication.

Checks only selected candidate Git blobs; no history audit, credential store
access, network calls, or printing candidate paths, content, or token values.
This is a minimum technical guard, not a privacy/consent certification.
"""
import argparse
import re
import subprocess
import sys
from pathlib import PurePosixPath

PRIVATE_DIRS = {"private", "raw_data", "fulltext", "evidence_store", "runs",
                "runs_dev", ".codex", ".ssh", ".aws", ".gnupg"}
PRIVATE_NAMES = {"auth.json", "login.json", "credentials.json", "credentials",
                 "token.json", "tokens.json", "secrets.json", "id_rsa",
                 "id_ed25519", "events.jsonl", "stderr.log", "stdout.log"}
PRIVATE_SUFFIXES = {".pem", ".key", ".p12", ".pfx", ".dta", ".sav", ".por",
                    ".parquet", ".sqlite", ".db", ".db-wal", ".db-shm"}
ARCHIVE_TEXT = {".json", ".md", ".txt", ".csv", ".jsonl", ".yaml", ".yml"}
# Restrict generic repository-wide rules to highly characteristic credentials;
# assignment heuristics only apply to research archives, not source examples.
TOKEN_RULES = (
    ("private_key_material", re.compile(r"-----BEGIN (?:[A-Z0-9]+ )*PRIVATE KEY-----")),
    ("github_token", re.compile(r"\b(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{30,})\b")),
    ("openai_token", re.compile(r"\bsk-(?:proj-|svcacct-)?[A-Za-z0-9_-]{32,}\b")),
    ("aws_access_key", re.compile(r"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b")),
    ("bearer_token", re.compile(r"(?i)\bBearer[ \t]+[A-Za-z0-9_.~+/-]{24,}={0,2}")),
)
ARCHIVE_RULES = (
    ("credential_assignment", re.compile(
        r"""(?im)(?:["']?(?:api[_-]?key|access[_-]?token|refresh[_-]?token|password|client[_-]?secret|authorization|cookie)["']?)\s*[:=]\s*["']?(?!null\b|false\b|true\b|redacted\b|not_checked\b|<|\$\{)[^\s"',}\]]{12,}""")),
    ("local_home_path", re.compile(r"(?i)(?:[A-Z]:[\\/](?:Users|Documents and Settings)[\\/]|/(?:home|Users)/)[^/\s\\\"']+")),
    ("url_credentials", re.compile(r"(?i)https?://[^/\s:@]+:[^/\s@]+@")),
)


def inspect_candidate(path, raw, *, mode="100644"):
    """Return rule codes only. All inputs are selected publication candidates."""
    parts=PurePosixPath(path).parts
    if not parts or "\\" in path or path.startswith("/") or ".." in parts:
        return {"invalid_path"}
    low=tuple(p.lower() for p in parts)
    name=low[-1]
    suffix=PurePosixPath(name).suffix
    if mode not in {"100644","100755"}:
        return {"non_regular_candidate"}
    if (set(low[:-1]) & PRIVATE_DIRS or name in PRIVATE_NAMES or
            suffix in PRIVATE_SUFFIXES or name==".env" or
            (name.startswith(".env.") and name!=".env.example")):
        return {"private_artifact_path"}
    archive=low[0]=="handoff_runs"
    if archive and suffix not in ARCHIVE_TEXT:
        return {"archive_requires_reviewed_text"}
    try:
        value=raw.decode("utf-8-sig")
    except UnicodeError:
        return {"archive_requires_reviewed_text"} if archive else set()
    if archive and "\x00" in value:
        return {"archive_requires_reviewed_text"}
    rules={kind for kind,pattern in TOKEN_RULES if pattern.search(value)}
    if archive:
        rules.update(kind for kind,pattern in ARCHIVE_RULES if pattern.search(value))
    return rules


def _git(*args):
    return subprocess.run(["git",*args],check=True,capture_output=True).stdout


def candidate_paths(*, staged, base=None, head=None):
    args=["diff","--name-only","-z","--no-renames","--diff-filter=ACMRT"]
    args+=["--cached"] if staged else [base,head]
    return [p.decode("utf-8") for p in _git(*args,"--").split(b"\0") if p]


def check_git(*, staged, base=None, head=None):
    counts={}
    paths=candidate_paths(staged=staged,base=base,head=head)
    for path in paths:
        if staged:
            entry=_git("ls-files","--stage","-z","--",path).split(b"\0")
            rows=[r for r in entry if r]
            if len(rows)!=1:
                raise ValueError("Unmerged candidate")
            mode,oid,stage=rows[0].split(b"\t",1)[0].decode().split()
            if stage!="0":
                raise ValueError("Unmerged candidate")
        else:
            rows=[r for r in _git("ls-tree","-z",head,"--",path).split(b"\0") if r]
            if len(rows)!=1:
                raise ValueError("Invalid selected tree candidate")
            mode,kind,oid=rows[0].split(b"\t",1)[0].decode().split()
        # Do not dereference symlinks or submodules, nor read workstation files.
        raw=_git("cat-file","blob",oid) if mode in {"100644","100755"} else b""
        for kind in inspect_candidate(path,raw,mode=mode):
            counts[kind]=counts.get(kind,0)+1
    return len(paths),counts


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    mode=parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--staged",action="store_true")
    mode.add_argument("--base")
    parser.add_argument("--head")
    args=parser.parse_args(argv)
    if not args.staged and (not args.head or args.base=="0"*40):
        print("Publication check blocked: explicit reachable base and head required.")
        return 2
    try:
        total,counts=check_git(staged=args.staged,base=args.base,head=args.head)
    except (OSError,ValueError,subprocess.CalledProcessError):
        print("Publication check blocked: cannot inspect selected Git candidates.")
        return 2
    if counts:
        print("Publication check blocked; rule counts only:")
        for kind,count in sorted(counts.items()):
            print(f"{kind}: {count}")
        return 1
    print(f"Publication check: {total} candidate files; no configured pattern detected.")
    print("Not a privacy, consent, or historical repository certification.")
    return 0


if __name__=="__main__":
    sys.exit(main())
