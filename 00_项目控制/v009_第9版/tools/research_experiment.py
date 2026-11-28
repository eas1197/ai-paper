"""Replayable, receipt-bound A/B exploration using the same Codex workload."""
import argparse
import json
from pathlib import Path
import subprocess
import time

from staged_topic import digest, load, write, run_mode, job_lock
from codex_literature import cli_environment, cli_executable, evidence, login_probe

MODEL = "gpt-6.2-sol"
EFFORT = "medium"
ROLES = ("proposal", "critique", "revision")
COMMON = (
    "研究任务：基于真实独立事件提出研究候选，完成概念化、理论化、抽象化、情境转换、"
    "对象/议题/理论文献对话、竞争解释、实质学术增量及材料可行性。未核证写未知；"
    "情境变换、重新命名和优化指标不构成学术创新。所有新外部证据给可定位 HTTPS URL，"
    "沿用初始材料的证据界限。不要发送消息、写文件或执行命令。"
    "输出 JSON 对象，包含 proposal、evidence_urls（仅新增且实际打开的 URL 字符串数组）、"
    "academic_increment、feasibility、limitations。"
)
TASKS = {
    "A": (
        "依 6.0A 顺序执行：比较事件并概念化，形成问题与反例，定位议题，依对象/议题/理论开展检索和深化。",
        "沿阶段顺序返修，只处理独立反方指明的前提、解释及增量缺口，分别记录各项判断。",
    ),
    "B": (
        "以自主研究者身份掌握完整上下文，自选顺序，允许回到旧材料、改变优先级、比较、放弃或重构候选问题。",
        "完整阅读历史和独立反方，自选推进、回退、重构或淘汰。说明哪些观察改变了学术判断。",
    ),
}


def native_call(folder, request, *, allow_search, timeout):
    executable, env = cli_executable(), cli_environment()
    login = login_probe(executable, env)
    write(folder / "login.json", login)
    if not login["chatgpt"]:
        raise RuntimeError("Codex subscription login unavailable")
    command = [executable, "-a", "never", "-c", f'model_reasoning_effort="{EFFORT}"',
               "-c", f'web_search="{"live" if allow_search else "disabled"}"', "exec",
               "--ignore-user-config", "--ephemeral", "--skip-git-repo-check", "-s", "read-only",
               "-m", MODEL, "--json", "-o", str(folder / "response.json"), "-"]
    started = time.monotonic()
    with (folder / "events.jsonl").open("wb") as stdout, (folder / "stderr.log").open("wb") as stderr:
        result = subprocess.run(command, cwd=folder, env=env, stdout=stdout, stderr=stderr,
                                input=json.dumps(request, ensure_ascii=False).encode(), timeout=timeout)
    if result.returncode:
        raise RuntimeError(f"Codex CLI failed with exit {result.returncode}: {folder.name}")
    events = [json.loads(line) for line in (folder / "events.jsonl").read_text(encoding="utf-8").splitlines()]
    invocations = [item["thread_id"] for item in events if item["type"] == "thread.started"]
    turns = [item["usage"] for item in events if item["type"] == "turn.completed"]
    if len(invocations) != 1 or len(turns) != 1:
        raise ValueError("Expected one completed independent Codex invocation")
    return {"thread": invocations[0], "usage": turns[0], "seconds": round(time.monotonic() - started, 2)}


