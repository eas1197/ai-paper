"""Run a ChatGPT-authenticated Codex search and admit only traceable observations."""

import json
import os
from pathlib import Path
import re
import shutil
import subprocess
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from abstract_acquisition import abstract_text, clean_doi, job_lock, safe_url, text_hash
from collect_common import digest, load, normalize, now, sha, write
from verified_identity import MATCH, resolve


ENGINE = "codex_native_v1"


def web_url(url):
    if not safe_url(url):
        # Source references may point to an abstract on the first page of a publisher PDF.
        if not isinstance(url, str):
            return None
        try:
            parsed = urlsplit(url)
        except ValueError:
            return None
        if (parsed.scheme != "https" or not parsed.hostname or parsed.username
                or not parsed.path.lower().endswith(".pdf")):
            return None
    parsed = urlsplit(url)
    query = [(key, value) for key, value in parse_qsl(parsed.query, keep_blank_values=True)
             if not key.lower().startswith("utm_")]
    return urlunsplit((parsed.scheme, parsed.netloc.lower(), parsed.path.rstrip("/") or "/",
                       urlencode(sorted(query)), ""))


def evidence(path):
    trace = []
    with path.open(encoding="utf-8-sig") as stream:
        for line in stream:
            event = json.loads(line)
            item = event.get("item") or {}
            if event["type"] == "item.completed" and item.get("type") == "web_search":
                trace.append(item)
            if event["type"] == "item.completed" and item.get("type") in (
                "command_execution", "mcp_tool_call", "file_change",
            ):
                raise ValueError("Non-native execution in literature search session")
    return trace


def proof(url, event_id, trace):
    canonical = web_url(url)
    for event in trace:
        if not canonical or event["id"] != event_id:
            continue
        if any(web_url(result.get("url")) == canonical for result in event.get("results", [])):
            return True
        action = event.get("action")
        if isinstance(action, dict) and action.get("type") in ("open_page", "find_in_page"):
            return web_url(action.get("url")) == canonical and bool(event.get("results"))
    return False


def url_event(url, trace):
    # The model sees search references; CLI item ids belong to the outer receipt.
    return next((event["id"] for event in reversed(trace)
                 if proof(url, event["id"], [event])), None)


def observation(row, trace, journals, batch, position):
    if row["journal"] not in journals or not normalize(row["title"]):
        raise ValueError("out_of_scope")
    authors = [name.strip() for name in row["authors"] if isinstance(name, str) and name.strip()]
    if not authors or not 1900 <= row["year"] <= 2100:
        raise ValueError("bibliography_incomplete")
    if row["relevance"] not in ("direct", "substantive") or not row["relevance_reason"].strip():
        raise ValueError("relevance_unconfirmed")
    summary = abstract_text(row["abstract_summary"], row["title"])
    excerpt = row["abstract_excerpt"].strip()
    if not summary or not 8 <= len(excerpt) <= 90 or not row["abstract_locator"].strip():
        raise ValueError("abstract_not_verified")
    identity_event = url_event(row["metadata_url"], trace)
    abstract_event = url_event(row["abstract_url"], trace)
    if not identity_event or not abstract_event:
        raise ValueError("missing_native_tool_receipt")
    return dict(row, authors=authors, doi=clean_doi(row["doi"]), year=str(row["year"]),
                status="valid_abstract", provider="codex_native_web", url=row["abstract_url"],
                abstract_summary=summary, abstract_hash=text_hash(summary),
                excerpt_sha256=text_hash(excerpt), searched_at=now(), batch=batch,
                observation_id=f"{batch}:{position}",
                metadata_event_id=identity_event, abstract_event_id=abstract_event)


