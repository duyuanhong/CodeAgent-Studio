from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path

from codeagent.config import Settings
from codeagent.runtime import AgentRuntime


def approval(tool_name: str, arguments: dict, reason: str) -> bool:
    print(f"\n[permission] {tool_name}: {json.dumps(arguments, ensure_ascii=False)}")
    print(f"reason: {reason}")
    return input("Allow once? [y/N] ").strip().lower() in {"y", "yes"}


def build_runtime(workspace: str | None = None) -> AgentRuntime:
    from codeagent.llm.anthropic import AnthropicProvider

    settings = Settings.from_env(workspace)
    provider = AnthropicProvider(
        model=settings.model,
        api_key=settings.anthropic_api_key,
        base_url=settings.anthropic_base_url,
    )
    return AgentRuntime(provider, settings, approval_callback=approval)


async def interactive(runtime: AgentRuntime) -> None:
    print(f"CodeAgent Harness | workspace={runtime.settings.workspace}")
    print("Commands: /goal <condition>, /goal clear, /goal status, /sessions, /resume <id>, /quit")
    try:
        while True:
            try:
                prompt = input("\n> ").strip()
            except (EOFError, KeyboardInterrupt):
                print()
                break
            if not prompt:
                continue
            if prompt in {"/quit", "/exit"}:
                break
            if prompt == "/sessions":
                print("\n".join(runtime.sessions.list()) or "(no sessions)")
                continue
            if prompt.startswith("/resume "):
                runtime.load_session(prompt.split(maxsplit=1)[1].strip())
                print(f"resumed {runtime.session_id}")
                continue
            if prompt == "/goal status":
                if runtime.goal.condition:
                    last = runtime.goal.last.reason if runtime.goal.last else "not evaluated yet"
                    print(f"active: {runtime.goal.condition}\nlast: {last}")
                else:
                    print("no active goal")
                continue
            if prompt == "/goal clear":
                runtime.goal.clear()
                print("goal cleared")
                continue
            if prompt.startswith("/goal "):
                runtime.set_goal(prompt[len("/goal ") :])
                print(f"goal set: {runtime.goal.condition}")
                continue
            result = await runtime.run(prompt)
            print(result.text)
            if result.status != "completed":
                print(f"[{result.status}] {result.reason}")
    finally:
        await runtime.close()


async def one_shot(runtime: AgentRuntime, prompt: str, goal: str | None = None) -> int:
    if goal:
        runtime.set_goal(goal)
    try:
        result = await runtime.run(prompt)
        print(result.text)
        if result.status != "completed":
            print(f"[{result.status}] {result.reason}")
            return 2
        return 0
    finally:
        await runtime.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="CodeAgent Harness")
    parser.add_argument("prompt", nargs="?", help="one-shot task; omit for interactive mode")
    parser.add_argument("--workspace", default=None)
    parser.add_argument("--goal", default=None)
    args = parser.parse_args()
    runtime = build_runtime(args.workspace)
    code = asyncio.run(one_shot(runtime, args.prompt, args.goal)) if args.prompt else (asyncio.run(interactive(runtime)) or 0)
    raise SystemExit(code)


if __name__ == "__main__":
    main()