def run_arm(work, context, arm, *, retry=False):
    manifest = run_mode.verified_run(work)
    control, sources = (manifest["workload"][step] for step in ("00", "11"))
    if len(ROLES) > control["model_calls"]:
        raise ValueError("Exploration exceeds frozen call budget")
    search_limit = sources["native_search_actions"] // 2
    area = work / "ab_exploration"
    area.mkdir(exist_ok=True)
    config = {"arm": arm, "context": context, "context_sha256": digest(context),
              "model": MODEL, "effort": EFFORT, "tool_events_per_research_turn": search_limit,
              "workload_sha256": manifest["workload_sha256"]}
    config_file = area / "experiment.json"
    if config_file.exists() and load(config_file) != config:
        raise ValueError("Experiment conditions changed")
    write(config_file, config)
    history = []
    for index, role in enumerate(ROLES):
        allow_search = role != "critique"
        folder = area / f"{index + 1:02}_{role}"
        attempts = {0: folder}
        for attempt in area.glob(folder.name + "_retry*"):
            suffix = attempt.name[len(folder.name + "_retry"):]
            if not suffix:
                attempts[1] = attempt
            elif suffix.isascii() and suffix.isdecimal() and int(suffix) >= 2 and suffix == str(int(suffix)):
                attempts[int(suffix)] = attempt
        accepted = next((number for number in sorted(attempts)
                         if (attempts[number] / "accepted.json").exists()), None)
        if accepted is not None:
            folder = attempts[accepted]
        elif retry and folder.exists():
            number = 1
            while number in attempts:
                number += 1
            suffix = "_retry" if number == 1 else f"_retry{number}"
            folder = folder.with_name(folder.name + suffix)

        turn_limit = 0
        if allow_search:
            # Rebuild an accepted request using only the spend that preceded it.
            earlier_attempts = {path for number, path in attempts.items()
                                if accepted is not None and number < accepted}
            spent = sum(len(evidence(path)) for path in area.glob("*/events.jsonl")
                        if "critique" not in path.parent.name
                        and (accepted is None or path.parent.name[:2] < folder.name[:2]
                             or path.parent in earlier_attempts))
            remaining_search = sources["native_search_actions"] - spent
            if accepted is None and remaining_search <= 0:
                raise ValueError("Frozen native search budget exhausted")
            turn_limit = min(search_limit, remaining_search)
        instruction = (
            "独立反诘：以同一学术标准找最强反例，审候选与近邻能否区分及材料可行性。"
            "只分析请求内的材料。禁止调用任何工具、读文件、执行命令或联网。"
            "不得为自己审稿。只返回 JSON，包含 objections, action_required, limits。"
            if not allow_search else COMMON + TASKS[arm][int(role == "revision")]
            + f"最多 {turn_limit} 个原生联网事件，新增证据请逐条给出真实打开页面的 URL。"
        )
        request = {"instruction": instruction, "context": context,
                   "prior": [entry["answer"] for entry in history]}
        if accepted is not None:
            record = load(folder / "accepted.json")
            if load(folder / "request.json") != request or digest(load(folder / "response.json")) != record["answer_sha256"]:
                raise ValueError("Saved checkpoint changed")
        else:
            if folder.exists():
                raise ValueError(f"Inspect incomplete turn before retry: {folder}")
            if sum(p.is_dir() for p in area.iterdir()) >= control["model_calls"]:
                raise ValueError("Frozen model call budget exhausted")
            folder.mkdir()
            write(folder / "request.json", request)
            record = native_call(folder, request, allow_search=allow_search, timeout=control["timeout_seconds"])
            trace = evidence(folder / "events.jsonl")
            if len(trace) > turn_limit:
                raise ValueError("Native search budget exceeded")
            answer = load(folder / "response.json")
            if not isinstance(answer, dict):
                raise ValueError("Research response must be an object")
            if allow_search:
                from codex_literature import url_event
                links = answer["evidence_urls"]
                if not isinstance(links, list) or any(not url_event(url, trace) for url in links):
                    raise ValueError("New evidence URL has no native receipt")
            record.update(answer=answer, answer_sha256=digest(answer), search_events=len(trace))
            write(folder / "accepted.json", record)
        if record["thread"] in {entry["thread"] for entry in history}:
            raise ValueError("Independent call was reused")
        history.append(record)
    write(area / "summary.json", {"config": config, "turns": history})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("work", type=Path)
    parser.add_argument("context", type=Path)
    parser.add_argument("--arm", choices=("A", "B"), required=True)
    parser.add_argument("--retry", action="store_true")
    args = parser.parse_args()
    work = args.work.resolve()
    run_mode.verified_run(work)
    state = load(work / "staged_topic.json")
    if state.get("research_route", "A") != args.arm:
        raise ValueError("Arm does not match the run")
    with job_lock(work):
        run_arm(work, load(args.context), args.arm, retry=args.retry)


if __name__ == "__main__":
    main()