def group(rows):
    """Apply the existing identity rule across all observations and registered journals."""
    components = []
    problems = []
    for row in rows:
        linked = []
        for component in components:
            for prev in component:
                same_doi = row["doi"] and row["doi"] == prev["doi"]
                same_title = (row["journal"] == prev["journal"]
                              and normalize(row["title"]) == normalize(prev["title"]))
                if same_doi or same_title and row["year"] == prev["year"]:
                    decision = resolve(prev, row)
                    if decision in MATCH:
                        linked.append(component)
                    elif same_doi or decision == "doi_conflict":
                        problems.append({"ids": [prev["observation_id"], row["observation_id"]],
                                         "reason": decision})
            # Compare each member; a lone author cannot bridge incompatible teams.
        merged = [row]
        for component in linked:
            if component in components:
                components.remove(component)
                merged.extend(component)
        components.append(merged)
    bad = {ident for conflict in problems for ident in conflict["ids"]}
    papers = []
    for component in components:
        conflicts = [resolve(a, b) for pos, a in enumerate(component) for b in component[pos + 1:]
                     if resolve(a, b) not in MATCH]
        if conflicts:
            problems.append({"ids": [r["observation_id"] for r in component],
                             "reason": "ambiguous_bridge:" + conflicts[0]})
        if conflicts or any(r["observation_id"] in bad for r in component):
            continue
        r = max(component, key=lambda item: (len(item["authors"]), item["relevance"] == "direct"))
        ident = r["doi"] or [r["journal"], normalize(r["title"]), r["year"],
                            sorted(normalize(n) for n in r["authors"])]
        papers.append(dict(r, article_id="A_" + digest(ident)[:24], provenance=component))
    return papers, problems


LEGACY_LOGIN_SOURCE = "4ceaa8c84aefb9468d66b623cbd93567c4fa2361139e6dcdb7c495584b6b7173"
UNCHANGED_COLLECTOR_CONTRACT = "d61e400a004e67c579eb1868fda0d59a2b9dd605c33b161ed9553514bfbd12c2"
LEGACY_LOGIN_FAILURE = "Codex CLI needs the existing ChatGPT login"


def cli_environment():
    env = {k: v for k, v in os.environ.items()
           if not (k.upper().endswith("_API_KEY") or k.startswith("CODEX_APP_TOOLS_")
                   or k in {"CODEX_SANDBOX_NETWORK_DISABLED", "CODEX_THREAD_ID", "CODEX_SESSION_ID"})}
    # The Windows desktop child can inherit USERPROFILE while the CLI's OS home lookup fails.
    if not env.get("CODEX_HOME") and os.name == "nt" and env.get("USERPROFILE"):
        existing = Path(env["USERPROFILE"]) / ".codex"
        if existing.is_dir():
            env["CODEX_HOME"] = str(existing)
    return env


def cli_executable():
    executable = shutil.which("codex")
    if executable:
        return executable
    if os.name == "nt" and os.environ.get("LOCALAPPDATA"):
        folder = Path(os.environ["LOCALAPPDATA"]) / "OpenAI/Codex/bin"
        installed = sorted(folder.glob("*/codex.exe"), key=lambda p: p.stat().st_mtime, reverse=True)
        if installed:
            return str(installed[0])
    raise RuntimeError("Codex CLI not found")


def login_probe(executable, env):
    login = subprocess.run([executable, "login", "status"], capture_output=True,
                           env=env, timeout=20, encoding="utf-8", errors="replace")
    def sanitize(output):
        output = re.sub(r"\x1b\[[0-?]*[ -/]*[@-~]", "", output)
        for variable in ("USERPROFILE", "CODEX_HOME"):
            path = env.get(variable)
            if path:
                output = re.sub(re.escape(path.replace("\\", "\\\\")), "<user-dir>", output, flags=re.I)
                output = re.sub(re.escape(path), "<user-dir>", output, flags=re.I)
        return re.sub(r"(?i)(?:\bBearer\s+|\bsk-)[A-Za-z0-9_.-]+", "<redacted>", output)

    stdout, stderr = sanitize(login.stdout), sanitize(login.stderr)
    chatgpt = login.returncode == 0 and any(
        re.fullmatch(r"\s*logged\s+in\s+using\s+chatgpt\s*\.?\s*", line, re.I)
        for line in (stdout + "\n" + stderr).splitlines()
    )
    return {"chatgpt": chatgpt, "exit_code": login.returncode, "stdout": stdout, "stderr": stderr}


def invoke(executable, work, prompt, schema, *, timeout, model=None):
    """Use the existing ChatGPT login without passing API keys."""
    for filename in ("prompt.txt", "events.jsonl", "stderr.log", "response.json"):
        if (work / filename).exists():
            raise FileExistsError("Batch already exists")
    (work / "prompt.txt").write_text(prompt, encoding="utf-8")
    env = cli_environment()
    login = login_probe(executable, env)
    write(work / "login_diagnostics.json", login)
    write(work / "login_status.json", {"chatgpt": login["chatgpt"]})
    if not login["chatgpt"]:
        raise RuntimeError(f"{LEGACY_LOGIN_FAILURE} (exit {login['exit_code']}; see login_diagnostics.json)")
    command = [
        executable, "-a", "never", "--search", "exec", "--ignore-user-config",
        "-s", "read-only", "--ephemeral", "--skip-git-repo-check", "-C", str(work),
        "--json", "--output-schema", str(schema.resolve()), "-o", str(work / "response.json"),
    ]
    if model:
        command.extend(["-m", model])
    with (work / "events.jsonl").open("wb") as events, (work / "stderr.log").open("wb") as errors:
        return subprocess.run(command + ["-"], input=prompt.encode("utf-8"),
                              stdout=events, stderr=errors, env=env, timeout=timeout).returncode


def collect(config, work, template, schema, *, resume=False, pilot=None, budget_migration=None,
            initial_observations=()):
    work = work.resolve()
    work.mkdir(parents=True, exist_ok=True)
    phase = config.get("topic_search_phase")
    if phase == "initial":
        targets = (5,)
    elif phase == "supplemental":
        targets = (5,) if config.get("run_mode") == "dev" else (35,)
    else:
        targets = (10,) if config.get("run_mode") == "dev" else (20, 100)
    if config["target"] not in targets or not 2 <= len(config["theme"].strip()) <= 160:
        raise ValueError("Invalid theme or target")
    if not 1 <= config["max_batches"] <= 8 or not 60 <= config["timeout_seconds"] <= 1800:
        raise ValueError("Invalid execution budget")
    identity = digest([ENGINE, config, sha(template), sha(schema), sha(__file__)])
    with job_lock(work):
        checkpoint = work / "checkpoint.json"
        if checkpoint.exists() != resume:
            raise ValueError("Choose an unused work path or use --resume")
        state = load(checkpoint) if resume else dict(
            config_sha256=identity, collection_id="COL_" + digest([identity, str(work), now()])[:24],
            engine=ENGINE, config=config, batches=[], observations=[], rejected=[],
        )
        if resume and not config.get("topic_batch_budget") and state["config"] == config:
            previous = digest([ENGINE, config, sha(template), sha(schema), UNCHANGED_COLLECTOR_CONTRACT])
            if state["config_sha256"] == previous:
                state["previous_config_sha256"] = previous
                state["config_sha256"] = identity
        if state["config_sha256"] != identity and budget_migration is not None:
            old = state["config"]
            migrated = dict(old, max_batches=config["max_batches"], topic_batch_budget=config["topic_batch_budget"])
            if (not resume or phase not in {"initial", "supplemental"} or old.get("run_mode") != "dev"
                    or digest(state) != budget_migration or migrated != config
                    or old["max_batches"] >= config["max_batches"]):
                raise ValueError("Checkpoint does not qualify for the reviewed budget increase")
            state.setdefault("budget_history", []).append({
                "prior_config": old, "prior_config_sha256": state["config_sha256"],
                "prior_checkpoint_sha256": budget_migration, "changed_at": now()})
            state.update(config=config, config_sha256=identity)
            write(checkpoint, state)
        if state["config_sha256"] != identity:
            legacy_identity = digest([ENGINE, config, sha(template), sha(schema), LEGACY_LOGIN_SOURCE])
            if (state["config_sha256"] != legacy_identity or state["config"] != config
                    or state["observations"] or state["rejected"] or not state["batches"]
                    or not all(batch["status"] == "failed" and batch["failure"] == LEGACY_LOGIN_FAILURE
                               and load(work / batch["batch"] / "login_status.json") == {"chatgpt": False}
                               and not (work / batch["batch"] / "events.jsonl").exists()
                               for batch in state["batches"])):
                raise ValueError("Resume requires the original config and code")
            state["previous_config_sha256"] = state["config_sha256"]
            state["config_sha256"] = identity
            state["login_preflight_only_batches"] = [batch["batch"] for batch in state["batches"]]
        if not resume and pilot:
            pilot_dir, review = pilot
            original = load(pilot_dir / "checkpoint.json")
            accepted = set(review["article_ids"])
            selected = [p for p in load(pilot_dir / "abstract_collection.json")["articles"]
                        if p["article_id"] in accepted]
            ids = {r["observation_id"] for p in selected for r in p["provenance"]}
            state["observations"] = [r for r in original["observations"] if r["observation_id"] in ids]
            state["batches"] = [r for r in original["batches"] if r["status"] == "completed"]
            state["pilot_review_sha256"] = digest(review)
            for batch in state["batches"]:
                name = batch["batch"]
                shutil.copytree(pilot_dir / name, work / name)
        write(checkpoint, state)
        executable = cli_executable()
        for _ in range(1 if config.get("topic_batch_budget") else config["max_batches"]):
            papers, _ = group(state["observations"])
            effective_count = len(papers)
            if initial_observations:
                prior, _ = group(initial_observations)
                scoped = [dict(row, observation_id="supplemental:" + row["observation_id"])
                          for row in state["observations"]]
                combined, _ = group([*initial_observations, *scoped])
                effective_count = len(combined) - len(prior)
            if effective_count >= config["target"]:
                break
            if len(state["batches"]) - len(state.get("login_preflight_only_batches", [])) >= config["max_batches"]:
                break
            batch = f"batch_{len(state['batches']) + 1:03}"
            directory = work / batch
            directory.mkdir()
            entry = {"batch": batch, "started_at": now(), "status": "started"}
            state["batches"].append(entry)
            write(checkpoint, state)
            prompt = template.read_text(encoding="utf-8").format(
                theme=config["theme"], journals="、".join(config["journals"]),
                desired=min(24, config["target"] - effective_count
                            + (0 if config.get("search_guidance") else 3)),
                accepted=json.dumps([*config.get("excluded_titles", []),
                                     *(r["title"] for r in papers)], ensure_ascii=False),
            )
            if config.get("run_mode") == "dev":
                prompt += (f"\n本轮是实验。最多使用 {config['search_action_budget']} 个原生网页工具动作，"
                           "接近预算时先提交已核实条目，保留缺口。")
            guidance = config.get("search_guidance")
            if guidance:
                prompt += "\n三层定位：" + json.dumps(guidance, ensure_ascii=False)
                prompt += ("\n议题层优先，寻找异场域但能解释相同机制的论文；对象层比较近邻避免重复。"
                           "理论层的经典单列。对每篇在摘要转述区分作者命题与研究者推论，"
                           "在相关性理由说明该解释能否回应反诘、能够迁移的条件和解释不到的部分。"
                           "在检索备注记下每层实际查询及结果。"
                           "尽早打开少量优先候选的摘要，再扩大候选名单。"
                           "出版商页面跳转到摘要镜像时，保留本次确实打开且返回该摘要的出版商入口作为摘要网址，"
                           "说明跳转和最终卷期；若入口没有返回可核实摘要，标为未核实。不要提交仅在答复中出现的镜像网址。"
                           "检索词和打开动作均记成本，分别报告发现、核实题录和获得摘要的数量。")
            try:
                code = invoke(executable, directory, prompt, schema,
                              timeout=config["timeout_seconds"], model=config.get("model"))
                if code:
                    raise RuntimeError(f"Codex process exit {code}")
                trace = evidence(directory / "events.jsonl")
                if not trace:
                    raise ValueError("No native web_search events")
                data = load(directory / "response.json")
            except (OSError, ValueError, RuntimeError, subprocess.TimeoutExpired) as exc:
                entry.update(status="failed", failure=str(exc), finished_at=now())
                write(checkpoint, state)
                break
            for position, row in enumerate(data["papers"], 1):
                try:
                    state["observations"].append(observation(row, trace, config["journals"],
                                                            batch, position))
                except (ValueError, KeyError, TypeError) as exc:
                    state["rejected"].append({"title": row.get("title"), "reason": str(exc), "batch": batch})
            state["rejected"].extend(dict(row, batch=batch) for row in data["unverified"])
            entry.update(status="completed", search_events=len(trace), finished_at=now(),
                         event_sha256=sha(directory / "events.jsonl"),
                         response_sha256=sha(directory / "response.json"), notes=data["search_notes"])
            write(checkpoint, state)
        papers, conflicts = group(state["observations"])
        bundle = {
            "engine": ENGINE, "schema_version": 2, "acquisition_mode": "abstract_only",
            "collection_id": state["collection_id"], "theme": config["theme"], "journals": config["journals"],
            "target": config["target"], "count": len(papers), "articles": papers, "conflicts": conflicts,
            "batches": state["batches"], "unverified": state["rejected"],
            "status": "verification_pending" if len(papers) >= config["target"] else "incomplete",
        }
        if config.get("run_mode") == "dev":
            bundle.update(run_mode="dev", formal_eligible=False,
                          workload_sha256=config["workload_sha256"])
            used = (max((b.get("search_events", 0) for b in state["batches"]), default=0)
                    if config.get("topic_batch_budget") else
                    sum(b.get("search_events", 0) for b in state["batches"]))
            if used > config["search_action_budget"]:
                bundle["status"] = "experimental_budget_exceeded"
        write(work / "abstract_collection.json", bundle)
        return bundle
